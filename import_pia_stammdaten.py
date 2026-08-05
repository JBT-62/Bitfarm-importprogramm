#!/usr/bin/env python3
"""
import_pia_stammdaten.py
Liest PIA-Stammdaten aus eEvolution und überträgt sie nach Odoo 19.

Ablauf:
  1. Artikel  "PIA" aus ARTIKEL + ARTIKELLONG
  2. Lieferanten der PIA-Komponenten (ADRESS + LIEFERANT)
  3. Stückliste aus PRODLIST + PRODINHALT (oder ARTSTUELI als Fallback)
  4. Alle Abhängigkeiten: LAND, ZAHLBEDING, Maßeinheiten

Ausführen:
  pip install pymssql python-dotenv
  python import_pia_stammdaten.py            # Trockenlauf (zeigt nur was gefunden)
  python import_pia_stammdaten.py --import   # Überträgt nach Odoo

Credentials: .env (niemals in dieses Skript eintragen)
"""

import os
import sys
import argparse
import xmlrpc.client
from pprint import pprint

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env manuell als Umgebungsvariablen setzen

# ── Konfiguration aus .env ──────────────────────────────────────────────────

EE_HOST    = os.getenv("EE_HOST", "192.168.120.234")
EE_PORT    = int(os.getenv("EE_PORT", "1433"))
EE_DB      = os.getenv("EE_DB", "KuF")
EE_USER    = os.getenv("EE_USER", "excel_kuf_readonly")
EE_PASS    = os.getenv("EE_PASS", "")

ODOO_URL    = os.getenv("ODOO_URL", "")
ODOO_DB     = os.getenv("ODOO_DB", "")
ODOO_USER   = os.getenv("ODOO_USER", "admin")
ODOO_APIKEY = os.getenv("ODOO_APIKEY", "")

EXT_PREFIX = "ev_import"   # Modul-Name für ir.model.data External IDs


# ── eEvolution-Verbindung ───────────────────────────────────────────────────

def ee_connect():
    try:
        import pymssql
        conn = pymssql.connect(
            server=EE_HOST, port=EE_PORT, database=EE_DB,
            user=EE_USER, password=EE_PASS,
            login_timeout=10, charset="UTF-8"
        )
        print(f"[EE]  Verbunden mit {EE_HOST}/{EE_DB}")
        return conn
    except ImportError:
        sys.exit("FEHLER: pymssql fehlt. Bitte: pip install pymssql")
    except Exception as e:
        sys.exit(f"FEHLER eEvolution-Verbindung: {e}")


def ee_rows(cursor, sql, params=None):
    cursor.execute(sql, params or ())
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ── Odoo-Verbindung ─────────────────────────────────────────────────────────

def odoo_connect():
    if not ODOO_URL or not ODOO_DB or not ODOO_APIKEY:
        sys.exit("FEHLER: ODOO_URL, ODOO_DB und ODOO_APIKEY in .env eintragen.")
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_APIKEY, {})
    if not uid:
        sys.exit("FEHLER: Odoo-Authentifizierung fehlgeschlagen (User/API-Key prüfen).")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
    print(f"[OD]  Verbunden mit {ODOO_URL}/{ODOO_DB} (uid={uid})")
    return models, uid


def odoo_call(models, uid, model, method, args, kwargs=None):
    return models.execute_kw(ODOO_DB, uid, ODOO_APIKEY, model, method, args, kwargs or {})


def ext_id_key(prefix, record_id):
    return f"{EXT_PREFIX}.{prefix}_{record_id}"


def odoo_upsert(models, uid, odoo_model, ext_key, vals):
    """Legt Datensatz an oder aktualisiert ihn (idempotent via External ID)."""
    module, name = ext_key.split(".", 1)
    existing = odoo_call(models, uid, "ir.model.data", "search_read",
        [[["module", "=", module], ["name", "=", name], ["model", "=", odoo_model]]],
        {"fields": ["res_id"], "limit": 1})
    if existing:
        rec_id = existing[0]["res_id"]
        odoo_call(models, uid, odoo_model, "write", [[rec_id], vals])
        return rec_id, "updated"
    rec_id = odoo_call(models, uid, odoo_model, "create", [vals])
    odoo_call(models, uid, "ir.model.data", "create", [{
        "name": name, "module": module,
        "model": odoo_model, "res_id": rec_id,
        "noupdate": False,
    }])
    return rec_id, "created"


