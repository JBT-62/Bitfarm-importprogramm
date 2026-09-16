#!/usr/bin/env python3
"""Read-only audit for the ten-year eEvolution purchase-document history."""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime

import pyodbc

import migration_runtime


START = datetime(2016, 9, 16)
END = datetime(2026, 9, 17)


def clean(value):
    return str(value or "").strip()


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
        migration_runtime.require_target(db)
        common = migration_runtime.server_proxy(url + "/xmlrpc/2/common", allow_none=True)
        uid = common.authenticate(db, user, key, {})
        if not uid:
            raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
        self.db, self.uid, self.key = db, uid, key
        self.models = migration_runtime.server_proxy(url + "/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args=None, kwargs=None):
        return self.models.execute_kw(
            self.db, self.uid, self.key, model, method, args or [], kwargs or {}
        )


def main():
    if migration_runtime.migration_mode() == "apply":
        raise RuntimeError("Dieser Audit ist ausschliesslich read-only")
    with source_connection() as cn:
        cur = cn.cursor()
        cur.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        cur.execute(
            """
            SELECT BESTNR,SAMMELBESTNR,POSNR,ARTNR,LIEFNR,
                   COALESCE(BIDAT,BVDAT) BELEGDATUM,BIDAT,BVDAT,BDDAT,LIEFERDAT,
                   BESTSTATUS,BESTTYP,BESTMENGE,GELMENGE,RESMENGE,EKPREIS,
                   PREISEINHEIT,EKMENGENSCHL,LFDWAEHRUNG,WSYMBOL,
                   ISNULL(RAHMEN,0) RAHMEN,LFDBESTRAHMEN,LFDSTORNONR,STORNOAM,
                   ARTNR1,ARTBEZ1,ARTBEZ2,LIEFERARTNR,LIEFERABEZ
              FROM dbo.BESTELLUNG
             WHERE COALESCE(BIDAT,BVDAT)>=? AND COALESCE(BIDAT,BVDAT)<?
             ORDER BY COALESCE(NULLIF(SAMMELBESTNR,0),BESTNR),POSNR,BESTNR
            """,
            START, END,
        )
        cols = [item[0] for item in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        cur.execute("SELECT LIEFNR,ADRNR FROM dbo.LIEFERANT WHERE LIEFNR IS NOT NULL")
        vendor_address = {int(r[0]): int(r[1]) for r in cur.fetchall() if r[1] is not None}
        cur.execute(
            """
            SELECT COUNT_BIG(*)
              FROM dbo.BESTELLUNG
             WHERE COALESCE(BIDAT,BVDAT)<?
            """,
            START,
        )
        before_cutoff = int(cur.fetchone()[0] or 0)

    normal = [row for row in rows if int(row["RAHMEN"] or 0) == 0]
    frameworks = [row for row in rows if int(row["RAHMEN"] or 0) != 0]
    framework_groups = {
        int(row["LFDBESTRAHMEN"] or 0) or int(row["SAMMELBESTNR"] or 0) or int(row["BESTNR"])
        for row in frameworks
    }
    groups = defaultdict(list)
    for row in normal:
        source_key = int(row["SAMMELBESTNR"] or 0)
        groups[f"S-{source_key}" if source_key else f"B-{int(row['BESTNR'])}"].append(row)

    odoo = Odoo()
    imd = odoo.call(
        "ir.model.data", "search_read",
        [[("module", "=", "__import__"),
          ("name", "like", "ev_product_%")]],
        {"fields": ["name", "model", "res_id"], "limit": 100000},
    )
    product_keys = {
        int(row["name"].removeprefix("ev_product_"))
        for row in imd
        if row["model"] == "product.template"
        and row["name"].removeprefix("ev_product_").isdigit()
    }
    partner_imd = odoo.call(
        "ir.model.data", "search_read",
        [[("module", "=", "__import__"), ("name", "like", "ev_adr_%"),
          ("model", "=", "res.partner")]],
        {"fields": ["name"], "limit": 100000},
    )
    partner_keys = {
        int(row["name"].removeprefix("ev_adr_"))
        for row in partner_imd if row["name"].removeprefix("ev_adr_").isdigit()
    }

    supplier_conflicts = 0
    date_conflicts = 0
    status_mixes = 0
    missing_partner_groups = 0
    missing_product_lines = 0
    empty_product_lines = 0
    cancelled_lines = 0
    for group_rows in groups.values():
        suppliers = {int(r["LIEFNR"]) for r in group_rows if r["LIEFNR"] is not None}
        dates = {r["BELEGDATUM"].date().isoformat() for r in group_rows if r["BELEGDATUM"]}
        statuses = {clean(r["BESTSTATUS"]) for r in group_rows}
        supplier_conflicts += len(suppliers) > 1
        date_conflicts += len(dates) > 1
        status_mixes += len(statuses) > 1
        if len(suppliers) != 1:
            missing_partner_groups += 1
        else:
            supplier = next(iter(suppliers))
            address = vendor_address.get(supplier)
            missing_partner_groups += not address or address not in partner_keys
        for row in group_rows:
            product_key = int(row["ARTNR"] or 0)
            empty_product_lines += product_key == 0
            missing_product_lines += bool(product_key and product_key not in product_keys)
            cancelled_lines += bool(row["LFDSTORNONR"] or row["STORNOAM"])

    target_models = {}
    for model in (
        "purchase.order", "purchase.requisition", "stock.picking", "stock.move",
        "account.move", "mail.mail",
    ):
        target_models[model] = int(odoo.call(model, "search_count", [[]]))
    fields = odoo.call("ir.model", "search_count", [[("model", "=", "kf.legacy.purchase.document")]])
    target_models["legacy_purchase_model_available"] = bool(fields)
    if fields:
        target_models["legacy_purchase_documents"] = int(
            odoo.call("kf.legacy.purchase.document", "search_count", [[]])
        )
        target_models["legacy_purchase_documents_purchase"] = int(
            odoo.call("kf.legacy.purchase.document", "search_count", [[("document_type", "=", "purchase")]])
        )
        target_models["legacy_purchase_documents_framework"] = int(
            odoo.call("kf.legacy.purchase.document", "search_count", [[("document_type", "=", "framework")]])
        )
        target_models["legacy_purchase_documents_review"] = int(
            odoo.call("kf.legacy.purchase.document", "search_count", [[("review_status", "=", "review")]])
        )
        target_models["legacy_purchase_lines"] = int(
            odoo.call("kf.legacy.purchase.document.line", "search_count", [[]])
        )
        target_models["legacy_purchase_lines_without_product"] = int(
            odoo.call("kf.legacy.purchase.document.line", "search_count", [[("product_id", "=", False)]])
        )

    result = {
        "database": os.environ["ODOO_DB"],
        "period_inclusive": "2016-09-16 bis 2026-09-16",
        "source": {
            "eligible_rows_all": len(rows),
            "normal_purchase_rows": len(normal),
            "framework_rows_excluded_from_document_import": len(frameworks),
            "framework_groups_for_separate_history": len(framework_groups),
            "normal_document_groups": len(groups),
            "fallback_single_line_groups_without_sammelbestnr": sum(
                key.startswith("B-") for key in groups
            ),
            "rows_before_cutoff_excluded": before_cutoff,
            "supplier_conflict_groups": supplier_conflicts,
            "document_date_conflict_groups": date_conflicts,
            "mixed_status_groups": status_mixes,
            "groups_without_resolved_partner": missing_partner_groups,
            "lines_without_product_key": empty_product_lines,
            "lines_without_resolved_product": missing_product_lines,
            "cancelled_lines": cancelled_lines,
            "status_distribution": dict(Counter(clean(r["BESTSTATUS"]) for r in normal)),
            "currency_distribution": dict(Counter(clean(r["WSYMBOL"]) for r in normal)),
        },
        "target": target_models,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("HISTORICAL_PURCHASE_AUDIT_OK_NO_WRITES")


if __name__ == "__main__":
    main()
