#!/usr/bin/env python3
"""
suche_pia_anfrage.py
Sucht im eEvolution-CRM nach Anfragen/Angeboten für PIA-Artikel.

Ausführen:
    python 99_scripts/suche_pia_anfrage.py

Gibt CRM-Tabellen, Angebots-Schema und PIA-Treffer aus.
"""

import os, sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import pyodbc
except ImportError:
    sys.exit("FEHLER: pyodbc fehlt. Bitte: pip install pyodbc")


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
    print(f"[OK] Verbunden mit {server}/{database}\n")
    return conn


def q(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or [])
    cols = [c[0] for c in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return cols, rows


def trennlinie(titel=""):
    print(f"\n{'─'*60}")
    if titel:
        print(f"  {titel}")
        print(f"{'─'*60}")


# ── 1. CRM-relevante Tabellen ────────────────────────────────────────────────

SQL_CRM_TABS = """
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
      AND (   TABLE_NAME LIKE '%ANFR%'
           OR TABLE_NAME LIKE '%CRM%'
           OR TABLE_NAME LIKE '%OPPORT%'
           OR TABLE_NAME LIKE '%ANGAUF%'
           OR TABLE_NAME LIKE '%ANGEBOT%'
           OR TABLE_NAME LIKE '%AKTIVIT%'
           OR TABLE_NAME LIKE '%VORGANG%')
    ORDER BY TABLE_NAME
"""

# ── 2. ANGAUFGUT Kopftabelle – Schema + Belegtypen ───────────────────────────

SQL_ANGAUFGUT_COLS = """
    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'ANGAUFGUT'
    ORDER BY ORDINAL_POSITION
"""

SQL_BELEGTYPEN = """
    SELECT BELEGTYP, COUNT(*) AS Anzahl
    FROM ANGAUFGUT
    GROUP BY BELEGTYP
    ORDER BY BELEGTYP
"""

# ── 3. Positionstabelle finden ───────────────────────────────────────────────

SQL_POS_TABS = """
    SELECT TABLE_NAME
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
      AND TABLE_NAME LIKE 'ANGAUFGUT%'
    ORDER BY TABLE_NAME
"""

# ── 4. PIA-Angebote/Anfragen in ANGAUFGUT suchen ────────────────────────────
# Wird dynamisch nach Schema-Analyse aufgebaut (siehe main)


def main():
    conn = ee_connect()

    # ── CRM-Tabellen ──────────────────────────────────────────────────────────
    trennlinie("1. CRM-relevante Tabellen in eEvolution")
    _, tabs = q(conn, SQL_CRM_TABS)
    if tabs:
        for t in tabs:
            print(f"   {t['TABLE_NAME']}")
    else:
        print("   (keine gefunden)")

    # ── Positionstabellen ─────────────────────────────────────────────────────
    trennlinie("2. ANGAUFGUT-Tabellenfamilie")
    _, pos_tabs = q(conn, SQL_POS_TABS)
    for t in pos_tabs:
        print(f"   {t['TABLE_NAME']}")

    # ── ANGAUFGUT Spalten ─────────────────────────────────────────────────────
    trennlinie("3. ANGAUFGUT-Spalten (erste 30)")
    cols, schema = q(conn, SQL_ANGAUFGUT_COLS)
    for s in schema[:30]:
        laenge = f"({s['CHARACTER_MAXIMUM_LENGTH']})" if s['CHARACTER_MAXIMUM_LENGTH'] else ""
        print(f"   {s['COLUMN_NAME']:<30} {s['DATA_TYPE']}{laenge}")
    if len(schema) > 30:
        print(f"   ... ({len(schema) - 30} weitere Spalten)")

    # ── Belegtypen ────────────────────────────────────────────────────────────
    trennlinie("4. BELEGTYP-Verteilung in ANGAUFGUT")
    try:
        _, btypen = q(conn, SQL_BELEGTYPEN)
        for b in btypen:
            print(f"   BELEGTYP {b['BELEGTYP']:>4}  →  {b['Anzahl']:>6} Datensätze")
    except Exception as e:
        print(f"   BELEGTYP-Abfrage fehlgeschlagen: {e}")

    # ── Spaltennamen dynamisch ermitteln ──────────────────────────────────────
    spaltennamen = {s['COLUMN_NAME'].upper() for s in schema}

    def hat(col): return col.upper() in spaltennamen

    # Artikelspalte in Kopftabelle? (manchmal direkt, meist nur in Position)
    artikel_in_kopf = hat("ARTNR") or hat("ARTNR1")

    # Positionstabellen-Name ermitteln
    pos_name = None
    for t in pos_tabs:
        n = t['TABLE_NAME']
        if n != "ANGAUFGUT":
            pos_name = n
            break

    # ── PIA in Kopftabelle (falls Artikel direkt drin) ────────────────────────
    if artikel_in_kopf:
        trennlinie("5a. PIA-Angebote in ANGAUFGUT (Artikel direkt im Kopf)")
        art_col = "ARTNR1" if hat("ARTNR1") else "ARTNR"
        sql = f"""
            SELECT TOP 20 *
            FROM ANGAUFGUT
            WHERE {art_col} LIKE '%PIA%'
            ORDER BY LFDNR DESC
        """
        try:
            col_list, rows = q(conn, sql)
            _print_rows(col_list, rows, max_cols=12)
        except Exception as e:
            print(f"   Fehler: {e}")

    # ── PIA über Positionstabelle suchen ─────────────────────────────────────
    if pos_name:
        trennlinie(f"5b. PIA-Treffer über {pos_name}")
        sql_pos_cols = f"""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{pos_name}'
            ORDER BY ORDINAL_POSITION
        """
        _, pos_schema = q(conn, sql_pos_cols)
        pos_spalten = {s['COLUMN_NAME'].upper() for s in pos_schema}

        art_col = None
        for c in ["ARTNR1", "ARTNR", "ARTIKELNR"]:
            if c in pos_spalten:
                art_col = c
                break

        bez_col = None
        for c in ["ABEZ1", "ARTBEZ", "BEZEICHNUNG", "BEZ"]:
            if c in pos_spalten:
                bez_col = c
                break

        if art_col or bez_col:
            bedingungen = []
            if art_col:
                bedingungen.append(f"p.{art_col} LIKE '%PIA%'")
            if bez_col:
                bedingungen.append(f"p.{bez_col} LIKE '%PIA%'")
            where = " OR ".join(bedingungen)

            # Kopfspalten für JOIN ermitteln
            kopf_cols = []
            for c in ["LFDNR", "BELEGTYP", "ADRNR", "DATUM", "BELEGNR",
                      "ANGNR", "AUFNR", "KUNDENNR", "NAME1", "GESAMTBETRAG",
                      "NETTOBETRAG", "SACHBEARB", "VERTRETER"]:
                if hat(c):
                    kopf_cols.append(f"h.{c}")

            kopf_select = ", ".join(kopf_cols[:10]) if kopf_cols else "h.*"

            # FK-Spalte Kopf→Position
            fk = None
            for c in ["ANGAUFGUTID", "LFDANGAUFGUT", "KOPFLFDNR", "HEADID"]:
                if c in pos_spalten:
                    fk = c
                    break

            if fk:
                sql_pia = f"""
                    SELECT TOP 30
                        {kopf_select},
                        p.{art_col or bez_col} AS Artikel,
                        p.{bez_col or art_col} AS Bezeichnung,
                        p.MENGE,
                        p.EKPR,
                        p.VKPR1
                    FROM ANGAUFGUT h
                    JOIN {pos_name} p ON p.{fk} = h.LFDNR
                    WHERE {where}
                    ORDER BY h.LFDNR DESC
                """
                try:
                    col_list, rows = q(conn, sql_pia)
                    print(f"   {len(rows)} Treffer\n")
                    _print_rows(col_list, rows, max_cols=14)
                except Exception as e:
                    print(f"   JOIN-Fehler: {e}")
                    # Fallback: nur Positionstabelle
                    sql_fallback = f"""
                        SELECT TOP 30 *
                        FROM {pos_name}
                        WHERE {where}
                        ORDER BY LFDNR DESC
                    """
                    try:
                        col_list, rows = q(conn, sql_fallback)
                        print(f"   Fallback (nur Position): {len(rows)} Treffer\n")
                        _print_rows(col_list, rows, max_cols=12)
                    except Exception as e2:
                        print(f"   Auch Fallback fehlgeschlagen: {e2}")
            else:
                print(f"   FK-Spalte nicht erkannt. Positionsspalten:")
                for s in pos_schema[:20]:
                    print(f"   {s['COLUMN_NAME']}")
        else:
            print(f"   Artikelspalte in {pos_name} nicht erkannt")
            print(f"   Spalten: {[s['COLUMN_NAME'] for s in pos_schema[:15]]}")
    else:
        # Letzte Option: direkte Volltext-Suche in ANGAUFGUT
        trennlinie("5c. Direkte PIA-Suche in ANGAUFGUT (kein JOIN)")
        for name_col in ["NAME1", "MATCHCODE", "SUCHBEGRIFF", "BEZEICHNUNG"]:
            if hat(name_col):
                sql = f"""
                    SELECT TOP 20 *
                    FROM ANGAUFGUT
                    WHERE {name_col} LIKE '%PIA%'
                    ORDER BY LFDNR DESC
                """
                try:
                    col_list, rows = q(conn, sql)
                    if rows:
                        print(f"   Treffer über {name_col}: {len(rows)}\n")
                        _print_rows(col_list, rows, max_cols=12)
                        break
                except Exception:
                    pass

    conn.close()
    print("\n[OK] Fertig.")


def _print_rows(col_list, rows, max_cols=12):
    if not rows:
        print("   (keine Treffer)")
        return
    cols = col_list[:max_cols]
    breite = 20
    header = "  ".join(f"{c:<{breite}}"[:breite] for c in cols)
    print("   " + header)
    print("   " + "-" * len(header))
    for r in rows:
        zeile = "  ".join(
            f"{str(r.get(c, '') or ''):<{breite}}"[:breite]
            for c in cols
        )
        print("   " + zeile)


if __name__ == "__main__":
    main()
