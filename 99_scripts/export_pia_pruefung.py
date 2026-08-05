#!/usr/bin/env python3
"""
export_pia_pruefung.py
Liest PIA-Stammdaten aus eEvolution und erstellt eine Excel-Datei
zur Prüfung und Freigabe durch den Produktionsleiter.

Ausführen (im Projektordner):
    python 99_scripts/export_pia_pruefung.py

Ergebnis:
    PIA_Pruefung_JJJJMMTT.xlsx  (im Projektordner)

Voraussetzungen:
    pip install pyodbc openpyxl python-dotenv
    .env mit EV_* Variablen (liegt bereits vor)
"""

import os
import sys
from datetime import date

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import pyodbc
except ImportError:
    sys.exit("FEHLER: pyodbc fehlt. Bitte: pip install pyodbc")

try:
    import openpyxl
    from openpyxl.styles import (
        Font, PatternFill, Alignment, Border, Side, numbers
    )
    from openpyxl.utils import get_column_letter
except ImportError:
    sys.exit("FEHLER: openpyxl fehlt. Bitte: pip install openpyxl")


# ── Verbindung ───────────────────────────────────────────────────────────────

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
    try:
        conn = pyodbc.connect(conn_str, timeout=10)
        print(f"[OK] Verbunden mit {server}/{database}")
        return conn
    except Exception as e:
        sys.exit(f"FEHLER Verbindung eEvolution: {e}")


def abfragen(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or [])
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ── SQL-Abfragen ─────────────────────────────────────────────────────────────

SQL_ARTIKEL = """
    SELECT
        a.LFDNR        AS ID,
        a.ARTNR1       AS Artikelnummer,
        a.ABEZ1        AS Bezeichnung,
        a.ABEZ2        AS Bezeichnung2,
        a.MENGENSCHL   AS Einheit,
        a.VKPR1        AS VK_Preis,
        a.EKPR         AS EK_Preis,
        al.CONTENT     AS Langtext
    FROM ARTIKEL a
    LEFT JOIN (
        SELECT LFDARTNR, MAX(CONTENT) AS CONTENT
        FROM ARTIKELLONG
        GROUP BY LFDARTNR
    ) al ON al.LFDARTNR = a.LFDNR
    WHERE a.ABEZ1 LIKE ? OR a.ARTNR1 LIKE ?
    ORDER BY a.ARTNR1
"""

SQL_STUECKLISTE = """
    SELECT
        p.LFD_NR       AS SB_ID,
        a_end.ARTNR1   AS Endprodukt_Nr,
        a_end.ABEZ1    AS Endprodukt,
        a_komp.ARTNR1  AS Komponente_Nr,
        a_komp.ABEZ1   AS Komponente,
        i.MENGE        AS Menge,
        i.MENGENSCHL   AS Einheit,
        a_komp.EKPR    AS EK_Preis
    FROM PRODLIST p
    JOIN ARTIKEL a_end ON a_end.LFDNR = p.ART_NR
    JOIN PRODINHALT i ON i.LIST_NR = p.LFD_NR
    JOIN ARTIKEL a_komp ON a_komp.LFDNR = i.ART_NR
    WHERE a_end.ABEZ1 LIKE ? OR a_end.ARTNR1 LIKE ?
    ORDER BY p.LFD_NR, i.LFD_NR
"""

SQL_STUECKLISTE_FALLBACK = """
    SELECT
        a_end.ARTNR1      AS Endprodukt_Nr,
        a_end.ABEZ1       AS Endprodukt,
        a_komp.ARTNR1     AS Komponente_Nr,
        a_komp.ABEZ1      AS Komponente,
        s.MENGE           AS Menge,
        a_komp.MENGENSCHL AS Einheit,
        a_komp.EKPR       AS EK_Preis
    FROM ARTSTUELI s
    JOIN ARTIKEL a_end ON a_end.LFDNR = s.LFDARTNR1
    JOIN ARTIKEL a_komp ON a_komp.LFDNR = s.LFDARTNR2
    WHERE a_end.ABEZ1 LIKE ? OR a_end.ARTNR1 LIKE ?
    ORDER BY s.LFDARTNR1, s.LFDARTNR2
"""

