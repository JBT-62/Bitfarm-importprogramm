#!/usr/bin/env python3
"""Read-only integrity audit for imported eEvolution CRM chatter history."""
from __future__ import annotations

import json
import os
import argparse
import migration_runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=int)
    args = parser.parse_args()
    info = migration_runtime.require_target(os.environ["ODOO_DB"])
    db, key = os.environ["ODOO_DB"], os.environ["ODOO_API_KEY"]
    common = migration_runtime.server_proxy(info.url.rstrip("/") + "/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, info.user, key, {})
    if not uid:
        raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
    models = migration_runtime.server_proxy(info.url.rstrip("/") + "/xmlrpc/2/object", allow_none=True)
    call = lambda model, method, args=None, kwargs=None: models.execute_kw(
        db, uid, key, model, method, args or [], kwargs or {}
    )

    imported_ids, offset = [], 0
    while True:
        rows = call("ir.model.data", "search_read", [[
            ("module", "=", "__import__"), ("model", "=", "mail.message"),
            ("name", "like", "ev_crm_history_%")
        ]], {"fields": ["res_id"], "limit": 5000, "offset": offset})
        imported_ids.extend(int(row["res_id"]) for row in rows)
        if len(rows) < 5000:
            break
        offset += len(rows)

    checks = {"found": 0, "wrong_model": 0, "wrong_type": 0, "missing_marker": 0, "missing_date": 0,
              "with_odoo_author": 0}
    for start in range(0, len(imported_ids), 2000):
        ids = imported_ids[start:start + 2000]
        base = [("id", "in", ids)]
        checks["found"] += call("mail.message", "search_count", [base])
        checks["wrong_model"] += call("mail.message", "search_count", [[*base, ("model", "not in", ["crm.lead", "res.partner"])]] )
        checks["wrong_type"] += call("mail.message", "search_count", [[*base, ("message_type", "!=", "comment")]])
        checks["missing_marker"] += call("mail.message", "search_count", [[*base, ("body", "not ilike", "Abgeschlossene Historie aus eEvolution")]])
        checks["missing_date"] += call("mail.message", "search_count", [[*base, ("date", "=", False)]])
        checks["with_odoo_author"] += call("mail.message", "search_count", [[*base, ("author_id", "!=", False)]])

    activity_anchors = call("ir.model.data", "search_count", [[
        ("module", "=", "__import__"), ("model", "=", "mail.activity"),
        ("name", "like", "ev_crm_history_%")
    ]])
    sample = call("mail.message", "read", [imported_ids[:5]], {
        "fields": ["model", "res_id", "date", "subject", "message_type", "author_id"]
    }) if imported_ids else []
    result = {
        "external_ids": len(imported_ids), "checks": checks,
        "activity_anchors": activity_anchors,
        "sample": sample,
    }
    print("CRM_HISTORY_AUDIT " + json.dumps(result, ensure_ascii=False, default=str))
    expected = args.expected if args.expected is not None else len(imported_ids)
    structural_errors = any(checks[name] for name in ("wrong_model", "wrong_type", "missing_marker", "missing_date"))
    if len(imported_ids) != expected or checks["found"] != expected or structural_errors or activity_anchors != 0:
        raise SystemExit("CRM_HISTORY_AUDIT_FAILED")
    print("CRM_HISTORY_AUDIT_OK")


if __name__ == "__main__":
    main()
