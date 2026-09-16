#!/usr/bin/env python3
"""Remove only proven, unbound duplicates from an interrupted purchase-history import."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import os

import migration_runtime


COMPARE_FIELDS = [
    "document_id", "source_key", "source_order_number", "position_number",
    "product_id", "source_product_id", "article_number", "name",
    "source_vendor_article_number", "source_vendor_description",
    "quantity_ordered", "quantity_delivered", "quantity_reserved",
    "price_raw", "price_unit_raw", "source_uom_key", "currency_symbol",
    "source_status", "source_order_type", "document_date", "internal_date",
    "vendor_date", "planned_date", "delivery_date", "source_framework_id",
    "cancelled", "cancellation_date",
]


def safe_token(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def normalized(value):
    if isinstance(value, list):
        return value[0] if value else False
    return value


class Odoo:
    def __init__(self):
        target = migration_runtime.require_target(os.environ["ODOO_DB"])
        self.db = os.environ["ODOO_DB"]
        self.key = os.environ["ODOO_API_KEY"]
        common = migration_runtime.server_proxy(
            target.url.rstrip("/") + "/xmlrpc/2/common", allow_none=True
        )
        self.uid = common.authenticate(self.db, target.user, self.key, {})
        if not self.uid:
            raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
        self.models = migration_runtime.server_proxy(
            target.url.rstrip("/") + "/xmlrpc/2/object", allow_none=True
        )

    def call(self, model, method, args=None, kwargs=None):
        return self.models.execute_kw(
            self.db, self.uid, self.key, model, method, args or [], kwargs or {}
        )

    def all(self, model, domain, fields, size=5000):
        rows, offset = [], 0
        while True:
            part = self.call(
                model, "search_read", [domain],
                {"fields": fields, "limit": size, "offset": offset, "order": "id"},
            )
            rows.extend(part)
            if len(part) < size:
                return rows
            offset += len(part)

    def count(self, model):
        return int(self.call(model, "search_count", [[]]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="")
    args = parser.parse_args()
    target = migration_runtime.require_target(os.environ.get("ODOO_DB", ""))
    if target.name != "kuf-erp-all-data":
        raise SystemExit("Bereinigung ist nur für kuf-erp-all-data freigegeben")
    if args.apply and migration_runtime.migration_mode() != "apply":
        raise SystemExit("--apply verlangt MIGRATION_MODE=apply")
    if args.apply and not args.backup.startswith(target.backup_prefix):
        raise SystemExit("--apply verlangt das verifizierte Ziel-Backup")

    odoo = Odoo()
    rows = odoo.all("kf.legacy.purchase.document.line", [], COMPARE_FIELDS)
    groups = defaultdict(list)
    for row in rows:
        groups[row["source_key"]].append(row)
    duplicates = {key: values for key, values in groups.items() if len(values) > 1}

    names = [f"ev_legacy_purchase_line_{safe_token(key)}" for key in duplicates]
    bindings = odoo.all(
        "ir.model.data",
        [("module", "=", "__import__"), ("name", "in", names)],
        ["name", "model", "res_id"],
    )
    binding_by_name = {row["name"]: row for row in bindings}
    delete_ids = []
    failures = []
    for key, values in sorted(duplicates.items()):
        name = f"ev_legacy_purchase_line_{safe_token(key)}"
        binding = binding_by_name.get(name)
        ids = {row["id"] for row in values}
        if len(values) != 2:
            failures.append(f"{key}: erwartet 2 Zeilen, gefunden {len(values)}")
            continue
        if not binding or binding["model"] != "kf.legacy.purchase.document.line":
            failures.append(f"{key}: gültiges External-ID-Binding fehlt")
            continue
        if binding["res_id"] not in ids:
            failures.append(f"{key}: Binding zeigt nicht auf die Dublettengruppe")
            continue
        left, right = values
        if any(normalized(left[field]) != normalized(right[field]) for field in COMPARE_FIELDS):
            failures.append(f"{key}: fachliche Felder sind nicht identisch")
            continue
        delete_ids.extend(row["id"] for row in values if row["id"] != binding["res_id"])

    print({
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "total_lines": len(rows),
        "duplicate_source_keys": len(duplicates),
        "proven_unbound_duplicates": len(delete_ids),
        "failures": len(failures),
        "failure_samples": failures[:20],
    })
    if failures:
        raise SystemExit("Abbruch: Dublettenbeweis ist nicht vollständig")
    if len(duplicates) != 500 or len(delete_ids) != 500:
        raise SystemExit("Abbruch: erwartete exakt 500 nachgewiesene Dubletten")
    if not args.apply:
        print("DRY_RUN_OK_NO_WRITES")
        return

    side_models = (
        "purchase.order", "purchase.requisition", "stock.picking", "stock.move",
        "account.move", "account.move.line",
    )
    before = {model: odoo.count(model) for model in side_models}
    for offset in range(0, len(delete_ids), 100):
        part = delete_ids[offset:offset + 100]
        odoo.call(
            "kf.legacy.purchase.document.line", "unlink", [part],
            {"context": {"tracking_disable": True, "mail_notrack": True}},
        )
    after = {model: odoo.count(model) for model in side_models}
    if before != after:
        raise SystemExit(f"SIDE_EFFECT_DETECTED before={before} after={after}")
    final_lines = odoo.count("kf.legacy.purchase.document.line")
    if final_lines != 41963:
        raise SystemExit(f"Unerwartete Abschlussmenge: {final_lines}")
    print({"cleanup": "OK", "removed": len(delete_ids), "final_lines": final_lines,
           "side_effects": 0, "backup": args.backup})


if __name__ == "__main__":
    main()
