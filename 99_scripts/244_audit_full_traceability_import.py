#!/usr/bin/env python3
"""Read-only completeness audit for the full legacy traceability import."""
from __future__ import annotations

import json
import os
from datetime import datetime

import pyodbc

import migration_runtime


START = datetime(2017, 1, 1)
END = datetime(2027, 1, 1)


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
        url, db, user, key = [
            os.environ[name] for name in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_API_KEY")
        ]
        common = migration_runtime.server_proxy(url + "/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(db, user, key, {})
        if not self.uid:
            raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
        self.db, self.key = db, key
        self.models = migration_runtime.server_proxy(url + "/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args=None, kwargs=None):
        return self.models.execute_kw(
            self.db, self.uid, self.key, model, method, args or [], kwargs or {}
        )

    def count(self, model, domain=None):
        return int(self.call(model, "search_count", [domain or []]))


def scalar(cur, sql, *params):
    cur.execute(sql, *params)
    return int(cur.fetchone()[0] or 0)


def main():
    if migration_runtime.migration_mode() == "apply":
        raise RuntimeError("Dieser Audit ist ausschliesslich read-only")

    conn = source_connection()
    cur = conn.cursor()
    cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
    odoo = Odoo()

    source_union = """
        SELECT LFDARTNR, 'serial' TRACE_TYPE, SNR TRACE_NUMBER, REFTYP
          FROM dbo.SNRARCHIV
         WHERE BUCHDATUM>=? AND BUCHDATUM<? AND NULLIF(LTRIM(RTRIM(SNR)),'') IS NOT NULL
        UNION ALL
        SELECT LFDARTNR, 'lot', CHARGENNR, REFTYP
          FROM dbo.CHARGENARCHIV
         WHERE BUCHDATUM>=? AND BUCHDATUM<? AND NULLIF(LTRIM(RTRIM(CHARGENNR)),'') IS NOT NULL
    """
    cur.execute(
        f"SELECT LFDARTNR,COUNT_BIG(*) FROM ({source_union}) x GROUP BY LFDARTNR",
        START, END, START, END,
    )
    events_by_product = {int(row[0]): int(row[1]) for row in cur.fetchall()}

    product_links = odoo.call(
        "ir.model.data", "search_read",
        [[("module", "=", "__import__"), ("name", "like", "ev_product_%"),
          ("model", "=", "product.template")]],
        {"fields": ["name", "res_id"], "limit": 100000},
    )
    key_by_template = {
        int(row["name"].removeprefix("ev_product_")): int(row["res_id"])
        for row in product_links
        if row["name"].removeprefix("ev_product_").isdigit()
    }
    template_has_variant = set()
    template_ids = sorted(set(key_by_template.values()))
    for offset in range(0, len(template_ids), 500):
        rows = odoo.call(
            "product.template", "read", [template_ids[offset:offset + 500]],
            {"fields": ["product_variant_ids"], "context": {"active_test": False}},
        )
        template_has_variant.update(int(row["id"]) for row in rows if row["product_variant_ids"])
    linked_keys = {
        key for key, template_id in key_by_template.items() if template_id in template_has_variant
    }
    unresolved = sorted(set(events_by_product) - linked_keys)
    article_state = {}
    for offset in range(0, len(unresolved), 1800):
        part = unresolved[offset:offset + 1800]
        marks = ",".join("?" for _ in part)
        cur.execute(
            f"SELECT LFDNR,ISNULL(LOESCHKNZ,0),ISNULL(INAKTIV,0) FROM dbo.ARTIKEL WHERE LFDNR IN ({marks})",
            *part,
        )
        article_state.update({int(r[0]): (int(r[1]), int(r[2])) for r in cur.fetchall()})

    missing_source = [key for key in unresolved if key not in article_state]
    deleted = [key for key in unresolved if key in article_state and article_state[key][0] != 0]
    inactive = [
        key for key in unresolved
        if key in article_state and article_state[key][0] == 0 and article_state[key][1] != 0
    ]
    otherwise = [
        key for key in unresolved
        if key in article_state and article_state[key][0] == 0 and article_state[key][1] == 0
    ]

    unknown_type_rows = scalar(
        cur,
        f"SELECT COUNT_BIG(*) FROM ({source_union}) x WHERE NOT EXISTS (SELECT 1 FROM dbo.SNREFTYP t WHERE t.LFDNR=x.REFTYP AND t.SPRKZ IN (0,1))",
        START, END, START, END,
    )
    total_source_events = sum(events_by_product.values())

    source = {
        "range": "2017-01-01 inklusive bis 2027-01-01 exklusiv",
        "products_with_events": len(events_by_product),
        "events_total": total_source_events,
        "serial_events": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.SNRARCHIV WHERE BUCHDATUM>=? AND BUCHDATUM<? AND NULLIF(LTRIM(RTRIM(SNR)),'') IS NOT NULL", START, END),
        "lot_events": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.CHARGENARCHIV WHERE BUCHDATUM>=? AND BUCHDATUM<? AND NULLIF(LTRIM(RTRIM(CHARGENNR)),'') IS NOT NULL", START, END),
        "trace_headers": scalar(cur, f"SELECT COUNT_BIG(*) FROM (SELECT DISTINCT LFDARTNR,TRACE_TYPE,TRACE_NUMBER FROM ({source_union}) x) d", START, END, START, END),
        "events_before_cutoff_excluded": scalar(cur, "SELECT (SELECT COUNT_BIG(*) FROM dbo.SNRARCHIV WHERE BUCHDATUM<? AND NULLIF(LTRIM(RTRIM(SNR)),'') IS NOT NULL)+(SELECT COUNT_BIG(*) FROM dbo.CHARGENARCHIV WHERE BUCHDATUM<? AND NULLIF(LTRIM(RTRIM(CHARGENNR)),'') IS NOT NULL)", START, START),
        "events_without_known_type_label": unknown_type_rows,
        "unresolved_product_keys": len(unresolved),
        "unresolved_product_events": sum(events_by_product[k] for k in unresolved),
        "unresolved_reasons": {
            "article_row_missing": {"products": len(missing_source), "events": sum(events_by_product[k] for k in missing_source)},
            "deleted_flag": {"products": len(deleted), "events": sum(events_by_product[k] for k in deleted)},
            "inactive_without_target_link": {"products": len(inactive), "events": sum(events_by_product[k] for k in inactive)},
            "otherwise_importable_without_target_link": {"products": len(otherwise), "events": sum(events_by_product[k] for k in otherwise)},
        },
        "unresolved_product_key_sample": unresolved[:30],
    }

    output_anchor_rows = odoo.call(
        "kf.legacy.production.output", "search_read",
        [[("trace_id", "!=", False), ("trace_id.event_ids", "=", False)]],
        {"fields": ["trace_id"], "limit": 10000},
    )
    output_anchor_heads = {
        row["trace_id"][0] for row in output_anchor_rows if row.get("trace_id")
    }

    target = {
        "trace_headers": odoo.count("kf.legacy.trace"),
        "trace_headers_serial": odoo.count("kf.legacy.trace", [("trace_type", "=", "serial")]),
        "trace_headers_lot": odoo.count("kf.legacy.trace", [("trace_type", "=", "lot")]),
        "trace_headers_without_odoo_product": odoo.count("kf.legacy.trace", [("product_id", "=", False)]),
        "trace_headers_review": odoo.count("kf.legacy.trace", [("quality_status", "=", "review")]),
        "trace_headers_retained_as_current_output_anchor": len(output_anchor_heads),
        "trace_events": odoo.count("kf.legacy.trace.event"),
        "trace_events_without_partner": odoo.count("kf.legacy.trace.event", [("eevo_partner_key", "!=", 0), ("partner_id", "=", False)]),
        "production_orders": odoo.count("kf.legacy.production"),
        "production_components": odoo.count("kf.legacy.production.component"),
        "production_outputs": odoo.count("kf.legacy.production.output"),
        "production_outputs_without_trace": odoo.count("kf.legacy.production.output", [("trace_id", "=", False)]),
        "trace_usages": odoo.count("kf.legacy.trace.usage"),
        "trace_usages_booking_batch": odoo.count("kf.legacy.trace.usage", [("allocation_basis", "=", "booking_batch")]),
        "trace_usages_production_order_candidate": odoo.count("kf.legacy.trace.usage", [("allocation_basis", "=", "production_order")]),
        "direct_deliveries": odoo.count("kf.legacy.trace.delivery"),
        "direct_deliveries_without_customer": odoo.count("kf.legacy.trace.delivery", [("partner_id", "=", False)]),
        "stock_pickings": odoo.count("stock.picking"),
        "stock_moves": odoo.count("stock.move"),
        "stock_move_lines": odoo.count("stock.move.line"),
        "account_moves": odoo.count("account.move"),
        "account_move_lines": odoo.count("account.move.line"),
        "mail_queue": odoo.count("mail.mail"),
    }
    result = {
        "database": os.environ["ODOO_DB"],
        "audit_timestamp": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "target": target,
        "reconciliation": {
            "events_match": source["events_total"] == target["trace_events"],
            "trace_headers_match": (
                source["trace_headers"] + target["trace_headers_retained_as_current_output_anchor"]
                == target["trace_headers"]
            ),
            "side_effect_models_unchanged_expected_zero": all(
                target[key] == 0 for key in (
                    "stock_pickings", "stock_moves", "stock_move_lines",
                    "account_moves", "account_move_lines",
                )
            ),
        },
    }
    result["pass"] = all(result["reconciliation"].values())
    conn.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["pass"]:
        raise SystemExit("FULL_TRACEABILITY_AUDIT_FAILED")
    print("FULL_TRACEABILITY_AUDIT_OK_NO_WRITES")


if __name__ == "__main__":
    main()