SQL_LIEFERANTEN = """
    SELECT DISTINCT
        a_komp.ARTNR1  AS Komponente_Nr,
        a_komp.ABEZ1   AS Komponente,
        l.ADRNR        AS Lieferant_ID,
        l.NAME1        AS Lieferant,
        l.NAME2        AS Lieferant2,
        l.ORT          AS Ort,
        a_komp.EKPR    AS EK_Preis,
        NULL           AS Lieferzeit_Tage
    FROM PRODLIST p
    JOIN ARTIKEL a_end ON a_end.LFDNR = p.ART_NR
    JOIN PRODINHALT i ON i.LIST_NR = p.LFD_NR
    JOIN ARTIKEL a_komp ON a_komp.LFDNR = i.ART_NR
    LEFT JOIN LIEFERANT l ON l.ADRNR = a_komp.LFDLIEFNR
    WHERE a_end.ABEZ1 LIKE ? OR a_end.ARTNR1 LIKE ?
    ORDER BY a_komp.ARTNR1, l.NAME1
"""

SQL_LIEFERANTEN_FALLBACK = """
    SELECT DISTINCT
        a_komp.ARTNR1     AS Komponente_Nr,
        a_komp.ABEZ1      AS Komponente,
        l.ADRNR           AS Lieferant_ID,
        l.NAME1           AS Lieferant,
        l.NAME2           AS Lieferant2,
        l.ORT             AS Ort,
        a_komp.EKPR       AS EK_Preis,
        NULL              AS Lieferzeit_Tage
    FROM ARTSTUELI s
    JOIN ARTIKEL a_end ON a_end.LFDNR = s.LFDARTNR1
    JOIN ARTIKEL a_komp ON a_komp.LFDNR = s.LFDARTNR2
    LEFT JOIN LIEFERANT l ON l.ADRNR = a_komp.LFDLIEFNR
    WHERE a_end.ABEZ1 LIKE ? OR a_end.ARTNR1 LIKE ?
    ORDER BY a_komp.ARTNR1, l.NAME1
"""


# ── Excel-Stile ──────────────────────────────────────────────────────────────

BLAU_DUNKEL = "1B4F8A"
BLAU_HELL   = "D6E4F7"
GRAU_HELL   = "F5F5F5"
GELB        = "FFF2CC"
GRUEN       = "E2EFDA"
WEISS       = "FFFFFF"

def stil_header(fett=True, schriftfarbe="FFFFFF", hintergrund=BLAU_DUNKEL, fontsize=10):
    return {
        "font": Font(name="Arial", bold=fett, color=schriftfarbe, size=fontsize),
        "fill": PatternFill("solid", fgColor=hintergrund),
        "alignment": Alignment(horizontal="center", vertical="center", wrap_text=True),
        "border": Border(
            bottom=Side(style="thin", color="AAAAAA"),
            right=Side(style="thin", color="DDDDDD"),
        ),
    }

def stil_daten(hintergrund=WEISS, fett=False, zahl=False):
    return {
        "font": Font(name="Arial", bold=fett, size=9),
        "fill": PatternFill("solid", fgColor=hintergrund),
        "alignment": Alignment(vertical="center", wrap_text=False),
        "border": Border(
            bottom=Side(style="thin", color="EEEEEE"),
            right=Side(style="thin", color="EEEEEE"),
        ),
    }

def stil_titel():
    return {
        "font": Font(name="Arial", bold=True, size=14, color=BLAU_DUNKEL),
        "alignment": Alignment(vertical="center"),
    }

def wende_stil(cell, stil_dict):
    for attr, val in stil_dict.items():
        setattr(cell, attr, val)

def schreibe_header_zeile(ws, zeile, spalten):
    for col_idx, text in enumerate(spalten, 1):
        cell = ws.cell(row=zeile, column=col_idx, value=text)
        wende_stil(cell, stil_header())

def schreibe_daten_zeile(ws, zeile, werte, abwechselnd=True):
    bg = BLAU_HELL if (abwechselnd and zeile % 2 == 0) else WEISS
    for col_idx, wert in enumerate(werte, 1):
        cell = ws.cell(row=zeile, column=col_idx, value=wert)
        s = stil_daten(hintergrund=bg)
        # Zahlen rechtsbündig
        if isinstance(wert, (int, float)):
            s["alignment"] = Alignment(horizontal="right", vertical="center")
            if col_idx > 3:  # Preisspalten
                cell.number_format = '#,##0.00 €'
        wende_stil(cell, s)