def odoo_find_by_ext(models, uid, ext_key):
    module, name = ext_key.split(".", 1)
    rows = odoo_call(models, uid, "ir.model.data", "search_read",
        [[["module", "=", module], ["name", "=", name]]],
        {"fields": ["res_id"], "limit": 1})
    return rows[0]["res_id"] if rows else None


# ── Schritt 1: PIA-Artikel aus eEvolution lesen ─────────────────────────────

def lese_pia_artikel(cur):
    """Alle Artikel deren Bezeichnung 'PIA' enthält."""
    rows = ee_rows(cur, """
        SELECT
            a.LFDNR        AS lfdnr,
            a.ARTNR        AS artnr,
            a.ARTBEZ       AS artbez,
            a.ARTBEZ2      AS artbez2,
            a.VK1          AS vk1,
            a.EINKPREIS    AS einkpreis,
            a.EINHEITID    AS einheitid,
            a.WARENGRUPPEID AS warengruppeid,
            a.MWSTID       AS mwstid,
            al.LANGTEXT    AS langtext
        FROM ARTIKEL a
        LEFT JOIN ARTIKELLONG al ON al.ARTID = a.LFDNR
        WHERE a.ARTBEZ LIKE '%PIA%' OR a.ARTNR LIKE '%PIA%'
        ORDER BY a.ARTNR
    """)
    return rows


# ── Schritt 2: Stückliste (PRODLIST + PRODINHALT) ───────────────────────────

def lese_stueckliste(cur, artikel_lfdnr):
    """Stückliste für einen Artikel. Versucht PRODLIST, Fallback ARTSTUELI."""
    # Versuch 1: PRODLIST + PRODINHALT (Produktionsstückliste)
    kopf = ee_rows(cur, """
        SELECT LFDNR, ARTID, BEZEICHNUNG
        FROM PRODLIST
        WHERE ARTID = %s
    """, (artikel_lfdnr,))

    if kopf:
        positionen = []
        for k in kopf:
            pos = ee_rows(cur, """
                SELECT
                    i.LFDNR,
                    i.ARTID       AS komp_lfdnr,
                    a.ARTNR       AS komp_artnr,
                    a.ARTBEZ      AS komp_artbez,
                    i.MENGE       AS menge,
                    i.EINHEITID   AS einheitid
                FROM PRODINHALT i
                JOIN ARTIKEL a ON a.LFDNR = i.ARTID
                WHERE i.PRODLISTID = %s
                ORDER BY i.LFDNR
            """, (k["lfdnr"],))
            positionen.extend(pos)
        return {"typ": "PRODLIST", "kopf": kopf[0], "positionen": positionen}

    # Fallback: ARTSTUELI (einfache Stückliste)
    pos = ee_rows(cur, """
        SELECT
            s.LFDNR,
            s.KOMP_ARTID  AS komp_lfdnr,
            a.ARTNR       AS komp_artnr,
            a.ARTBEZ      AS komp_artbez,
            s.MENGE       AS menge,
            s.EINHEITID   AS einheitid
        FROM ARTSTUELI s
        JOIN ARTIKEL a ON a.LFDNR = s.KOMP_ARTID
        WHERE s.UEBERARTIKELID = %s
        ORDER BY s.LFDNR
    """, (artikel_lfdnr,))

    return {"typ": "ARTSTUELI", "positionen": pos} if pos else None


# ── Schritt 3: Lieferanten der Komponenten ──────────────────────────────────

