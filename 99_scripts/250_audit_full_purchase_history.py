#!/usr/bin/env python3
"""Read-only acceptance audit for the full eEvolution purchase history."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path

import migration_runtime


ROOT = Path(__file__).resolve().parents[1]


def safe_token(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


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
        rows = []
        offset = 0
        while True:
            part = self.call(
                model,
                "search_read",
                [domain],
                {"fields": fields, "limit": size, "offset": offset, "order": "id"},
            )
            rows.extend(part)
            if len(part) < size:
                return rows
            offset += len(part)

    def count(self, model, domain=None):
        return int(self.call(model, "search_count", [domain or []]))


def expected_name(prefix, source_key):
    return f"{prefix}{safe_token(source_key)}"


def main():
    if migration_runtime.migration_mode() == "apply":
        raise RuntimeError("Dieser Audit ist ausschließlich read-only")
    if os.environ.get("ODOO_DB") != "kuf-erp-all-data":
        raise RuntimeError("Audit ist für kuf-erp-all-data freigegeben")

    odoo = Odoo()
    documents = odoo.all(
        "kf.legacy.purchase.document", [], ["source_group_key", "line_ids", "review_status"]
    )
    lines = odoo.all(
        "kf.legacy.purchase.document.line", [], ["source_key", "document_id"]
    )
    bindings = odoo.all(
        "ir.model.data",
        [
            ("module", "=", "__import__"),
            ("model", "in", [
                "kf.legacy.purchase.document", "kf.legacy.purchase.document.line"
            ]),
        ],
        ["name", "model", "res_id"],
    )
    binding_by_name = {row["name"]: row for row in bindings}

    missing = []
    mismatched = []
    expected = set()
    for row in documents:
        name = expected_name("ev_legacy_purchase_doc_", row["source_group_key"])
        expected.add(name)
        binding = binding_by_name.get(name)
        if not binding:
            missing.append({"model": "document", "source": row["source_group_key"], "id": row["id"]})
        elif binding["model"] != "kf.legacy.purchase.document" or binding["res_id"] != row["id"]:
            mismatched.append({"name": name, "expected_id": row["id"], "actual": binding})
    for row in lines:
        name = expected_name("ev_legacy_purchase_line_", row["source_key"])
        expected.add(name)
        binding = binding_by_name.get(name)
        if not binding:
            missing.append({"model": "line", "source": row["source_key"], "id": row["id"]})
        elif binding["model"] != "kf.legacy.purchase.document.line" or binding["res_id"] != row["id"]:
            mismatched.append({"name": name, "expected_id": row["id"], "actual": binding})

    source_keys = Counter(row["source_key"] for row in lines)
    group_keys = Counter(row["source_group_key"] for row in documents)
    orphan_lines = sum(1 for row in lines if not row.get("document_id"))
    extras = sorted(set(binding_by_name) - expected)
    side_effects = {
        "purchase_orders": odoo.count("purchase.order"),
        "purchase_requisitions": odoo.count("purchase.requisition"),
        "stock_pickings": odoo.count("stock.picking"),
        "stock_moves": odoo.count("stock.move"),
        "account_moves": odoo.count("account.move"),
        "account_move_lines": odoo.count("account.move.line"),
    }
    result = {
        "database": odoo.db,
        "captured_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "documents": len(documents),
        "lines": len(lines),
        "review_documents": sum(row["review_status"] == "review" for row in documents),
        "bindings": len(bindings),
        "missing_bindings": len(missing),
        "mismatched_bindings": len(mismatched),
        "extra_bindings": len(extras),
        "duplicate_document_source_keys": sum(value > 1 for value in group_keys.values()),
        "duplicate_line_source_keys": sum(value > 1 for value in source_keys.values()),
        "orphan_lines": orphan_lines,
        "side_effects": side_effects,
        "samples": {
            "missing_bindings": missing[:20],
            "mismatched_bindings": mismatched[:20],
            "extra_bindings": extras[:20],
        },
    }
    result["pass"] = (
        result["documents"] == 22010
        and result["lines"] == 41963
        and not missing
        and not mismatched
        and not extras
        and result["duplicate_document_source_keys"] == 0
        and result["duplicate_line_source_keys"] == 0
        and orphan_lines == 0
        and all(value == 0 for value in side_effects.values())
    )
    output = ROOT / "05_doku" / "PROBEIMPORT_EINKAUF_VOLLBESTAND_AUDIT_20260916.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["pass"]:
        raise SystemExit("PURCHASE_HISTORY_AUDIT_FAILED")
    print("PURCHASE_HISTORY_AUDIT_OK_NO_WRITES")


if __name__ == "__main__":
    main()
