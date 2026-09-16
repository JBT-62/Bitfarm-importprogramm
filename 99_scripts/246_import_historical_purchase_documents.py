#!/usr/bin/env python3
"""Import eEvolution purchase history into effect-free, read-only Legacy models."""
from __future__ import annotations

import argparse
import hashlib
import os
import socket
import time
import xmlrpc.client
from collections import Counter, defaultdict
from datetime import datetime

import pyodbc

import migration_runtime


def clean(value):
    return str(value or "").strip()


def as_int(value):
    return int(value) if value is not None else None


def as_date(value):
    return value.date().isoformat() if value else False


def as_datetime(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else False


def chunks(values, size):
    for offset in range(0, len(values), size):
        yield values[offset:offset + size]


def safe_token(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def source_connection():
    return pyodbc.connect(
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
        f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "ApplicationIntent=ReadOnly;",
        readonly=True,
        timeout=30,
    )


class Odoo:
    def __init__(self):
        self.url, self.db, self.user, self.key = [
            os.environ[name] for name in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_API_KEY")
        ]
        migration_runtime.require_target(self.db)
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
                time.sleep(2 ** attempt)
                self.connect()

    def search_read_all(self, model, domain, fields, size=5000):
        result, offset = [], 0
        while True:
            rows = self.call(
                model, "search_read", [domain],
                {"fields": fields, "offset": offset, "limit": size, "order": "id"},
            )
            result.extend(rows)
            if len(rows) < size:
                return result
            offset += len(rows)

    def register_many(self, model, names, ids):
        if not names:
            return
        self.call("ir.model.data", "create", [[
            {"module": "__import__", "name": name, "model": model, "res_id": record_id,
             "noupdate": True}
            for name, record_id in zip(names, ids)
        ]])


def group_key(row):
    if int(row["RAHMEN"] or 0):
        key = as_int(row["LFDBESTRAHMEN"]) or as_int(row["SAMMELBESTNR"]) or as_int(row["BESTNR"])
        return f"F-{key}"
    collective = as_int(row["SAMMELBESTNR"]) or 0
    return f"S-{collective}" if collective else f"B-{as_int(row['BESTNR'])}"


def load_source(start, end):
    with source_connection() as cn:
        cur = cn.cursor()
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cur.execute(
            """
            SELECT BESTNR,SAMMELBESTNR,POSNR,ARTNR,LIEFNR,
                   COALESCE(BIDAT,BVDAT) BELEGDATUM,BIDAT,BVDAT,BDDAT,LIEFERDAT,
                   BESTSTATUS,BESTTYP,BESTMENGE,GELMENGE,RESMENGE,EKPREIS,
                   PREISEINHEIT,EKMENGENSCHL,LFDWAEHRUNG,WSYMBOL,
                   ISNULL(RAHMEN,0) RAHMEN,LFDBESTRAHMEN,LFDSTORNONR,STORNOAM,
                   ARTNR1,ARTBEZ1,ARTBEZ2,LIEFERARTNR,LIEFERABEZ
              FROM dbo.BESTELLUNG
             WHERE COALESCE(BIDAT,BVDAT)>=? AND COALESCE(BIDAT,BVDAT)<?
             ORDER BY COALESCE(NULLIF(SAMMELBESTNR,0),BESTNR),POSNR,BESTNR
            """,
            start, end,
        )
        columns = [item[0] for item in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
        cur.execute("SELECT LIEFNR,ADRNR FROM dbo.LIEFERANT WHERE LIEFNR IS NOT NULL")
        vendor_address = {int(r[0]): int(r[1]) for r in cur.fetchall() if r[1] is not None}
    source_keys = [f"BESTELLUNG:{as_int(row['BESTNR'])}" for row in rows]
    duplicates = [key for key, count in Counter(source_keys).items() if count > 1]
    if duplicates:
        raise RuntimeError(f"BESTELLUNG.BESTNR ist nicht eindeutig: {duplicates[:20]}")
    grouped = defaultdict(list)
    for row in rows:
        grouped[group_key(row)].append(row)
    return rows, grouped, vendor_address


def resolve_targets(odoo, source_product_keys, source_vendor_numbers, vendor_address):
    product_imd = odoo.call(
        "ir.model.data", "search_read",
        [[("module", "=", "__import__"), ("name", "like", "ev_product_%"),
          ("model", "=", "product.template")]],
        {"fields": ["name", "res_id"], "limit": 100000},
    )
    template_by_source = {
        int(row["name"].removeprefix("ev_product_")): row["res_id"]
        for row in product_imd
        if row["name"].removeprefix("ev_product_").isdigit()
        and int(row["name"].removeprefix("ev_product_")) in source_product_keys
    }
    template_rows = {}
    for part in chunks(sorted(set(template_by_source.values())), 500):
        for row in odoo.call(
            "product.template", "read", [part],
            {"fields": ["product_variant_ids"], "context": {"active_test": False}},
        ):
            template_rows[row["id"]] = row
    products = {
        source_id: template_rows[template_id]["product_variant_ids"][0]
        for source_id, template_id in template_by_source.items()
        if template_rows.get(template_id, {}).get("product_variant_ids")
    }
    partner_imd = odoo.call(
        "ir.model.data", "search_read",
        [[("module", "=", "__import__"), ("name", "like", "ev_adr_%"),
          ("model", "=", "res.partner")]],
        {"fields": ["name", "res_id"], "limit": 100000},
    )
    partner_by_address = {
        int(row["name"].removeprefix("ev_adr_")): row["res_id"]
        for row in partner_imd if row["name"].removeprefix("ev_adr_").isdigit()
    }
    partners = {
        vendor: partner_by_address[address]
        for vendor in source_vendor_numbers
        if (address := vendor_address.get(vendor)) in partner_by_address
    }
    return products, partners


def document_values(key, rows, partners):
    suppliers = sorted({as_int(row["LIEFNR"]) for row in rows if row["LIEFNR"] is not None})
    dates = sorted({as_date(row["BELEGDATUM"]) for row in rows if row["BELEGDATUM"]})
    statuses = sorted({clean(row["BESTSTATUS"]) for row in rows})
    currencies = sorted({clean(row["WSYMBOL"]) for row in rows})
    notes = []
    vendor_id = False
    source_vendor = suppliers[0] if len(suppliers) == 1 else 0
    if len(suppliers) != 1:
        notes.append("Beleggruppe enthält keine oder mehrere eEvolution-Lieferantennummern.")
    elif source_vendor not in partners:
        notes.append(
            f"eEvolution-Lieferant {source_vendor} besitzt keinen auflösbaren Odoo-Partnerbezug."
        )
    else:
        vendor_id = partners[source_vendor]
    if len(dates) > 1:
        notes.append(
            "Positionen enthalten unterschiedliche Belegdaten; im Kopf wird das früheste Datum gezeigt."
        )
    if len(statuses) > 1:
        notes.append("Positionen enthalten unterschiedliche eEvolution-Statuscodes.")
    if "" in currencies:
        notes.append("Mindestens eine Position enthält kein Währungskennzeichen.")
    if key.startswith("B-"):
        notes.append(
            "Keine Sammelbestellnummer vorhanden; BESTELLUNG.BESTNR bildet den eigenständigen Beleg."
        )
    collective_numbers = sorted({as_int(r["SAMMELBESTNR"]) for r in rows if r["SAMMELBESTNR"]})
    cancelled = sum(bool(row["LFDSTORNONR"] or row["STORNOAM"]) for row in rows)
    return {
        "name": key[2:],
        "source_group_key": key,
        "source_collective_number": collective_numbers[0] if len(collective_numbers) == 1 else 0,
        "document_type": "framework" if key.startswith("F-") else "purchase",
        "document_date": dates[0] if dates else False,
        "vendor_id": vendor_id,
        "source_vendor_number": source_vendor,
        "source_status_summary": ", ".join(statuses),
        "currency_summary": ", ".join(value or "(leer)" for value in currencies),
        "source_line_count": len(rows),
        "cancelled_line_count": cancelled,
        "review_status": "review" if notes else "ok",
        "review_note": "\n".join(notes),
    }


def line_values(row, document_id, products):
    product_key = as_int(row["ARTNR"]) or 0
    return {
        "document_id": document_id,
        "source_key": f"BESTELLUNG:{as_int(row['BESTNR'])}",
        "source_order_number": as_int(row["BESTNR"]) or 0,
        "position_number": as_int(row["POSNR"]) or 0,
        "product_id": products.get(product_key) or False,
        "source_product_id": product_key,
        "article_number": clean(row["ARTNR1"]),
        "name": " ".join(filter(None, (clean(row["ARTBEZ1"]), clean(row["ARTBEZ2"])))),
        "source_vendor_article_number": clean(row["LIEFERARTNR"]),
        "source_vendor_description": clean(row["LIEFERABEZ"]),
        "quantity_ordered": float(row["BESTMENGE"] or 0),
        "quantity_delivered": float(row["GELMENGE"] or 0),
        "quantity_reserved": float(row["RESMENGE"] or 0),
        "price_raw": float(row["EKPREIS"] or 0),
        "price_unit_raw": float(row["PREISEINHEIT"] or 0),
        "source_uom_key": as_int(row["EKMENGENSCHL"]) or 0,
        "currency_symbol": clean(row["WSYMBOL"]),
        "source_status": clean(row["BESTSTATUS"]),
        "source_order_type": clean(row["BESTTYP"]),
        "document_date": as_date(row["BELEGDATUM"]),
        "internal_date": as_date(row["BIDAT"]),
        "vendor_date": as_date(row["BVDAT"]),
        "planned_date": as_date(row["BDDAT"]),
        "delivery_date": as_date(row["LIEFERDAT"]),
        "source_framework_id": as_int(row["LFDBESTRAHMEN"]) or 0,
        "cancelled": bool(row["LFDSTORNONR"] or row["STORNOAM"]),
        "cancellation_date": as_datetime(row["STORNOAM"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup")
    parser.add_argument("--from-date", default="2016-09-16")
    parser.add_argument("--to-date", default="2026-09-17", help="Exklusives Enddatum")
    args = parser.parse_args()
    target = migration_runtime.require_target(os.environ.get("ODOO_DB", ""))
    if args.apply and migration_runtime.migration_mode() != "apply":
        raise SystemExit("--apply verlangt MIGRATION_MODE=apply")
    if args.apply and (not args.backup or not args.backup.startswith(target.backup_prefix)):
        raise SystemExit("--apply verlangt eine passende verifizierte Sicherung")
    start = datetime.fromisoformat(args.from_date)
    end = datetime.fromisoformat(args.to_date)
    if start >= end:
        raise SystemExit("Ungültiger Zeitraum")

    rows, grouped, vendor_address = load_source(start, end)
    odoo = Odoo()
    products, partners = resolve_targets(
        odoo,
        {as_int(row["ARTNR"]) for row in rows if row["ARTNR"] is not None},
        {as_int(row["LIEFNR"]) for row in rows if row["LIEFNR"] is not None},
        vendor_address,
    )
    missing_products = sorted({as_int(row["ARTNR"]) for row in rows if row["ARTNR"] is not None} - set(products))
    if missing_products:
        raise SystemExit(f"Abbruch: historische Artikelbezüge fehlen: {missing_products[:30]}")

    model_available = bool(odoo.call(
        "ir.model", "search_count", [[("model", "=", "kf.legacy.purchase.document")]]
    ))
    existing_documents = existing_lines = {}
    if model_available:
        existing_documents = {
            row["source_group_key"]: row["id"]
            for row in odoo.search_read_all(
                "kf.legacy.purchase.document", [], ["source_group_key"]
            )
        }
        existing_lines = {
            row["source_key"]: row["id"]
            for row in odoo.search_read_all(
                "kf.legacy.purchase.document.line", [], ["source_key"]
            )
        }
    document_plan = {
        key: document_values(key, group_rows, partners) for key, group_rows in grouped.items()
    }
    review_reasons = Counter()
    for values in document_plan.values():
        for note in (values["review_note"] or "").splitlines():
            if note:
                review_reasons[note] += 1
    print({
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "period": {"from": args.from_date, "to_exclusive": args.to_date},
        "source_lines": len(rows),
        "documents": len(grouped),
        "purchase_documents": sum(not key.startswith("F-") for key in grouped),
        "framework_documents": sum(key.startswith("F-") for key in grouped),
        "resolved_products": len(products),
        "resolved_vendors": len(partners),
        "review_documents": sum(v["review_status"] == "review" for v in document_plan.values()),
        "review_reasons": dict(review_reasons),
        "existing_documents": len(existing_documents),
        "existing_lines": len(existing_lines),
        "model_available": model_available,
    })
    if not args.apply:
        print("DRY_RUN_OK_NO_WRITES")
        return
    if not model_available:
        raise SystemExit("Legacy-Einkaufsmodell fehlt; Modul zuerst aktualisieren")
    module = odoo.call(
        "ir.module.module", "search_read", [[("name", "=", "kf_legacy_migration")]],
        {"fields": ["state", "installed_version"], "limit": 1},
    )
    if not module or module[0]["state"] != "installed" or module[0].get("installed_version") != "19.0.12.0.0":
        raise SystemExit("kf_legacy_migration 19.0.12.0.0 muss installiert sein")

    side_models = ("purchase.order", "purchase.order.line", "stock.picking", "stock.move", "account.move", "mail.mail")
    before = {model: odoo.call(model, "search_count", [[]]) for model in side_models}
    context = {"tracking_disable": True, "mail_create_nosubscribe": True, "mail_notrack": True}
    created_documents = 0
    missing_doc_items = [(key, vals) for key, vals in sorted(document_plan.items()) if key not in existing_documents]
    for part in chunks(missing_doc_items, 250):
        ids = odoo.call(
            "kf.legacy.purchase.document", "create", [[item[1] for item in part]],
            {"context": context},
        )
        if isinstance(ids, int):
            ids = [ids]
        names = [f"ev_legacy_purchase_doc_{safe_token(item[0])}" for item in part]
        odoo.register_many("kf.legacy.purchase.document", names, ids)
        existing_documents.update({item[0]: record_id for item, record_id in zip(part, ids)})
        created_documents += len(ids)
        print(f"DOCUMENT_PROGRESS={created_documents}/{len(missing_doc_items)}")

    created_lines = 0
    line_items = []
    for key, group_rows in sorted(grouped.items()):
        document_id = existing_documents[key]
        for row in group_rows:
            source_key = f"BESTELLUNG:{as_int(row['BESTNR'])}"
            if source_key in existing_lines:
                continue
            line_items.append((source_key, line_values(row, document_id, products)))
    for part in chunks(line_items, 500):
        ids = odoo.call(
            "kf.legacy.purchase.document.line", "create", [[item[1] for item in part]],
            {"context": context},
        )
        if isinstance(ids, int):
            ids = [ids]
        names = [f"ev_legacy_purchase_line_{safe_token(item[0])}" for item in part]
        odoo.register_many("kf.legacy.purchase.document.line", names, ids)
        created_lines += len(ids)
        print(f"LINE_PROGRESS={created_lines}/{len(line_items)}")

    after = {model: odoo.call(model, "search_count", [[]]) for model in side_models}
    if before != after:
        raise SystemExit(f"SIDE_EFFECT_DETECTED before={before} after={after}")
    final_documents = odoo.call("kf.legacy.purchase.document", "search_count", [[]])
    final_lines = odoo.call("kf.legacy.purchase.document.line", "search_count", [[]])
    print({
        "apply": "OK", "created_documents": created_documents,
        "created_lines": created_lines, "final_documents": final_documents,
        "final_lines": final_lines, "side_effects": 0, "backup": args.backup,
    })


if __name__ == "__main__":
    main()