def lese_lieferanten(cur, artikel_lfdnr_liste):
    """Lieferanten für eine Liste von Artikel-IDs (über ARTLIEFERANT oder LIEFERANT)."""
    if not artikel_lfdnr_liste:
        return []
    platzhalter = ",".join(["%s"] * len(artikel_lfdnr_liste))

    # Versuch: Artikel-Lieferant-Verknüpfungstabelle
    try:
        rows = ee_rows(cur, f"""
            SELECT
                al.ARTID        AS artid,
                ad.ADRNR        AS adrnr,
                ad.NAME1        AS name1,
                ad.NAME2        AS name2,
                ad.STRASSE      AS strasse,
                ad.PLZ          AS plz,
                ad.ORT          AS ort,
                ad.LANDID       AS landid,
                ad.EMAIL        AS email,
                ad.TELEFON      AS telefon,
                ad.USTIDNR      AS ustidnr,
                l.ZAHLBEDINGID  AS zahlbedingid
            FROM ARTLIEFERANT al
            JOIN ADRESS ad ON ad.ADRNR = al.ADRNR
            LEFT JOIN LIEFERANT l ON l.ADRNR = al.ADRNR
            WHERE al.ARTID IN ({platzhalter})
        """, tuple(artikel_lfdnr_liste))
        if rows:
            return rows
    except Exception:
        pass  # Tabelle heißt möglicherweise anders

    # Fallback: alle Adressen mit LIEFERANT-Flag
    print("[WRN] ARTLIEFERANT nicht gefunden – lade alle Lieferanten-Adressen")
    rows = ee_rows(cur, """
        SELECT
            ad.ADRNR        AS adrnr,
            ad.NAME1        AS name1,
            ad.NAME2        AS name2,
            ad.STRASSE      AS strasse,
            ad.PLZ          AS plz,
            ad.ORT          AS ort,
            ad.LANDID       AS landid,
            ad.EMAIL        AS email,
            ad.TELEFON      AS telefon,
            ad.USTIDNR      AS ustidnr,
            l.ZAHLBEDINGID  AS zahlbedingid
        FROM ADRESS ad
        JOIN LIEFERANT l ON l.ADRNR = ad.ADRNR
        WHERE ad.GESPERRT = 0
        ORDER BY ad.NAME1
    """)
    return rows


# ── Schritt 4: Hilfstabellen ────────────────────────────────────────────────

def lese_laender(cur):
    return {r["lfdnr"]: r for r in ee_rows(cur, """
        SELECT LFDNR, LANDKUERZEL, LANDNAME FROM LAND
    """)}


def lese_zahlbeding(cur):
    return {r["lfdnr"]: r for r in ee_rows(cur, """
        SELECT LFDNR, BEZEICHNUNG, ZAHLUNGSTAGE FROM ZAHLBEDING
    """)}


def lese_einheiten(cur):
    return {r["lfdnr"]: r for r in ee_rows(cur, """
        SELECT LFDNR, EINHEITKUERZEL, BEZEICHNUNG FROM MENGENSCHL
    """)}


# ── Odoo: Zahlungsbedingung anlegen ─────────────────────────────────────────

def odoo_sync_zahlbeding(models, uid, zb):
    ext_key = ext_id_key("zahlbeding", zb["lfdnr"])
    tage = zb.get("zahlungstage") or 30
    vals = {
        "name": zb["bezeichnung"],
        "note": f"Importiert aus eEvolution (ID {zb['lfdnr']})",
        "line_ids": [(5, 0, 0), (0, 0, {
            "value": "balance",
            "days": int(tage),
        })],
    }
    rec_id, action = odoo_upsert(models, uid, "account.payment.term", ext_key, vals)
    print(f"  Zahlungsbedingung '{zb['bezeichnung']}' → {action} (id={rec_id})")
    return rec_id


# ── Odoo: Lieferant anlegen ─────────────────────────────────────────────────

