#!/usr/bin/env python3
"""
mapping_report.py
Vergleicht eEvolution-Schema (eevo_schema.json) mit Odoo 19-Schema
(odoo_schema.json) und erzeugt einen Excel-Mapping-Report.

Ausführen:
    python 99_scripts/mapping_report.py

Ergebnis:
    Mapping_EE_Odoo_JJJJMMTT.xlsx
      Blatt 1: Übersicht (Gruppen + Ampel)
      Blatt 2-N: Pro Stammdaten-Gruppe (eEvolution-Feld → Odoo-Feld)
      Letztes Blatt: Offene Punkte (Lücken, Typ-Konflikte)
"""

import json, sys
from pathlib import Path
from datetime import date

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    sys.exit("FEHLER: openpyxl fehlt.  pip install openpyxl")


# ── Schemas laden ─────────────────────────────────────────────────────────────

def lade(pfad):
    for p in [Path(pfad), Path("..") / pfad]:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    return None


# ── Mapping-Definition ────────────────────────────────────────────────────────
# Logische Gruppen: Name → { ee_tabellen, odoo_modell, felder: [(ee_col, odoo_field, notiz)] }

MAPPING = [
    {
        "gruppe":    "Kunden (res.partner)",
        "ee":        ["ADRESS", "KUNDE"],
        "odoo":      "res.partner",
        "filter_ee": "ADRESS.KUNDE = 1",
        "felder": [
            # (eEvolution-Tabelle, eEvolution-Spalte, Odoo-Feld, Transformation/Notiz)
            ("ADRESS",  "ADRNR",      "ref",              "external_id: ev_kuf_adr_<ADRNR>"),
            ("ADRESS",  "KUNDE",      "customer_rank",    "1 wenn KUNDE=1"),
            ("LIEFERANT","NAME1",     "name",             "aus LIEFERANT.NAME1 oder ADRESS"),
            ("LIEFERANT","NAME2",     "name",             "ggf. anhängen"),
            ("LIEFERANT","STRASSE",   "street",           ""),
            ("LIEFERANT","PLZ",       "zip",              ""),
            ("LIEFERANT","ORT",       "city",             ""),
            ("LIEFERANT","LAND",      "country_id",       "ISO2-Code → res.country"),
            ("LIEFERANT","TELEFON",   "phone",            ""),
            ("LIEFERANT","EMAIL",     "email",            ""),
            ("KUNDE",   "ZBEDING",    "property_payment_term_id", "→ account.payment.term"),
            ("KUNDE",   "VERMITNR",   "user_id",          "Vertreter → res.users"),
        ],
    },
    {
        "gruppe":    "Lieferanten (res.partner)",
        "ee":        ["ADRESS", "LIEFERANT"],
        "odoo":      "res.partner",
        "filter_ee": "ADRESS.LIEFERANT = 1",
        "felder": [
            ("ADRESS",   "ADRNR",    "ref",             "external_id: ev_kuf_adr_<ADRNR>"),
            ("ADRESS",   "LIEFERANT","supplier_rank",   "1 wenn LIEFERANT=1"),
            ("LIEFERANT","NAME1",    "name",            ""),
            ("LIEFERANT","NAME2",    "name",            "ggf. anhängen"),
            ("LIEFERANT","STRASSE",  "street",          ""),
            ("LIEFERANT","PLZ",      "zip",             ""),
            ("LIEFERANT","ORT",      "city",            ""),
            ("LIEFERANT","LAND",     "country_id",      "ISO2 → res.country"),
            ("LIEFERANT","TELEFON",  "phone",           ""),
            ("LIEFERANT","EMAIL",    "email",           ""),
            ("LIEFERANT","ZBEDING",  "property_supplier_payment_term_id", ""),
        ],
    },
    {
        "gruppe":    "Ansprechpartner (res.partner contact)",
        "ee":        ["ADRANSPRECH"],
        "odoo":      "res.partner",
        "filter_ee": "type='contact', parent_id=ADRNR",
        "felder": [
            ("ADRANSPRECH","ADRNR",     "parent_id",       "→ res.partner (Firma)"),
            ("ADRANSPRECH","NAME1",     "name",            ""),
            ("ADRANSPRECH","VORNAME",   "name",            "Vorname + NAME1"),
            ("ADRANSPRECH","TELEFON",   "phone",           ""),
            ("ADRANSPRECH","EMAIL",     "email",           ""),
            ("ADRANSPRECH","POSITION",  "function",        "Berufsbezeichnung"),
        ],
    },
    {
        "gruppe":    "Lieferadressen (res.partner delivery)",
        "ee":        ["KNDLIEFER"],
        "odoo":      "res.partner",
        "filter_ee": "type='delivery'",
        "felder": [
            ("KNDLIEFER","KNDNR",    "parent_id",   "→ res.partner Kunde"),
            ("KNDLIEFER","NAME1",    "name",         ""),
            ("KNDLIEFER","STRASSE",  "street",       ""),
            ("KNDLIEFER","PLZ",      "zip",          ""),
            ("KNDLIEFER","ORT",      "city",         ""),
            ("KNDLIEFER","LAND",     "country_id",   ""),
        ],
    },
    {
        "gruppe":    "Artikel (product.template)",
        "ee":        ["ARTIKEL", "ARTIKELLONG"],
        "odoo":      "product.template",
        "felder": [
            ("ARTIKEL",     "LFDNR",      "default_code",    "external_id: ev_kuf_art_<LFDNR>"),
            ("ARTIKEL",     "ARTNR1",     "default_code",    "Interne Referenz"),
            ("ARTIKEL",     "ABEZ1",      "name",            "Produktname"),
            ("ARTIKEL",     "ABEZ2",      "name",            "ggf. in Beschreibung"),
            ("ARTIKEL",     "MENGENSCHL", "uom_id",          "→ uom.uom (Kürzel)"),
            ("ARTIKEL",     "VKPR1",      "list_price",      "Verkaufspreis"),
            ("ARTIKEL",     "EKPR",       "standard_price",  "Einkaufspreis (Kostpreis)"),
            ("ARTIKEL",     "LFDLIEFNR",  "seller_ids",      "→ product.supplierinfo"),
            ("ARTIKEL",     "AGRUPPE",    "categ_id",        "Artikelgruppe → product.category"),
            ("ARTIKELLONG", "CONTENT",    "description",     "Langtext / Verkaufsbeschreibung"),
        ],
    },
    {
        "gruppe":    "Stückliste Produktion (mrp.bom)",
        "ee":        ["PRODLIST", "PRODINHALT"],
        "odoo":      "mrp.bom",
        "felder": [
            ("PRODLIST",   "LFD_NR",   "id (ext)",        "external_id: ev_kuf_bom_<LFD_NR>"),
            ("PRODLIST",   "ART_NR",   "product_tmpl_id", "→ product.template"),
            ("PRODLIST",   "BEZEICHNUNG","name",           "BOM-Bezeichnung"),
            ("PRODINHALT", "LIST_NR",  "bom_id",          "→ mrp.bom"),
            ("PRODINHALT", "ART_NR",   "product_id",      "Komponente → product.product"),
            ("PRODINHALT", "MENGE",    "product_qty",     "Menge"),
            ("PRODINHALT", "MENGENSCHL","product_uom_id", "Einheit → uom.uom"),
        ],
    },
    {
        "gruppe":    "Stückliste Legacy (mrp.bom)",
        "ee":        ["ARTSTUELI"],
        "odoo":      "mrp.bom",
        "felder": [
            ("ARTSTUELI","LFDARTNR1", "product_tmpl_id","Endprodukt → product.template"),
            ("ARTSTUELI","LFDARTNR2", "product_id",     "Komponente → product.product"),
            ("ARTSTUELI","MENGE",     "product_qty",    ""),
            ("ARTSTUELI","ANZAHL",    "product_qty",    "alternativ zu MENGE"),
        ],
    },
    {
        "gruppe":    "Kunden-Angebote (sale.order Angebot)",
        "ee":        ["ANGAUFGUT", "ANGAUFPOS"],
        "odoo":      "sale.order",
        "filter_ee": "ANGAUFGUT.ANGEBOT=1",
        "felder": [
            ("ANGAUFGUT","LFDNR",       "name / ref",      "external_id: ev_kuf_ang_<LFDNR>"),
            ("ANGAUFGUT","KNDNR",       "partner_id",      "→ res.partner"),
            ("ANGAUFGUT","ERFASSDATUM", "date_order",      ""),
            ("ANGAUFGUT","STATUS",      "state",           "draft/sent"),
            ("ANGAUFGUT","VERMITNR",    "user_id",         "→ res.users"),
            ("ANGAUFPOS","LFDANGAUFGUTNR","order_id",      "→ sale.order"),
            ("ANGAUFPOS","LFDARTNR",    "product_id",      "→ product.product"),
            ("ANGAUFPOS","BESTMENGE",   "product_uom_qty", ""),
            ("ANGAUFPOS","PREIS",       "price_unit",      ""),
            ("ANGAUFPOS","RABATT",      "discount",        "Rabatt %"),
            ("ANGAUFPOS","POSNR",       "sequence",        "Positionsnummer"),
            ("ANGAUFPOS","LANGTEXT",    "name",            "Positionsbeschreibung"),
        ],
    },
    {
        "gruppe":    "Kunden-Aufträge (sale.order bestätigt)",
        "ee":        ["ANGAUFGUT", "ANGAUFPOS"],
        "odoo":      "sale.order",
        "filter_ee": "ANGAUFGUT.AUFTRAG=1",
        "felder": [
            ("ANGAUFGUT","LFDNR",       "name",          "external_id: ev_kuf_auf_<LFDNR>"),
            ("ANGAUFGUT","KNDNR",       "partner_id",    "→ res.partner"),
            ("ANGAUFGUT","ERFASSDATUM", "date_order",    ""),
            ("ANGAUFGUT","ERLEDIGT",    "state",         "done/cancel"),
            ("ANGAUFPOS","BESTMENGE",   "product_uom_qty",""),
            ("ANGAUFPOS","LIEFERMENGE", "qty_delivered",  "gelieferte Menge"),
            ("ANGAUFPOS","BISHERRECHMENGE","qty_invoiced","berechnete Menge"),
        ],
    },
    {
        "gruppe":    "Gutschriften (account.move out_refund)",
        "ee":        ["ANGAUFGUT", "ANGAUFPOS"],
        "odoo":      "account.move",
        "filter_ee": "ANGAUFGUT.GUTSCHRIFT=1",
        "felder": [
            ("ANGAUFGUT","LFDNR",       "name",        ""),
            ("ANGAUFGUT","KNDNR",       "partner_id",  "→ res.partner"),
            ("ANGAUFGUT","ERFASSDATUM", "invoice_date",""),
        ],
    },
    {
        "gruppe":    "Eingangsrechnungen (account.move in_invoice)",
        "ee":        ["LIEFRECH"],
        "odoo":      "account.move",
        "filter_ee": "move_type='in_invoice'",
        "felder": [
            ("LIEFRECH","LFDNR",      "name / ref",   "external_id"),
            ("LIEFRECH","ADRNR",      "partner_id",   "→ res.partner Lieferant"),
            ("LIEFRECH","DATUM",      "invoice_date", ""),
            ("LIEFRECH","BETRAG",     "amount_total", ""),
        ],
    },
    {
        "gruppe":    "Zahlungsbedingungen (account.payment.term)",
        "ee":        ["ZAHLBEDING"],
        "odoo":      "account.payment.term",
        "felder": [
            ("ZAHLBEDING","LFDNR",  "id (ext)",  "external_id"),
            ("ZAHLBEDING","BEZ",    "name",       "Bezeichnung"),
            ("ZAHLBEDING","TAGE",   "line_ids",   "Fälligkeitstage"),
        ],
    },
    {
        "gruppe":    "Mengeneinheiten (uom.uom)",
        "ee":        ["MENGENSCHL"],
        "odoo":      "uom.uom",
        "felder": [
            ("MENGENSCHL","LFDNR",  "id (ext)",  ""),
            ("MENGENSCHL","BEZ",    "name",       "Kürzel: Stk, m, kg …"),
            ("MENGENSCHL","LBEZ",   "name",       "Langname"),
        ],
    },
    {
        "gruppe":    "Länder (res.country)",
        "ee":        ["LAND"],
        "odoo":      "res.country",
        "felder": [
            ("LAND","ISO2",  "code",  "ISO2-Code (DE, AT, CH …)"),
            ("LAND","NAME1", "name",  ""),
        ],
    },
    {
        "gruppe":    "Seriennummern (stock.lot serial)",
        "ee":        ["SERNR"],
        "odoo":      "stock.lot",
        "felder": [
            ("SERNR","LFDNR",   "id (ext)",       ""),
            ("SERNR","SERNR",   "name",            "Seriennummer"),
            ("SERNR","LFDARTNR","product_id",      "→ product.product"),
        ],
    },
    {
        "gruppe":    "Chargen (stock.lot)",
        "ee":        ["CHARGEN"],
        "odoo":      "stock.lot",
        "felder": [
            ("CHARGEN","LFDNR",    "id (ext)",    ""),
            ("CHARGEN","CHARGENNR","name",         "Chargennummer"),
            ("CHARGEN","LFDARTNR", "product_id",  "→ product.product"),
        ],
    },
]


