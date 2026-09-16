#!/usr/bin/env python3
"""Read-only size comparison: full business history vs ten-year history.

Serial and lot archive tables are reported for context but deliberately remain on the
ten-year rule.  All queries use business dates and never write to the source or Odoo.
"""
from __future__ import annotations

from datetime import datetime
import json
import os

import pyodbc

import migration_runtime


START = datetime(2016, 9, 16)
END = datetime(2026, 9, 17)


def connection():
    return pyodbc.connect(
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
        f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "ApplicationIntent=ReadOnly;",
        readonly=True,
        timeout=30,
    )


def scalar(cur, sql, *params):
    cur.execute(sql, *params)
    return int(cur.fetchone()[0] or 0)


class Odoo:
    def __init__(self):
        info = migration_runtime.require_target(os.environ["ODOO_DB"])
        self.db = os.environ["ODOO_DB"]
        self.key = os.environ["ODOO_API_KEY"]
        common = migration_runtime.server_proxy(info.url.rstrip("/") + "/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, info.user, self.key, {})
        if not self.uid:
            raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
        self.models = migration_runtime.server_proxy(info.url.rstrip("/") + "/xmlrpc/2/object", allow_none=True)

    def count(self, model, domain=None):
        return int(self.models.execute_kw(self.db, self.uid, self.key, model, "search_count", [domain or []], {}))

    def anchor_count(self, model, prefix):
        return self.count("ir.model.data", [
            ("module", "=", "__import__"), ("model", "=", model), ("name", "like", prefix + "%")
        ])


def dated_counts(cur, table, date_expr, where="1=1"):
    return {
        "all_dated": scalar(cur, f"SELECT COUNT_BIG(*) FROM {table} WHERE {where} AND {date_expr} IS NOT NULL"),
        "in_10y": scalar(cur, f"SELECT COUNT_BIG(*) FROM {table} WHERE {where} AND {date_expr}>=? AND {date_expr}<?", START, END),
        "older_additional": scalar(cur, f"SELECT COUNT_BIG(*) FROM {table} WHERE {where} AND {date_expr}<?", START),
        "after_cutoff": scalar(cur, f"SELECT COUNT_BIG(*) FROM {table} WHERE {where} AND {date_expr}>=?", END),
        "without_date": scalar(cur, f"SELECT COUNT_BIG(*) FROM {table} WHERE {where} AND {date_expr} IS NULL"),
    }


def main():
    if migration_runtime.migration_mode() == "apply":
        raise RuntimeError("Dieser Audit ist ausschliesslich read-only")
    odoo = Odoo()
    with connection() as cn:
        cur = cn.cursor()
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")

        sales_where = "AAGAUFART<>8 AND NOT (GUTSCHRIFT=1 AND AUFTRAG=0 AND ANGEBOT=0)"
        result = {
            "period": {"from": START.isoformat(), "to_exclusive": END.isoformat()},
            "crm_opportunities": dated_counts(cur, "dbo.VERKAUFSCHANCE", "ERSTELLDATUM"),
            "crm_history_events": dated_counts(cur, "dbo.TERMIN", "ANFTERMIN"),
            "sales_document_heads": dated_counts(cur, "dbo.ANGAUFGUT", "ERFASSDATUM", sales_where),
            "sales_document_lines": dated_counts(
                cur,
                "dbo.ANGAUFPOS p JOIN dbo.ANGAUFGUT h ON h.LFDNR=p.LFDANGAUFGUTNR",
                "h.ERFASSDATUM",
                "h.AAGAUFART<>8 AND NOT (h.GUTSCHRIFT=1 AND h.AUFTRAG=0 AND h.ANGEBOT=0)",
            ),
            "delivery_heads_non_cancelled": dated_counts(cur, "dbo.AAGLS", "LSDATUM", "ISNULL(STORNO,0)=0"),
            "delivery_lines_non_cancelled": dated_counts(
                cur,
                "dbo.AAGLSPOS p JOIN dbo.AAGLS h ON h.LSNR=p.LSNR",
                "h.LSDATUM",
                "ISNULL(h.STORNO,0)=0 AND ISNULL(p.STORNO,0)=0",
            ),
            "purchase_lines": dated_counts(cur, "dbo.BESTELLUNG", "COALESCE(BIDAT,BVDAT)"),
            "outgoing_invoice_heads_non_cancelled": dated_counts(cur, "dbo.AAGFAKT", "FAKTDATUM", "ISNULL(STORNO,0)=0"),
            "outgoing_invoice_lines_non_cancelled": dated_counts(
                cur,
                "dbo.AAGFAKTPOS p JOIN dbo.AAGFAKT h ON h.LFDFAKTNR=p.LFDFAKTNR",
                "h.FAKTDATUM",
                "ISNULL(h.STORNO,0)=0",
            ),
            "incoming_invoice_heads_non_cancelled": dated_counts(cur, "dbo.RECHEINGANG", "RECHDATUM", "ISNULL(STORNO,0)=0"),
            "incoming_invoice_lines_non_cancelled": dated_counts(
                cur,
                "dbo.RECHEINPOS p JOIN dbo.RECHEINGANG h ON h.LFDNR=p.LFDNR",
                "h.RECHDATUM",
                "ISNULL(h.STORNO,0)=0",
            ),
            "production_order_heads": dated_counts(
                cur, "dbo.PRODUKTION", "COALESCE(PPDAT,PVDAT,PDDAT,ENDDAT,TMSTMP)"
            ),
            "production_component_bookings": dated_counts(
                cur, "dbo.PRODAUFINHIST", "BELEGDAT"
            ),
            "serial_events_keep_10y": dated_counts(cur, "dbo.SNRARCHIV", "BUCHDATUM"),
            "lot_events_keep_10y": dated_counts(cur, "dbo.CHARGENARCHIV", "BUCHDATUM"),
        }

        purchase_docs_sql = """
            SELECT COUNT_BIG(*) FROM (
                SELECT CASE WHEN ISNULL(RAHMEN,0)=0 THEN 'purchase' ELSE 'framework' END kind,
                       CASE WHEN ISNULL(RAHMEN,0)=0
                            THEN COALESCE(NULLIF(SAMMELBESTNR,0),BESTNR)
                            ELSE COALESCE(NULLIF(LFDBESTRAHMEN,0),NULLIF(SAMMELBESTNR,0),BESTNR)
                       END document_key
                  FROM dbo.BESTELLUNG
                 WHERE COALESCE(BIDAT,BVDAT) {predicate}
                 GROUP BY CASE WHEN ISNULL(RAHMEN,0)=0 THEN 'purchase' ELSE 'framework' END,
                          CASE WHEN ISNULL(RAHMEN,0)=0
                               THEN COALESCE(NULLIF(SAMMELBESTNR,0),BESTNR)
                               ELSE COALESCE(NULLIF(LFDBESTRAHMEN,0),NULLIF(SAMMELBESTNR,0),BESTNR)
                          END
            ) x
        """
        result["purchase_document_heads"] = {
            "all_dated": scalar(cur, purchase_docs_sql.format(predicate="IS NOT NULL")),
            "in_10y": scalar(cur, purchase_docs_sql.format(predicate=">=? AND COALESCE(BIDAT,BVDAT)<?"), START, END),
            "older_additional": scalar(cur, purchase_docs_sql.format(predicate="<?"), START),
            "after_cutoff": scalar(cur, purchase_docs_sql.format(predicate=">=?"), END),
            "without_date": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.BESTELLUNG WHERE COALESCE(BIDAT,BVDAT) IS NULL"),
        }

        result["cancelled_context"] = {
            "delivery_heads_cancelled_all": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.AAGLS WHERE ISNULL(STORNO,0)<>0"),
            "delivery_lines_cancelled_all": scalar(cur, """
                SELECT COUNT_BIG(*) FROM dbo.AAGLSPOS p
                JOIN dbo.AAGLS h ON h.LSNR=p.LSNR
                WHERE ISNULL(h.STORNO,0)<>0 OR ISNULL(p.STORNO,0)<>0
            """),
            "outgoing_invoice_heads_cancelled_all": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.AAGFAKT WHERE ISNULL(STORNO,0)<>0"),
            "outgoing_invoice_lines_cancelled_all": scalar(cur, """
                SELECT COUNT_BIG(*) FROM dbo.AAGFAKTPOS p
                JOIN dbo.AAGFAKT h ON h.LFDFAKTNR=p.LFDFAKTNR
                WHERE ISNULL(h.STORNO,0)<>0
            """),
            "incoming_invoice_heads_cancelled_all": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.RECHEINGANG WHERE ISNULL(STORNO,0)<>0"),
            "incoming_invoice_lines_cancelled_all": scalar(cur, """
                SELECT COUNT_BIG(*) FROM dbo.RECHEINPOS p
                JOIN dbo.RECHEINGANG h ON h.LFDNR=p.LFDNR
                WHERE ISNULL(h.STORNO,0)<>0
            """),
        }

    additional_heads = sum(
        result[key]["older_additional"]
        for key in (
            "crm_opportunities", "sales_document_heads", "delivery_heads_non_cancelled",
            "purchase_document_heads", "outgoing_invoice_heads_non_cancelled",
            "incoming_invoice_heads_non_cancelled", "production_order_heads",
        )
    )
    additional_detail_rows = sum(
        result[key]["older_additional"]
        for key in (
            "crm_history_events", "sales_document_lines", "delivery_lines_non_cancelled",
            "purchase_lines", "outgoing_invoice_lines_non_cancelled",
            "incoming_invoice_lines_non_cancelled", "production_component_bookings",
        )
    )
    result["summary"] = {
        "additional_business_document_heads_excluding_serial_lot": additional_heads,
        "additional_detail_and_history_rows_excluding_serial_lot": additional_detail_rows,
        "additional_total_records_before_relational_helpers": additional_heads + additional_detail_rows,
        "serial_lot_older_events_still_excluded": (
            result["serial_events_keep_10y"]["older_additional"]
            + result["lot_events_keep_10y"]["older_additional"]
        ),
    }
    current = {
        "crm_opportunity_heads": odoo.anchor_count("crm.lead", "ev_vkchance_"),
        "crm_history_events": odoo.anchor_count("mail.message", "ev_crm_history_"),
        "sales_document_heads": odoo.count("sale.order", [("kf_legacy_history", "=", True)])
            + odoo.count("kf.legacy.sales.document"),
        "sales_document_lines": odoo.count("sale.order.line", [("order_id.kf_legacy_history", "=", True)])
            + odoo.count("kf.legacy.sales.document.line"),
        "delivery_document_heads": 0,
        "delivery_document_lines": 0,
        "purchase_document_heads": odoo.count("kf.legacy.purchase.document"),
        "purchase_document_lines": odoo.count("kf.legacy.purchase.document.line"),
        "outgoing_invoice_heads": 0,
        "outgoing_invoice_lines": 0,
        "incoming_invoice_heads": 0,
        "incoming_invoice_lines": 0,
        "production_order_heads": odoo.count("kf.legacy.production"),
        "production_component_bookings": odoo.count("kf.legacy.production.component"),
    }
    desired = {
        "crm_opportunity_heads": result["crm_opportunities"]["all_dated"],
        "crm_history_events": result["crm_history_events"]["all_dated"],
        "sales_document_heads": result["sales_document_heads"]["all_dated"],
        "sales_document_lines": result["sales_document_lines"]["all_dated"],
        "delivery_document_heads": result["delivery_heads_non_cancelled"]["all_dated"],
        "delivery_document_lines": result["delivery_lines_non_cancelled"]["all_dated"],
        "purchase_document_heads": result["purchase_document_heads"]["all_dated"],
        "purchase_document_lines": result["purchase_lines"]["all_dated"],
        "outgoing_invoice_heads": result["outgoing_invoice_heads_non_cancelled"]["all_dated"],
        "outgoing_invoice_lines": result["outgoing_invoice_lines_non_cancelled"]["all_dated"],
        "incoming_invoice_heads": result["incoming_invoice_heads_non_cancelled"]["all_dated"],
        "incoming_invoice_lines": result["incoming_invoice_lines_non_cancelled"]["all_dated"],
        "production_order_heads": result["production_order_heads"]["all_dated"],
        "production_component_bookings": result["production_component_bookings"]["all_dated"],
    }
    delta = {key: max(desired[key] - current[key], 0) for key in desired}
    result["current_target_comparable"] = current
    result["full_history_target_comparable"] = desired
    result["additional_from_current_target"] = {
        **delta,
        "total": sum(delta.values()),
        "total_without_production_component_bookings": sum(delta.values()) - delta["production_component_bookings"],
    }
    cancelled_total = sum(result["cancelled_context"].values())
    result["additional_from_current_target"]["cancelled_heads_and_lines_optional"] = cancelled_total
    result["additional_from_current_target"]["total_including_cancelled"] = sum(delta.values()) + cancelled_total
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print("FULL_HISTORY_SCOPE_DELTA_AUDIT_OK_NO_WRITES")


if __name__ == "__main__":
    main()
