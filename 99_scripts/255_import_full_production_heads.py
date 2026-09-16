#!/usr/bin/env python3
"""Import all eEvolution production heads; no operational MRP records or old details."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import os

import pyodbc

import migration_runtime


END = datetime(2027, 1, 1)
BATCH = 200


def connect_source():
    return pyodbc.connect(
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};PWD={os.environ['EV_PASSWORD']};"
        "Encrypt=yes;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;",
        readonly=True, timeout=30,
    )


def dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else False


class Odoo:
    def __init__(self):
        target = migration_runtime.require_target(os.environ["ODOO_DB"])
        self.db, self.key = os.environ["ODOO_DB"], os.environ["ODOO_API_KEY"]
        common = migration_runtime.server_proxy(target.url.rstrip("/") + "/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, target.user, self.key, {})
        self.models = migration_runtime.server_proxy(target.url.rstrip("/") + "/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args=None, kw=None):
        return self.models.execute_kw(self.db, self.uid, self.key, model, method, args or [], kw or {})

    def binding_map(self, prefix, model):
        result, offset = {}, 0
        while True:
            page = self.call("ir.model.data", "search_read", [[
                ("module", "=", "__import__"), ("model", "=", model), ("name", "like", prefix + "%")
            ]], {"fields": ["name", "res_id"], "limit": 5000, "offset": offset, "order": "id"})
            result.update({row["name"]: row["res_id"] for row in page})
            if len(page) < 5000:
                return result
            offset += len(page)


def load_source():
    with connect_source() as connection:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cursor.execute("""
            SELECT p.LFDNR,p.STATUS,p.TYP,p.MENGE,p.PRODMENGE,p.AUSMENGE,
                   p.PVDAT,p.PPDAT,p.ENDDAT,p.ARTNR,p.PRODLISTLFDNR,
                   a.ARTNR1,a.ABEZ1,a.ABEZ2
              FROM dbo.PRODUKTION p
              LEFT JOIN dbo.ARTIKEL a ON a.LFDNR=p.ARTNR
             WHERE COALESCE(p.PPDAT,p.PVDAT,p.PDDAT,p.ENDDAT,p.TMSTMP)<?
             ORDER BY p.LFDNR
        """, END)
        return cursor.fetchall()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="")
    args = parser.parse_args()
    if os.environ.get("ODOO_DB") != "kuf-erp-all-data":
        raise SystemExit("Nur für kuf-erp-all-data freigegeben")
    target = migration_runtime.require_target(os.environ["ODOO_DB"])
    if args.apply and (
        migration_runtime.migration_mode() != "apply" or os.environ.get("KF_ALLOW_WRITE") != "1"
        or not args.backup.startswith(target.backup_prefix)
    ):
        raise SystemExit("Apply nur geschützt mit passender Sicherung")
    source = load_source()
    odoo = Odoo()
    product_links = odoo.binding_map("ev_product_", "product.template")
    template_by_source = {
        int(name.removeprefix("ev_product_")): template_id
        for name, template_id in product_links.items() if name.removeprefix("ev_product_").isdigit()
    }
    templates = odoo.call("product.template", "read", [list(template_by_source.values())], {"fields": ["product_variant_ids"]})
    variant_by_template = {row["id"]: row["product_variant_ids"][0] for row in templates if row["product_variant_ids"]}
    products = {source_id: variant_by_template[template_id] for source_id, template_id in template_by_source.items()
                if template_id in variant_by_template}
    bindings = odoo.binding_map("ev_legacy_production_", "kf.legacy.production")
    existing_rows = odoo.call(
        "kf.legacy.production", "search_read", [[]],
        {"fields": ["eevo_product_key", "product_id"], "limit": 100000, "order": "id"},
    )
    repairs = defaultdict(list)
    for existing in existing_rows:
        product_key = int(existing["eevo_product_key"] or 0)
        if not existing["product_id"] and products.get(product_key):
            repairs[products[product_key]].append(existing["id"])
    plan = []
    missing_products = set()
    for row in source:
        key = int(row[0])
        name = f"ev_legacy_production_{key}"
        if name in bindings:
            continue
        product_key = int(row[9] or 0)
        if product_key and product_key not in products:
            missing_products.add(product_key)
        plan.append((name, {
            "eevo_order_key": key, "name": f"P-{key}", "status_code": str(row[1] or ""),
            "order_type": str(row[2] or "").strip(), "quantity_ordered": float(row[3] or 0),
            "quantity_produced": float(row[4] or 0), "quantity_scrapped": float(row[5] or 0),
            "planned_date": dt(row[6]), "production_date": dt(row[7]), "end_date": dt(row[8]),
            "eevo_product_key": product_key, "product_id": products.get(product_key) or False,
            "bom_reference": int(row[10] or 0), "article_number": str(row[11] or "").strip(),
            "article_name": " ".join(str(value).strip() for value in row[12:14] if value).strip(),
            "locked": True,
        }))
    unlocked = odoo.call("kf.legacy.production", "search_count", [[("locked", "=", False)]])
    summary = {"source_heads": len(source), "existing_heads": len(bindings), "new_heads": len(plan),
               "missing_product_relations_new": len(missing_products),
               "existing_product_relations_to_repair": sum(len(ids) for ids in repairs.values()),
               "unlocked_existing": unlocked}
    print(summary, flush=True)
    if unlocked:
        raise SystemExit("Abbruch: ungesperrter Produktionskopf")
    if not args.apply:
        print("DRY_RUN_OK_NO_WRITES")
        return
    repaired = 0
    for product_id, record_ids in repairs.items():
        for offset in range(0, len(record_ids), 500):
            ids = record_ids[offset:offset + 500]
            odoo.call("kf.legacy.production", "write", [ids, {"product_id": product_id, "locked": True}])
            repaired += len(ids)
    if repaired:
        print(f"production_product_relations_repaired: {repaired}", flush=True)
    created = 0
    for offset in range(0, len(plan), BATCH):
        part = plan[offset:offset + BATCH]
        ids = odoo.call("kf.legacy.production", "create", [[values for _, values in part]])
        if isinstance(ids, int):
            ids = [ids]
        odoo.call("ir.model.data", "create", [[
            {"module": "__import__", "name": name, "model": "kf.legacy.production", "res_id": record_id, "noupdate": True}
            for (name, _), record_id in zip(part, ids)
        ]])
        created += len(ids)
        print(f"production_heads: {created}/{len(plan)}", flush=True)
    print("APPLY_OK_EFFECT_FREE", summary, flush=True)


if __name__ == "__main__":
    main()
