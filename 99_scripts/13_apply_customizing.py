#!/usr/bin/env python3
"""
13_apply_customizing.py — Odoo-19 [Std]-Customizing per XML-RPC aktivieren.

Aenderungen (Stand 2026-06-01, kuf-erp-test):
  group_stock_tracking_lot    False -> True  (Pakete/Packages)
  group_sale_delivery_address False -> True  (Liefer-/Rechnungsadressen am Kunden)
  group_use_lead              False -> True  (CRM-Leads aktivieren)
  module_mrp_subcontracting   False -> True  (Unterauftragsvergabe / Lohnfertigung)
  + Englisch (en_US) als 2. Sprache installieren

Bereits aktiv (unveraendert): group_stock_multi_locations, group_stock_production_lot,
  group_product_pricelist, group_multi_currency, module_stock_barcode.

Vorsicht: module_* loest Modul-Installation aus -> Odoo-Worker kann neu starten.
  Kein Problem auf Test-DB; vor Produktivsystem Snapshot nehmen.

Aufruf: python 99_scripts/13_apply_customizing.py [--dry-run]
"""
import os, sys, time, xmlrpc.client
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if (ROOT / ".env").exists() else []:
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

URL, DB = os.getenv("ODOO_URL"), os.getenv("ODOO_DB")
USER, KEY = os.getenv("ODOO_USER"), os.getenv("ODOO_API_KEY")

SETTINGS_TO_ENABLE = {
    "group_stock_multi_locations": "Mehrere Lagerorte",
    "group_stock_adv_location":    "Mehrstufige Routen je Produkt",
    "group_stock_production_lot":  "Seriennummern und Chargen",
    "group_stock_tracking_lot":    "Pakete (Packages)",
    "group_product_pricelist":     "Verkaufspreislisten",
    "group_multi_currency":        "Mehrwaehrung",
    "group_sale_delivery_address": "Liefer-/Rechnungsadressen",
    "group_mrp_routings":          "Arbeitsgaenge und Werkstatt",
    "module_quality_control":      "Qualitaetskontrolle (QS-Pruefpunkte + Pruefprotokolle)",
    # quality_mrp + quality_mrp_workorder werden per ir.module.module direkt installiert
    # (kein res.config.settings-Feld in Odoo 19)
    "group_use_lead":              "CRM-Leads",
    "module_mrp_subcontracting":   "Unterauftragsvergabe (Modul-Install!)",
    "module_purchase_requisition": "Einkaufsvereinbarungen/Rahmenbestellungen",
}


def connect():
    common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
    uid = common.authenticate(DB, USER, KEY, {})
    if not uid:
        sys.exit("Auth fehlgeschlagen.")
    return uid, xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")