def spaltenbreiten(ws, breiten):
    for col_letter, breite in breiten.items():
        ws.column_dimensions[col_letter].width = breite

def zeile_einfrieren(ws, ab_zeile):
    ws.freeze_panes = ws.cell(row=ab_zeile, column=1)


# ── Blatt: Übersicht ─────────────────────────────────────────────────────────

def blatt_uebersicht(wb, filter_str, artikel, stk, lieferanten, heute):
    ws = wb.create_sheet("Übersicht", 0)
    ws.sheet_view.showGridLines = False

    ws.row_dimensions[1].height = 40
    ws.row_dimensions[3].height = 20

    # Titel
    cell = ws["B1"]
    cell.value = f"K&F PIA – Stammdaten-Prüfung für Odoo-Import"
    wende_stil(cell, stil_titel())
    ws.row_dimensions[1].height = 36

    ws["B2"].value = f"Exportiert am {heute.strftime('%d.%m.%Y')}  ·  Filter: '{filter_str}'"
    ws["B2"].font = Font(name="Arial", size=9, color="888888")

    # Kennzahlen
    daten = [
        ("Gefundene Artikel",    len(artikel)),
        ("Stücklisten-Pos.",     len(stk)),
        ("Lieferanten",          len(lieferanten)),
        ("Freigabe-Status",      "⬜  Ausstehend"),
    ]
    ws["B4"].value = "Zusammenfassung"
    wende_stil(ws["B4"], {"font": Font(name="Arial", bold=True, size=10, color=BLAU_DUNKEL)})

    for i, (label, wert) in enumerate(daten, 5):
        ws.cell(row=i, column=2, value=label).font = Font(name="Arial", size=9)
        cell = ws.cell(row=i, column=3, value=wert)
        cell.font = Font(name="Arial", bold=True, size=9)

    ws["B10"].value = "Hinweis für den Produktionsleiter"
    wende_stil(ws["B10"], {"font": Font(name="Arial", bold=True, size=10, color=BLAU_DUNKEL)})
    ws["B11"].value = ("Bitte alle vier Blätter prüfen und das Blatt 'Freigabe' ausfüllen.\n"
                       "Korrekturen direkt in die gelben Zellen eintragen.")
    ws["B11"].font = Font(name="Arial", size=9)
    ws["B11"].alignment = Alignment(wrap_text=True)
    ws.row_dimensions[11].height = 30

    spaltenbreiten(ws, {"A": 3, "B": 32, "C": 20})


# ── Blatt: Artikel ───────────────────────────────────────────────────────────

def blatt_artikel(wb, daten):
    ws = wb.create_sheet("PIA Artikel")
    ws.sheet_view.showGridLines = False

    spalten = ["ID (EE)", "Artikelnummer", "Bezeichnung", "Bezeichnung 2",
               "Einheit", "VK-Preis €", "EK-Preis €", "Langtext"]
    schreibe_header_zeile(ws, 1, spalten)
    ws.row_dimensions[1].height = 22

    for i, row in enumerate(daten, 2):
        werte = [
            row.get("ID"),
            row.get("Artikelnummer"),
            row.get("Bezeichnung"),
            row.get("Bezeichnung2"),
            row.get("Einheit"),
            row.get("VK_Preis"),
            row.get("EK_Preis"),
            row.get("Langtext"),
        ]
        schreibe_daten_zeile(ws, i, werte)

    spaltenbreiten(ws, {
        "A": 10, "B": 18, "C": 32, "D": 20,
        "E": 10, "F": 14, "G": 14, "H": 40,
    })
    zeile_einfrieren(ws, 2)
    ws.auto_filter.ref = f"A1:H{len(daten)+1}"


# ── Blatt: Stückliste ────────────────────────────────────────────────────────

