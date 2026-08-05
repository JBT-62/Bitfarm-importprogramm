#!/usr/bin/env python3
"""
build_odoo_schema.py
Liest das Odoo 19 Enterprise Schema via XML-RPC (read-only).
Speichert alle relevanten Modell-Felder als odoo_schema.json.

Ausführen:
    python 99_scripts/build_odoo_schema.py

Ergebnis:
    odoo_schema.json
"""

import os, sys, json, xmlrpc.client
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Odoo-Verbindung ───────────────────────────────────────────────────────────

def odoo_connect():
    url     = os.getenv("ODOO_URL",    "http://192.168.120.225:8069")
    db      = os.getenv("ODOO_DB",     "erp-test-1")
    user    = os.getenv("ODOO_USER",   "admin")
    api_key = os.getenv("ODOO_API_KEY", os.getenv("ODOO_APIKEY", ""))

    if not api_key:
        sys.exit("FEHLER: ODOO_API_KEY fehlt in .env")

    common  = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common", allow_none=True)
    uid     = common.authenticate(db, user, api_key, {})
    if not uid:
        sys.exit("FEHLER: Odoo-Authentifizierung fehlgeschlagen")

    models  = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
    version = common.version()
    print(f"[OK] Verbunden mit {url} / {db}  (Odoo {version.get('server_version', '?')})")
    return models, db, uid, api_key


def odoo_call(models, db, uid, api_key, model, method, args=None, kwargs=None):
    return models.execute_kw(db, uid, api_key, model, method,
                              args or [[]], kwargs or {})


# ── Relevante Odoo-Modelle ─────────────────────────────────────────────────────

RELEVANTE_MODELLE = [
    # Partner / Adressen
    "res.partner",
    "res.country",
    "res.country.state",

    # Produkte
    "product.template",
    "product.product",
    "product.category",
    "uom.uom",
    "uom.category",

    # Stücklisten
    "mrp.bom",
    "mrp.bom.line",

    # Verkauf
    "sale.order",
    "sale.order.line",

    # Einkauf
    "purchase.order",
    "purchase.order.line",
    "product.supplierinfo",

    # Rechnung / Buchhaltung
    "account.move",
    "account.move.line",
    "account.payment.term",
    "account.payment.term.line",
    "account.tax",
    "account.account",

    # Lager
    "stock.lot",
    "stock.quant",
    "stock.location",
    "stock.picking",
    "stock.move",

    # CRM
    "crm.lead",

    # Benutzer / Unternehmen
    "res.users",
    "res.company",

    # Preislisten
    "product.pricelist",
    "product.pricelist.item",

    # Sonstiges
    "account.fiscal.position",
]


def lade_felder(models, db, uid, api_key, modell_name):
    """Alle Felder eines Odoo-Modells laden."""
    try:
        felder = odoo_call(
            models, db, uid, api_key,
            "ir.model.fields", "search_read",
            [[["model", "=", modell_name]]],
            {"fields": [
                "name", "field_description", "ttype",
                "required", "readonly", "store",
                "relation", "relation_field",
                "selection", "help",
            ]}
        )
        return felder
    except Exception as e:
        print(f"    WARN: {modell_name} – Felder nicht lesbar: {e}")
        return []


def lade_modell_info(models, db, uid, api_key, modell_name):
    """Modell-Metadaten laden."""
    try:
        info = odoo_call(
            models, db, uid, api_key,
            "ir.model", "search_read",
            [[["model", "=", modell_name]]],
            {"fields": ["name", "model", "info", "transient"]}
        )
        return info[0] if info else {}
    except Exception:
        return {}


# ── Schema aufbauen ───────────────────────────────────────────────────────────

def baue_odoo_schema(models, db, uid, api_key):
    schema = {}
    meta_modelle = {}

    for modell in RELEVANTE_MODELLE:
        print(f"  {modell} …", end=" ", flush=True)
        info   = lade_modell_info(models, db, uid, api_key, modell)
        felder = lade_felder(models, db, uid, api_key, modell)

        if not felder:
            print("(leer/fehlt)")
            continue

        meta_modelle[modell] = {
            "name":    info.get("name", modell),
            "model":   modell,
            "felder":  len(felder),
        }

        schema[modell] = []
        for f in sorted(felder, key=lambda x: x["name"]):
            eintrag = {
                "name":        f["name"],
                "label":       f["field_description"],
                "type":        f["ttype"],
                "required":    f["required"],
                "readonly":    f["readonly"],
                "stored":      f["store"],
                "relation":    f.get("relation") or "",
                "help":        (f.get("help") or "")[:200],
            }
            if f["ttype"] == "selection" and f.get("selection"):
                eintrag["choices"] = f["selection"]
            schema[modell].append(eintrag)

        print(f"{len(felder)} Felder")

    return schema, meta_modelle


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    models, db, uid, api_key = odoo_connect()

    print(f"\n[1] Lade Felder für {len(RELEVANTE_MODELLE)} Modelle …")
    schema, meta = baue_odoo_schema(models, db, uid, api_key)

    total_felder = sum(len(v) for v in schema.values())
    print(f"\n    {len(schema)} Modelle  ·  {total_felder} Felder geladen")

    cache = {
        "_meta": {
            "url":       os.getenv("ODOO_URL"),
            "db":        db,
            "generated": datetime.now().isoformat(timespec="seconds"),
            "modelle":   len(schema),
            "felder":    total_felder,
        },
        "modelle": meta,
        "felder":  schema,
    }

    pfad = "odoo_schema.json"
    with open(pfad, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"[OK] Gespeichert: {pfad}")
    print(f"\nNächster Schritt:")
    print(f"    python 99_scripts/mapping_report.py")


if __name__ == "__main__":
    main()
