#!/usr/bin/env python3
"""Read-only cross-domain audit of the current eEvolution migration rehearsal.

The audit deliberately combines object counts, relational integrity, time scope and
operational side effects.  It never writes to eEvolution or Odoo.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
import re

import pyodbc

import migration_runtime


START = datetime(2016, 9, 16)
END = datetime(2026, 9, 17)


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
        info = migration_runtime.require_target(os.environ["ODOO_DB"])
        self.db = os.environ["ODOO_DB"]
        self.key = os.environ["ODOO_API_KEY"]
        common = migration_runtime.server_proxy(info.url.rstrip("/") + "/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, info.user, self.key, {})
        if not self.uid:
            raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
        self.models = migration_runtime.server_proxy(info.url.rstrip("/") + "/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args=None, kwargs=None):
        return self.models.execute_kw(self.db, self.uid, self.key, model, method, args or [], kwargs or {})

    def count(self, model, domain=None):
        return int(self.call(model, "search_count", [domain or []]))

    def external_names(self, model, prefix):
        rows = self.call(
            "ir.model.data", "search_read",
            [[("module", "=", "__import__"), ("model", "=", model), ("name", "like", prefix + "%")]],
            {"fields": ["name"], "limit": 100000},
        )
        return {row["name"] for row in rows}


def scalar(cur, sql, *params):
    cur.execute(sql, *params)
    return int(cur.fetchone()[0] or 0)


def crm_anchor(value):
    suffix = re.sub("[^0-9A-Fa-f]", "", str(value or ""))[:16]
    return f"ev_vkchance_{suffix}"


def main():
    if migration_runtime.migration_mode() == "apply":
        raise RuntimeError("Dieser Audit ist ausschliesslich read-only")

    odoo = Odoo()
    with source_connection() as cn:
        cur = cn.cursor()
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")

        cur.execute("""
            SELECT ID,ERSTELLDATUM,AENDERUNGSDATUM,BEZEICHNUNG
              FROM dbo.VERKAUFSCHANCE
             WHERE ERSTELLDATUM>=? AND ERSTELLDATUM<?
             ORDER BY ERSTELLDATUM,ID
        """, START, END)
        crm_rows = cur.fetchall()
        crm_names = odoo.external_names("crm.lead", "ev_vkchance_")
        missing_crm = [
            {"source_id": str(row[0]), "created": str(row[1]), "changed": str(row[2]), "name": str(row[3] or "")}
            for row in crm_rows if crm_anchor(row[0]) not in crm_names
        ]

        sales_filter = """
            AAGAUFART<>8
            AND NOT (GUTSCHRIFT=1 AND AUFTRAG=0 AND ANGEBOT=0)
        """
        cur.execute(f"""
            SELECT LFDNR,ERFASSDATUM,KENNZEICHEN,STATUS,ERLEDIGT
              FROM dbo.ANGAUFGUT
             WHERE {sales_filter} AND ERFASSDATUM>=? AND ERFASSDATUM<?
             ORDER BY ERFASSDATUM,LFDNR
        """, START, END)
        sales_rows = cur.fetchall()
        sales_names = odoo.external_names("sale.order", "ev_vorgang_")
        review_names = odoo.external_names("kf.legacy.sales.document", "ev_legacy_sales_review_")
        missing_sales = [
            {"source_id": int(row[0]), "created": str(row[1]), "identifier": str(row[2] or ""),
             "status": str(row[3] or ""), "finished": bool(row[4])}
            for row in sales_rows
            if f"ev_vorgang_{int(row[0])}" not in sales_names
            and f"ev_legacy_sales_review_{int(row[0])}" not in review_names
        ]

        source = {
            "products_not_deleted": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.ARTIKEL WHERE ISNULL(LOESCHKNZ,0)=0"),
            "products_inactive_not_deleted": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.ARTIKEL WHERE ISNULL(LOESCHKNZ,0)=0 AND ISNULL(INAKTIV,0)<>0"),
            "crm_in_window": len(crm_rows),
            "crm_before_window": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.VERKAUFSCHANCE WHERE ERSTELLDATUM<?", START),
            "sales_in_window": len(sales_rows),
            "sales_before_window": scalar(cur, f"SELECT COUNT_BIG(*) FROM dbo.ANGAUFGUT WHERE {sales_filter} AND ERFASSDATUM<?", START),
            "purchase_lines_in_window": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.BESTELLUNG WHERE COALESCE(BIDAT,BVDAT)>=? AND COALESCE(BIDAT,BVDAT)<?", START, END),
            "purchase_lines_before_window": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.BESTELLUNG WHERE COALESCE(BIDAT,BVDAT)<?", START),
            "trace_events_in_window": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.SNRARCHIV WHERE BUCHDATUM>=? AND BUCHDATUM<?", START, END)
                + scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.CHARGENARCHIV WHERE BUCHDATUM>=? AND BUCHDATUM<?", START, END),
            "trace_events_before_window": scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.SNRARCHIV WHERE BUCHDATUM<?", START)
                + scalar(cur, "SELECT COUNT_BIG(*) FROM dbo.CHARGENARCHIV WHERE BUCHDATUM<?", START),
        }

    target = {
        "product_anchors": len(odoo.external_names("product.template", "ev_product_")),
        "partner_anchors": len(odoo.external_names("res.partner", "ev_adr_")),
        "crm_anchors": len(crm_names),
        "crm_history_anchors": len(odoo.external_names("mail.message", "ev_crm_history_")),
        "sales_documents": len(sales_names),
        "sales_review_documents": len(review_names),
        "purchase_documents": odoo.count("kf.legacy.purchase.document"),
        "purchase_lines": odoo.count("kf.legacy.purchase.document.line"),
        "purchase_lines_without_product": odoo.count("kf.legacy.purchase.document.line", [("product_id", "=", False)]),
        "trace_headers": odoo.count("kf.legacy.trace"),
        "trace_events": odoo.count("kf.legacy.trace.event"),
        "trace_headers_without_product": odoo.count("kf.legacy.trace", [("product_id", "=", False)]),
        "direct_deliveries_without_customer": odoo.count("kf.legacy.trace.delivery", [("partner_id", "=", False)]),
        "users_active": odoo.count("res.users", []),
        "users_including_archived": int(odoo.call(
            "res.users", "search_count", [[]], {"context": {"active_test": False}}
        )),
        "employees_active": odoo.count("hr.employee", []),
        "employees_including_archived": int(odoo.call(
            "hr.employee", "search_count", [[]], {"context": {"active_test": False}}
        )),
        "operational_purchase_orders": odoo.count("purchase.order", []),
        "operational_stock_pickings": odoo.count("stock.picking", []),
        "operational_stock_moves": odoo.count("stock.move", []),
        "account_moves": odoo.count("account.move", []),
        "mail_queue": odoo.count("mail.mail", []),
    }
    result = {
        "database": odoo.db,
        "audit_time": datetime.now().isoformat(timespec="seconds"),
        "window": {"from": START.isoformat(), "to_exclusive": END.isoformat()},
        "source": source,
        "target": target,
        "delta_since_import": {"missing_crm": missing_crm, "missing_sales": missing_sales},
        "checks": {
            "products_complete": target["product_anchors"] == source["products_not_deleted"],
            "crm_current_for_window": not missing_crm,
            "sales_current_for_window": not missing_sales,
            "purchase_lines_complete": target["purchase_lines"] == source["purchase_lines_in_window"],
            "trace_events_complete": target["trace_events"] == source["trace_events_in_window"],
            "legacy_relations_complete": target["purchase_lines_without_product"] == 0
                and target["trace_headers_without_product"] == 0
                and target["direct_deliveries_without_customer"] == 0,
            "no_operational_document_effects": target["operational_purchase_orders"] == 0
                and target["operational_stock_pickings"] == 0
                and target["operational_stock_moves"] == 0
                and target["account_moves"] == 0,
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    print("MIGRATION_3D_AUDIT_OK_NO_WRITES")


if __name__ == "__main__":
    main()
