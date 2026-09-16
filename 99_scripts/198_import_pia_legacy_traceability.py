#!/usr/bin/env python3
"""PIA serial/lot history from eEvolution into effect-free legacy models.

The importer never creates stock moves, pickings, quants, manufacturing orders,
sales documents, invoices, or journal entries. The default mode is read-only.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import socket
import time
import xmlrpc.client
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pyodbc

import migration_runtime


ROOT = Path(__file__).resolve().parents[1]
SCOPE_FILE = ROOT / "outputs" / "pia_all_variants" / "pia_alle_varianten_artikel.csv"


def safe_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def load_scope():
    result = {}
    with SCOPE_FILE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            key = int(row["LFDNR"])
            role = "root" if "Variantenwurzel" in row.get("PILOTROLLE", "") else "component"
            result[key] = {
                "article_number": row.get("ARTNR1") or "",
                "article_name": " ".join(x for x in (row.get("ABEZ1"), row.get("ABEZ2")) if x).strip(),
                "role": role,
            }
    if not result:
        raise RuntimeError("PIA-Scope ist leer")
    return result


def load_all_scope(cur, start, end):
    """Build the complete trace scope from actual archive events in the fixed period."""
    cur.execute(
        """
        SELECT x.LFDARTNR,
               MAX(COALESCE(NULLIF(LTRIM(RTRIM(a.ARTNR1)),''),x.ARTNR1,'')) ARTNR1,
               MAX(COALESCE(NULLIF(LTRIM(RTRIM(a.ABEZ1)),''),x.ABEZ1,'')) ABEZ1,
               MAX(COALESCE(NULLIF(LTRIM(RTRIM(a.ABEZ2)),''),'')) ABEZ2
          FROM (
                SELECT LFDARTNR,MAX(ARTNR1) ARTNR1,MAX(ABEZ1) ABEZ1
                  FROM dbo.SNRARCHIV
                 WHERE BUCHDATUM>=? AND BUCHDATUM<?
                   AND NULLIF(LTRIM(RTRIM(SNR)),'') IS NOT NULL
                 GROUP BY LFDARTNR
                UNION ALL
                SELECT LFDARTNR,MAX(ARTNR1),MAX(ABEZ1)
                  FROM dbo.CHARGENARCHIV
                 WHERE BUCHDATUM>=? AND BUCHDATUM<?
                   AND NULLIF(LTRIM(RTRIM(CHARGENNR)),'') IS NOT NULL
                 GROUP BY LFDARTNR
          ) x
          LEFT JOIN dbo.ARTIKEL a ON a.LFDNR=x.LFDARTNR
         WHERE x.LFDARTNR IS NOT NULL
         GROUP BY x.LFDARTNR
        """,
        start, end, start, end,
    )
    base = {
        int(row[0]): {
            "article_number": str(row[1] or "").strip(),
            "article_name": " ".join(str(value).strip() for value in row[2:4] if value).strip(),
            "role": "root",
        }
        for row in cur.fetchall()
    }
    if not base:
        raise RuntimeError("Gesamt-Scope aus SNRARCHIV/CHARGENARCHIV ist leer")
    consumed = set()
    keys = sorted(base)
    for offset in range(0, len(keys), 1800):
        part = keys[offset:offset + 1800]
        marks = ",".join("?" for _ in part)
        cur.execute(
            f"SELECT DISTINCT LFDARTNR FROM dbo.PRODAUFINHIST WHERE LFDARTNR IN ({marks})",
            *part,
        )
        consumed.update(int(row[0]) for row in cur.fetchall() if row[0] is not None)
    for key in consumed:
        base[key]["role"] = "component"
    return base


def source_connection():
    required = ("EV_DRIVER", "EV_SERVER", "EV_DATABASE", "EV_USER", "EV_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Fehlende eEvolution-Umgebung: " + ", ".join(missing))
    cs = (
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
        f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "ApplicationIntent=ReadOnly;"
    )
    return pyodbc.connect(cs, readonly=True, timeout=30)


class Odoo:
    def __init__(self):
        self.url = os.environ["ODOO_URL"]
        self.db = os.environ["ODOO_DB"]
        self.user = os.environ["ODOO_USER"]
        self.key = os.environ["ODOO_API_KEY"]
        self.connect()

    def connect(self):
        common = migration_runtime.server_proxy(self.url + "/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, self.user, self.key, {})
        if not self.uid:
            raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
        self.models = migration_runtime.server_proxy(self.url + "/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args=None, kwargs=None):
        for attempt in range(6):
            try:
                return self.models.execute_kw(
                    self.db, self.uid, self.key, model, method, args or [], kwargs or {}
                )
            except xmlrpc.client.Fault:
                raise
            except (OSError, ConnectionError, socket.error):
                if attempt == 5:
                    raise
                time.sleep(2**attempt)
                self.connect()

    def search_read_all(self, model, domain, fields, batch_size=5000):
        """Read large models in deterministic pages to keep XML-RPC responses bounded."""
        result = []
        offset = 0
        while True:
            rows = self.call(
                model, "search_read", [domain],
                {"fields": fields, "limit": batch_size, "offset": offset, "order": "id"},
            )
            result.extend(rows)
            if len(rows) < batch_size:
                return result
            offset += len(rows)


def load_events(cur, scope, start, end):
    keys = sorted(scope)
    type_names = {
        int(row[0]): str(row[1] or "").strip()
        for row in cur.execute("SELECT LFDNR,SNREFTYP FROM dbo.SNREFTYP WHERE SPRKZ IN (0,1)")
    }
    events = []
    for offset in range(0, len(keys), 1800):
        part = keys[offset:offset + 1800]
        placeholders = ",".join("?" for _ in part)
        sql_common = f"LFDARTNR IN ({placeholders}) AND BUCHDATUM >= ? AND BUCHDATUM < ?"
        params = [*part, start, end]
        serial_sql = f"""
        SELECT CONVERT(varchar(36),_ID),LFDSNR,LFDSNLFDNR,LFDARTNR,ARTNR1,ABEZ1,SNR,
               BUCHDATUM,BELEGNR,REFTYP,REFNR,REFPOSNR,PTEXT,CAST(NULL AS decimal(18,6))
        FROM dbo.SNRARCHIV
        WHERE {sql_common} AND NULLIF(LTRIM(RTRIM(SNR)),'') IS NOT NULL
        """
        lot_sql = f"""
        SELECT CONVERT(varchar(36),_ID),LFDCHARGENNR,LFDCHLFDNR,LFDARTNR,ARTNR1,ABEZ1,CHARGENNR,
               BUCHDATUM,BELEGNR,REFTYP,REFNR,REFPOSNR,PTEXT,MENGE
        FROM dbo.CHARGENARCHIV
        WHERE {sql_common} AND NULLIF(LTRIM(RTRIM(CHARGENNR)),'') IS NOT NULL
        """
        for trace_type, table, sql in (
            ("serial", "SNRARCHIV", serial_sql),
            ("lot", "CHARGENARCHIV", lot_sql),
        ):
            cur.execute(sql, params)
            for row in cur.fetchall():
                guid, master_key, line_key, product_key, artnr, article_name, number = row[:7]
                event_type = int(row[9]) if row[9] is not None else None
                events.append({
                    "trace_type": trace_type,
                    "source_table": table,
                    "source_key": f"{table}:{guid or f'{master_key}:{line_key}'}",
                    "eevo_product_key": int(product_key),
                    "article_number": str(artnr or scope[int(product_key)]["article_number"]).strip(),
                    "article_name": str(article_name or scope[int(product_key)]["article_name"]).strip(),
                    "pia_scope_role": scope[int(product_key)]["role"],
                    "name": str(number).strip(),
                    "event_date": row[7],
                    "document_number": str(row[8] or "").strip(),
                    "event_type_code": str(event_type) if event_type is not None else "",
                    "event_type_name": type_names.get(event_type, f"Unbekannter Typ {event_type}"),
                    "reference_number": str(row[10] or "").strip(),
                    "reference_position": int(row[11] or 0),
                    "description": str(row[12] or "").strip(),
                    "quantity": float(row[13] or 0),
                })
    return events


def partner_maps(cur):
    delivery = {}
    cur.execute("""
        SELECT ls.LSNR,g.LFDNR,k.ADRNR,g.VORGANG
        FROM dbo.AAGLS ls
        LEFT JOIN dbo.ANGAUFGUT g ON g.LFDNR=ls.LFDANGAUFGUTNR
        LEFT JOIN dbo.KUNDE k ON k.KNDNR=g.KNDNR
    """)
    for lsnr, order_key, address_key, order_number in cur.fetchall():
        if lsnr is not None:
            delivery[str(int(float(lsnr)))] = (
                int(address_key) if address_key is not None else None,
                int(order_key) if order_key is not None else 0,
                str(order_number or "").strip(),
            )
    orders = {}
    cur.execute("""
        SELECT g.LFDNR,k.ADRNR FROM dbo.ANGAUFGUT g
        LEFT JOIN dbo.KUNDE k ON k.KNDNR=g.KNDNR
    """)
    for order_key, address_key in cur.fetchall():
        orders[str(int(order_key))] = int(address_key) if address_key is not None else None
    return delivery, orders


def production_number(value):
    """Return an integer eEvolution production key without accepting free text."""
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return int(text) if text.isdigit() else None


def load_productions(cur, events, start, end):
    order_keys = sorted({
        production_number(event["reference_number"])
        for event in events
        if event["event_type_code"] == "2"
    } - {None})
    if not order_keys:
        return {}, [], []
    headers = {}
    components = []
    outputs = []
    # The output UNION repeats the key list three times; stay below SQL Server's
    # 2,100-parameter limit for the complete statement.
    for offset in range(0, len(order_keys), 600):
        part = order_keys[offset:offset + 600]
        placeholders = ",".join("?" for _ in part)
        cur.execute(f"""
        SELECT p.LFDNR,p.STATUS,p.TYP,p.MENGE,p.PRODMENGE,p.AUSMENGE,
               p.PVDAT,p.PPDAT,p.ENDDAT,p.ARTNR,p.PRODLISTLFDNR,
               a.ARTNR1,a.ABEZ1,a.ABEZ2
        FROM dbo.PRODUKTION p
        LEFT JOIN dbo.ARTIKEL a ON a.LFDNR=p.ARTNR
        WHERE p.LFDNR IN ({placeholders})
        """, part)
        for row in cur.fetchall():
            key = int(row[0])
            headers[key] = {
            "eevo_order_key": key,
            "name": f"P-{key}",
            "status_code": str(row[1] if row[1] is not None else ""),
            "order_type": str(row[2] or "").strip(),
            "quantity_ordered": float(row[3] or 0),
            "quantity_produced": float(row[4] or 0),
            "quantity_scrapped": float(row[5] or 0),
            "planned_date": row[6],
            "production_date": row[7],
            "end_date": row[8],
            "eevo_product_key": int(row[9]) if row[9] is not None else 0,
            "bom_reference": int(row[10]) if row[10] is not None else 0,
            "article_number": str(row[11] or "").strip(),
            "article_name": " ".join(str(x).strip() for x in row[12:14] if x).strip(),
            }

        cur.execute(f"""
        SELECT CONVERT(varchar(36),h._ID),h.LFDNR,h.PRDAUFNR,h.PRDINHLFDNR,
               h.LFDARTNR,h.ARTNR1,h.ABEZ1,h.BELEGDAT,h.BELEGNR,h.MENGE,
               h.SERIENNR,h.CHARGENNR,h.STORNO,h.BUCHUNGSTORNO,
               t.ID,t.SERIENNR,t.CHARGENNR,t.CHARGENNR_EIGEN,t.MENGE
        FROM dbo.PRODAUFINHIST h
        LEFT JOIN dbo.PRODAUFINHIST_SNRTRACK t ON t.PRDINHISTLFDNR=h.LFDNR
        WHERE h.PRDAUFNR IN ({placeholders})
          AND h.BELEGDAT >= ? AND h.BELEGDAT < ?
        ORDER BY h.PRDAUFNR,h.LFDNR,t.ID
        """, [*part, start, end])
        for row in cur.fetchall():
            posting_key = int(row[1])
            tracking_key = int(row[14]) if row[14] is not None else 0
            serial = str(row[15] or row[10] or "").strip()
            lot = str(row[16] or row[17] or row[11] or "").strip()
            components.append({
            "production_key": int(row[2]),
            "source_key": f"PRODAUFINHIST:{row[0] or posting_key}:{tracking_key}",
            "source_posting_key": posting_key,
            "source_position_key": int(row[3]) if row[3] is not None else 0,
            "eevo_product_key": int(row[4]),
            "article_number": str(row[5] or "").strip(),
            "article_name": str(row[6] or "").strip(),
            "booking_date": row[7],
            "document_number": str(row[8] or "").strip(),
            "quantity": float(row[18] if row[18] is not None else row[9] or 0),
            "serial_number": serial,
            "lot_number": lot,
            "is_cancelled": bool(row[12] or row[13]),
            })

        cur.execute(f"""
        SELECT 'serial',CONVERT(varchar(36),_ID),PRDAUFNR,SERIENNR,
               CAST(1 AS decimal(18,6)),EINLAGDAT,LFDARTNR,LFDNR,EINLAGNR
        FROM dbo.PRODAUFSERIEN
        WHERE PRDAUFNR IN ({placeholders})
          AND EINLAGDAT >= ? AND EINLAGDAT < ?
        UNION ALL
        SELECT 'lot',CONVERT(varchar(36),_ID),PRDAUFNR,CHARGENNR,
               MENGE,EINLAGDAT,LFDARTNR,0,0
        FROM dbo.PRODAUFCHARGEN
        WHERE PRDAUFNR IN ({placeholders})
          AND EINLAGDAT >= ? AND EINLAGDAT < ?
        UNION ALL
        SELECT 'lot',CONVERT(varchar(36),e._ID),e.PRDAUFNR,e.CHARGENNR,
               e.GUTMENGE,e.EINLAGDAT,e.LFDARTNR,e.LFDNR,0
        FROM dbo.PRODAUFEINLAGERN e
        WHERE e.PRDAUFNR IN ({placeholders})
          AND e.EINLAGDAT >= ? AND e.EINLAGDAT < ?
          AND NULLIF(LTRIM(RTRIM(e.CHARGENNR)),'') IS NOT NULL
          AND COALESCE(e.GUTMENGE,0) <> 0
          AND NOT EXISTS (
              SELECT 1 FROM dbo.PRODAUFCHARGEN c
              WHERE c.PRDAUFNR=e.PRDAUFNR AND c.LFDARTNR=e.LFDARTNR
                AND LTRIM(RTRIM(c.CHARGENNR))=LTRIM(RTRIM(e.CHARGENNR))
          )
        """, [
            *part, start, end,
            *part, start, end,
            *part, start, end,
        ])
        for row in cur.fetchall():
            output_type = str(row[0])
            order_key = int(row[2])
            number = str(row[3] or "").strip()
            outputs.append({
            "production_key": order_key,
            "source_key": (
                f"PRODAUFOUTPUT:{output_type}:{row[1] or f'{order_key}:{row[7]}:{row[8]}:{number}'}"
            ),
            "output_type": output_type,
            "number": number,
            "quantity": float(row[4] or 0),
            "storage_date": row[5],
            "eevo_product_key": int(row[6]) if row[6] is not None else 0,
            })
    return headers, components, outputs


def resolve_external_ids(odoo, scope, address_keys):
    product_links = odoo.call("ir.model.data", "search_read", [[
        ("module", "=", "__import__"), ("name", "like", "ev_product_%"),
        ("model", "=", "product.template")
    ]], {"fields": ["name", "res_id"], "limit": 100000})
    template_by_key = {
        int(row["name"].removeprefix("ev_product_")): row["res_id"]
        for row in product_links
        if row["name"].removeprefix("ev_product_").isdigit()
        and int(row["name"].removeprefix("ev_product_")) in scope
    }
    variants_by_template = {}
    template_ids = list(template_by_key.values())
    for offset in range(0, len(template_ids), 500):
        for row in odoo.call(
            "product.template", "read", [template_ids[offset:offset + 500]],
            {"fields": ["product_variant_ids"], "context": {"active_test": False}},
        ):
            if row["product_variant_ids"]:
                variants_by_template[row["id"]] = row["product_variant_ids"][0]
    product_ids = {
        key: variants_by_template[template_id]
        for key, template_id in template_by_key.items() if template_id in variants_by_template
    }
    partner_links = odoo.call("ir.model.data", "search_read", [[
        ("module", "=", "__import__"), ("name", "like", "ev_adr_%"),
        ("model", "=", "res.partner")
    ]], {"fields": ["name", "res_id"], "limit": 100000})
    partner_ids = {
        int(row["name"].removeprefix("ev_adr_")): row["res_id"]
        for row in partner_links
        if row["name"].removeprefix("ev_adr_").isdigit()
        and int(row["name"].removeprefix("ev_adr_")) in address_keys
    }
    return product_ids, partner_ids


def create_with_xmlids(odoo, model, records, xmlids, batch_size=500, create_xmlids=True):
    created = 0
    for offset in range(0, len(records), batch_size):
        vals = records[offset:offset + batch_size]
        names = xmlids[offset:offset + batch_size]
        ids = odoo.call(model, "create", [vals])
        if isinstance(ids, int):
            ids = [ids]
        if create_xmlids:
            imd = [
                {"module": "__import__", "name": name, "model": model, "res_id": record_id, "noupdate": True}
                for name, record_id in zip(names, ids)
            ]
            odoo.call("ir.model.data", "create", [imd])
        created += len(ids)
    return created


def original_sale_info(grouped, partner_ids):
    delivery_candidates = sorted(
        (
            event for event in grouped
            if event["event_type_code"] == "9"
            and event.get("eevo_partner_key")
            and "storno" not in event["description"].lower()
            and "ausgang lieferschein" in event["description"].lower()
        ),
        key=lambda event: (event["event_date"], event["source_key"]),
    )
    if not delivery_candidates:
        delivery_candidates = sorted(
            (
                event for event in grouped
                if event["event_type_code"] == "9"
                and event.get("eevo_partner_key")
                and "storno" not in event["description"].lower()
            ),
            key=lambda event: (event["event_date"], event["source_key"]),
        )
    order_candidates = sorted(
        (
            event for event in grouped
            if event["event_type_code"] == "1" and event.get("eevo_partner_key")
        ),
        key=lambda event: (event["event_date"], event["source_key"]),
    )
    delivery = delivery_candidates[0] if delivery_candidates else None
    order = order_candidates[0] if order_candidates else None
    anchor = delivery or order
    partner_key = anchor.get("eevo_partner_key") if anchor else None
    return {
        "original_partner_id": partner_ids.get(partner_key) or False,
        "original_eevo_partner_key": partner_key or 0,
        "original_order_number": (
            (order["document_number"] or order["reference_number"]) if order else ""
        ),
        "original_delivery_number": (
            (delivery["document_number"] or delivery["reference_number"]) if delivery else ""
        ),
        "original_delivery_date": delivery["event_date"] if delivery else False,
    }


def build_direct_deliveries(by_trace, delivery_map):
    """Select factual outbound delivery events for the exact serial/lot."""
    result = []
    for trace_key, grouped in sorted(by_trace.items()):
        for event in grouped:
            description = event["description"].lower()
            if (
                event["event_type_code"] != "9"
                or "ausgang lieferschein" not in description
                or "storno" in description
            ):
                continue
            ref = event["reference_number"] or event["document_number"]
            address_key, order_key, order_number = delivery_map.get(ref, (None, 0, ""))
            if not address_key:
                continue
            result.append({
                "trace_key": trace_key,
                "source_key": event["source_key"],
                "delivery_date": event["event_date"],
                "delivery_number": event["document_number"] or ref,
                "order_key": order_key,
                "order_number": order_number,
                "eevo_partner_key": address_key,
                "quantity": abs(event["quantity"]),
            })
    return result


def build_trace_usages(scope, by_trace, productions, components, outputs, root_only=True):
    """Derive conservative component-trace -> finished-output relations.

    A relation is strong only when consumption and output belong to the same
    production order and were posted within the same 120-second booking run.
    If an order has no such timestamp match at all, its outputs remain clearly
    labelled order-level candidates. No direct unit allocation is asserted.
    """
    outputs_by_production = defaultdict(list)
    for output in outputs:
        outputs_by_production[output["production_key"]].append(output)
    components_by_trace_production = defaultdict(list)
    for component in components:
        if component["is_cancelled"]:
            continue
        if component["serial_number"]:
            components_by_trace_production[
                ("serial", component["eevo_product_key"], component["serial_number"], component["production_key"])
            ].append(component)
        if component["lot_number"]:
            components_by_trace_production[
                ("lot", component["eevo_product_key"], component["lot_number"], component["production_key"])
            ].append(component)

    usages = []
    for trace_key, grouped in sorted(by_trace.items()):
        trace_type, product_key, number = trace_key
        production_keys = sorted({
            production_number(event["reference_number"])
            for event in grouped if event["event_type_code"] == "2"
        } - {None})
        for production_key in production_keys:
            production = productions.get(production_key)
            if not production:
                continue
            output_product_key = production["eevo_product_key"]
            if root_only and scope.get(output_product_key, {}).get("role") != "root":
                continue
            matching_components = components_by_trace_production.get(
                (trace_type, product_key, number, production_key), []
            )
            if not matching_components:
                continue
            order_outputs = outputs_by_production.get(production_key, [])
            batch_matches = {}
            for output in order_outputs:
                if not output["storage_date"]:
                    continue
                candidates = []
                for component in matching_components:
                    if not component["booking_date"]:
                        continue
                    delta = (output["storage_date"] - component["booking_date"]).total_seconds()
                    if 0 <= delta <= 120:
                        candidates.append((delta, component))
                if candidates:
                    batch_matches[output["source_key"]] = min(candidates, key=lambda item: item[0])
            if batch_matches:
                selected = [
                    (output, batch_matches[output["source_key"]][1], "booking_batch",
                     batch_matches[output["source_key"]][0])
                    for output in order_outputs if output["source_key"] in batch_matches
                ]
            else:
                selected = [
                    (output, matching_components[0], "production_order", None)
                    for output in order_outputs
                ]
            for output, component, basis, seconds in selected:
                if basis == "booking_batch":
                    note = (
                        f"Abgeleitet aus gleichem Produktionsauftrag und Buchungslauf "
                        f"({seconds:.1f} Sekunden Abstand); keine direkte Einzelstück-ID."
                    )
                else:
                    note = (
                        "Nur gemeinsamer Produktionsauftrag belegt; die Zuordnung zum "
                        "einzelnen Endgerät ist ein Kandidat."
                    )
                usages.append({
                    "trace_key": trace_key,
                    "production_key": production_key,
                    "component_source_key": component["source_key"],
                    "output_source_key": output["source_key"],
                    "output_number": output["number"],
                    "source_key": (
                        f"TRACEUSAGE:{trace_type}:{product_key}:{safe_token(number)}:"
                        f"{output['source_key']}"
                    ),
                    "allocation_basis": basis,
                    "allocation_note": note,
                })
    return usages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-date", default="2016-09-15")
    parser.add_argument("--to-date", default="2026-09-16")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="")
    parser.add_argument("--scope", choices=("pia", "all"), default="pia")
    parser.add_argument("--only-product", type=int, action="append", default=[])
    args = parser.parse_args()
    start = datetime.fromisoformat(args.from_date)
    end = datetime.fromisoformat(args.to_date)
    if end <= start:
        raise SystemExit("Ungültiger Halbintervall-Zeitraum")
    target = migration_runtime.require_target(os.environ.get("ODOO_DB", ""))
    if args.apply:
        if os.environ.get("KF_ALLOW_WRITE") != "1":
            raise SystemExit("Apply nur über zentralen Wrapper")
        if not args.backup or not args.backup.startswith(target.backup_prefix):
            raise SystemExit("Apply verlangt eine verifizierte Ziel-DB-Sicherung")

    cn = source_connection()
    cur = cn.cursor()
    scope = load_scope() if args.scope == "pia" else load_all_scope(cur, start, end)
    if args.only_product:
        selected = set(args.only_product)
        scope = {key: value for key, value in scope.items() if key in selected}
        missing_selected = sorted(selected - set(scope))
        if missing_selected:
            raise SystemExit("Gewählte Artikel ohne Ereignisse im Zeitraum: " + ", ".join(map(str, missing_selected)))
    events = load_events(cur, scope, start, end)
    delivery_map, order_map = partner_maps(cur)
    productions, production_components, production_outputs = load_productions(
        cur, events, start, end
    )
    cn.close()

    by_trace = defaultdict(list)
    number_products = defaultdict(set)
    address_keys = set()
    for event in events:
        ref = event["reference_number"]
        address_key = None
        if event["event_type_code"] == "9" and ref:
            address_key = delivery_map.get(ref, (None, 0, ""))[0]
        elif event["event_type_code"] == "1" and ref:
            address_key = order_map.get(ref)
        event["eevo_partner_key"] = address_key
        if address_key:
            address_keys.add(address_key)
        key = (event["trace_type"], event["eevo_product_key"], event["name"])
        by_trace[key].append(event)
        number_products[(event["trace_type"], event["name"])].add(event["eevo_product_key"])

    trace_usages = build_trace_usages(
        scope, by_trace, productions, production_components, production_outputs,
        root_only=args.scope == "pia",
    )
    direct_deliveries = build_direct_deliveries(by_trace, delivery_map)
    golden_usage = [
        usage for usage in trace_usages
        if usage["trace_key"] == ("lot", 5111, "22.05.2026")
    ]

    odoo = Odoo()
    product_ids, partner_ids = resolve_external_ids(odoo, scope, address_keys)
    model_available = True
    try:
        existing_headers = odoo.call("kf.legacy.trace", "search_count", [[]])
        existing_events = odoo.call("kf.legacy.trace.event", "search_count", [[]])
    except xmlrpc.client.Fault:
        model_available = False
        existing_headers = existing_events = 0

    summary = {
        "mode": "APPLY" if args.apply else "DRY-RUN",
        "target": odoo.db,
        "scope_mode": args.scope,
        "selected_products": sorted(args.only_product),
        "period": {"from": args.from_date, "to_exclusive": args.to_date},
        "scope_products": len(scope),
        "scope_roots": sum(x["role"] == "root" for x in scope.values()),
        "source_events": len(events),
        "events_by_type": dict(Counter(x["trace_type"] for x in events)),
        "event_types": dict(Counter(f"{x['event_type_code']} {x['event_type_name']}" for x in events)),
        "trace_headers": len(by_trace),
        "headers_by_type": dict(Counter(x[0] for x in by_trace)),
        "cross_product_number_conflicts": sum(len(v) > 1 for v in number_products.values()),
        "resolved_products": len(product_ids),
        "unresolved_products_with_events": sorted(set(x[1] for x in by_trace) - set(product_ids)),
        "address_keys_in_events": len(address_keys),
        "resolved_partners": len(partner_ids),
        "legacy_model_available": model_available,
        "existing_legacy_headers": existing_headers,
        "existing_legacy_events": existing_events,
        "production_orders": len(productions),
        "production_component_rows": len(production_components),
        "production_output_rows": len(production_outputs),
        "derived_trace_output_usages": len(trace_usages),
        "derived_usages_by_basis": dict(Counter(x["allocation_basis"] for x in trace_usages)),
        "direct_serial_lot_deliveries": len(direct_deliveries),
        "direct_delivery_customers": len({x["eevo_partner_key"] for x in direct_deliveries}),
        "golden_charge_22_05_2026": {
            "finished_outputs": len(golden_usage),
            "by_basis": dict(Counter(x["allocation_basis"] for x in golden_usage)),
            "serials": sorted(x["output_number"] for x in golden_usage),
        },
    }
    if model_available and not args.apply:
        existing_component_keys = {
            row["source_key"] for row in odoo.search_read_all(
                "kf.legacy.production.component", [], ["source_key"]
            )
        }
        existing_output_keys = {
            row["source_key"] for row in odoo.search_read_all(
                "kf.legacy.production.output", [], ["source_key"]
            )
        }
        existing_usage_keys = {
            row["source_key"] for row in odoo.search_read_all(
                "kf.legacy.trace.usage", [], ["source_key"]
            )
        }
        existing_delivery_keys = {
            row["source_key"] for row in odoo.search_read_all(
                "kf.legacy.trace.delivery", [], ["source_key"]
            )
        }
        expected_component_keys = {row["source_key"] for row in production_components}
        expected_output_keys = {row["source_key"] for row in production_outputs}
        expected_usage_keys = {row["source_key"] for row in trace_usages}
        expected_delivery_keys = {row["source_key"] for row in direct_deliveries}
        summary["idempotency_preview"] = {
            "components_to_create": len(expected_component_keys - existing_component_keys),
            "components_not_in_fixed_window_source": len(
                existing_component_keys - expected_component_keys
            ),
            "outputs_to_create": len(expected_output_keys - existing_output_keys),
            "outputs_not_in_fixed_window_source": len(existing_output_keys - expected_output_keys),
            "usages_to_create": len(expected_usage_keys - existing_usage_keys),
            "usages_not_in_fixed_window_source": len(existing_usage_keys - expected_usage_keys),
            "deliveries_to_create": len(expected_delivery_keys - existing_delivery_keys),
            "deliveries_not_in_fixed_window_source": len(
                existing_delivery_keys - expected_delivery_keys
            ),
            "missing_usage_source_key_sample": sorted(
                expected_usage_keys - existing_usage_keys
            )[:10],
        }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY_RUN_OK: keine Odoo- oder eEvolution-Daten geändert")
        return
    if not model_available:
        raise SystemExit("Legacy-Modell fehlt; Modul zuerst installieren/aktualisieren")

    existing_header_rows = odoo.search_read_all(
        "kf.legacy.trace", [], ["id", "trace_type", "eevo_product_key", "name", "product_id"]
    )
    header_cache = {(r["trace_type"], r["eevo_product_key"], r["name"]): r["id"] for r in existing_header_rows}
    existing_event_rows = odoo.search_read_all(
        "kf.legacy.trace.event", [], ["source_key"]
    )
    existing_source_keys = {r["source_key"] for r in existing_event_rows}

    header_records, header_xmlids, header_keys = [], [], []
    for key, grouped in sorted(by_trace.items()):
        if key in header_cache:
            continue
        trace_type, product_key, number = key
        cross_product = len(number_products[(trace_type, number)]) > 1
        unknown_types = sorted({e["event_type_code"] for e in grouped if e["event_type_name"].startswith("Unbekannter")})
        notes = []
        if cross_product:
            notes.append("Nummer kommt bei mehreren eEvolution-Artikeln vor; keine Zusammenführung vorgenommen.")
        if unknown_types:
            notes.append("Unbekannte Ereignistypen: " + ", ".join(unknown_types))
        product = scope[product_key]
        header_records.append({
            "name": number,
            "trace_type": trace_type,
            "product_id": product_ids.get(product_key) or False,
            "eevo_product_key": product_key,
            "article_number": grouped[0]["article_number"] or product["article_number"],
            "article_name": grouped[0]["article_name"] or product["article_name"],
            "pia_scope_role": product["role"],
            "first_event_date": min(e["event_date"] for e in grouped),
            "last_event_date": max(e["event_date"] for e in grouped),
            "event_count": len(grouped),
            "quality_status": "review" if notes else "ok",
            "quality_note": "\n".join(notes),
            **original_sale_info(grouped, partner_ids),
        })
        header_keys.append(key)
        header_xmlids.append(f"ev_legacy_trace_{trace_type}_{product_key}_{safe_token(number)}")
    created_headers = create_with_xmlids(odoo, "kf.legacy.trace", header_records, header_xmlids)
    if created_headers:
        rows = odoo.search_read_all(
            "kf.legacy.trace", [], ["id", "trace_type", "eevo_product_key", "name"]
        )
        header_cache = {(r["trace_type"], r["eevo_product_key"], r["name"]): r["id"] for r in rows}

    # Archived product variants are intentionally part of the full history.  Odoo's
    # default active filter used to hide them while resolving the product relation.
    # Repair only the missing relation; the legacy facts themselves remain unchanged.
    repaired_header_products = 0
    missing_header_ids_by_product = defaultdict(list)
    for row in existing_header_rows:
        product_key = int(row["eevo_product_key"])
        if not row["product_id"] and product_ids.get(product_key):
            missing_header_ids_by_product[product_ids[product_key]].append(row["id"])
    for product_id, record_ids in missing_header_ids_by_product.items():
        for offset in range(0, len(record_ids), 500):
            ids = record_ids[offset:offset + 500]
            odoo.call("kf.legacy.trace", "write", [ids, {"product_id": product_id}])
            repaired_header_products += len(ids)

    # Refresh customer/document heads for records created by earlier idempotent runs.
    sale_head_rows = odoo.search_read_all(
        "kf.legacy.trace", [], [
            "id", "original_partner_id", "original_eevo_partner_key",
            "original_order_number", "original_delivery_number", "original_delivery_date",
        ],
    )
    current_sale_heads = {row["id"]: row for row in sale_head_rows}
    updated_sale_heads = 0
    for key, grouped in sorted(by_trace.items()):
        if key not in header_cache:
            continue
        desired = original_sale_info(grouped, partner_ids)
        current = current_sale_heads[header_cache[key]]
        current_partner_id = current["original_partner_id"][0] if current["original_partner_id"] else False
        comparable_current = {
            "original_partner_id": current_partner_id,
            "original_eevo_partner_key": current["original_eevo_partner_key"],
            "original_order_number": current["original_order_number"] or "",
            "original_delivery_number": current["original_delivery_number"] or "",
            "original_delivery_date": current["original_delivery_date"] or False,
        }
        comparable_desired = dict(desired)
        if comparable_desired["original_delivery_date"]:
            comparable_desired["original_delivery_date"] = comparable_desired[
                "original_delivery_date"
            ].strftime("%Y-%m-%d %H:%M:%S")
        if comparable_current == comparable_desired:
            continue
        odoo.call(
            "kf.legacy.trace", "write",
            [[header_cache[key]], desired],
        )
        updated_sale_heads += 1

    existing_production_rows = odoo.search_read_all(
        "kf.legacy.production", [], ["id", "eevo_order_key", "eevo_product_key", "product_id"]
    )
    production_cache = {r["eevo_order_key"]: r["id"] for r in existing_production_rows}
    component_counts = Counter(x["production_key"] for x in production_components if not x["is_cancelled"])
    traced_component_counts = Counter(
        x["production_key"] for x in production_components
        if not x["is_cancelled"] and (x["serial_number"] or x["lot_number"])
    )
    output_counts = Counter(x["production_key"] for x in production_outputs)
    production_records, production_xmlids = [], []
    for key, production in sorted(productions.items()):
        if key in production_cache:
            continue
        vals = dict(production)
        vals["product_id"] = product_ids.get(vals["eevo_product_key"]) or False
        vals["component_posting_count"] = component_counts[key]
        vals["traced_component_posting_count"] = traced_component_counts[key]
        vals["output_count"] = output_counts[key]
        production_records.append(vals)
        production_xmlids.append(f"ev_legacy_production_{key}")
    created_productions = create_with_xmlids(
        odoo, "kf.legacy.production", production_records, production_xmlids
    )
    if created_productions:
        rows = odoo.search_read_all(
            "kf.legacy.production", [], ["id", "eevo_order_key"]
        )
        production_cache = {r["eevo_order_key"]: r["id"] for r in rows}

    repaired_production_products = 0
    production_ids_by_product = defaultdict(list)
    for row in existing_production_rows:
        product_key = int(row["eevo_product_key"] or 0)
        if not row["product_id"] and product_ids.get(product_key):
            production_ids_by_product[product_ids[product_key]].append(row["id"])
    for product_id, record_ids in production_ids_by_product.items():
        for offset in range(0, len(record_ids), 500):
            ids = record_ids[offset:offset + 500]
            odoo.call("kf.legacy.production", "write", [ids, {"product_id": product_id}])
            repaired_production_products += len(ids)

    existing_component_keys = {
        r["source_key"] for r in odoo.search_read_all(
            "kf.legacy.production.component", [], ["source_key"]
        )
    }
    existing_component_rows = odoo.search_read_all(
        "kf.legacy.production.component", [], ["id", "eevo_product_key", "product_id"]
    )
    repaired_component_products = 0
    component_ids_by_product = defaultdict(list)
    for row in existing_component_rows:
        product_key = int(row["eevo_product_key"] or 0)
        if not row["product_id"] and product_ids.get(product_key):
            component_ids_by_product[product_ids[product_key]].append(row["id"])
    for product_id, record_ids in component_ids_by_product.items():
        for offset in range(0, len(record_ids), 500):
            ids = record_ids[offset:offset + 500]
            odoo.call("kf.legacy.production.component", "write", [ids, {"product_id": product_id}])
            repaired_component_products += len(ids)
    component_records, component_xmlids = [], []
    for component in production_components:
        if component["source_key"] in existing_component_keys:
            continue
        vals = dict(component)
        production_key = vals.pop("production_key")
        vals["production_id"] = production_cache[production_key]
        vals["product_id"] = product_ids.get(vals["eevo_product_key"]) or False
        component_records.append(vals)
        component_xmlids.append(f"ev_legacy_production_component_{safe_token(vals['source_key'])}")
    created_components = create_with_xmlids(
        odoo, "kf.legacy.production.component", component_records, component_xmlids,
        create_xmlids=False,
    )

    existing_output_keys = {
        r["source_key"] for r in odoo.search_read_all(
            "kf.legacy.production.output", [], ["source_key"]
        )
    }
    output_records, output_xmlids = [], []
    for output in production_outputs:
        if output["source_key"] in existing_output_keys:
            continue
        vals = dict(output)
        production_key = vals.pop("production_key")
        product_key = vals.pop("eevo_product_key")
        vals["production_id"] = production_cache[production_key]
        vals["trace_id"] = header_cache.get((vals["output_type"], product_key, vals["number"])) or False
        output_records.append(vals)
        output_xmlids.append(f"ev_legacy_production_output_{safe_token(vals['source_key'])}")
    created_outputs = create_with_xmlids(
        odoo, "kf.legacy.production.output", output_records, output_xmlids,
        create_xmlids=False,
    )

    # Reconcile output counters for existing production heads after fallback outputs are added.
    desired_output_counts = Counter(x["production_key"] for x in production_outputs)
    current_production_counts = odoo.search_read_all(
        "kf.legacy.production", [], ["id", "eevo_order_key", "output_count"]
    )
    output_count_updates = defaultdict(list)
    for row in current_production_counts:
        desired_count = desired_output_counts.get(row["eevo_order_key"], 0)
        if row["output_count"] != desired_count:
            output_count_updates[desired_count].append(row["id"])
    updated_output_heads = 0
    for desired_count, ids in output_count_updates.items():
        odoo.call("kf.legacy.production", "write", [ids, {"output_count": desired_count}])
        updated_output_heads += len(ids)

    component_id_by_source = {
        row["source_key"]: row["id"] for row in odoo.search_read_all(
            "kf.legacy.production.component", [], ["source_key"]
        )
    }
    output_id_by_source = {
        row["source_key"]: row["id"] for row in odoo.search_read_all(
            "kf.legacy.production.output", [], ["source_key"]
        )
    }
    existing_usage_keys = {
        row["source_key"] for row in odoo.search_read_all(
            "kf.legacy.trace.usage", [], ["source_key"]
        )
    }
    usage_records, usage_xmlids = [], []
    for usage in trace_usages:
        if usage["source_key"] in existing_usage_keys:
            continue
        vals = {
            "trace_id": header_cache[usage["trace_key"]],
            "source_key": usage["source_key"],
            "production_id": production_cache[usage["production_key"]],
            "component_id": component_id_by_source[usage["component_source_key"]],
            "output_id": output_id_by_source[usage["output_source_key"]],
            "allocation_basis": usage["allocation_basis"],
            "allocation_note": usage["allocation_note"],
        }
        usage_records.append(vals)
        usage_xmlids.append(f"ev_legacy_trace_usage_{safe_token(vals['source_key'])}")
    created_usages = create_with_xmlids(
        odoo, "kf.legacy.trace.usage", usage_records, usage_xmlids,
        create_xmlids=False,
    )

    existing_delivery_keys = {
        row["source_key"] for row in odoo.search_read_all(
            "kf.legacy.trace.delivery", [], ["source_key"]
        )
    }
    delivery_records, delivery_xmlids = [], []
    for delivery in direct_deliveries:
        if delivery["source_key"] in existing_delivery_keys:
            continue
        if delivery["eevo_partner_key"] not in partner_ids:
            continue
        vals = dict(delivery)
        trace_key = vals.pop("trace_key")
        vals["trace_id"] = header_cache[trace_key]
        vals["partner_id"] = partner_ids[vals["eevo_partner_key"]]
        delivery_records.append(vals)
        delivery_xmlids.append(f"ev_legacy_trace_delivery_{safe_token(vals['source_key'])}")
    created_deliveries = create_with_xmlids(
        odoo, "kf.legacy.trace.delivery", delivery_records, delivery_xmlids,
        create_xmlids=False,
    )
    desired_usage_counts = Counter(header_cache[x["trace_key"]] for x in trace_usages)
    trace_count_rows = odoo.search_read_all(
        "kf.legacy.trace", [], ["usage_count"]
    )
    usage_count_updates = defaultdict(list)
    for row in trace_count_rows:
        desired_count = desired_usage_counts.get(row["id"], 0)
        if row["usage_count"] != desired_count:
            usage_count_updates[desired_count].append(row["id"])
    updated_usage_heads = 0
    for desired_count, ids in usage_count_updates.items():
        odoo.call("kf.legacy.trace", "write", [ids, {"usage_count": desired_count}])
        updated_usage_heads += len(ids)

    event_records, event_xmlids = [], []
    for key, grouped in sorted(by_trace.items()):
        for event in grouped:
            if event["source_key"] in existing_source_keys:
                continue
            event_records.append({
                "trace_id": header_cache[key],
                "source_key": event["source_key"],
                "source_table": event["source_table"],
                "event_date": event["event_date"],
                "event_type_code": event["event_type_code"],
                "event_type_name": event["event_type_name"],
                "reference_number": event["reference_number"],
                "reference_position": event["reference_position"],
                "document_number": event["document_number"],
                "partner_id": partner_ids.get(event["eevo_partner_key"]) or False,
                "eevo_partner_key": event["eevo_partner_key"] or 0,
                "quantity": event["quantity"],
                "description": event["description"],
                "production_id": (
                    production_cache.get(production_number(event["reference_number"])) or False
                    if event["event_type_code"] == "2" else False
                ),
            })
            event_xmlids.append(f"ev_legacy_trace_event_{safe_token(event['source_key'])}")
    created_events = create_with_xmlids(odoo, "kf.legacy.trace.event", event_records, event_xmlids)

    # Link production events imported by earlier idempotent runs.
    link_groups = defaultdict(list)
    current_events = odoo.search_read_all(
        "kf.legacy.trace.event", [("event_type_code", "=", "2")],
        ["id", "reference_number", "production_id"],
    )
    for row in current_events:
        key = production_number(row["reference_number"])
        production_id = production_cache.get(key)
        current_id = row["production_id"][0] if row["production_id"] else None
        if production_id and current_id != production_id:
            link_groups[production_id].append(row["id"])
    linked_existing_events = 0
    for production_id, ids in link_groups.items():
        odoo.call("kf.legacy.trace.event", "write", [ids, {"production_id": production_id}])
        linked_existing_events += len(ids)
    final_headers = odoo.call("kf.legacy.trace", "search_count", [[]])
    final_events = odoo.call("kf.legacy.trace.event", "search_count", [[]])
    print(json.dumps({
        "apply": "OK", "created_headers": created_headers, "created_events": created_events,
        "created_productions": created_productions,
        "created_components": created_components,
        "created_outputs": created_outputs,
        "created_usages": created_usages,
        "created_direct_deliveries": created_deliveries,
        "updated_output_heads": updated_output_heads,
        "updated_usage_heads": updated_usage_heads,
        "linked_existing_events": linked_existing_events,
        "updated_sale_heads": updated_sale_heads,
        "repaired_header_products": repaired_header_products,
        "repaired_production_products": repaired_production_products,
        "repaired_component_products": repaired_component_products,
        "final_headers": final_headers, "final_events": final_events, "backup": args.backup,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
