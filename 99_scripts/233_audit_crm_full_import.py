#!/usr/bin/env python3
"""Read-only evidence audit for the full eEvolution CRM import."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os

import migration_runtime
import pyodbc


def norm(value):
    return str(value or "").strip().casefold()


def source_connection():
    cs = (
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
        f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "ApplicationIntent=ReadOnly;"
    )
    return pyodbc.connect(cs, readonly=True, timeout=30)


def rows(cursor, sql, *params):
    cursor.execute(sql, *params)
    names = [item[0] for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff", default="2016-09-16")
    args = parser.parse_args()
    cutoff = datetime.fromisoformat(args.cutoff)

    with source_connection() as connection:
        cursor = connection.cursor()
        owners = rows(cursor, """
            SELECT v.BESITZER AS MITARBNR, COUNT_BIG(*) AS CHANCEN,
                   MAX(m.NAME1) AS NAME1, MAX(m.NAME2) AS NAME2,
                   MAX(m.EMAILINTERN) AS EMAIL
              FROM dbo.VERKAUFSCHANCE v
              LEFT JOIN dbo.MITARBEITER m ON m.MITARBNR=v.BESITZER
             WHERE v.ERSTELLDATUM>=? AND v.BESITZER IS NOT NULL
             GROUP BY v.BESITZER ORDER BY v.BESITZER
        """, cutoff)
        statuses = rows(cursor, """
            SELECT CONVERT(nvarchar(64), v.STATUS) AS STATUS_GUID,
                   MAX(s.BEZEICHNUNG) AS BEZEICHNUNG,
                   COUNT_BIG(*) AS CHANCEN,
                   SUM(CASE WHEN ISNULL(v.ISTVERLOREN,0)<>0 THEN 1 ELSE 0 END) AS VERLOREN
              FROM dbo.VERKAUFSCHANCE v
              LEFT JOIN dbo.LEADSTATUS s ON s.GUID=v.STATUS
             WHERE v.ERSTELLDATUM>=?
             GROUP BY v.STATUS ORDER BY MAX(s.BEZEICHNUNG)
        """, cutoff)
        product_interest = rows(cursor, """
            SELECT TOP (30) CONVERT(nvarchar(4000), PRODUKTINTERESSE) AS WERT,
                   COUNT_BIG(*) AS CHANCEN
              FROM dbo.VERKAUFSCHANCE
             WHERE ERSTELLDATUM>=?
             GROUP BY CONVERT(nvarchar(4000), PRODUKTINTERESSE)
             ORDER BY COUNT_BIG(*) DESC, CONVERT(nvarchar(4000), PRODUKTINTERESSE)
        """, cutoff)
        source_summary = rows(cursor, """
            SELECT COUNT_BIG(*) AS CHANCEN,
                   MIN(ERSTELLDATUM) AS ERSTES_DATUM,
                   MAX(ERSTELLDATUM) AS LETZTES_DATUM,
                   SUM(CASE WHEN KUNDE IS NULL THEN 1 ELSE 0 END) AS OHNE_KUNDE,
                   SUM(CASE WHEN PRODUKTINTERESSE IS NULL THEN 1 ELSE 0 END) AS OHNE_PRODUKTINTERESSE,
                   SUM(CASE WHEN ISDATE(ISTABSCHLUSSDATUM)=0 AND ISDATE(ABSCHLUSSDATUM)=0
                                  AND (ISTABSCHLUSSDATUM IS NOT NULL OR ABSCHLUSSDATUM IS NOT NULL)
                            THEN 1 ELSE 0 END) AS UNGUELTIGES_ABSCHLUSSDATUM
              FROM dbo.VERKAUFSCHANCE WHERE ERSTELLDATUM>=?
        """, cutoff)[0]
        customer_addresses = rows(cursor, """
            SELECT DISTINCT k.ADRNR
              FROM dbo.VERKAUFSCHANCE v
              JOIN dbo.KUNDE k ON k.KNDNR=v.KUNDE
             WHERE v.ERSTELLDATUM>=? AND k.ADRNR IS NOT NULL
        """, cutoff)

    target_info = migration_runtime.require_target(os.environ["ODOO_DB"])
    common = migration_runtime.server_proxy(target_info.url.rstrip("/") + "/xmlrpc/2/common", allow_none=True)
    target_db = os.environ["ODOO_DB"]
    uid = common.authenticate(target_db, target_info.user, os.environ["ODOO_API_KEY"], {})
    if not uid:
        raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
    models = migration_runtime.server_proxy(target_info.url.rstrip("/") + "/xmlrpc/2/object", allow_none=True)

    def call(model, method, call_args=None, kwargs=None):
        return models.execute_kw(target_db, uid, os.environ["ODOO_API_KEY"], model, method, call_args or [], kwargs or {})

    users = call("res.users", "search_read", [[("active", "=", True)]], {
        "fields": ["login", "name", "partner_id"], "context": {"active_test": False}, "limit": 1000,
    })
    user_by_login = {norm(row["login"]): row for row in users}
    owner_mapping = []
    for owner in owners:
        email = norm(owner.get("EMAIL"))
        match = user_by_login.get(email)
        owner_mapping.append({
            "mitarbnr": int(owner["MITARBNR"]), "chancen": int(owner["CHANCEN"]),
            "name": " ".join(x for x in (str(owner.get("NAME1") or "").strip(), str(owner.get("NAME2") or "").strip()) if x),
            "email": owner.get("EMAIL") or "", "target_user_login": match["login"] if match else "",
            "resolution": "unique_login" if match else "missing",
        })

    ev_user_rows = call("ir.model.data", "search_read", [[
        ("module", "=", "__import__"), ("model", "=", "res.users"), ("name", "like", "ev_user_")
    ]], {"fields": ["name", "res_id"], "limit": 1000})
    partner_rows = call("ir.model.data", "search_read", [[
        ("module", "=", "__import__"), ("model", "=", "res.partner"), ("name", "like", "ev_adr_")
    ]], {"fields": ["name"], "limit": 30000})
    partner_names = {row["name"] for row in partner_rows}
    missing_partner_addresses = sorted(
        int(row["ADRNR"]) for row in customer_addresses
        if f"ev_adr_{int(row['ADRNR'])}" not in partner_names
    )
    opportunity_imd = call("ir.model.data", "search_read", [[
        ("module", "=", "__import__"), ("model", "=", "crm.lead"), ("name", "like", "ev_vkchance_")
    ]], {"fields": ["res_id"], "limit": 10000})
    opportunity_ids = [int(row["res_id"]) for row in opportunity_imd]
    def opportunity_count(extra_domain):
        if not opportunity_ids:
            return 0
        return call("crm.lead", "search_count", [[("id", "in", opportunity_ids), *extra_domain]], {
            "context": {"active_test": False}
        })
    target = {
        "crm_leads": call("crm.lead", "search_count", [[]]),
        "crm_stages": call("crm.stage", "search_count", [[]]),
        "imported_opportunities": len(opportunity_ids),
        "imported_active": opportunity_count([("active", "=", True)]),
        "imported_archived": opportunity_count([("active", "=", False)]),
        "missing_partner": opportunity_count([("partner_id", "=", False)]),
        "missing_product_interest": opportunity_count([("kf_legacy_product_interest", "=", False)]),
        "missing_owner_number": opportunity_count([("kf_legacy_owner_number", "=", 0)]),
        "missing_owner_name": opportunity_count([("kf_legacy_owner_name", "=", False)]),
        "assigned_odoo_salesperson": opportunity_count([("user_id", "!=", False)]),
        "imported_history": call("ir.model.data", "search_count", [[
            ("module", "=", "__import__"), ("model", "=", "mail.message"), ("name", "like", "ev_crm_history_")
        ]]),
        "ev_user_anchors": sorted(row["name"] for row in ev_user_rows),
        "missing_opportunity_partner_addresses": missing_partner_addresses,
    }

    output = {
        "cutoff": args.cutoff,
        "source_summary": {key: (value.isoformat() if hasattr(value, "isoformat") else int(value or 0))
                           for key, value in source_summary.items()},
        "owners": owner_mapping,
        "statuses": [{key: int(value) if key in {"CHANCEN", "VERLOREN"} else str(value or "")
                      for key, value in row.items()} for row in statuses],
        "product_interest_top": [{"value": str(row["WERT"] or ""), "count": int(row["CHANCEN"])}
                                 for row in product_interest],
        "target": target,
    }
    print("CRM_FULL_IMPORT_AUDIT " + json.dumps(output, ensure_ascii=False))
    print("READ_ONLY")


if __name__ == "__main__":
    main()