def odoo_sync_lieferant(models, uid, lief, laender_map, zahlbeding_map, odoo_zb_ids):
    ext_key = ext_id_key("adr", lief["adrnr"])

    # Land aufloesen
    country_id = False
    if lief.get("landid") and lief["landid"] in laender_map:
        iso2 = laender_map[lief["landid"]].get("landkuerzel", "")
        if iso2:
            res = odoo_call(models, uid, "res.country", "search",
                [[["code", "=", iso2.upper()]]])
            if res:
                country_id = res[0]

    name = lief["name1"] or ""
    if lief.get("name2"):
        name = f"{name} {lief['name2']}".strip()

    vals = {
        "name": name,
        "is_company": True,
        "supplier_rank": 1,
        "street": lief.get("strasse") or "",
        "zip": lief.get("plz") or "",
        "city": lief.get("ort") or "",
        "email": lief.get("email") or "",
        "phone": lief.get("telefon") or "",
    }
    if country_id:
        vals["country_id"] = country_id
    if lief.get("ustidnr"):
        vals["vat"] = lief["ustidnr"]
    if lief.get("zahlbedingid") and lief["zahlbedingid"] in odoo_zb_ids:
        vals["property_supplier_payment_term_id"] = odoo_zb_ids[lief["zahlbedingid"]]

    rec_id, action = odoo_upsert(models, uid, "res.partner", ext_key, vals)
    print(f"  Lieferant '{name}' (ADRNR={lief['adrnr']}) → {action} (id={rec_id})")
    return rec_id


# ── Odoo: Produkt anlegen ───────────────────────────────────────────────────

def odoo_uom_id(models, uid, einheit_kuerzel):
    """Sucht UoM in Odoo nach Kurzzeichen, gibt Stück als Fallback."""
    if einheit_kuerzel:
        res = odoo_call(models, uid, "uom.uom", "search",
            [[["name", "ilike", einheit_kuerzel]]], {"limit": 1})
        if res:
            return res[0]
    # Fallback: Stück
    res = odoo_call(models, uid, "uom.uom", "search",
        [[["name", "in", ["Stück", "Stk", "Units", "Unit", "u"]]]], {"limit": 1})
    return res[0] if res else False


def odoo_sync_produkt(models, uid, art, einheiten_map, ist_fertigprodukt=False):
    ext_key = ext_id_key("product", art["lfdnr"])

    uom_kuerzel = ""
    if art.get("einheitid") and art["einheitid"] in einheiten_map:
        uom_kuerzel = einheiten_map[art["einheitid"]].get("einheitkuerzel", "")
    uom_id = odoo_uom_id(models, uid, uom_kuerzel)

    name = art["artbez"] or art["artnr"]
    if art.get("artbez2"):
        name = f"{name} – {art['artbez2']}"

    vals = {
        "name": name,
        "default_code": art["artnr"],
        "type": "consu" if not ist_fertigprodukt else "product",
        "detailed_type": "product",
        "list_price": float(art.get("vk1") or 0),
        "standard_price": float(art.get("einkpreis") or 0),
        "purchase_ok": True,
        "sale_ok": ist_fertigprodukt,
    }
    if uom_id:
        vals["uom_id"] = uom_id
        vals["uom_po_id"] = uom_id
    if art.get("langtext"):
        vals["description"] = art["langtext"]
    if ist_fertigprodukt:
        # Route: Fertigen
        mfg_route = odoo_call(models, uid, "stock.route", "search",
            [[["name", "ilike", "Fert"]]], {"limit": 1})
        if mfg_route:
            vals["route_ids"] = [(6, 0, mfg_route)]

    rec_id, action = odoo_upsert(models, uid, "product.template", ext_key, vals)
    print(f"  Produkt '{art['artnr']}' '{art['artbez']}' → {action} (id={rec_id})")
    return rec_id


# ── Odoo: Stückliste anlegen ─────────────────────────────────────────────────