# ── Stimmigkeitsprüfung ───────────────────────────────────────────────────────

def pruefe_stimmigkeit(gruppe, odoo_schema):
    """Prüft ob die gemappten Odoo-Felder im Schema vorhanden sind."""
    modell = gruppe["odoo"]
    odoo_felder = {f["name"] for f in odoo_schema.get(modell, [])}
    if not odoo_felder:
        return [f"Modell {modell} nicht in odoo_schema.json"]

    issues = []
    for ee_tbl, ee_col, odoo_field, notiz in gruppe["felder"]:
        if odoo_field in ("id (ext)", "ref"):
            continue  # External IDs, keine direkten Felder
        # Prüfe ob das Odoo-Feld existiert (ignoriere Notiz-Felder)
        kern = odoo_field.split(" / ")[0].split(" (")[0].strip()
        if kern and kern not in odoo_felder:
            issues.append(f"  ⚠ {ee_tbl}.{ee_col} → {modell}.{kern}  (Feld nicht gefunden)")
    return issues


# ── Excel-Stile ───────────────────────────────────────────────────────────────

BLAU_D = "1B4F8A"
BLAU_H = "D6E4F7"
GRUEN  = "E2EFDA"
GELB   = "FFF2CC"
ROT_H  = "FCE4D6"
GRAU   = "F5F5F5"
WEISS  = "FFFFFF"

