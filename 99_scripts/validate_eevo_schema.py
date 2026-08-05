#!/usr/bin/env python3
"""
validate_eevo_schema.py
KI-Logik-Prüfung des eevo_schema.json – kein DB-Zugriff, keine Änderungen.

Prüft:
  1. FK-Konsistenz  – Ziel-Tabelle und -Spalte vorhanden?
  2. PK-Erkennung  – hat jede Tabelle einen erkennbaren PK?
  3. Namens-Anomalien – ungelöste LFD*-Spalten, fehlende Pflichtfelder
  4. Doppel-Tabellen – Kandidaten für denselben Sachverhalt
  5. Migrationslücken – wichtige eEvolution-Tabellen ohne Odoo-Pendant

Ausführen:
    python 99_scripts/validate_eevo_schema.py

Ausgabe: Konsole + validate_report.json
"""

import json, sys, re
from pathlib import Path
from collections import defaultdict

# ── Schema laden ─────────────────────────────────────────────────────────────

def lade_schema():
    for p in [Path("eevo_schema.json"), Path("../eevo_schema.json")]:
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    sys.exit("FEHLER: eevo_schema.json nicht gefunden. Erst build_schema_cache.py ausführen.")

# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def col_set(schema, tbl):
    return {c["col"].upper() for c in schema.get(tbl, [])}

def trenn(titel, zeichen="─"):
    print(f"\n{zeichen*64}\n  {titel}\n{zeichen*64}")

# ── Prüfung 1: FK-Konsistenz ──────────────────────────────────────────────────

def pruefe_fk_konsistenz(cache):
    trenn("1. FK-Konsistenz")
    schema    = cache["tables"]
    relations = cache.get("relations", [])
    alle_tbls = set(schema.keys())

    fehler, warnungen, ok = [], [], []

    for r in relations:
        von_tbl  = r["von"]
        von_col  = r["von_spalte"]
        zu_tbl   = r["zu"]
        zu_col   = r["zu_spalte"]
        quelle   = r["quelle"]

        # Ziel-Tabelle vorhanden?
        if zu_tbl not in alle_tbls:
            fehler.append(f"  FEHLER  {von_tbl}.{von_col} → {zu_tbl}.{zu_col}  (Tabelle fehlt)")
            continue

        # Ziel-Spalte vorhanden?
        if zu_col.upper() not in col_set(schema, zu_tbl):
            if quelle == "db_constraint":
                fehler.append(f"  FEHLER  {von_tbl}.{von_col} → {zu_tbl}.{zu_col}  (Spalte fehlt, DB-Constraint!)")
            else:
                warnungen.append(f"  WARN    {von_tbl}.{von_col} → {zu_tbl}.{zu_col}  (Spalte fehlt, inferiert)")
        else:
            ok.append(r)

    print(f"  Geprüft: {len(relations)} Beziehungen")
    print(f"  ✓ OK:      {len(ok)}")
    print(f"  ⚠ Warnungen: {len(warnungen)}")
    print(f"  ✗ Fehler:  {len(fehler)}")
    for w in warnungen[:20]:
        print(w)
    for f in fehler[:20]:
        print(f)
    if len(warnungen) > 20:
        print(f"  ... ({len(warnungen)-20} weitere Warnungen)")

    return {"ok": len(ok), "warnungen": warnungen, "fehler": fehler}

# ── Prüfung 2: PK-Erkennung ───────────────────────────────────────────────────

def pruefe_pks(cache):
    trenn("2. PK-Erkennung (hat jede Tabelle einen erkennbaren PK?)")
    schema = cache["tables"]

    PK_MUSTER = re.compile(r"^(LFDNR|LFD_NR|LFD\w+|ID|_ID|\w+ID)$", re.IGNORECASE)
    BEKANNTE_PKS = {"LFDNR", "LFD_NR", "ADRNR", "LFDANFRAGE", "LFDANGAUFGUT"}

    ohne_pk = []
    mehrere_pk_kandidaten = []

    for tbl, cols in schema.items():
        col_namen = [c["col"].upper() for c in cols]
        kandidaten = [c for c in col_namen
                      if c in BEKANNTE_PKS or PK_MUSTER.match(c)]
        if not kandidaten:
            ohne_pk.append(tbl)
        elif len(kandidaten) > 3:
            mehrere_pk_kandidaten.append((tbl, kandidaten[:5]))

    print(f"  Tabellen ohne erkennbaren PK: {len(ohne_pk)}")
    for t in ohne_pk[:15]:
        cols_kurz = [c["col"] for c in schema[t][:6]]
        print(f"    {t:<40} Spalten: {', '.join(cols_kurz)}")
    if len(ohne_pk) > 15:
        print(f"    ... ({len(ohne_pk)-15} weitere)")

    print(f"\n  Tabellen mit >3 PK-Kandidaten (möglicherweise Komposit-PK):")
    for tbl, kands in mehrere_pk_kandidaten[:10]:
        print(f"    {tbl:<40} {kands}")

    return {"ohne_pk": ohne_pk, "komposit_pk": [t for t, _ in mehrere_pk_kandidaten]}

