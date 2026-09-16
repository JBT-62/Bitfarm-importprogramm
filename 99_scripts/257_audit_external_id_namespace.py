#!/usr/bin/env python3
"""Audit the controlled External-ID transition from __import__ to eevolution.

This tool is deliberately read-only.  It inventories both namespaces, detects
name/model/record collisions and verifies that referenced Odoo records still
exist.  It never creates, updates, deletes or rebinds an ``ir.model.data`` row.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
import os
from pathlib import Path

import migration_runtime


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MODULE = "__import__"
TARGET_MODULE = "eevolution"


class Odoo:
    def __init__(self):
        database = os.environ.get("ODOO_DB", "")
        if database != "kuf-erp-all-data":
            raise RuntimeError("Audit ist ausschließlich für kuf-erp-all-data freigegeben")
        target = migration_runtime.require_target(database)
        self.db = database
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

    def read_all_bindings(self):
        domain = [("module", "in", [SOURCE_MODULE, TARGET_MODULE])]
        fields = ["module", "name", "model", "res_id", "noupdate"]
        result = []
        offset = 0
        while True:
            rows = self.call(
                "ir.model.data",
                "search_read",
                [domain],
                {"fields": fields, "offset": offset, "limit": 5000, "order": "id"},
            )
            result.extend(rows)
            if len(rows) < 5000:
                return result
            offset += len(rows)

    def existing_ids(self, model, ids):
        existing = set()
        ordered = sorted(set(int(value) for value in ids if value))
        for offset in range(0, len(ordered), 1000):
            part = ordered[offset : offset + 1000]
            try:
                rows = self.call(
                    model, "search_read", [[("id", "in", part)]],
                    {"fields": ["id"], "limit": len(part), "context": {"active_test": False}},
                )
            except Exception as exc:  # Preserve the audit finding instead of guessing.
                return None, f"{type(exc).__name__}: {exc}"
            existing.update(int(row["id"]) for row in rows)
        return existing, None


def prefix(name):
    if not name.startswith("ev_"):
        return "NON_EV"
    tail = name[3:]
    return "ev_" + (tail.split("_", 1)[0] if "_" in tail else tail)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if migration_runtime.migration_mode() == "apply":
        raise RuntimeError("Dieser Audit ist ausschließlich read-only")

    odoo = Odoo()
    bindings = odoo.read_all_bindings()
    by_module = Counter(row["module"] for row in bindings)
    by_model = Counter((row["module"], row["model"]) for row in bindings)
    by_prefix = Counter((row["module"], prefix(row["name"])) for row in bindings)
    grouped = defaultdict(list)
    model_ids = defaultdict(list)
    for row in bindings:
        grouped[row["name"]].append(row)
        model_ids[row["model"]].append(row["res_id"])

    same_target = []
    conflicts = []
    source_only = []
    target_only = []
    for name, rows in sorted(grouped.items()):
        source = [row for row in rows if row["module"] == SOURCE_MODULE]
        target = [row for row in rows if row["module"] == TARGET_MODULE]
        if source and target:
            pairs = {(row["model"], int(row["res_id"])) for row in rows}
            item = {
                "name": name,
                "source": [{"id": r["id"], "model": r["model"], "res_id": r["res_id"]} for r in source],
                "target": [{"id": r["id"], "model": r["model"], "res_id": r["res_id"]} for r in target],
            }
            (same_target if len(pairs) == 1 else conflicts).append(item)
        elif source:
            source_only.extend(source)
        else:
            target_only.extend(target)

    orphaned = []
    unverifiable_models = []
    for model, ids in sorted(model_ids.items()):
        existing, error = odoo.existing_ids(model, ids)
        if error:
            unverifiable_models.append({"model": model, "error": error})
            continue
        for row in bindings:
            if row["model"] == model and int(row["res_id"]) not in existing:
                orphaned.append({
                    "module": row["module"], "name": row["name"],
                    "model": model, "res_id": row["res_id"], "imd_id": row["id"],
                })

    ev_source_only = [row for row in source_only if row["name"].startswith("ev_")]
    non_ev_source_only = [row for row in source_only if not row["name"].startswith("ev_")]
    blockers = len(conflicts) + len(orphaned) + len(unverifiable_models)
    result = {
        "database": odoo.db,
        "captured_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "read-only",
        "source_module": SOURCE_MODULE,
        "target_module": TARGET_MODULE,
        "summary": {
            "bindings_total": len(bindings),
            "source_bindings": by_module[SOURCE_MODULE],
            "target_bindings": by_module[TARGET_MODULE],
            "source_only_ev_candidates": len(ev_source_only),
            "source_only_non_ev_review": len(non_ev_source_only),
            "target_only": len(target_only),
            "dual_namespace_same_record": len(same_target),
            "dual_namespace_conflicts": len(conflicts),
            "orphaned_bindings": len(orphaned),
            "unverifiable_models": len(unverifiable_models),
            "blockers": blockers,
            "safe_to_prepare_apply_plan": blockers == 0,
        },
        "counts_by_model": [
            {"module": module, "model": model, "count": count}
            for (module, model), count in sorted(by_model.items())
        ],
        "counts_by_prefix": [
            {"module": module, "prefix": item_prefix, "count": count}
            for (module, item_prefix), count in sorted(by_prefix.items())
        ],
        "dual_namespace_same_record": same_target,
        "dual_namespace_conflicts": conflicts,
        "orphaned_bindings": orphaned,
        "unverifiable_models": unverifiable_models,
        "source_only_non_ev_review": [
            {"name": row["name"], "model": row["model"], "res_id": row["res_id"]}
            for row in non_ev_source_only
        ],
        "planned_next_step": (
            "Apply-Skript mit exakter Bestandsliste, Backup-Guard, Kollisionsstopp, "
            "Read-back und Wiederholungs-Dry-run erstellen"
            if blockers == 0 else
            "Blocker fachlich/technisch klären; keine Namespace-Migration ausführen"
        ),
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print(f"AUDIT_OUTPUT={output}")
    print("READ_ONLY_OK_NO_WRITES")


if __name__ == "__main__":
    main()