def hdr(ws, zeile, texte, bg=BLAU_D):
    for col, txt in enumerate(texte, 1):
        c = ws.cell(row=zeile, column=col, value=txt)
        c.font      = Font(name="Arial", bold=True, color="FFFFFF", size=9)
        c.fill      = PatternFill("solid", fgColor=bg)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border    = Border(bottom=Side(style="thin", color="CCCCCC"),
                             right=Side(style="thin", color="CCCCCC"))
    ws.row_dimensions[zeile].height = 22

def dat(ws, zeile, werte, bg=WEISS):
    for col, wert in enumerate(werte, 1):
        c = ws.cell(row=zeile, column=col, value=wert)
        c.font      = Font(name="Arial", size=9)
        c.fill      = PatternFill("solid", fgColor=bg)
        c.alignment = Alignment(vertical="center", wrap_text=False)
        c.border    = Border(bottom=Side(style="thin", color="EEEEEE"),
                             right=Side(style="thin", color="EEEEEE"))

def breite(ws, bmap):
    for col, b in bmap.items():
        ws.column_dimensions[col].width = b

def titel(ws, zeile, text, farbe=BLAU_D):
    ws.cell(row=zeile, column=1, value=text).font = \
        Font(name="Arial", bold=True, size=13, color=farbe)
    ws.row_dimensions[zeile].height = 28


