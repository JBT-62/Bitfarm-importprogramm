#!/usr/bin/env python3
"""Read-only discovery for the remaining full-history rehearsal blocks."""
from __future__ import annotations

import json
import os

import pyodbc


TABLES = (
    "AAGLS",
    "AAGLSPOS",
    "AAGFAKT",
    "AAGFAKTPOS",
    "RECHEINGANG",
    "RECHEINPOS",
    "PRODUKTION",
)


def connect():
    return pyodbc.connect(
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
        f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "ApplicationIntent=ReadOnly;",
        readonly=True,
        timeout=30,
    )


def main():
    result = {}
    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        for table in TABLES:
            cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, ORDINAL_POSITION
                  FROM INFORMATION_SCHEMA.COLUMNS
                 WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?
                 ORDER BY ORDINAL_POSITION
                """,
                table,
            )
            columns = [
                {"name": row[0], "type": row[1], "nullable": row[2], "position": row[3]}
                for row in cursor.fetchall()
            ]
            cursor.execute(f"SELECT TOP 2 * FROM dbo.[{table}] ORDER BY 1 DESC")
            names = [item[0] for item in cursor.description]
            samples = []
            for row in cursor.fetchall():
                samples.append({name: str(value) if value is not None else None for name, value in zip(names, row)})
            result[table] = {"columns": columns, "samples": samples}
    for table, payload in result.items():
        print(table + "|" + ",".join(column["name"] for column in payload["columns"]))
        for sample in payload["samples"]:
            selected = {
                key: value for key, value in sample.items()
                if key in {
                    "LFDNR", "LFDFAKTNR", "LSNR", "LFDANGAUFGUTNR", "AUFNR",
                    "POSNR", "KNDNR1", "LIEFNR", "LFDLIEFNR", "ARTLFDNR",
                    "ARTNR", "ARTNR1", "BEZEICHNUNG", "RECHNR", "BELEGNR",
                    "LSDATUM", "FAKTDATUM", "RECHDATUM", "PPDAT", "PVDAT",
                    "PDDAT", "ENDDAT", "TMSTMP", "MENGE", "BESTMENGE",
                    "PRODMENGE", "AUSMENGE", "AUSSCHUSS", "PREIS", "BETRAG",
                    "WSYMBOL", "STATUS", "TYP", "STORNO", "STORNOTIMESTAMP",
                    "NAME1", "KNDNAME1", "LIEFNAME1", "ABEZ1", "TEXT", "LANGTEXT",
                }
            }
            print("SAMPLE|" + table + "|" + json.dumps(selected, ensure_ascii=False))
    print("REMAINING_HISTORY_SOURCE_DISCOVERY_OK_NO_WRITES")


if __name__ == "__main__":
    main()
