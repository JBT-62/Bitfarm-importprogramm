#!/usr/bin/env python3
"""
build_schema_cache.py
Einmalig ausführen: liest das komplette INFORMATION_SCHEMA aus eEvolution
und schreibt eevo_schema.json + eevo_schema.md als Referenz.

Ausführen:
    python 99_scripts/build_schema_cache.py

Ergebnisse (im Projektordner):
    eevo_schema.json   ← von anderen Skripten importiert (eevo_schema.py)
    eevo_schema.md     ← lesbare Referenz für Claude / Entwickler
"""

import os, sys, json
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import pyodbc
except ImportError:
    sys.exit("FEHLER: pyodbc fehlt.  pip install pyodbc")


def ee_connect():
    driver   = os.getenv("EV_DRIVER",   "ODBC Driver 18 for SQL Server")
    server   = os.getenv("EV_SERVER",   "192.168.120.234")
    database = os.getenv("EV_DATABASE", "KuF")
    user     = os.getenv("EV_USER",     "excel_kuf_readonly")
    password = os.getenv("EV_PASSWORD", "")
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},1433;"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, timeout=10)
    print(f"[OK] Verbunden mit {server}/{database}")
    return conn, server, database


def main():
    conn, server, database = ee_connect()
    cur = conn.cursor()

    # ── Alle Tabellen + Spalten aus INFORMATION_SCHEMA ───────────────────────
    print("[1] Lese INFORMATION_SCHEMA …")
    cur.execute("""
        SELECT
            t.TABLE_NAME,
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.NUMERIC_PRECISION,
            c.NUMERIC_SCALE,
            c.IS_NULLABLE,
            c.ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c
            ON c.TABLE_NAME = t.TABLE_NAME
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION
    """)

    schema = {}   # { "TABELLE": [ {col, type, ...}, ... ] }
    for row in cur.fetchall():
        tbl  = row[0]
        col  = row[1]
        typ  = row[2]
        clen = row[3]
        prec = row[4]
        scal = row[5]
        null = row[6]
        pos  = row[7]

        if typ in ("numeric", "decimal") and prec is not None:
            type_str = f"{typ}({prec},{scal})"
        elif clen and clen != -1:
            type_str = f"{typ}({clen})"
        elif clen == -1:
            type_str = f"{typ}(MAX)"
        else:
            type_str = typ

        schema.setdefault(tbl, []).append({
            "col":      col,
            "type":     type_str,
            "nullable": null == "YES",
            "pos":      pos,
        })

    conn.close()
    print(f"    {len(schema)} Tabellen, {sum(len(v) for v in schema.values())} Spalten")

    # ── JSON speichern ────────────────────────────────────────────────────────
    cache = {
        "_meta": {
            "server":    server,
            "database":  database,
            "generated": datetime.now().isoformat(timespec="seconds"),
            "tables":    len(schema),
            "columns":   sum(len(v) for v in schema.values()),
        },
        "tables": schema,
    }

    json_pfad = "eevo_schema.json"
    with open(json_pfad, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"[OK] Gespeichert: {json_pfad}")

    # ── Markdown-Referenz ─────────────────────────────────────────────────────
    print("[2] Erstelle eevo_schema.md …")
    md_pfad = "eevo_schema.md"

    # Wichtige Tabellen zuerst
    WICHTIG = [
        "ARTIKEL", "ARTIKELLONG", "ADRESS", "KUNDE", "LIEFERANT",
        "ADRANSPRECH", "ANGAUFGUT", "ANGAUFPOS", "ANGAUFARCHIV",
        "ANGAUFARCHIVPOS", "ANGEBOT", "ANFRAGE", "ANFRAGEPOS",
        "PRODLIST", "PRODINHALT", "ARTSTUELI",
        "MENGENSCHL", "ZAHLBEDING", "LAND", "VERTRETER",
        "PREISLISTEN", "PREISLISTKOPF", "CHARGEN", "SERNR",
        "LIEFRECH", "BESTELLUNG", "KNDLIEFER",
    ]

    with open(md_pfad, "w", encoding="utf-8") as f:
        m = cache["_meta"]
        f.write(f"# eEvolution Schema – {m['database']} @ {m['server']}\n\n")
        f.write(f"Generiert: {m['generated']}  ·  "
                f"{m['tables']} Tabellen  ·  {m['columns']} Spalten\n\n")
        f.write("> Automatisch generiert von `build_schema_cache.py`.\n"
                "> Neu generieren nach Schema-Änderungen in eEvolution.\n\n")

        def tabelle_schreiben(name, cols):
            f.write(f"## {name}\n\n")
            f.write(f"| # | Spalte | Typ | Null? |\n")
            f.write(f"|---|--------|-----|-------|\n")
            for c in cols:
                null = "✓" if c["nullable"] else ""
                f.write(f"| {c['pos']} | `{c['col']}` | {c['type']} | {null} |\n")
            f.write("\n")

        # Wichtige Tabellen zuerst
        f.write("---\n\n## Wichtige Tabellen (Kerntabellen)\n\n")
        for name in WICHTIG:
            if name in schema:
                tabelle_schreiben(name, schema[name])

        # Rest alphabetisch
        f.write("---\n\n## Alle weiteren Tabellen (alphabetisch)\n\n")
        for name in sorted(schema.keys()):
            if name not in WICHTIG:
                tabelle_schreiben(name, schema[name])

    print(f"[OK] Gespeichert: {md_pfad}")
    print(f"\nNächster Schritt:")
    print(f"  git add eevo_schema.json eevo_schema.md")
    print(f"  git commit -m 'add: eEvolution Schema-Cache'")
    print(f"  git push")
    print(f"\nDanach in Skripten nutzen:")
    print(f"  from eevo_schema import find, cols, has, pk")


if __name__ == "__main__":
    main()