# ── Blatt: Übersicht ──────────────────────────────────────────────────────────

def blatt_uebersicht(wb, eevo_meta, odoo_meta, alle_issues, heute):
    ws = wb.create_sheet("Übersicht", 0)
    ws.sheet_view.showGridLines = False

    titel(ws, 1, "eEvolution → Odoo 19 Enterprise – Mapping-Übersicht")
    ws.cell(row=2, column=1,
            value=f"Stand: {heute.strftime('%d.%m.%Y')}  ·  "
                  f"eEvolution {eevo_meta.get('database')} @ {eevo_meta.get('server')}  ·  "
                  f"Odoo {odoo_meta.get('db')}").font = Font(name="Arial", size=9, color="888888")

    hdr(ws, 4, ["Gruppe", "eEvolution-Tabellen", "Odoo-Modell",
                "Felder gemappt", "Issues", "Status"])

    for i, g in enumerate(MAPPING, 5):
        issues = alle_issues.get(g["gruppe"], [])
        n_felder = len(g["felder"])
        status = "✓ OK" if not issues else f"⚠ {len(issues)} Issues"
        bg = GRUEN if not issues else GELB
        dat(ws, i, [
            g["gruppe"],
            ", ".join(g["ee"]),
            g["odoo"],
            n_felder,
            len(issues),
            status,
        ], bg=bg)

    breite(ws, {"A": 38, "B": 30, "C": 28, "D": 14, "E": 10, "F": 14})
    ws.freeze_panes = ws.cell(row=5, column=1)