def blatt_stueckliste(wb, daten):
    ws = wb.create_sheet("Stückliste")
    ws.sheet_view.showGridLines = False

    spalten = ["Endprodukt-Nr.", "Endprodukt", "Komponente-Nr.",
               "Komponente", "Menge", "Einheit", "EK-Preis €",
               "✓ Korrekt?", "Anmerkung"]
    schreibe_header_zeile(ws, 1, spalten)
    ws.row_dimensions[1].height = 22

    for i, row in enumerate(daten, 2):
        werte = [
            row.get("Endprodukt_Nr"),
            row.get("Endprodukt"),
            row.get("Komponente_Nr"),
            row.get("Komponente"),
            row.get("Menge"),
            row.get("Einheit"),
            row.get("EK_Preis"),
            "",   # Freigabe-Checkbox (manuell)
            "",   # Anmerkung (manuell)
        ]
        schreibe_daten_zeile(ws, i, werte)
        # Freigabe- und Anmerkungsfelder gelb markieren
        for col in [8, 9]:
            cell = ws.cell(row=i, column=col)
            cell.fill = PatternFill("solid", fgColor=GELB)
            cell.font = Font(name="Arial", size=9)

    spaltenbreiten(ws, {
        "A": 16, "B": 28, "C": 16, "D": 28,
        "E": 8,  "F": 10, "G": 14, "H": 14, "I": 30,
    })
    zeile_einfrieren(ws, 2)
    ws.auto_filter.ref = f"A1:I{len(daten)+1}"

    # Legende
    leg_row = len(daten) + 3
    ws.cell(row=leg_row, column=1, value="Legende:").font = Font(name="Arial", bold=True, size=8)
    ws.cell(row=leg_row, column=2, value="Gelbe Zellen = vom Produktionsleiter auszufüllen").font = Font(name="Arial", size=8, color="888888")


# ── Blatt: Lieferanten ───────────────────────────────────────────────────────

def blatt_lieferanten(wb, daten):
    ws = wb.create_sheet("Lieferanten")
    ws.sheet_view.showGridLines = False

    spalten = ["Komponente-Nr.", "Komponente", "Lieferant-ID (EE)",
               "Lieferant", "Ort", "EK-Preis €", "Lieferzeit (Tage)",
               "✓ Korrekt?", "Anmerkung"]
    schreibe_header_zeile(ws, 1, spalten)
    ws.row_dimensions[1].height = 22

    for i, row in enumerate(daten, 2):
        name = row.get("Lieferant", "")
        if row.get("Lieferant2"):
            name = f"{name} {row['Lieferant2']}".strip()
        werte = [
            row.get("Komponente_Nr"),
            row.get("Komponente"),
            row.get("Lieferant_ID"),
            name,
            row.get("Ort"),
            row.get("EK_Preis"),
            row.get("Lieferzeit_Tage"),
            "",
            "",
        ]
        schreibe_daten_zeile(ws, i, werte)
        for col in [8, 9]:
            cell = ws.cell(row=i, column=col)
            cell.fill = PatternFill("solid", fgColor=GELB)
            cell.font = Font(name="Arial", size=9)

    spaltenbreiten(ws, {
        "A": 16, "B": 28, "C": 14, "D": 30,
        "E": 18, "F": 14, "G": 16, "H": 14, "I": 30,
    })
    zeile_einfrieren(ws, 2)
    ws.auto_filter.ref = f"A1:I{len(daten)+1}"


# ── Blatt: Freigabe ──────────────────────────────────────────────────────────

