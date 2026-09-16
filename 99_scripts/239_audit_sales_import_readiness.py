#!/usr/bin/env python3
"""Read-only readiness audit for the historical eEvolution sales import."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import os

import pyodbc

import migration_runtime


CUTOFF = datetime(2016, 9, 16)
TAX_XMLIDS = {
    1: "__import__.ev_tax_16",
    2: "account.1_tax_not_taxable_skr03",
    3: "account.1_tax_ust_7_skr03",
    4: "account.1_tax_eu_sale_skr03",
    5: "account.1_tax_ust_19_skr03",
    6: "account.1_tax_eu_sale_skr03",
}


def source_connection():
    cs = (
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
        f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "ApplicationIntent=ReadOnly;"
    )
    return pyodbc.connect(cs, readonly=True, timeout=30)


def main():
    url, db, user, key = [os.environ[name] for name in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_API_KEY")]
    migration_runtime.require_target(db)
    common = migration_runtime.server_proxy(url + "/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, user, key, {})
    if not uid:
        raise SystemExit("Odoo-Authentifizierung fehlgeschlagen")
    models = migration_runtime.server_proxy(url + "/xmlrpc/2/object", allow_none=True)

    def call(model, method, args=None, kwargs=None):
        return models.execute_kw(db, uid, key, model, method, args or [], kwargs or {})

    sale_fields = call("sale.order", "fields_get", [], {"attributes": ["type", "readonly"]})
    line_fields = call("sale.order.line", "fields_get", [], {"attributes": ["type", "readonly"]})

    def resolve(xmlid):
        module, name = xmlid.split(".", 1)
        rows = call("ir.model.data", "search_read", [[("module", "=", module), ("name", "=", name)]], {"fields": ["model", "res_id"], "limit": 1})
        return rows[0] if rows else None

    tax_targets = {str(code): resolve(xmlid) for code, xmlid in TAX_XMLIDS.items()}
    product_links = call("ir.model.data", "search_count", [[("module", "=", "__import__"), ("name", "like", "ev_product_%"), ("model", "=", "product.template")]])
    partner_links = call("ir.model.data", "search_count", [[("module", "=", "__import__"), ("name", "like", "ev_adr_%"), ("model", "=", "res.partner")]])

    with source_connection() as cn:
        cur = cn.cursor()
        cur.execute(
            """
            SELECT
              COUNT_BIG(*) AS TOTAL,
              SUM(CASE WHEN ISNULL(p.POS_GUELTIG,0)>0 AND NOT (
                    ISNULL(h.ABWEICH,0)<>0 AND (
                      NULLIF(LTRIM(RTRIM(ISNULL(h.ABWNAME1,''))),'') IS NULL OR
                      NULLIF(LTRIM(RTRIM(ISNULL(h.ABWSTRASSE,''))),'') IS NULL OR
                      NULLIF(LTRIM(RTRIM(ISNULL(h.ABWORT,''))),'') IS NULL)) THEN 1 ELSE 0 END) AS OPERATIVLOS,
              SUM(CASE WHEN ISNULL(p.POS_GUELTIG,0)=0 OR (
                    ISNULL(h.ABWEICH,0)<>0 AND (
                      NULLIF(LTRIM(RTRIM(ISNULL(h.ABWNAME1,''))),'') IS NULL OR
                      NULLIF(LTRIM(RTRIM(ISNULL(h.ABWSTRASSE,''))),'') IS NULL OR
                      NULLIF(LTRIM(RTRIM(ISNULL(h.ABWORT,''))),'') IS NULL)) THEN 1 ELSE 0 END) AS REVIEW,
              SUM(CASE WHEN ISNULL(p.POS_GUELTIG,0)=0 AND ISNULL(h.ABWEICH,0)<>0 AND (
                      NULLIF(LTRIM(RTRIM(ISNULL(h.ABWNAME1,''))),'') IS NULL OR
                      NULLIF(LTRIM(RTRIM(ISNULL(h.ABWSTRASSE,''))),'') IS NULL OR
                      NULLIF(LTRIM(RTRIM(ISNULL(h.ABWORT,''))),'') IS NULL) THEN 1 ELSE 0 END) AS REVIEW_OVERLAP
            FROM dbo.ANGAUFGUT h
            OUTER APPLY (
              SELECT SUM(CASE WHEN ISNULL(GUELTIG,0)=1 THEN 1 ELSE 0 END) POS_GUELTIG
              FROM dbo.ANGAUFPOS WHERE LFDANGAUFGUTNR=h.LFDNR
            ) p
            WHERE h.AAGAUFART<>8 AND h.ERFASSDATUM>=?
              AND NOT (h.GUTSCHRIFT=1 AND h.AUFTRAG=0 AND h.ANGEBOT=0)
            """,
            CUTOFF,
        )
        source_partition = dict(zip([c[0] for c in cur.description], cur.fetchone()))
        cur.execute(
            """
            SELECT ISNULL(p.MWSTSCHL,-1) MWSTSCHL, COUNT_BIG(*) ANZAHL
              FROM dbo.ANGAUFPOS p
              JOIN dbo.ANGAUFGUT h ON h.LFDNR=p.LFDANGAUFGUTNR
             WHERE h.AAGAUFART<>8 AND h.ERFASSDATUM>=? AND ISNULL(p.GUELTIG,0)=1
               AND NOT (h.GUTSCHRIFT=1 AND h.AUFTRAG=0 AND h.ANGEBOT=0)
             GROUP BY ISNULL(p.MWSTSCHL,-1) ORDER BY MWSTSCHL
            """,
            CUTOFF,
        )
        source_taxes = {str(int(row[0])): int(row[1]) for row in cur.fetchall()}
        cur.execute(
            """
            SELECT UPPER(LTRIM(RTRIM(ISNULL(ABWLAND,'')))) LAND, COUNT_BIG(*) ANZAHL
              FROM dbo.ANGAUFGUT
             WHERE AAGAUFART<>8 AND ERFASSDATUM>=? AND ISNULL(ABWEICH,0)<>0
               AND NOT (GUTSCHRIFT=1 AND AUFTRAG=0 AND ANGEBOT=0)
             GROUP BY UPPER(LTRIM(RTRIM(ISNULL(ABWLAND,'')))) ORDER BY ANZAHL DESC
            """,
            CUTOFF,
        )
        countries = {str(row[0]): int(row[1]) for row in cur.fetchall()}
        cur.execute(
            """
            SELECT ISNULL(f.WSYMBOL,'EUR') WAEHRUNG, COUNT_BIG(*) ANZAHL
              FROM dbo.ANGAUFGUT h
              LEFT JOIN dbo.FREMDWAEHRUNG f ON f.LFDNR=h.WAEHRUNG
             WHERE h.AAGAUFART<>8 AND h.ERFASSDATUM>=?
               AND NOT (h.GUTSCHRIFT=1 AND h.AUFTRAG=0 AND h.ANGEBOT=0)
             GROUP BY ISNULL(f.WSYMBOL,'EUR') ORDER BY ANZAHL DESC
            """,
            CUTOFF,
        )
        source_currencies = {str(row[0]).strip().upper(): int(row[1]) for row in cur.fetchall()}

    target_currency_rows = call("res.currency", "search_read", [[("name", "in", list(source_currencies))]], {"fields": ["name", "active"], "context": {"active_test": False}})

    required_sale_fields = ["name", "partner_id", "partner_shipping_id", "date_order", "state", "locked", "client_order_ref", "order_line", "user_id", "team_id"]
    required_line_fields = ["product_id", "product_uom_id", "name", "product_uom_qty", "price_unit", "discount", "tax_ids"]
    output = {
        "cutoff": CUTOFF.date().isoformat(),
        "source_partition": {k: int(v or 0) for k, v in source_partition.items()},
        "source_tax_keys": source_taxes,
        "target_tax_xmlids": tax_targets,
        "alternate_delivery_countries": countries,
        "source_currencies": source_currencies,
        "target_currencies": target_currency_rows,
        "odoo_sale_fields": {name: sale_fields.get(name) for name in required_sale_fields},
        "odoo_line_fields": {name: line_fields.get(name) for name in required_line_fields},
        "product_external_ids": product_links,
        "partner_external_ids": partner_links,
    }
    unresolved_tax_keys = sorted(code for code in source_taxes if int(code) not in TAX_XMLIDS or not tax_targets.get(code))
    if unresolved_tax_keys:
        raise SystemExit("Unaufgeloeste Steuerschluessel: " + ", ".join(unresolved_tax_keys))
    if any(sale_fields.get(name) is None for name in required_sale_fields):
        raise SystemExit("Erforderliche sale.order-Felder fehlen")
    print("SALES_IMPORT_READINESS " + json.dumps(output, ensure_ascii=False, default=str))
    print("READ_ONLY_OK")


if __name__ == "__main__":
    main()