# ── Blatt: Pro Gruppe ─────────────────────────────────────────────────────────

def blatt_gruppe(wb, gruppe, odoo_schema, issues):
    name = gruppe["gruppe"][:28]
    ws   = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False

    titel(ws, 1, f"{gruppe['gruppe']}")
    ws.cell(row=2, column=1,
            value=f"eEvolution: {', '.join(gruppe['ee'])}  →  Odoo: {gruppe['odoo']}"
                  + (f"  |  Filter: {gruppe.get('filter_ee', '')}" if gruppe.get('filter_ee') else "")
            ).font = Font(name="Arial", size=9, color="555555")

    hdr(ws, 4, ["eEvolution Tabelle", "eEvolution Spalte",
                "Odoo Modell", "Odoo Feld", "Odoo Typ",
                "Pflicht?", "Transformation / Notiz", "Status"])

    odoo_felder_map = {f["name"]: f for f in odoo_schema.get(gruppe["odoo"], [])}

    for i, (ee_tbl, ee_col, odoo_field, notiz) in enumerate(gruppe["felder"], 5):
        kern = odoo_field.split(" / ")[0].split(" (")[0].strip()
        odoo_f = odoo_felder_map.get(kern, {})
        odoo_typ     = odoo_f.get("type", "–") if odoo_f else "nicht gefunden"
        odoo_pflicht = "✓" if odoo_f.get("required") else ""
        ok = kern in odoo_felder_map or odoo_field in ("id (ext)", "ref")
        bg = WEISS if ok else ROT_H if "nicht gefunden" in odoo_typ else GELB

        dat(ws, i, [
            ee_tbl,
            ee_col,
            gruppe["odoo"],
            odoo_field,
            odoo_typ,
            odoo_pflicht,
            notiz,
            "✓" if ok else "⚠ prüfen",
        ], bg=bg)

    # Issues unten anhängen
    if issues:
        ws.cell(row=len(gruppe["felder"])+7, column=1, value="Issues:").font = \
            Font(name="Arial", bold=True, size=9, color="CC0000")
        for j, issue in enumerate(issues, len(gruppe["felder"])+8):
            ws.cell(row=j, column=1, value=issue).font = \
                Font(name="Arial", size=9, color="CC0000")

    breite(ws, {"A": 18, "B": 22, "C": 22, "D": 28, "E": 14,
                "F": 9,  "G": 40, "H": 12})
    ws.freeze_panes = ws.cell(row=5, column=1)