def blatt_freigabe(wb, heute):
    ws = wb.create_sheet("Freigabe")
    ws.sheet_view.showGridLines = False

    # Titel
    ws["B2"].value = "Freigabe – PIA Stammdaten-Prüfung"
    wende_stil(ws["B2"], {
        "font": Font(name="Arial", bold=True, size=14, color=BLAU_DUNKEL),
        "alignment": Alignment(vertical="center"),
    })
    ws.row_dimensions[2].height = 32

    ws["B3"].value = f"Bitte vollständig ausfüllen und als gescanntes PDF zurücksenden."
    ws["B3"].font = Font(name="Arial", size=9, color="888888")

    felder = [
        (6,  "Prüfer (Name)",              ""),
        (7,  "Abteilung",                  "Produktion"),
        (8,  "Datum der Prüfung",          heute.strftime("%d.%m.%Y")),
        (9,  "Stückliste geprüft?",        "☐  Ja    ☐  Nein, Korrekturen siehe Blatt 'Stückliste'"),
        (10, "Lieferanten geprüft?",       "☐  Ja    ☐  Nein, Korrekturen siehe Blatt 'Lieferanten'"),
        (11, "Artikel-Stammdaten OK?",     "☐  Ja    ☐  Nein, Korrekturen siehe Blatt 'PIA Artikel'"),
        (13, "Gesamtfreigabe",             "☐  Freigegeben    ☐  Nicht freigegeben (Korrekturen nötig)"),
        (15, "Unterschrift Produktionsleiter", ""),
        (17, "Unterschrift Projektleitung",   ""),
    ]

    for zeile, label, vorbelegung in felder:
        lbl = ws.cell(row=zeile, column=2, value=label)
        lbl.font = Font(name="Arial", bold=True, size=10)

        val = ws.cell(row=zeile, column=3, value=vorbelegung)
        val.font = Font(name="Arial", size=10)
        val.fill = PatternFill("solid", fgColor=GELB)
        val.alignment = Alignment(vertical="center")
        ws.row_dimensions[zeile].height = 24

        # Unterschriftszeilen extra hoch
        if "Unterschrift" in label:
            ws.row_dimensions[zeile].height = 40
            val.value = ""
            val.border = Border(bottom=Side(style="medium", color="333333"))

    # Anmerkungsfeld
    ws["B19"].value = "Allgemeine Anmerkungen / Korrekturen:"
    ws["B19"].font = Font(name="Arial", bold=True, size=10)
    ws.merge_cells("B20:F25")
    anm = ws["B20"]
    anm.fill = PatternFill("solid", fgColor=GELB)
    anm.alignment = Alignment(vertical="top", wrap_text=True)
    anm.border = Border(
        top=Side(style="thin", color="AAAAAA"),
        bottom=Side(style="thin", color="AAAAAA"),
        left=Side(style="thin", color="AAAAAA"),
        right=Side(style="thin", color="AAAAAA"),
    )
    for r in range(20, 26):
        ws.row_dimensions[r].height = 18

    spaltenbreiten(ws, {"A": 3, "B": 35, "C": 55, "D": 10})


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    filter_str = "PIA"
    like = f"%{filter_str}%"
    heute = date.today()

    conn = ee_connect()

    print(f"[1] Lese Artikel ({filter_str})...")
    artikel = abfragen(conn, SQL_ARTIKEL, [like, like])
    print(f"    {len(artikel)} Artikel gefunden")

    print("[2] Lese Stückliste (PRODLIST)...")
    stk = abfragen(conn, SQL_STUECKLISTE, [like, like])
    use_artstueli = not stk
    if use_artstueli:
        print("    PRODLIST leer – versuche ARTSTUELI...")
        stk = abfragen(conn, SQL_STUECKLISTE_FALLBACK, [like, like])
    print(f"    {len(stk)} Positionen")

    print("[3] Lese Lieferanten...")
    try:
        sql_lief = SQL_LIEFERANTEN_FALLBACK if use_artstueli else SQL_LIEFERANTEN
        lieferanten = abfragen(conn, sql_lief, [like, like])
    except Exception as e:
        print(f"    Lieferanten-Abfrage fehlgeschlagen ({e}) – Blatt bleibt leer")
        lieferanten = []
    print(f"    {len(lieferanten)} Lieferanten-Einträge")

    conn.close()

    print("[4] Erstelle Excel...")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Standard-Sheet entfernen

    blatt_uebersicht(wb, filter_str, artikel, stk, lieferanten, heute)
    blatt_artikel(wb, artikel)
    blatt_stueckliste(wb, stk)
    blatt_lieferanten(wb, lieferanten)
    blatt_freigabe(wb, heute)

    dateiname = f"PIA_Pruefung_{heute.strftime('%Y%m%d')}.xlsx"
    wb.save(dateiname)

    print(f"\n[OK] Gespeichert: {dateiname}")
    print(f"     Bitte an den Produktionsleiter weiterleiten.")


if __name__ == "__main__":
    main()
