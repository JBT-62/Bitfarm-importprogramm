#!/usr/bin/env python3
"""Read-only classification of historical sales-document import blockers."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
import os
import pyodbc


def connection():
    cs = (
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
        f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "ApplicationIntent=ReadOnly;"
    )
    return pyodbc.connect(cs, readonly=True, timeout=30)


def rows(cursor, sql, *params):
    cursor.execute(sql, *params)
    cols = [item[0] for item in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def main():
    cutoff = datetime(2016, 9, 16)
    with connection() as cn:
        cur = cn.cursor()
        base = """
          FROM dbo.ANGAUFGUT h
          OUTER APPLY (
              SELECT COUNT_BIG(*) AS POS_ALLE,
                     SUM(CASE WHEN ISNULL(p.GUELTIG,0)=1 THEN 1 ELSE 0 END) AS POS_GUELTIG
                FROM dbo.ANGAUFPOS p WHERE p.LFDANGAUFGUTNR=h.LFDNR
          ) p
         WHERE h.AAGAUFART<>8 AND h.ERFASSDATUM>=?
           AND NOT (h.GUTSCHRIFT=1 AND h.AUFTRAG=0 AND h.ANGEBOT=0)
        """
        summary = rows(cur, "SELECT COUNT_BIG(*) AS KOPF, "
                       "SUM(CASE WHEN ISNULL(p.POS_GUELTIG,0)=0 THEN 1 ELSE 0 END) AS OHNE_GUELTIGE_POS, "
                       "SUM(CASE WHEN ISNULL(p.POS_ALLE,0)=0 THEN 1 ELSE 0 END) AS OHNE_JEDE_POS, "
                       "SUM(CASE WHEN ISNULL(p.POS_ALLE,0)>0 AND ISNULL(p.POS_GUELTIG,0)=0 THEN 1 ELSE 0 END) AS NUR_UNGUELTIGE_POS "
                       + base, cutoff)[0]
        flags = rows(cur, """
            SELECT h.ANGEBOT,h.AUFTRAG,h.GUTSCHRIFT,h.ERLEDIGT,h.STATUS,
                   COUNT_BIG(*) AS KOPF,
                   MIN(h.ERFASSDATUM) AS ERSTES_DATUM,MAX(h.ERFASSDATUM) AS LETZTES_DATUM
        """ + base + " AND ISNULL(p.POS_GUELTIG,0)=0 "
              "GROUP BY h.ANGEBOT,h.AUFTRAG,h.GUTSCHRIFT,h.ERLEDIGT,h.STATUS "
              "ORDER BY COUNT_BIG(*) DESC", cutoff)
        address = rows(cur, """
            SELECT COUNT_BIG(*) AS UNVOLLSTAENDIG,
                   SUM(CASE WHEN NULLIF(LTRIM(RTRIM(ISNULL(h.ABWNAME1,''))),'') IS NULL THEN 1 ELSE 0 END) AS NAME_FEHLT,
                   SUM(CASE WHEN NULLIF(LTRIM(RTRIM(ISNULL(h.ABWSTRASSE,''))),'') IS NULL THEN 1 ELSE 0 END) AS STRASSE_FEHLT,
                   SUM(CASE WHEN NULLIF(LTRIM(RTRIM(ISNULL(h.ABWORT,''))),'') IS NULL THEN 1 ELSE 0 END) AS ORT_FEHLT,
                   MIN(h.ERFASSDATUM) AS ERSTES_DATUM,MAX(h.ERFASSDATUM) AS LETZTES_DATUM
              FROM dbo.ANGAUFGUT h
             WHERE h.AAGAUFART<>8 AND h.ERFASSDATUM>=?
               AND NOT (h.GUTSCHRIFT=1 AND h.AUFTRAG=0 AND h.ANGEBOT=0)
               AND ISNULL(h.ABWEICH,0)<>0
               AND (NULLIF(LTRIM(RTRIM(ISNULL(h.ABWNAME1,''))),'') IS NULL
                    OR NULLIF(LTRIM(RTRIM(ISNULL(h.ABWSTRASSE,''))),'') IS NULL
                    OR NULLIF(LTRIM(RTRIM(ISNULL(h.ABWORT,''))),'') IS NULL)
        """, cutoff)[0]
        examples = rows(cur, """
            SELECT TOP (20) h.LFDNR,h.ERFASSDATUM,h.ANGEBOT,h.AUFTRAG,h.GUTSCHRIFT,
                   h.ERLEDIGT,h.STATUS,p.POS_ALLE,p.POS_GUELTIG
        """ + base + " AND ISNULL(p.POS_GUELTIG,0)=0 ORDER BY h.ERFASSDATUM DESC,h.LFDNR DESC", cutoff)
        identity_columns = rows(cur, """
            SELECT COLUMN_NAME,DATA_TYPE
              FROM INFORMATION_SCHEMA.COLUMNS
             WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='ANGAUFGUT'
               AND (COLUMN_NAME LIKE '%VORG%' OR COLUMN_NAME LIKE '%BELEG%'
                    OR COLUMN_NAME LIKE '%NUMMER%' OR COLUMN_NAME LIKE '%KENN%')
             ORDER BY ORDINAL_POSITION
        """)
        identity_examples = rows(cur, """
            SELECT TOP (20) LFDNR,VORGANG,KENNZEICHEN,ANGEBOT,AUFTRAG,GUTSCHRIFT,
                   ERFASSDATUM,ERLEDIGT,STATUS
              FROM dbo.ANGAUFGUT
             WHERE AAGAUFART<>8 AND ERFASSDATUM>=?
             ORDER BY ERFASSDATUM DESC,LFDNR DESC
        """, cutoff)

    def clean(value):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return int(value) if isinstance(value, (int, Decimal)) else value
    output = {
        "cutoff": "2016-09-16",
        "summary": {k: clean(v) for k, v in summary.items()},
        "empty_by_flags_status": [{k: clean(v) for k, v in row.items()} for row in flags],
        "incomplete_delivery_addresses": {k: clean(v) for k, v in address.items()},
        "examples": [{k: clean(v) for k, v in row.items()} for row in examples],
        "identity_columns": identity_columns,
        "identity_examples": [{k: clean(v) for k, v in row.items()} for row in identity_examples],
    }
    print("SALES_DOCUMENT_BLOCKER_AUDIT " + json.dumps(output, ensure_ascii=False))
    print("READ_ONLY")


if __name__ == "__main__":
    main()