# ── Prüfung 3: Ungelöste LFD*-Spalten ────────────────────────────────────────

def pruefe_ungeloeste_fks(cache):
    trenn("3. Ungelöste LFD*-Spalten (potenzielle FK ohne Zuordnung)")
    schema    = cache["tables"]
    relations = cache.get("relations", [])
    alle_tbls = set(schema.keys())

    # Bereits aufgelöste FK-Spalten
    aufgeloest = {(r["von"], r["von_spalte"].upper()) for r in relations}

    ungeklaert = []
    for tbl, cols in schema.items():
        for c in cols:
            col = c["col"]
            col_u = col.upper()
            # Verdächtige Muster: LFD*, *LFDNR, *NR (numerisch)
            if col_u.startswith("LFD") and col_u not in ("LFDNR", "LFD_NR"):
                if (tbl, col_u) not in aufgeloest:
                    ungeklaert.append((tbl, col, c["type"]))

    print(f"  {len(ungeklaert)} ungelöste LFD*-Spalten")
    for tbl, col, typ in sorted(ungeklaert)[:30]:
        print(f"    {tbl:<35} {col:<30} ({typ})")
    if len(ungeklaert) > 30:
        print(f"    ... ({len(ungeklaert)-30} weitere)")

    return {"ungeklaert": [(t, c) for t, c, _ in ungeklaert]}

# ── Prüfung 4: Doppel-Tabellen ────────────────────────────────────────────────

def pruefe_duplikate(cache):
    trenn("4. Tabellen-Dubletten / Archiv-Paare")
    schema = cache["tables"]

    # Muster: TABELLE + ARCHIV, TABELLE + POS, TABELLE + KOPF
    ENDUNGEN = ["ARCHIV", "POS", "KOPF", "HIST", "ALT", "LOG", "ARC"]
    paare = []
    alle = set(schema.keys())

    for tbl in sorted(alle):
        for ende in ENDUNGEN:
            if tbl.endswith(ende):
                basis = tbl[:-len(ende)]
                if basis in alle:
                    paare.append((basis, tbl, ende))

    print(f"  {len(paare)} Tabellen-Paare erkannt:")
    for basis, abgeleitet, typ in paare:
        n_basis = len(schema[basis])
        n_abg   = len(schema[abgeleitet])
        print(f"    {basis:<30} ↔ {abgeleitet:<35} ({typ}, {n_basis}/{n_abg} Spalten)")

    return {"paare": [(b, a) for b, a, _ in paare]}

# ── Prüfung 5: Migrations-Relevanz ───────────────────────────────────────────

def pruefe_migrationstabellen(cache):
    trenn("5. Migrations-relevante Tabellen (Vollständigkeit)")
    schema = cache["tables"]

    SOLL = {
        "ADRESS":        "res.partner (Firmenstamm)",
        "KUNDE":         "res.partner customer_rank",
        "LIEFERANT":     "res.partner supplier_rank",
        "ADRANSPRECH":   "res.partner type=contact",
        "KNDLIEFER":     "res.partner type=delivery",
        "ARTIKEL":       "product.template",
        "ARTIKELLONG":   "product.template.description",
        "PRODLIST":      "mrp.bom",
        "PRODINHALT":    "mrp.bom.line",
        "ARTSTUELI":     "mrp.bom.line (Legacy)",
        "ANGAUFGUT":     "sale.order / account.move",
        "ANGAUFPOS":     "sale.order.line",
        "ANGAUFARCHIV":  "sale.order (historisch)",
        "BESTELLUNG":    "purchase.order",
        "LIEFRECH":      "account.move (in_invoice)",
        "ZAHLBEDING":    "account.payment.term",
        "LAND":          "res.country",
        "MENGENSCHL":    "uom.uom",
        "VERTRETER":     "res.users (Vertreter)",
        "CHARGEN":       "stock.lot (Charge)",
        "SERNR":         "stock.lot (Seriennummer)",
        "PREISLISTEN":   "product.pricelist",
        "PREISLISTKOPF": "product.pricelist",
    }

    print(f"  {'Tabelle':<20} {'Status':<10} {'Odoo-Ziel'}")
    print(f"  {'-'*70}")
    fehlend = []
    for tbl, odoo in SOLL.items():
        if tbl in schema:
            n = len(schema[tbl])
            print(f"  {tbl:<20} {'✓ vorhanden':<10} {odoo}  ({n} Spalten)")
        else:
            print(f"  {tbl:<20} {'✗ FEHLT':<10} {odoo}")
            fehlend.append(tbl)

    print(f"\n  Fehlende Tabellen: {fehlend or 'keine'}")
    return {"soll": SOLL, "fehlend": fehlend}

# ── Prüfung 6: Feld-Vollständigkeit Kerntabellen ──────────────────────────────

