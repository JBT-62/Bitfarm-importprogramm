#!/usr/bin/env python3
"""
pilot_import_angebot.py
───────────────────────
Liest ein Angebot aus eEvolution und importiert alle benötigten Stammdaten
nach Odoo 19, damit der Vorgang dort manuell durchgeführt werden kann:
  - Mengeneinheiten
  - Lieferanten / Lohnfertiger (res.partner)
  - Artikel (product.template)
  - Stücklisten inkl. Komponenten (mrp.bom + mrp.bom.line)

Der Kunde / das Angebot selbst wird NICHT importiert – das legen die
Mitarbeiter händisch an.

Ausführen:
    python 99_scripts/pilot_import_angebot.py             # Dry-Run, Angebot 39575
    python 99_scripts/pilot_import_angebot.py --nr 12345  # anderes Angebot
    python 99_scripts/pilot_import_angebot.py --import    # wirklich importieren

Voraussetzungen:
    .env mit ODOO_URL / ODOO_DB / ODOO_USER / ODOO_API_KEY
    pyodbc + ODBC Driver 18 for SQL Server
    python-dotenv, openpyxl (nur für Ausgabe)
"""

import os, sys, argparse, json, textwrap
import pyodbc, xmlrpc.client
from collections import defaultdict

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Konfiguration ─────────────────────────────────────────────────────────────

EEVO_SERVER  = os.getenv("EEVO_SERVER",  "192.168.120.234")
EEVO_DB      = os.getenv("EEVO_DB",      "KuF")
EEVO_USER    = os.getenv("EEVO_USER",    "excel_kuf_readonly")
EEVO_PWD     = os.getenv("EEVO_PWD",     "readonly")

ODOO_URL     = os.getenv("ODOO_URL",     "http://192.168.120.225:8069")
ODOO_DB      = os.getenv("ODOO_DB",      "erp-test-1")
ODOO_USER    = os.getenv("ODOO_USER",    "admin")
ODOO_API_KEY = os.getenv("ODOO_API_KEY", "")

EXT_PREFIX   = "ev_kuf"   # Prefix für Odoo External IDs


# ── Verbindungen ──────────────────────────────────────────────────────────────

def verbinde_eevo():
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={EEVO_SERVER};DATABASE={EEVO_DB};"
        f"UID={EEVO_USER};PWD={EEVO_PWD};"
        f"TrustServerCertificate=yes;"
    )
    try:
        conn = pyodbc.connect(conn_str, timeout=10)
        print(f"[eEvo] Verbunden: {EEVO_SERVER}/{EEVO_DB}")
        return conn
    except Exception as e:
        sys.exit(f"FEHLER eEvolution: {e}")


def verbinde_odoo():
    if not ODOO_API_KEY:
        sys.exit("FEHLER: ODOO_API_KEY fehlt in .env")
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
    uid    = common.authenticate(ODOO_DB, ODOO_USER, ODOO_API_KEY, {})
    if not uid:
        sys.exit("FEHLER: Odoo-Authentifizierung fehlgeschlagen")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)
    ver    = common.version().get("server_version", "?")
    print(f"[Odoo] Verbunden: {ODOO_URL}/{ODOO_DB}  (v{ver})")
    return models, uid


def odoo_call(models, method, model, args=None, kwargs=None):
    return models.execute_kw(
        ODOO_DB, _odoo_uid, ODOO_API_KEY,
        model, method, args or [[]], kwargs or {}
    )

_odoo_uid = None  # wird in main() gesetzt


# ── Phase 1: eEvolution – Angebot laden ──────────────────────────────────────

def lade_angebot(conn, lfdnr: int) -> dict:
    """Lädt Angebots-Header aus ANGAUFGUT."""
    sql = """
        SELECT ag.LFDNR, ag.KNDNR, ag.ERFASSDATUM,
               ag.ANGEBOT, ag.AUFTRAG, ag.GUTSCHRIFT,
               ag.GESAMTPREIS
        FROM ANGAUFGUT ag
        WHERE ag.LFDNR = ?
    """
    row = conn.cursor().execute(sql, lfdnr).fetchone()
    if not row:
        sys.exit(f"FEHLER: Angebot LFDNR={lfdnr} nicht in ANGAUFGUT gefunden.")
    return dict(zip([d[0] for d in conn.cursor().execute(sql, lfdnr).description], row)) \
           if False else _row_to_dict(conn, sql, lfdnr)