def odoo_sync_stueckliste(models, uid, bom_data, produkt_odoo_id, odoo_produkte):
    """Legt mrp.bom an mit allen Positionen."""
    if not bom_data or not bom_data["positionen"]:
        print("  [SKP] Keine Stückliste gefunden.")
        return None

    # product.product ID aus product.template ermitteln
    pp_ids = odoo_call(models, uid, "product.product", "search",
        [[["product_tmpl_id", "=", produkt_odoo_id]]], {"limit": 1})
    if not pp_ids:
        print(f"  [ERR] product.product für template {produkt_odoo_id} nicht gefunden.")
        return None
    pp_id = pp_ids[0]

    # Positionen aufbauen
    bom_lines = []
    for pos in bom_data["positionen"]:
        komp_tmpl_id = odoo_produkte.get(pos["komp_lfdnr"])
        if not komp_tmpl_id:
            print(f"  [SKP] Komponente LFDNR={pos['komp_lfdnr']} '{pos['komp_artbez']}' nicht in Odoo – übersprungen")
            continue
        komp_pp = odoo_call(models, uid, "product.product", "search",
            [[["product_tmpl_id", "=", komp_tmpl_id]]], {"limit": 1})
        if not komp_pp:
            continue
        bom_lines.append((0, 0, {
            "product_id": komp_pp[0],
            "product_qty": float(pos.get("menge") or 1),
        }))

    if not bom_lines:
        print("  [SKP] Keine Stücklisten-Positionen übertragbar.")
        return None

    ext_key = ext_id_key("bom", produkt_odoo_id)
    vals = {
        "product_tmpl_id": produkt_odoo_id,
        "product_id": pp_id,
        "type": "normal",
        "product_qty": 1.0,
        "bom_line_ids": bom_lines,
    }
    rec_id, action = odoo_upsert(models, uid, "mrp.bom", ext_key, vals)
    print(f"  Stückliste → {action} mit {len(bom_lines)} Position(en) (id={rec_id})")
    return rec_id