def pruefe_pflichtfelder(cache):
    trenn("6. Pflichtfelder in Kerntabellen")
    schema = cache["tables"]

    SOLL_FELDER = {
        "ARTIKEL":   ["LFDNR", "ARTNR1", "ABEZ1", "EKPR", "VKPR1", "MENGENSCHL", "LFDLIEFNR"],
        "ADRESS":    ["ADRNR", "KUNDE", "LIEFERANT"],
        "LIEFERANT": ["ADRNR", "NAME1", "ORT", "EMAIL"],
        "ANGAUFGUT": ["LFDNR", "ANGEBOT", "AUFTRAG", "GUTSCHRIFT", "KNDNR", "ERFASSDATUM"],
        "ANGAUFPOS": ["LFDANGAUFGUTNR", "LFDARTNR", "BESTMENGE", "PREIS", "POSNR"],
        "PRODLIST":  ["LFD_NR", "ART_NR"],
        "PRODINHALT":["LIST_NR", "ART_NR", "MENGE"],
        "ARTSTUELI": ["LFDARTNR1", "LFDARTNR2", "MENGE"],
        "ANFRAGE":   ["LFDANFRAGE", "ANFRAGEDATUM"],
        "ANFRAGEPOS":["LFDANFRAGE", "ARTNR1", "MENGE"],
    }

    alle_ok = True
    for tbl, pflicht in SOLL_FELDER.items():
        if tbl not in schema:
            print(f"  ✗ {tbl}: Tabelle fehlt komplett!")
            alle_ok = False
            continue
        vorhanden = col_set(schema, tbl)
        fehlend = [f for f in pflicht if f.upper() not in vorhanden]
        status = "✓" if not fehlend else "⚠"
        print(f"  {status} {tbl:<20} fehlend: {fehlend or 'keine'}")
        if fehlend:
            alle_ok = False

    return {"alle_ok": alle_ok}

# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    print("=" * 64)
    print("  eEvolution Schema – KI-Logik-Validierung")
    print("  (read-only, keine DB-Verbindung nötig)")
    print("=" * 64)

    cache = lade_schema()
    m = cache["_meta"]
    print(f"\n  Schema: {m.get('database')} @ {m.get('server')}")
    print(f"  Stand:  {m.get('generated')}")
    print(f"  Inhalt: {m.get('tables')} Tabellen · "
          f"{m.get('columns')} Spalten · "
          f"{m.get('relations')} Beziehungen")

    ergebnisse = {}
    ergebnisse["fk"]          = pruefe_fk_konsistenz(cache)
    ergebnisse["pk"]          = pruefe_pks(cache)
    ergebnisse["ungeklaert"]  = pruefe_ungeloeste_fks(cache)
    ergebnisse["duplikate"]   = pruefe_duplikate(cache)
    ergebnisse["migration"]   = pruefe_migrationstabellen(cache)
    ergebnisse["pflichtfeld"] = pruefe_pflichtfelder(cache)

    # ── Zusammenfassung ───────────────────────────────────────────────────────
    trenn("ZUSAMMENFASSUNG", "═")
    fk = ergebnisse["fk"]
    print(f"  FK-Konsistenz:   {fk['ok']} OK  |  "
          f"{len(fk['warnungen'])} Warnungen  |  "
          f"{len(fk['fehler'])} Fehler")
    print(f"  PKs erkannt:     {len(ergebnisse['pk']['ohne_pk'])} Tabellen ohne PK")
    print(f"  Offene LFD*-FK:  {len(ergebnisse['ungeklaert']['ungeklaert'])}")
    print(f"  Archiv-Paare:    {len(ergebnisse['duplikate']['paare'])}")
    fehlend = ergebnisse["migration"]["fehlend"]
    print(f"  Migrationstab.:  {len(fehlend)} fehlend: {fehlend or 'keine'}")
    pf_ok = ergebnisse["pflichtfeld"]["alle_ok"]
    print(f"  Pflichtfelder:   {'✓ alle vorhanden' if pf_ok else '⚠ Lücken gefunden'}")

    # ── JSON-Report ───────────────────────────────────────────────────────────
    report = {
        "schema_meta": m,
        "ergebnisse": {
            "fk_fehler":        ergebnisse["fk"]["fehler"],
            "fk_warnungen":     ergebnisse["fk"]["warnungen"][:50],
            "ohne_pk":          ergebnisse["pk"]["ohne_pk"],
            "ungeklaerte_fks":  [f"{t}.{c}" for t, c in ergebnisse["ungeklaert"]["ungeklaert"][:50]],
            "archiv_paare":     ergebnisse["duplikate"]["paare"],
            "fehlende_tabellen":fehlend,
            "pflichtfelder_ok": pf_ok,
        }
    }
    with open("validate_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Report gespeichert: validate_report.json")
    print(f"\nNächster Schritt:")
    print(f"    python 99_scripts/build_odoo_schema.py")


if __name__ == "__main__":
    main()
