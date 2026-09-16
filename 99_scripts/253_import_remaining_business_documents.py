#!/usr/bin/env python3
"""Import complete delivery and invoice history as effect-free Legacy records.

No stock, accounting, mail or workflow model is written.  Source access is read-only;
all target records are locked custom records with stable eEvolution bindings.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import os
import re

import pyodbc

import migration_runtime


END = datetime(2027, 1, 1)
BATCH = 200


def clean(value):
    return str(value).strip() if value is not None else ""


def integer(value):
    if value in (None, ""):
        return 0
    return int(float(value))


def number(value):
    return float(value or 0)


def dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else False


def external_token(value):
    return re.sub(r"[^A-Za-z0-9_]", "_", clean(value)).strip("_")


def chunks(values, size=BATCH):
    for offset in range(0, len(values), size):
        yield values[offset:offset + size]


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
        target = migration_runtime.require_target(os.environ["ODOO_DB"])
        self.db = os.environ["ODOO_DB"]
        self.key = os.environ["ODOO_API_KEY"]
        common = migration_runtime.server_proxy(target.url.rstrip("/") + "/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, target.user, self.key, {})
        if not self.uid:
            raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
        self.models = migration_runtime.server_proxy(target.url.rstrip("/") + "/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args=None, kwargs=None):
        return self.models.execute_kw(self.db, self.uid, self.key, model, method, args or [], kwargs or {})

    def bindings(self, prefixes, model=None):
        domain = [("module", "=", "__import__")]
        if model:
            domain.append(("model", "=", model))
        rows = []
        for prefix in prefixes:
            offset = 0
            while True:
                page = self.call(
                    "ir.model.data", "search_read",
                    [domain + [("name", "like", prefix + "%")]],
                    {"fields": ["name", "model", "res_id"], "limit": 5000, "offset": offset, "order": "id"},
                )
                rows.extend(page)
                if len(page) < 5000:
                    break
                offset += len(page)
        return {row["name"]: row for row in rows}


def rows(cursor, sql, *params):
    cursor.execute(sql, *params)
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def load_source():
    with source_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        customer_to_address = {
            integer(row["KNDNR"]): integer(row["ADRNR"])
            for row in rows(cursor, "SELECT KNDNR,ADRNR FROM dbo.KUNDE WHERE ADRNR IS NOT NULL")
        }
        vendor_to_address = {
            integer(row["LIEFNR"]): integer(row["ADRNR"])
            for row in rows(cursor, "SELECT LIEFNR,ADRNR FROM dbo.LIEFERANT WHERE ADRNR IS NOT NULL")
        }
        deliveries = rows(cursor, """
            SELECT h.LSNR,h.LFDANGAUFGUTNR,h.AUFNR,h.KNDNR1,h.KNDNAME1,h.KNDNAME2,g.KNDNR,
                   h.LSDATUM,h.STORNO,h.STORNOTIMESTAMP,h.WSYMBOL,h.KENNZEICHEN
              FROM dbo.AAGLS h
              LEFT JOIN dbo.ANGAUFGUT g ON g.LFDNR=h.LFDANGAUFGUTNR
             WHERE h.LSDATUM<?
             ORDER BY h.LSNR
        """, END)
        delivery_lines = rows(cursor, """
            SELECT CONVERT(varchar(36),p._ID) SOURCE_GUID,p.LSNR,p.POSNR,p.LFDARTNR,
                   p.ARTNR1,p.ABEZ1,p.ABEZ2,p.LANGTEXT,p.LIEFERMENGE,p.PREIS,p.MWST,
                   p.MENGENSCHL,p.STORNO
              FROM dbo.AAGLSPOS p JOIN dbo.AAGLS h ON h.LSNR=p.LSNR
             WHERE h.LSDATUM<?
             ORDER BY p.LSNR,p.POSNR,p._ID
        """, END)
        outgoing = rows(cursor, """
            SELECT h.LFDFAKTNR,h.LFDANGAUFGUTNR,h.AUFNR,h.RECHNR,h.GUTNR,h.FAKTART,
                   h.KNDNR1,h.KNDNAME1,h.KNDNAME2,h.FAKTDATUM,h.STORNO,h.WSYMBOL,
                   h.OPOSERLEDIGT,h.EXCL,h.INCL,h.SUMMWST1,h.SUMMWST2,h.SUMMWST3,
                   g.KNDNR
              FROM dbo.AAGFAKT h
              LEFT JOIN dbo.ANGAUFGUT g ON g.LFDNR=h.LFDANGAUFGUTNR
             WHERE h.FAKTDATUM<?
             ORDER BY h.LFDFAKTNR
        """, END)
        outgoing_lines = rows(cursor, """
            SELECT CONVERT(varchar(36),p._ID) SOURCE_GUID,p.LFDFAKTNR,p.POSNR,p.LFDARTNR,
                   p.ARTNR1,p.ABEZ1,p.ABEZ2,p.LANGTEXT,p.BERECHMENGE,p.PREIS,
                   p.FIBUPREIS,p.MWST,p.MENGENSCHL,p.STORNO
              FROM dbo.AAGFAKTPOS p JOIN dbo.AAGFAKT h ON h.LFDFAKTNR=p.LFDFAKTNR
             WHERE h.FAKTDATUM<?
             ORDER BY p.LFDFAKTNR,p.POSNR,p._ID
        """, END)
        incoming = rows(cursor, """
            SELECT r.LFDNR,r.SAMMELBESTNR,r.LIEFNR,r.KREDITOR,r.RECHNR,r.BELEGNR,
                   r.RECHDATUM,r.STATUS,r.STORNO,r.WSYMBOL,r.BETRAG,r.BRUTTO,
                   r.SUMMWST1,r.SUMMWST2,r.SUMMWST3,v.LIEFNR_INT
              FROM dbo.RECHEINGANG r
              OUTER APPLY (
                   SELECT TOP 1 b.LIEFNR LIEFNR_INT
                     FROM dbo.BESTELLUNG b
                    WHERE b.SAMMELBESTNR=r.SAMMELBESTNR
                    ORDER BY b.BESTNR
              ) v
             WHERE r.RECHDATUM<?
             ORDER BY r.LFDNR
        """, END)
        incoming_lines = rows(cursor, """
            SELECT CONVERT(varchar(36),p._ID) SOURCE_GUID,p.LFDNR,p.POSNR,p.ARTLFDNR,
                   p.ARTNR1,p.BUCHTEXT,p.MENGE,p.BETRAG,p.MWST,p.MGESCHL
              FROM dbo.RECHEINPOS p JOIN dbo.RECHEINGANG h ON h.LFDNR=p.LFDNR
             WHERE h.RECHDATUM<?
             ORDER BY p.LFDNR,p.POSNR,p._ID
        """, END)
    return (customer_to_address, vendor_to_address, deliveries, delivery_lines,
            outgoing, outgoing_lines, incoming, incoming_lines)


def target_maps(odoo):
    links = odoo.bindings(("ev_adr_", "ev_product_"))
    partners = {
        integer(name.removeprefix("ev_adr_")): row["res_id"]
        for name, row in links.items()
        if name.startswith("ev_adr_") and name.removeprefix("ev_adr_").isdigit()
    }
    templates = {
        integer(name.removeprefix("ev_product_")): row["res_id"]
        for name, row in links.items()
        if name.startswith("ev_product_") and name.removeprefix("ev_product_").isdigit()
    }
    records = odoo.call("product.template", "read", [list(templates.values())], {"fields": ["product_variant_ids"]})
    variant_by_template = {row["id"]: row["product_variant_ids"][0] for row in records if row["product_variant_ids"]}
    products = {source: variant_by_template[template] for source, template in templates.items() if template in variant_by_template}
    return partners, products


def add_head(plan, ext_name, values):
    values["locked"] = True
    plan.append((ext_name, values))


def prepare_heads(customer_to_address, vendor_to_address, partners, deliveries, outgoing, incoming):
    plan = []
    reviews = Counter()
    for row in deliveries:
        source_id = str(integer(row["LSNR"]))
        customer = integer(row["KNDNR"])
        partner = partners.get(customer_to_address.get(customer))
        notes = [] if partner else [f"Kunde {clean(row['KNDNR1'])} nicht eindeutig auf Odoo-Partner auflösbar."]
        reviews.update(["delivery_partner"] if notes else [])
        add_head(plan, "ev_legacy_delivery_" + source_id, {
            "name": source_id, "source_id": source_id, "document_type": "delivery",
            "document_date": dt(row["LSDATUM"]), "partner_id": partner or False,
            "source_partner_number": clean(row["KNDNR1"]),
            "source_partner_name": " ".join(filter(None, [clean(row["KNDNAME1"]), clean(row["KNDNAME2"])])),
            "source_order_id": integer(row["LFDANGAUFGUTNR"]), "source_order_number": clean(row["AUFNR"]),
            "source_status": clean(row["KENNZEICHEN"]), "currency_symbol": clean(row["WSYMBOL"]),
            "cancelled": bool(row["STORNO"]), "cancellation_date": dt(row["STORNOTIMESTAMP"]),
            "review_status": "review" if notes else "ok", "review_note": "\n".join(notes),
        })
    for row in outgoing:
        source_id = str(integer(row["LFDFAKTNR"]))
        customer = integer(row["KNDNR"] or row["KNDNR1"])
        partner = partners.get(customer_to_address.get(customer))
        notes = [] if partner else [f"Kunde {customer or clean(row['KNDNR1'])} nicht eindeutig auf Odoo-Partner auflösbar."]
        doc_type = "out_refund" if integer(row["FAKTART"]) in (2, 3) else "out_invoice"
        document_number = clean(row["GUTNR"] if doc_type == "out_refund" else row["RECHNR"]) or source_id
        tax = sum(number(row[key]) for key in ("SUMMWST1", "SUMMWST2", "SUMMWST3"))
        reviews.update(["outgoing_partner"] if notes else [])
        add_head(plan, "ev_legacy_out_invoice_" + source_id, {
            "name": document_number, "source_id": source_id, "document_type": doc_type,
            "document_date": dt(row["FAKTDATUM"]), "partner_id": partner or False,
            "source_partner_number": str(customer or clean(row["KNDNR1"])),
            "source_partner_name": " ".join(filter(None, [clean(row["KNDNAME1"]), clean(row["KNDNAME2"])])),
            "source_order_id": integer(row["LFDANGAUFGUTNR"]), "source_order_number": clean(row["AUFNR"]),
            "source_status": "erledigt" if bool(row["OPOSERLEDIGT"]) else "offen in Quelle",
            "currency_symbol": clean(row["WSYMBOL"]), "amount_net": number(row["EXCL"]),
            "amount_tax": tax, "amount_gross": number(row["INCL"]), "cancelled": bool(row["STORNO"]),
            "review_status": "review" if notes else "ok", "review_note": "\n".join(notes),
        })
    for row in incoming:
        source_id = str(integer(row["LFDNR"]))
        vendor = integer(row["LIEFNR_INT"])
        partner = partners.get(vendor_to_address.get(vendor))
        notes = [] if partner else [f"Lieferant zum Sammelbeleg {clean(row['SAMMELBESTNR'])} nicht eindeutig auflösbar."]
        tax = sum(number(row[key]) for key in ("SUMMWST1", "SUMMWST2", "SUMMWST3"))
        reviews.update(["incoming_partner"] if notes else [])
        add_head(plan, "ev_legacy_in_invoice_" + source_id, {
            "name": clean(row["RECHNR"]) or clean(row["BELEGNR"]) or source_id,
            "source_id": source_id, "document_type": "in_invoice", "document_date": dt(row["RECHDATUM"]),
            "partner_id": partner or False, "source_partner_number": str(vendor or ""),
            "source_partner_name": clean(row["KREDITOR"]), "source_order_number": clean(row["SAMMELBESTNR"]),
            "source_status": clean(row["STATUS"]), "currency_symbol": clean(row["WSYMBOL"]),
            "amount_net": number(row["BETRAG"]), "amount_tax": tax, "amount_gross": number(row["BRUTTO"]),
            "cancelled": bool(row["STORNO"]), "review_status": "review" if notes else "ok",
            "review_note": "\n".join(notes),
        })
    return plan, reviews


def prepare_lines(products, delivery_lines, outgoing_lines, incoming_lines):
    plan = []
    for row in delivery_lines:
        guid = external_token(row["SOURCE_GUID"])
        product_key = integer(row["LFDARTNR"])
        plan.append(("ev_legacy_delivery_line_" + guid, "ev_legacy_delivery_" + str(integer(row["LSNR"])), {
            "source_key": "AAGLSPOS:" + clean(row["SOURCE_GUID"]), "position_number": integer(row["POSNR"]),
            "product_id": products.get(product_key) or False, "source_product_id": product_key or False,
            "article_number": clean(row["ARTNR1"]), "name": " ".join(filter(None, [clean(row["ABEZ1"]), clean(row["ABEZ2"]), clean(row["LANGTEXT"])])),
            "quantity": number(row["LIEFERMENGE"]), "price_unit": number(row["PREIS"]),
            "tax_rate": number(row["MWST"]), "uom_name": clean(row["MENGENSCHL"]), "cancelled": bool(row["STORNO"]),
        }))
    for row in outgoing_lines:
        guid = external_token(row["SOURCE_GUID"])
        product_key = integer(row["LFDARTNR"])
        plan.append(("ev_legacy_out_invoice_line_" + guid, "ev_legacy_out_invoice_" + str(integer(row["LFDFAKTNR"])), {
            "source_key": "AAGFAKTPOS:" + clean(row["SOURCE_GUID"]), "position_number": integer(row["POSNR"]),
            "product_id": products.get(product_key) or False, "source_product_id": product_key or False,
            "article_number": clean(row["ARTNR1"]), "name": " ".join(filter(None, [clean(row["ABEZ1"]), clean(row["ABEZ2"]), clean(row["LANGTEXT"])])),
            "quantity": number(row["BERECHMENGE"]), "price_unit": number(row["PREIS"]),
            "amount": number(row["FIBUPREIS"]), "tax_rate": number(row["MWST"]),
            "uom_name": clean(row["MENGENSCHL"]), "cancelled": bool(row["STORNO"]),
        }))
    for row in incoming_lines:
        guid = external_token(row["SOURCE_GUID"])
        product_key = integer(row["ARTLFDNR"])
        plan.append(("ev_legacy_in_invoice_line_" + guid, "ev_legacy_in_invoice_" + str(integer(row["LFDNR"])), {
            "source_key": "RECHEINPOS:" + clean(row["SOURCE_GUID"]), "position_number": integer(row["POSNR"]),
            "product_id": products.get(product_key) or False, "source_product_id": product_key or False,
            "article_number": clean(row["ARTNR1"]), "name": clean(row["BUCHTEXT"]),
            "quantity": number(row["MENGE"]), "amount": number(row["BETRAG"]),
            "tax_rate": number(row["MWST"]), "uom_name": clean(row["MGESCHL"]),
        }))
    return plan


def create_batch(odoo, model, plan, bindings):
    created = 0
    for part in chunks(plan):
        names = [item[0] for item in part]
        values = [item[1] for item in part]
        ids = odoo.call(model, "create", [values])
        if isinstance(ids, int):
            ids = [ids]
        odoo.call("ir.model.data", "create", [[
            {"module": "__import__", "name": name, "model": model, "res_id": record_id, "noupdate": True}
            for name, record_id in zip(names, ids)
        ]])
        bindings.update({name: {"model": model, "res_id": record_id} for name, record_id in zip(names, ids)})
        created += len(ids)
        print(f"{model}: {created}/{len(plan)}", flush=True)
    return created


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="")
    args = parser.parse_args()
    if os.environ.get("ODOO_DB") != "kuf-erp-all-data":
        raise SystemExit("Nur für kuf-erp-all-data freigegeben")
    target = migration_runtime.require_target(os.environ["ODOO_DB"])
    if args.apply:
        if migration_runtime.migration_mode() != "apply" or os.environ.get("KF_ALLOW_WRITE") != "1":
            raise SystemExit("Apply nur über den geschützten Migrations-Wrapper")
        if not args.backup.startswith(target.backup_prefix):
            raise SystemExit("Passende verifizierte Sicherung erforderlich")

    source = load_source()
    customer_to_address, vendor_to_address = source[0], source[1]
    deliveries, delivery_lines, outgoing, outgoing_lines, incoming, incoming_lines = source[2:]
    odoo = Odoo()
    partners, products = target_maps(odoo)
    head_plan, reviews = prepare_heads(customer_to_address, vendor_to_address, partners, deliveries, outgoing, incoming)
    line_plan = prepare_lines(products, delivery_lines, outgoing_lines, incoming_lines)
    source_line_counts = Counter(head_name for _, head_name, _ in line_plan)
    for head_name, values in head_plan:
        values["source_line_count"] = source_line_counts.get(head_name, 0)
    bindings = odoo.bindings(("ev_legacy_delivery_", "ev_legacy_out_invoice_", "ev_legacy_in_invoice_"))
    missing_heads = [(name, values) for name, values in head_plan if name not in bindings]
    missing_lines = [(name, head_name, values) for name, head_name, values in line_plan if name not in bindings]
    source_head_names = {name for name, _ in head_plan}
    missing_parent = sorted({head_name for _, head_name, _ in missing_lines if head_name not in source_head_names})
    duplicate_line_names = [name for name, count in Counter(name for name, _, _ in line_plan).items() if count > 1]
    summary = {
        "deliveries": len(deliveries), "delivery_lines": len(delivery_lines),
        "outgoing_invoices": len(outgoing), "outgoing_lines": len(outgoing_lines),
        "incoming_invoices": len(incoming), "incoming_lines": len(incoming_lines),
        "heads_total": len(head_plan), "lines_total": len(line_plan),
        "heads_new": len(missing_heads), "lines_new": len(missing_lines),
        "review_reasons": dict(reviews), "duplicate_line_external_ids": len(duplicate_line_names),
        "missing_line_parents": len(missing_parent),
    }
    print(summary, flush=True)
    if duplicate_line_names or missing_parent:
        raise SystemExit("Abbruch wegen nicht eindeutiger oder verwaister Quellpositionen")
    if not args.apply:
        print("DRY_RUN_OK_NO_WRITES")
        return
    if missing_heads:
        create_batch(odoo, "kf.legacy.business.document", missing_heads, bindings)
    creatable_lines = []
    for name, head_name, values in missing_lines:
        parent = bindings.get(head_name)
        if not parent:
            raise RuntimeError(f"Fehlender Zielkopf {head_name}")
        values["document_id"] = parent["res_id"]
        creatable_lines.append((name, values))
    if creatable_lines:
        create_batch(odoo, "kf.legacy.business.document.line", creatable_lines, bindings)
    print("APPLY_OK_EFFECT_FREE", summary, flush=True)


if __name__ == "__main__":
    main()
