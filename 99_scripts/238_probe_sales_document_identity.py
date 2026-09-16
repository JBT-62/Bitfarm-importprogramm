#!/usr/bin/env python3
"""Read-only ANGAUFGUT column inventory for document identity mapping."""
import os
import pyodbc

cs = (
    f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
    f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
    f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
    "ApplicationIntent=ReadOnly;"
)
with pyodbc.connect(cs, readonly=True, timeout=30) as connection:
    cursor = connection.cursor()
    cursor.execute("""
        SELECT COLUMN_NAME,DATA_TYPE
          FROM INFORMATION_SCHEMA.COLUMNS
         WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='ANGAUFGUT'
         ORDER BY ORDINAL_POSITION
    """)
    print("ANGAUFGUT_COLUMNS=" + "|".join(f"{row[0]}:{row[1]}" for row in cursor.fetchall()))
    cursor.execute("""
        SELECT COLUMN_NAME,DATA_TYPE
          FROM INFORMATION_SCHEMA.COLUMNS
         WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME='ANGAUFPOS'
         ORDER BY ORDINAL_POSITION
    """)
    print("ANGAUFPOS_COLUMNS=" + "|".join(f"{row[0]}:{row[1]}" for row in cursor.fetchall()))
print("READ_ONLY")