# ── Hauptprogramm ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PIA-Stammdaten: eEvolution → Odoo 19")
    parser.add_argument("--import", dest="do_import", action="store_true",
                        help="Tatsächlich nach Odoo schreiben (ohne Flag: nur Anzeige)")
    parser.add_argument("--filter", default="PIA",
                        help="Suchbegriff für Artikel (Standard: PIA)")
    args = parser.parse_args()

    print("=" * 60)
    print(f"Modus: {'IMPORT → Odoo' if args.do_import else 'TROCKENLAUF (nur Anzeige)'}")
    print("=" * 60)

    # ── Lesen aus eEvolution ──────────────────────────────────────
    conn = ee_connect()
    cur = conn.cursor()

    print(f"\n[1] Suche Artikel mit '{args.filter}'...")
    artikel_liste = lese_pia_artikel(cur)
    if not artikel_liste:
        print(f"  Keine Artikel mit '{args.filter}' gefunden. Abbruch.")
        sys.exit(1)

    print(f"  Gefunden: {len(artikel_liste)} Artikel")
    for a in artikel_liste:
        print(f"    LFDNR={a['lfdnr']}  ARTNR={a['artnr']}  BEZ={a['artbez']}")

    # Hauptartikel = erstes Ergebnis (kann per --filter eingegrenzt werden)
    haupt = artikel_liste[0]
    print(f"\n  → Hauptartikel: {haupt['artnr']} – {haupt['artbez']}")

    print("\n[2] Lese Stückliste...")
    bom = lese_stueckliste(cur, haupt["lfdnr"])
    if bom:
        print(f"  Typ: {bom['typ']}, {len(bom['positionen'])} Position(en)")
        for p in bom["positionen"]:
            print(f"    LFDNR={p['komp_lfdnr']}  {p['komp_artnr']}  {p['komp_artbez']}  {p['menge']}")
    else:
        print("  Keine Stückliste gefunden.")

    # Alle beteiligten Artikel-IDs (Hauptartikel + Komponenten)
    alle_ids = [haupt["lfdnr"]]
    komp_lfdnr_liste = []
    if bom:
        for p in bom["positionen"]:
            alle_ids.append(p["komp_lfdnr"])
            komp_lfdnr_liste.append(p["komp_lfdnr"])

    print("\n[3] Lese Lieferanten...")
    lieferanten = lese_lieferanten(cur, alle_ids)
    # Deduplizieren nach ADRNR
    seen = set()
    lieferanten_dedup = []
    for l in lieferanten:
        if l["adrnr"] not in seen:
            seen.add(l["adrnr"])
            lieferanten_dedup.append(l)
    print(f"  {len(lieferanten_dedup)} Lieferant(en) gefunden")
    for l in lieferanten_dedup:
        print(f"    ADRNR={l['adrnr']}  {l['name1']}")

    print("\n[4] Lade Hilfstabellen...")
    laender_map   = lese_laender(cur)
    zahlbeding_map = lese_zahlbeding(cur)
    einheiten_map  = lese_einheiten(cur)
    conn.close()
    print(f"  {len(laender_map)} Länder, {len(zahlbeding_map)} Zahlungsbedingungen, {len(einheiten_map)} Einheiten")

    if not args.do_import:
        print("\n" + "=" * 60)
        print("Trockenlauf abgeschlossen. Mit --import nach Odoo schreiben.")
        print("=" * 60)
        return

    # ── Schreiben nach Odoo ──────────────────────────────────────
    models, uid = odoo_connect()

    print("\n[5] Zahlungsbedingungen synchronisieren...")
    odoo_zb_ids = {}   # ee-lfdnr → odoo-id
    verwendete_zb_ids = {l["zahlbedingid"] for l in lieferanten_dedup if l.get("zahlbedingid")}
    for zb_id, zb in zahlbeding_map.items():
        if zb_id in verwendete_zb_ids:
            odoo_id = odoo_sync_zahlbeding(models, uid, zb)
            odoo_zb_ids[zb_id] = odoo_id

    print("\n[6] Lieferanten synchronisieren...")
    for lief in lieferanten_dedup:
        odoo_sync_lieferant(models, uid, lief, laender_map, zahlbeding_map, odoo_zb_ids)

    print("\n[7] Komponenten synchronisieren...")
    odoo_produkte = {}   # ee-lfdnr → odoo product.template id
    for art in artikel_liste:
        if art["lfdnr"] != haupt["lfdnr"]:
            pid = odoo_sync_produkt(models, uid, art, einheiten_map, ist_fertigprodukt=False)
            odoo_produkte[art["lfdnr"]] = pid

    # Komponenten, die nicht in der Artikelliste sind (nur in SB)
    if bom:
        alle_komp_artnr = {p["komp_lfdnr"]: p for p in bom["positionen"]}
        for lfdnr, pos in alle_komp_artnr.items():
            if lfdnr not in odoo_produkte:
                komp_art = {
                    "lfdnr": lfdnr,
                    "artnr": pos["komp_artnr"],
                    "artbez": pos["komp_artbez"],
                    "artbez2": None,
                    "vk1": 0,
                    "einkpreis": 0,
                    "einheitid": pos.get("einheitid"),
                    "langtext": None,
                }
                pid = odoo_sync_produkt(models, uid, komp_art, einheiten_map, ist_fertigprodukt=False)
                odoo_produkte[lfdnr] = pid

    print("\n[8] Hauptartikel (Fertigprodukt) synchronisieren...")
    haupt_odoo_id = odoo_sync_produkt(models, uid, haupt, einheiten_map, ist_fertigprodukt=True)
    odoo_produkte[haupt["lfdnr"]] = haupt_odoo_id

    print("\n[9] Stückliste synchronisieren...")
    odoo_sync_stueckliste(models, uid, bom, haupt_odoo_id, odoo_produkte)

    print("\n" + "=" * 60)
    print("Import abgeschlossen.")
    print(f"  Odoo: {ODOO_URL} / DB: {ODOO_DB}")
    print(f"  Artikel:    {ODOO_URL}/web#action=product.product_template_action_all")
    print(f"  Lieferanten:{ODOO_URL}/web#action=contacts.action_contacts")
    print(f"  Stücklisten:{ODOO_URL}/web#action=mrp.mrp_bom_form_action")
    print("=" * 60)


if __name__ == "__main__":
    main()
