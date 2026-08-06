#!/usr/bin/env python3
"""
eEvolution DB-Profiler (lokal ausfuehren)
Verbindet mit KuF-Datenbank und schreibt Schema + Beispieldaten
in 'eevo_profil.txt' - diese Datei dann an Claude schicken.

Installation (einmalig in CMD/PowerShell):
    pip install pymssql

Ausfuehren:
    python profil_eevolution.py
"""

import os
import sys
import json
from datetime import datetime

HOST     = "192.168.120.234"
PORT     = 1433
DATABASE = "KuF"
USER     = os.getenv("EV_USER", "")
PASSWORD = os.getenv("EV_PASSWORD", "")

ZIEL_TABELLEN = [
    "ADRESS", "ADRANSPRECH", "ANSPRECHPARTNEREMAIL",
    "KUNDE", "LIEFERANT", "ARTIKEL", "ARTIKELLONG",
    "AUFTRAG", "ANGAUFPOS", "LIEFRECH", "BESTELLUNG",
    "LAND", "ZAHLBEDING", "PREISLISTEN", "PREISLISTKOPF",
    "VERTRETER", "KOMMUNIKATION", "KNDLIEFER",
    "LAGER", "LAGERBEWEGUNG", "MWSTSCHL", "WAHLFALL",
]

def verbinden():
    try:
        import pymssql
        conn = pymssql.connect(
            server=HOST, port=PORT, database=DATABASE,
            user=USER, password=PASSWORD, login_timeout=10,
            charset="UTF-8"
        )
        print(f"[OK] Verbunden mit {HOST}/{DATABASE}")
        return conn
    except ImportError:
        print("FEHLER: pymssql nicht installiert.")
        print("Bitte ausfuehren: pip install pymssql")
        sys.exit(1)
    except Exception as e:
        print(f"FEHLER Verbindung: {e}")
        sys.exit(1)

def tabellen_schema(cursor, tabellen):
    result = {}
    sql = """
        SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE,
               IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH, NUMERIC_PRECISION, NUMERIC_SCALE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME IN ({})
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """.format(",".join(f"'{t}'" for t in tabellen))
    cursor.execute(sql)
    for row in cursor.fetchall():
        tab = row[0]
        if tab not in result:
            result[tab] = []
        result[tab].append({
            "spalte":     row[1],
            "typ":        row[2],
            "nullable":   row[3],
            "max_len":    row[4],
            "precision":  row[5],
            "scale":      row[6],
        })
    return result

def zeilen_zaehlen(cursor, tabellen):
    counts = {}
    for t in tabellen:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
            counts[t] = cursor.fetchone()[0]
        except Exception:
            counts[t] = "FEHLER"
    return counts

def beispiel_daten(cursor, tabelle, n=3):
    try:
        cursor.execute(f"SELECT TOP {n} * FROM [{tabelle}]")
        cols = [d[0] for d in cursor.description]
        rows = []
        for row in cursor.fetchall():
            rows.append({cols[i]: (str(v) if v is not None else None)
                         for i, v in enumerate(row)})
        return {"spalten": cols, "zeilen": rows}
    except Exception as e:
        return {"fehler": str(e)}

def fremdschluessel(cursor, tabellen):
    sql = """
        SELECT
            fk.TABLE_NAME   as quelle,
            kcu.COLUMN_NAME as spalte,
            pk.TABLE_NAME   as ziel,
            pt.COLUMN_NAME  as ziel_spalte
        FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
        JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS fk
            ON rc.CONSTRAINT_NAME = fk.CONSTRAINT_NAME
        JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS pk
            ON rc.UNIQUE_CONSTRAINT_NAME = pk.CONSTRAINT_NAME
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            ON rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
        JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE pt
            ON rc.UNIQUE_CONSTRAINT_NAME = pt.CONSTRAINT_NAME
        WHERE fk.TABLE_NAME IN ({})
        ORDER BY fk.TABLE_NAME, kcu.COLUMN_NAME
    """.format(",".join(f"'{t}'" for t in tabellen))
    try:
        cursor.execute(sql)
        fks = []
        for row in cursor.fetchall():
            fks.append({"von": f"{row[0]}.{row[1]}", "nach": f"{row[2]}.{row[3]}"})
        return fks
    except Exception:
        return []

def main():
    ausgabe_datei = "eevo_profil.txt"
    conn   = verbinden()
    cursor = conn.cursor()

    print("Lese Schema...")
    schema  = tabellen_schema(cursor, ZIEL_TABELLEN)
    gefunden = list(schema.keys())
    fehlen   = [t for t in ZIEL_TABELLEN if t not in gefunden]

    print("Zaehle Zeilen...")
    counts  = zeilen_zaehlen(cursor, gefunden)

    print("Lese Beispieldaten (ADRESS, KUNDE, ARTIKEL)...")
    beispiele = {}
    for tab in ["ADRESS", "KUNDE", "ARTIKEL", "LAND", "ZAHLBEDING", "ADRANSPRECH"]:
        if tab in gefunden:
            beispiele[tab] = beispiel_daten(cursor, tab)

    print("Lese Fremdschluessel...")
    fks = fremdschluessel(cursor, gefunden)

    conn.close()

    # ---------- Ausgabe ----------
    out = []
    out.append("=" * 70)
    out.append(f"eEvolution DB-Profil  |  {HOST}/{DATABASE}")
    out.append(f"Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    out.append("=" * 70)

    out.append(f"\nGEFUNDEN ({len(gefunden)} Tabellen):")
    for t in sorted(gefunden):
        out.append(f"  {t:<35} {counts.get(t, '?'):>8} Zeilen")

    if fehlen:
        out.append(f"\nNICHT GEFUNDEN ({len(fehlen)}):")
        for t in fehlen:
            out.append(f"  {t}")

    out.append("\n" + "=" * 70)
    out.append("SPALTENSTRUKTUR")
    out.append("=" * 70)
    for tab in sorted(schema.keys()):
        out.append(f"\n-- {tab} --")
        for col in schema[tab]:
            typ = col["typ"]
            if col["max_len"]:
                typ += f"({col['max_len']})"
            elif col["precision"]:
                typ += f"({col['precision']},{col['scale']})"
            null = "NULL" if col["nullable"] == "YES" else "NOT NULL"
            out.append(f"  {col['spalte']:<40} {typ:<20} {null}")

    out.append("\n" + "=" * 70)
    out.append("BEISPIELDATEN (TOP 3)")
    out.append("=" * 70)
    for tab, data in beispiele.items():
        out.append(f"\n-- {tab} --")
        if "fehler" in data:
            out.append(f"  FEHLER: {data['fehler']}")
            continue
        for zeile in data["zeilen"]:
            out.append(f"  Datensatz:")
            for k, v in zeile.items():
                if v is not None and v != "" and v != "None":
                    out.append(f"    {k:<40} {v}")

    if fks:
        out.append("\n" + "=" * 70)
        out.append("FREMDSCHLUESSEL")
        out.append("=" * 70)
        for fk in fks:
            out.append(f"  {fk['von']:<45} → {fk['nach']}")

    text = "\n".join(out)
    with open(ausgabe_datei, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"\n[FERTIG] Profil gespeichert: {ausgabe_datei}")
    print(f"  Bitte diese Datei an Claude schicken.")
    print(text[:500] + "\n...")

if __name__ == "__main__":
    main()
