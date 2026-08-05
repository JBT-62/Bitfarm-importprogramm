#!/usr/bin/env python3
"""
suche_pia_anfrage2.py
Sucht PIA-Anfragen in ANFRAGE/ANFRAGEPOS und ANGEBOT/ANGAUFPOS.

Ausführen:
    python 99_scripts/suche_pia_anfrage2.py
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
    sys.exit("FEHLER: pyodbc fehlt. pip install pyodbc")


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


def schema(conn, tabelle):
    _, rows = q(conn, """
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
    """, [tabelle])
    return {r['COLUMN_NAME'].upper(): r['DATA_TYPE'] for r in rows}, \
           [r['COLUMN_NAME'] for r in rows]


def trenn(titel):
    print(f"\n{'─'*64}\n  {titel}\n{'─'*64}")


def zeige(cols, rows, max_breite=22, max_cols=10):
    if not rows:
        print("  (keine Treffer)")
        return
    anzahl_cols = min(len(cols), max_cols)
    sichtbar = cols[:anzahl_cols]
    header = "  ".join(f"{c:<{max_breite}}"[:max_breite] for c in sichtbar)
    print(f"  {header}")
    print(f"  {'-' * len(header)}")
    for r in rows:
        zeile = "  ".join(
            f"{str(r.get(c) or ''):<{max_breite}}"[:max_breite]
            for c in sichtbar
        )
        print(f"  {zeile}")
    if len(rows) == 30:
        print("  ... (max. 30 Zeilen angezeigt)")


def main():
    conn = ee_connect()
    like = "%PIA%"

    # ── ANFRAGE Schema ────────────────────────────────────────────────────────
    trenn("1. ANFRAGE – Spalten")
    anf_typen, anf_cols = schema(conn, "ANFRAGE")
    for c in anf_cols:
        print(f"  {c:<35} {anf_typen[c.upper()]}")

    # ── ANFRAGEPOS Schema ─────────────────────────────────────────────────────
    trenn("2. ANFRAGEPOS – Spalten")
    pos_typen, pos_cols = schema(conn, "ANFRAGEPOS")
    for c in pos_cols:
        print(f"  {c:<35} {pos_typen[c.upper()]}")

    # ── PIA in ANFRAGEPOS suchen ──────────────────────────────────────────────
    trenn("3. PIA-Treffer in ANFRAGEPOS")

    # Artikelspalte ermitteln
    art_col = next((c for c in ["ARTNR1", "ARTNR", "ARTIKELNR"] if c in pos_typen), None)
    bez_col = next((c for c in ["ABEZ1", "ARTBEZ", "BEZEICHNUNG", "BEZ"] if c in pos_typen), None)
    mng_col = next((c for c in ["MENGE", "ANZAHL"] if c in pos_typen), None)
    vk_col  = next((c for c in ["VKPR1", "VK1", "VKPREIS", "PREIS"] if c in pos_typen), None)
    ek_col  = next((c for c in ["EKPR", "EK1", "EKPREIS"] if c in pos_typen), None)

    print(f"  Artikel-Spalte : {art_col}")
    print(f"  Bez-Spalte     : {bez_col}")
    print(f"  Mengen-Spalte  : {mng_col}")

    if not (art_col or bez_col):
        print("  WARNUNG: Keine Artikelspalte erkannt – zeige alle ANFRAGEPOS-Spalten:")
        print(f"  {pos_cols}")
    else:
        bed = []
        if art_col: bed.append(f"p.{art_col} LIKE ?")
        if bez_col: bed.append(f"p.{bez_col} LIKE ?")
        params = [like] * len(bed)

        # FK Kopf→Position
        fk = next((c for c in ["ANFRAGELFDNR", "ANFRAGEID", "KOPFLFDNR", "LFDANFRAGE"]
                   if c in pos_typen), None)
        print(f"  FK-Spalte      : {fk}\n")

        # Kopfspalten die wir zeigen wollen
        kopf_auswahl = []
        for c in ["LFDNR", "KNDNR", "DATUM", "ERFASSDATUM", "STATUS",
                  "NAME1", "MATCHCODE", "SACHBEARBEITNR", "BETREUNR",
                  "BELEGNR", "ANFRAGNR", "BETREFF", "PROJEKT"]:
            if c.upper() in anf_typen:
                kopf_auswahl.append(f"h.{c}")

        pos_auswahl = []
        for c in [art_col, bez_col, mng_col, vk_col, ek_col]:
            if c:
                pos_auswahl.append(f"p.{c}")

        select_cols = (kopf_auswahl[:6] + pos_auswahl)[:14]
        select = ", ".join(select_cols) if select_cols else "h.*, p.*"

        if fk:
            sql = f"""
                SELECT TOP 30 {select}
                FROM ANFRAGE h
                JOIN ANFRAGEPOS p ON p.{fk} = h.LFDNR
                WHERE {' OR '.join(bed)}
                ORDER BY h.LFDNR DESC
            """
        else:
            sql = f"""
                SELECT TOP 30 {', '.join(pos_auswahl) or '*'}
                FROM ANFRAGEPOS p
                WHERE {' OR '.join(bed)}
                ORDER BY p.LFDNR DESC
            """

        try:
            col_list, rows = q(conn, sql, params)
            print(f"  {len(rows)} Treffer:\n")
            zeige(col_list, rows)
        except Exception as e:
            print(f"  Fehler: {e}")
            # Nur ANFRAGEPOS direkt
            sql2 = f"SELECT TOP 20 * FROM ANFRAGEPOS WHERE {' OR '.join(bed)}"
            try:
                col_list, rows = q(conn, sql2, params)
                print(f"  Fallback – {len(rows)} Treffer:\n")
                zeige(col_list, rows)
            except Exception as e2:
                print(f"  Auch Fallback fehlgeschlagen: {e2}")

    # ── ANGEBOT Schema + PIA ──────────────────────────────────────────────────
    trenn("4. ANGEBOT – Spalten")
    ang_typen, ang_cols = schema(conn, "ANGEBOT")
    for c in ang_cols:
        print(f"  {c:<35} {ang_typen[c.upper()]}")

    # ── PIA in ANGAUFPOS suchen (Aufträge/Angebote) ───────────────────────────
    trenn("5. ANGAUFPOS – Spalten + PIA-Treffer")
    apos_typen, apos_cols = schema(conn, "ANGAUFPOS")
    print("  Spalten:")
    for c in apos_cols[:25]:
        print(f"  {c:<35} {apos_typen[c.upper()]}")
    if len(apos_cols) > 25:
        print(f"  ... ({len(apos_cols) - 25} weitere)")

    art_col2 = next((c for c in ["ARTNR1", "ARTNR", "ARTIKELNR"] if c in apos_typen), None)
    bez_col2 = next((c for c in ["ABEZ1", "ARTBEZ", "BEZEICHNUNG"] if c in apos_typen), None)
    fk2 = next((c for c in ["ANGAUFGUTLFDNR", "ANGAUFLFDNR", "KOPFLFDNR", "LFDANGAUFGUT"]
                if c in apos_typen), None)

    print(f"\n  Artikel: {art_col2}  Bez: {bez_col2}  FK: {fk2}")

    if (art_col2 or bez_col2) and fk2:
        bed2 = []
        if art_col2: bed2.append(f"p.{art_col2} LIKE ?")
        if bez_col2: bed2.append(f"p.{bez_col2} LIKE ?")
        params2 = [like] * len(bed2)

        sql_auf = f"""
            SELECT TOP 20
                h.LFDNR, h.ANGEBOT, h.AUFTRAG, h.KNDNR,
                h.ERFASSDATUM, h.STATUS, h.ERLEDIGT,
                p.{art_col2 or bez_col2} AS Artikel,
                p.{bez_col2 or art_col2} AS Bezeichnung,
                p.MENGE
            FROM ANGAUFGUT h
            JOIN ANGAUFPOS p ON p.{fk2} = h.LFDNR
            WHERE {' OR '.join(bed2)}
            ORDER BY h.LFDNR DESC
        """
        try:
            col_list, rows = q(conn, sql_auf, params2)
            print(f"\n  {len(rows)} PIA-Treffer in ANGAUFGUT:\n")
            zeige(col_list, rows)
        except Exception as e:
            print(f"\n  Fehler: {e}")

    conn.close()
    print("\n[OK] Fertig.")


if __name__ == "__main__":
    main()
