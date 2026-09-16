#!/usr/bin/env python3
"""Prune technical Legacy details outside the approved fixed ten-year window."""
from __future__ import annotations

import argparse
import os

import migration_runtime


START = "2017-01-01 00:00:00"
END = "2027-01-01 00:00:00"


class Odoo:
    def __init__(self):
        target = migration_runtime.require_target(os.environ["ODOO_DB"])
        self.db, self.key = os.environ["ODOO_DB"], os.environ["ODOO_API_KEY"]
        common = migration_runtime.server_proxy(target.url.rstrip("/") + "/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, target.user, self.key, {})
        self.models = migration_runtime.server_proxy(target.url.rstrip("/") + "/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args=None, kw=None):
        return self.models.execute_kw(self.db, self.uid, self.key, model, method, args or [], kw or {})

    def search(self, model, domain):
        return self.call(model, "search", [domain], {"order": "id"})

    def count(self, model, domain):
        return int(self.call(model, "search_count", [domain]))

    def unlink(self, model, ids):
        removed = 0
        for offset in range(0, len(ids), 500):
            part = ids[offset:offset + 500]
            self.call(model, "unlink", [part])
            removed += len(part)
            print(f"{model}: removed {removed}/{len(ids)}", flush=True)

    def write_batches(self, model, ids, values):
        for offset in range(0, len(ids), 1000):
            self.call(model, "write", [ids[offset:offset + 1000], values])


def outside(field):
    return ["|", (field, "<", START), (field, ">=", END)]


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
    odoo = Odoo()
    old_events = odoo.search("kf.legacy.trace.event", outside("event_date"))
    old_components = odoo.search("kf.legacy.production.component", outside("booking_date"))
    old_outputs = odoo.search("kf.legacy.production.output", outside("storage_date"))
    old_usages = odoo.search("kf.legacy.trace.usage", outside("consumption_date"))
    old_deliveries = odoo.search("kf.legacy.trace.delivery", outside("delivery_date"))
    all_heads = set(odoo.search("kf.legacy.trace", []))
    kept_heads = set(odoo.search("kf.legacy.trace", [
        ("event_ids.event_date", ">=", START), ("event_ids.event_date", "<", END)
    ]))
    candidate_removed_heads = sorted(all_heads - kept_heads)
    retained_outputs = odoo.call(
        "kf.legacy.production.output", "search_read",
        [[("trace_id", "in", candidate_removed_heads), ("id", "not in", old_outputs)]],
        {"fields": ["trace_id"], "limit": 10000},
    ) if candidate_removed_heads else []
    output_anchor_heads = {row["trace_id"][0] for row in retained_outputs if row.get("trace_id")}
    removed_heads = sorted(set(candidate_removed_heads) - output_anchor_heads)
    retained_output_blockers = 0
    summary = {
        "window": {"from": START, "to_exclusive": END},
        "events_to_remove": len(old_events), "components_to_remove": len(old_components),
        "outputs_to_remove": len(old_outputs), "usages_to_remove_explicit": len(old_usages),
        "direct_deliveries_to_remove": len(old_deliveries), "trace_heads_to_remove": len(removed_heads),
        "trace_heads_retained_as_current_output_anchor": len(output_anchor_heads),
        "retained_output_blockers": retained_output_blockers,
    }
    print(summary, flush=True)
    if retained_output_blockers:
        raise SystemExit("Abbruch: aktuelle Produktionsausgaben referenzieren zu löschende Trace-Köpfe")
    if not args.apply:
        print("DRY_RUN_OK_NO_WRITES")
        return
    # Usages reference components/outputs; remove them first.  Remaining usages
    # linked to an old component/output are cascaded by the following unlinks.
    odoo.unlink("kf.legacy.trace.usage", old_usages)
    odoo.unlink("kf.legacy.trace.delivery", old_deliveries)
    odoo.unlink("kf.legacy.production.output", old_outputs)
    odoo.unlink("kf.legacy.production.component", old_components)
    odoo.unlink("kf.legacy.trace.event", old_events)
    odoo.unlink("kf.legacy.trace", removed_heads)
    empty_component_heads = odoo.search("kf.legacy.production", [("component_ids", "=", False)])
    empty_output_heads = odoo.search("kf.legacy.production", [("output_ids", "=", False)])
    empty_event_heads = odoo.search("kf.legacy.trace", [("event_ids", "=", False)])
    empty_usage_heads = odoo.search("kf.legacy.trace", [("usage_ids", "=", False)])
    odoo.write_batches("kf.legacy.production", empty_component_heads, {
        "component_posting_count": 0, "traced_component_posting_count": 0, "locked": True,
    })
    odoo.write_batches("kf.legacy.production", empty_output_heads, {"output_count": 0, "locked": True})
    odoo.write_batches("kf.legacy.trace", empty_event_heads, {
        "event_count": 0, "first_event_date": False, "last_event_date": False,
    })
    odoo.write_batches("kf.legacy.trace", empty_usage_heads, {"usage_count": 0})
    print({
        "empty_component_heads_reset": len(empty_component_heads),
        "empty_output_heads_reset": len(empty_output_heads),
        "empty_event_heads_reset": len(empty_event_heads),
        "empty_usage_heads_reset": len(empty_usage_heads),
    }, flush=True)
    print("APPLY_OK_FIXED_WINDOW", summary, flush=True)


if __name__ == "__main__":
    main()