def main():
    dry = "--dry-run" in sys.argv
    if dry:
        print("[DRY-RUN] Keine Aenderungen werden gespeichert.\n")
    if not all([URL, DB, USER, KEY]):
        sys.exit("ODOO_URL/DB/USER/API_KEY fehlen (.env).")

    uid, models = connect()

    def kw(model, method, a, kwargs=None):
        return models.execute_kw(DB, uid, KEY, model, method, a, kwargs or {})

    # -- 1. res.config.settings -----------------------------------------------
    print("=== res.config.settings ===")

    # Felder die wirklich existieren (module_* fuer noch nicht installierte fehlen)
    all_fields = kw("res.config.settings", "fields_get", [list(SETTINGS_TO_ENABLE.keys())],
                    {"attributes": ["type"]})
    existing_fields = [f for f in SETTINGS_TO_ENABLE if f in all_fields]
    missing_fields  = [f for f in SETTINGS_TO_ENABLE if f not in all_fields]
    if missing_fields:
        print(f"  INFO: {len(missing_fields)} Felder noch nicht verfuegbar (Modul erst installieren):")
        for f in missing_fields: print(f"    {f}: {SETTINGS_TO_ENABLE[f]}")

    # Ist-Stand lesen (nur vorhandene Felder)
    cur_vals = kw("res.config.settings", "default_get", [existing_fields]) if existing_fields else {}

    changes = {}
    for field, label in SETTINGS_TO_ENABLE.items():
        if field not in existing_fields:
            continue  # wird nach Modul-Install in naechstem Lauf gesetzt
        cur_val = cur_vals.get(field, False)
        if cur_val:
            print(f"  SKIP  {field}: bereits True ({label})")
        else:
            print(f"  SET   {field}: False -> True ({label})")
            changes[field] = True

    if changes and not dry:
        print("\nErzeuge res.config.settings-Record und fuehre execute() aus...")
        cfg_id = kw("res.config.settings", "create", [changes])
        print(f"  Config-ID: {cfg_id}")
        try:
            kw("res.config.settings", "execute", [[cfg_id]])
            print("  execute() OK")
        except xmlrpc.client.Fault as e:
            print(f"  WARN execute() Fault: {e.faultString[:200]}")
            # Manche Odoo-Versionen werfen 'False'-Marshal-Fehler aber fuehren es durch
            print("  (Pruefen ob Settings trotzdem gesetzt wurden)")

        # Verifikation (nur Felder die existieren)
        time.sleep(3)
        ver = kw("res.config.settings", "search_read", [[]],
                 {"fields": existing_fields, "limit": 1, "order": "id desc"})
        if ver:
            print("\nVerifikation:")
            for f in SETTINGS_TO_ENABLE:
                print(f"  {f}: {ver[0].get(f)}")
    elif not changes:
        print("  Alle Settings bereits aktiv, nichts zu tun.")

    # -- 2. Englisch installieren ---------------------------------------------
    print("\n=== Sprache en_US ===")
    # Pruefen ob en_US aktiv
    active_en = kw("res.lang", "search", [[["code", "=", "en_US"], ["active", "=", True]]])
    if active_en:
        print("  en_US bereits aktiv, SKIP.")
    else:
        # Pruefen ob inaktiv vorhanden
        inactive_en = kw("res.lang", "search",
                         [[["code", "=", "en_US"], ["active", "=", False]]])
        if not dry:
            if inactive_en:
                print(f"  en_US vorhanden (inaktiv, id={inactive_en[0]}), aktiviere...")
                kw("res.lang", "write", [inactive_en, {"active": True}])
            # Sprach-Wizard (laedt auch Uebersetzungen)
            print("  Starte base.language.install-Wizard...")
            try:
                wiz_id = kw("base.language.install", "create",
                            [{"lang_ids": [(4, inactive_en[0])] if inactive_en else [],
                              "lang": "en_US", "overwrite": False}])
                kw("base.language.install", "lang_install", [[wiz_id]])
                print("  Sprachinstallation OK")
            except xmlrpc.client.Fault as e:
                print(f"  WARN Sprachinstallation: {e.faultString[:200]}")
                # Fallback: manuell aktivieren
                if inactive_en:
                    print("  Fallback: nur res.lang aktiviert (ohne Uebersetzungen)")
                else:
                    print("  en_US Sprachdatensatz nicht gefunden; ggf. manuell in Einstellungen aktivieren.")
        else:
            print("  [dry-run] wuerde en_US installieren")

    # -- 3. Pflichtmodule direkt installieren (idempotent) --------------------
    print("\n=== Pflichtmodule (direkt) ===")
    for mod_name, mod_label in [
        ("quality_control",       "Qualitaetskontrolle"),
        ("quality_mrp",           "QS in Fertigung"),
        ("quality_mrp_workorder", "QS in Werkstatt/Shop Floor"),
        ("mrp_subcontracting",     "Unterauftragsvergabe/Fremdfertigung"),
        ("purchase_requisition",   "Einkaufsvereinbarungen/Rahmenbestellungen"),
        ("delivery",               "Versandmethoden/Versandkosten (Basis)"),
    ]:
        mod = kw("ir.module.module", "search_read",
                 [[["name", "=", mod_name]]], {"fields": ["state", "id"], "limit": 1})
        if not mod:
            print(f"  {mod_name}: nicht gefunden")
        elif mod[0]["state"] == "installed":
            print(f"  {mod_name}: bereits installiert, SKIP ({mod_label})")
        elif not dry:
            print(f"  {mod_name}: installiere ({mod_label})...")
            try:
                kw("ir.module.module", "button_immediate_install", [[mod[0]["id"]]])
                print(f"  {mod_name}: installiert")
                time.sleep(3)
            except xmlrpc.client.Fault as e:
                print(f"  WARN {mod_name}: {e.faultString[:100]}")
        else:
            print(f"  [dry] {mod_name}: wuerde installieren")

    # -- 4. Zusammenfassung ---------------------------------------------------
    print("\n=== Zusammenfassung ===")
    if dry:
        print("  DRY-RUN -- keine Aenderungen geschrieben.")
    else:
        print("  Gesetzt:", list(changes.keys()) if changes else "nichts geaendert")
        print("  Sprache: en_US installiert/aktiviert (falls noch nicht)")
        print()
        print("  HINWEIS: Wenn module_mrp_subcontracting installiert wurde,")
        print("  war ein Odoo-Worker-Neustart moeglich. Kurz warten und pruefen")
        print("  ob http://192.168.120.225:8069 erreichbar bleibt.")
    print("[FERTIG]")


if __name__ == "__main__":
    main()