# ── Blatt: Offene Punkte ──────────────────────────────────────────────────────

def blatt_issues(wb, alle_issues):
    ws = wb.create_sheet("Offene Punkte")
    ws.sheet_view.showGridLines = False
    titel(ws, 1, "Offene Punkte – Mapping-Issues")
    hdr(ws, 3, ["Gruppe", "Issue"])

    zeile = 4
    for gruppe, issues in alle_issues.items():
        for issue in issues:
            dat(ws, zeile, [gruppe, issue], bg=ROT_H if "FEHLER" in issue else GELB)
            zeile += 1

    if zeile == 4:
        ws.cell(row=4, column=1, value="✓ Keine Issues gefunden").font = \
            Font(name="Arial", bold=True, color="009900")

    breite(ws, {"A": 38, "B": 70})


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    heute = date.today()

    eevo_cache = lade("eevo_schema.json")
    if not eevo_cache:
        sys.exit("FEHLER: eevo_schema.json nicht gefunden.")

    odoo_cache = lade("odoo_schema.json")
    if not odoo_cache:
        print("WARNUNG: odoo_schema.json fehlt – Odoo-Felder nicht prüfbar.")
        print("         Erst build_odoo_schema.py ausführen.")
        odoo_schema = {}
        odoo_meta   = {}
    else:
        odoo_schema = odoo_cache.get("felder", {})
        odoo_meta   = odoo_cache.get("_meta", {})

    eevo_meta = eevo_cache.get("_meta", {})

    print(f"eEvolution: {eevo_meta.get('tables')} Tabellen  ·  {eevo_meta.get('relations')} Beziehungen")
    print(f"Odoo:       {odoo_meta.get('modelle', '?')} Modelle  ·  {odoo_meta.get('felder', '?')} Felder")

    # Stimmigkeitsprüfung
    print("\n[1] Prüfe Stimmigkeit …")
    alle_issues = {}
    for g in MAPPING:
        issues = pruefe_stimmigkeit(g, odoo_schema)
        if issues:
            alle_issues[g["gruppe"]] = issues
            print(f"  ⚠ {g['gruppe']}: {len(issues)} Issues")
        else:
            print(f"  ✓ {g['gruppe']}")

    total_issues = sum(len(v) for v in alle_issues.values())
    print(f"\n  Gesamt: {total_issues} Issues in {len(alle_issues)} Gruppen")

    # Excel erzeugen
    print("\n[2] Erstelle Excel …")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    blatt_uebersicht(wb, eevo_meta, odoo_meta, alle_issues, heute)
    for g in MAPPING:
        blatt_gruppe(wb, g, odoo_schema, alle_issues.get(g["gruppe"], []))
    blatt_issues(wb, alle_issues)

    datei = f"Mapping_EE_Odoo_{heute.strftime('%Y%m%d')}.xlsx"
    wb.save(datei)
    print(f"\n[OK] Gespeichert: {datei}")
    print(f"     {len(MAPPING)} Gruppen  ·  "
          f"{sum(len(g['felder']) for g in MAPPING)} Feld-Mappings  ·  "
          f"{total_issues} Issues")


if __name__ == "__main__":
    main()