def _row_to_dict(conn, sql, *params):
    cur = conn.cursor()
    cur.execute(sql, *params)
    cols = [d[0] for d in cur.description]
    row  = cur.fetchone()
    return dict(zip(cols, row)) if row else None


def _rows_to_dicts(conn, sql, *params):
    cur = conn.cursor()
    cur.execute(sql, *params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def lade_positionen(conn, ang_lfdnr: int) -> list:
    """Lädt alle Positionen eines Angebots aus ANGAUFPOS."""
    sql = """
        SELECT p.LFDNR, p.LFDANGAUFGUTNR, p.POSNR,
               p.LFDARTNR, p.BESTMENGE, p.PREIS, p.LANGTEXT,
               ar.ARTNR1, ar.ABEZ1, ar.MENGENSCHL
        FROM ANGAUFPOS p
        LEFT JOIN ARTIKEL ar ON ar.LFDNR = p.LFDARTNR
        WHERE p.LFDANGAUFGUTNR = ?
        ORDER BY p.POSNR
    """
    return _rows_to_dicts(conn, sql, ang_lfdnr)


def lade_artikel(conn, art_lfdnr_list: list) -> dict:
    """Lädt Artikelstamm für eine Liste von LFDNR. Gibt dict {lfdnr: dict}."""
    if not art_lfdnr_list:
        return {}
    platzhalter = ",".join("?" * len(art_lfdnr_list))
    sql = f"""
        SELECT a.LFDNR, a.ARTNR1, a.ABEZ1, a.ABEZ2,
               a.MENGENSCHL, a.VKPR1, a.EKPR, a.LFDLIEFNR,
               al.CONTENT AS LANGTEXT
        FROM ARTIKEL a
        LEFT JOIN (
            SELECT LFDARTNR, MAX(CONTENT) AS CONTENT
            FROM ARTIKELLONG GROUP BY LFDARTNR
        ) al ON al.LFDARTNR = a.LFDNR
        WHERE a.LFDNR IN ({platzhalter})
    """
    rows = _rows_to_dicts(conn, sql, art_lfdnr_list)
    return {r["LFDNR"]: r for r in rows}


def lade_stuecklisten(conn, art_lfdnr_list: list) -> tuple:
    """
    Lädt PRODLIST + PRODINHALT für eine Liste von Fertigprodukt-LFDNR.
    Gibt (boms: list, komponenten_ids: set) zurück.
    """
    if not art_lfdnr_list:
        return [], set()
    platzhalter = ",".join("?" * len(art_lfdnr_list))
    sql_boms = f"""
        SELECT p.LFD_NR, p.ART_NR,
               a.ARTNR1, a.ABEZ1
        FROM PRODLIST p
        JOIN ARTIKEL a ON a.LFDNR = p.ART_NR
        WHERE p.ART_NR IN ({platzhalter})
    """
    boms = _rows_to_dicts(conn, sql_boms, art_lfdnr_list)
    if not boms:
        return [], set()

    bom_ids = [b["LFD_NR"] for b in boms]
    platzhalter2 = ",".join("?" * len(bom_ids))
    sql_lines = f"""
        SELECT i.LFD_NR, i.LIST_NR, i.ART_NR, i.MENGE, i.MENGENSCHL,
               a.ARTNR1, a.ABEZ1
        FROM PRODINHALT i
        JOIN ARTIKEL a ON a.LFDNR = i.ART_NR
        WHERE i.LIST_NR IN ({platzhalter2})
        ORDER BY i.LIST_NR, i.LFD_NR
    """
    lines = _rows_to_dicts(conn, sql_lines, bom_ids)

    # Stücklisten mit Positionen zusammenführen
    lines_by_bom = defaultdict(list)
    for l in lines:
        lines_by_bom[l["LIST_NR"]].append(l)
    for b in boms:
        b["positionen"] = lines_by_bom.get(b["LFD_NR"], [])

    komp_ids = {l["ART_NR"] for l in lines}
    return boms, komp_ids


def lade_lieferanten(conn, adrnr_list: list) -> dict:
    """Lädt Lieferantenstamm. Gibt dict {adrnr: dict}."""
    if not adrnr_list:
        return {}
    # None-Werte filtern
    adrnr_list = [a for a in adrnr_list if a]
    if not adrnr_list:
        return {}
    platzhalter = ",".join("?" * len(adrnr_list))
    sql = f"""
        SELECT l.ADRNR, l.NAME1, l.NAME2, l.STRASSE, l.PLZ, l.ORT,
               l.EMAIL, l.TEL1, l.LAND
        FROM LIEFERANT l
        WHERE l.ADRNR IN ({platzhalter})
    """
    rows = _rows_to_dicts(conn, sql, adrnr_list)
    return {r["ADRNR"]: r for r in rows}


def sammle_stammdaten(conn, ang_lfdnr: int) -> dict:
    """
    Hauptfunktion Phase 1: Lädt alle für das Angebot benötigten Stammdaten
    aus eEvolution (rekursiv über Stücklisten-Ebenen).
    """
    print(f"\n[1] Lade Angebot LFDNR={ang_lfdnr} aus eEvolution …")

    angebot = _row_to_dict(conn, """
        SELECT ag.LFDNR, ag.KNDNR, ag.ERFASSDATUM,
               ag.ANGEBOT, ag.AUFTRAG, ag.GESAMTPREIS
        FROM ANGAUFGUT ag WHERE ag.LFDNR = ?
    """, ang_lfdnr)

    if not angebot:
        sys.exit(f"FEHLER: ANGAUFGUT.LFDNR={ang_lfdnr} nicht gefunden.")

    typ = "Angebot" if angebot["ANGEBOT"] else "Auftrag" if angebot["AUFTRAG"] else "Sonstig"
    print(f"    {typ}  Datum={angebot['ERFASSDATUM']}  "
          f"Kunde-Nr={angebot['KNDNR']}  "
          f"Gesamt={angebot.get('GESAMTPREIS', '?')} €")

    # Positionen
    positionen = lade_positionen(conn, ang_lfdnr)
    print(f"    {len(positionen)} Positionen gefunden")

    # Direkte Artikel aus Positionen
    direkte_art_ids = {p["LFDARTNR"] for p in positionen if p["LFDARTNR"]}
    print(f"    {len(direkte_art_ids)} direkte Artikel")

    # Rekursiv alle Stücklisten + Komponenten sammeln
    alle_art_ids    = set(direkte_art_ids)
    alle_boms       = []
    verarbeitete    = set()
    zu_verarbeiten  = set(direkte_art_ids)

    ebene = 0
    while zu_verarbeiten:
        ebene += 1
        neu = zu_verarbeiten - verarbeitete
        if not neu:
            break
        verarbeitete |= neu

        boms, komp_ids = lade_stuecklisten(conn, list(neu))
        alle_boms.extend(boms)
        neue_komp = komp_ids - alle_art_ids
        alle_art_ids |= komp_ids
        zu_verarbeiten = neue_komp
        if boms:
            print(f"    Ebene {ebene}: {len(boms)} Stücklisten, "
                  f"{len(komp_ids)} Komponenten")

    # Alle Artikel laden
    alle_artikel = lade_artikel(conn, list(alle_art_ids))

    # Lieferanten aller Artikel
    lief_ids = {a["LFDLIEFNR"] for a in alle_artikel.values() if a.get("LFDLIEFNR")}
    lieferanten = lade_lieferanten(conn, list(lief_ids))

    # Mengeneinheiten
    einheiten = {a["MENGENSCHL"] for a in alle_artikel.values() if a.get("MENGENSCHL")}
    for b in alle_boms:
        for p in b.get("positionen", []):
            if p.get("MENGENSCHL"):
                einheiten.add(p["MENGENSCHL"])

    print(f"\n  Zusammenfassung eEvolution:")
    print(f"    Artikel gesamt:     {len(alle_artikel)}")
    print(f"    Stücklisten:        {len(alle_boms)}")
    print(f"    Lieferanten:        {len(lieferanten)}")
    print(f"    Mengeneinheiten:    {len(einheiten)}")

    return {
        "angebot":    angebot,
        "positionen": positionen,
        "artikel":    alle_artikel,
        "boms":       alle_boms,
        "lieferanten":lieferanten,
        "einheiten":  einheiten,
    }


# ── Phase 2: Odoo Import ──────────────────────────────────────────────────────

def odoo_ext_id(prefix: str, id_val) -> str:
    """Erzeugt eine Odoo External ID."""
    return f"{EXT_PREFIX}_{prefix}_{id_val}"


def odoo_find_or_create(model: str, domain: list, vals: dict,
                         models, ext_id: str = None,
                         do_import: bool = False) -> int | None:
    """
    Sucht einen Datensatz in Odoo. Wenn nicht gefunden und do_import=True: anlegen.
    Gibt die ID zurück oder None (dry-run).
    """
    ids = odoo_call(models, "search", model, [domain])
    if ids:
        return ids[0]
    if not do_import:
        return None
    new_id = odoo_call(models, "create", model, [vals])
    if ext_id:
        # External ID registrieren
        try:
            odoo_call(models, "create", "ir.model.data", [{
                "name":    ext_id.split(".")[-1] if "." in ext_id else ext_id,
                "module":  EXT_PREFIX,
                "model":   model,
                "res_id":  new_id,
            }])
        except Exception:
            pass  # External ID ist optional
    return new_id


def importiere_einheiten(einheiten: set, models, do_import: bool) -> dict:
    """
    Legt Mengeneinheiten in Odoo an falls nicht vorhanden.
    Gibt dict {kuerzel: odoo_uom_id} zurück.
    """
    print(f"\n[2] Mengeneinheiten ({len(einheiten)}) …")
    mapping = {}

    # Standard-Kategorie holen oder anlegen
    kat_ids = odoo_call(models, "search", "uom.category",
                        [[["name", "=", "Allgemein"]]])
    kat_id = kat_ids[0] if kat_ids else None

    for bez in sorted(einheiten):
        if not bez:
            continue
        ids = odoo_call(models, "search", "uom.uom",
                        [[["name", "=", bez]]])
        if ids:
            mapping[bez] = ids[0]
            print(f"    ✓ {bez} (ID {ids[0]})")
        elif do_import:
            vals = {
                "name":         bez,
                "category_id":  kat_id,
                "uom_type":     "reference",
                "factor":       1.0,
            }
            new_id = odoo_call(models, "create", "uom.uom", [vals])
            mapping[bez] = new_id
            print(f"    + {bez} → angelegt (ID {new_id})")
        else:
            print(f"    ? {bez} → würde angelegt (dry-run)")

    return mapping


def importiere_lieferanten(lieferanten: dict, models, do_import: bool) -> dict:
    """
    Legt Lieferanten als res.partner in Odoo an.
    Gibt dict {adrnr: odoo_partner_id} zurück.
    """
    print(f"\n[3] Lieferanten ({len(lieferanten)}) …")
    mapping = {}

    for adrnr, lief in lieferanten.items():
        name    = lief.get("NAME1", "") or ""
        name2   = lief.get("NAME2", "") or ""
        vollname = f"{name} {name2}".strip() if name2 else name
        ext_key  = odoo_ext_id("lief", adrnr)

        # Suche: zuerst External ID, dann Name
        ids = odoo_call(models, "search", "res.partner",
                        [[["name", "=", vollname], ["supplier_rank", ">", 0]]])
        if ids:
            mapping[adrnr] = ids[0]
            print(f"    ✓ {vollname[:40]} (ID {ids[0]})")
        elif do_import:
            # Länder-ID
            land_code = lief.get("LAND", "DE") or "DE"
            land_ids  = odoo_call(models, "search", "res.country",
                                  [[["code", "=", land_code]]])
            land_id   = land_ids[0] if land_ids else None

            vals = {
                "name":          vollname,
                "supplier_rank": 1,
                "street":        lief.get("STRASSE") or "",
                "zip":           lief.get("PLZ") or "",
                "city":          lief.get("ORT") or "",
                "country_id":    land_id,
                "email":         lief.get("EMAIL") or "",
                "phone":         lief.get("TEL1") or "",
                "comment":       f"Importiert aus eEvolution ADRNR={adrnr}",
            }
            new_id = odoo_call(models, "create", "res.partner", [vals])
            mapping[adrnr] = new_id
            print(f"    + {vollname[:40]} → angelegt (ID {new_id})")
        else:
            print(f"    ? {vollname[:40]} → würde angelegt (dry-run)")

    return mapping


def importiere_artikel(artikel: dict, uom_map: dict, lief_map: dict,
                        models, do_import: bool) -> dict:
    """
    Legt Artikel als product.template in Odoo an.
    Gibt dict {lfdnr: odoo_product_tmpl_id} zurück.
    """
    print(f"\n[4] Artikel ({len(artikel)}) …")
    mapping = {}

    for lfdnr, art in artikel.items():
        artnr   = art.get("ARTNR1", "") or ""
        bez     = art.get("ABEZ1", "") or ""
        bez2    = art.get("ABEZ2", "") or ""
        einheit = art.get("MENGENSCHL", "") or ""

        # Suche nach internal reference (Artikelnummer)
        ids = odoo_call(models, "search", "product.template",
                        [[["default_code", "=", artnr]]])
        if ids:
            mapping[lfdnr] = ids[0]
            print(f"    ✓ {artnr:<20} {bez[:35]}")
        elif do_import:
            uom_id = uom_map.get(einheit)
            if not uom_id:
                # Fallback auf Stück
                uom_ids = odoo_call(models, "search", "uom.uom",
                                    [[["name", "in", ["Stück", "PCE", "Units", "Unit"]]]])
                uom_id = uom_ids[0] if uom_ids else None

            sup_adrnr   = art.get("LFDLIEFNR")
            sup_partner  = lief_map.get(sup_adrnr) if sup_adrnr else None

            name_voll = bez
            if bez2:
                name_voll = f"{bez} {bez2}".strip()

            vals = {
                "name":          name_voll,
                "default_code":  artnr,
                "type":          "consu",  # oder 'product' für Lagerführung
                "uom_id":        uom_id,
                "uom_po_id":     uom_id,
                "standard_price": float(art.get("EKPR") or 0),
                "list_price":    float(art.get("VKPR1") or 0),
                "description":   art.get("LANGTEXT") or "",
                "purchase_ok":   True,
                "sale_ok":       True,
            }

            # Lieferant als supplierinfo
            new_id = odoo_call(models, "create", "product.template", [vals])
            mapping[lfdnr] = new_id

            if sup_partner:
                try:
                    odoo_call(models, "create", "product.supplierinfo", [{
                        "product_tmpl_id": new_id,
                        "partner_id":      sup_partner,
                        "min_qty":         0,
                        "price":           float(art.get("EKPR") or 0),
                    }])
                except Exception:
                    pass

            print(f"    + {artnr:<20} {bez[:35]} → ID {new_id}")
        else:
            print(f"    ? {artnr:<20} {bez[:35]} → würde angelegt")

    return mapping


def importiere_stuecklisten(boms: list, prod_map: dict, uom_map: dict,
                             models, do_import: bool):
    """Legt Stücklisten (mrp.bom + mrp.bom.line) in Odoo an."""
    print(f"\n[5] Stücklisten ({len(boms)}) …")

    # Fallback UoM
    uom_fallback = None
    fallback_ids = odoo_call(models, "search", "uom.uom",
                             [[["name", "in", ["Stück", "PCE", "Units", "Unit"]]]])
    if fallback_ids:
        uom_fallback = fallback_ids[0]

    for bom in boms:
        art_lfdnr  = bom["ART_NR"]
        tmpl_id    = prod_map.get(art_lfdnr)
        artnr      = bom.get("ARTNR1", "?")

        if not tmpl_id:
            print(f"    ⚠ {artnr}: Artikel nicht in Odoo – übersprungen")
            continue

        # Produkt-Variante ermitteln
        prod_ids = odoo_call(models, "search", "product.product",
                             [[["product_tmpl_id", "=", tmpl_id]]])
        prod_id = prod_ids[0] if prod_ids else None

        # Stückliste schon vorhanden?
        existing = odoo_call(models, "search", "mrp.bom",
                             [[["product_tmpl_id", "=", tmpl_id]]])
        if existing:
            print(f"    ✓ SL {artnr} (BOM ID {existing[0]})")
            continue

        if not do_import:
            print(f"    ? SL {artnr} ({len(bom['positionen'])} Komp.) → würde angelegt")
            continue

        # Positionen aufbauen
        bom_lines = []
        for pos in bom.get("positionen", []):
            komp_lfdnr  = pos["ART_NR"]
            komp_tmpl   = prod_map.get(komp_lfdnr)
            if not komp_tmpl:
                continue
            komp_prods = odoo_call(models, "search", "product.product",
                                   [[["product_tmpl_id", "=", komp_tmpl]]])
            komp_prod = komp_prods[0] if komp_prods else None
            einheit   = pos.get("MENGENSCHL") or ""
            uom_id    = uom_map.get(einheit) or uom_fallback

            bom_lines.append((0, 0, {
                "product_id":      komp_prod,
                "product_qty":     float(pos.get("MENGE") or 1),
                "product_uom_id":  uom_id,
            }))

        vals = {
            "product_tmpl_id": tmpl_id,
            "product_id":      prod_id,
            "type":            "normal",  # ggf. 'subcontract' für Lohnfertigung
            "bom_line_ids":    bom_lines,
        }
        new_id = odoo_call(models, "create", "mrp.bom", [vals])
        print(f"    + SL {artnr} ({len(bom_lines)} Komp.) → BOM ID {new_id}")


# ── Ausgabe / Dry-Run ─────────────────────────────────────────────────────────

def drucke_zusammenfassung(daten: dict):
    print("\n" + "═" * 64)
    print("  ZUSAMMENFASSUNG (Dry-Run – nichts wurde importiert)")
    print("═" * 64)

    ang  = daten["angebot"]
    pos  = daten["positionen"]
    print(f"\n  Angebot LFDNR {ang['LFDNR']}")
    print(f"  Kunde-Nr:    {ang['KNDNR']}")
    print(f"  Datum:       {ang['ERFASSDATUM']}")

    print(f"\n  Positionen ({len(pos)}):")
    for p in pos:
        artnr = p.get("ARTNR1") or "?"
        bez   = (p.get("ABEZ1") or "")[:40]
        print(f"    Pos {p['POSNR']:>3}  {artnr:<20} {bez}  {p['BESTMENGE']} {p['MENGENSCHL']}")

    print(f"\n  Zu importierende Stammdaten:")
    print(f"    Mengeneinheiten: {len(daten['einheiten'])}")
    print(f"    Lieferanten:     {len(daten['lieferanten'])}")
    print(f"    Artikel:         {len(daten['artikel'])}")
    print(f"    Stücklisten:     {len(daten['boms'])}")

    if daten["lieferanten"]:
        print(f"\n  Lieferanten:")
        for adrnr, l in daten["lieferanten"].items():
            print(f"    {adrnr:>6}  {l.get('NAME1', '')[:45]}")

    print(f"\n  Zum wirklichen Import: --import Flag hinzufügen")
    print("═" * 64)


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    global _odoo_uid

    parser = argparse.ArgumentParser(
        description="Pilot-Import: Stammdaten eines Angebots nach Odoo 19"
    )
    parser.add_argument("--nr",     type=int, default=39575,
                        help="ANGAUFGUT.LFDNR des Angebots (Standard: 39575)")
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="Wirklich importieren (sonst Dry-Run)")
    args = parser.parse_args()

    print("=" * 64)
    print(f"  Pilot-Import: Angebot {args.nr} → Odoo 19")
    if not args.do_import:
        print("  MODUS: Dry-Run (--import zum wirklichen Import)")
    else:
        print("  MODUS: IMPORT (Daten werden nach Odoo geschrieben)")
    print("=" * 64)

    # eEvolution
    conn = verbinde_eevo()
    daten = sammle_stammdaten(conn, args.nr)
    conn.close()

    if not args.do_import:
        drucke_zusammenfassung(daten)
        return

    # Odoo
    models, _odoo_uid = verbinde_odoo()

    uom_map  = importiere_einheiten(daten["einheiten"],  models, args.do_import)
    lief_map = importiere_lieferanten(daten["lieferanten"], models, args.do_import)
    prod_map = importiere_artikel(daten["artikel"], uom_map, lief_map,
                                   models, args.do_import)
    importiere_stuecklisten(daten["boms"], prod_map, uom_map,
                            models, args.do_import)

    print("\n" + "═" * 64)
    print("  Import abgeschlossen.")
    print("  Nächste Schritte (händisch in Odoo):")
    print("   1. Kunden anlegen (oder vorhandenen suchen)")
    print("   2. Angebot neu erstellen mit den importierten Artikeln")
    print("   3. Angebot → Auftrag bestätigen")
    print("   4. Fertigungsauftrag aus Stückliste erstellen")
    print("   5. Lieferung + Rechnung erzeugen")
    print("═" * 64)


if __name__ == "__main__":
    main()
