#!/usr/bin/env python3
"""
04_load_config.py — Konfig-/Stammobjekte in Odoo anlegen (Phase B1), idempotent.

Legt die External IDs an, die 02_transform.py referenziert:
  - product.category   ev_wgrup_<LFDNR>   aus lookups/WGRUPPE.csv
  - account.payment.term ev_zbed_<ZBNR>   aus lookups/ZAHLBEDING.csv (mit Frist + Skonto)
  - uom.uom            ev_uom_6 / ev_uom_8  (Rollen / Set, Kategorie Einheit)

Upsert über ir.model.data (mehrfacher Lauf aktualisiert statt dupliziert).
Zugang aus .env (ODOO_URL/DB/USER/API_KEY). Schreibt in Odoo -> Testinstanz!
"""
import os, sys, csv, re, xmlrpc.client
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOOKUP_DIR = ROOT / "01_quelle_eevolution" / "lookups"

for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if (ROOT / ".env").exists() else []:
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

URL, DB = os.getenv("ODOO_URL"), os.getenv("ODOO_DB")
USER, KEY = os.getenv("ODOO_USER"), os.getenv("ODOO_API_KEY")


def read_csv(name):
    with (LOOKUP_DIR / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def connect():
    common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
    uid = common.authenticate(DB, USER, KEY, {})
    if not uid:
        sys.exit("Auth fehlgeschlagen.")
    return uid, xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")


def main():
    if not all([URL, DB, USER, KEY]):
        sys.exit("ODOO_URL/DB/USER/API_KEY fehlen (.env).")
    uid, models = connect()

    def has_field(model, field):
        return field in models.execute_kw(DB, uid, KEY, model, "fields_get", [[], ["string"]])

    def upsert(model, xmlid, vals):
        mod, nm = xmlid.split(".", 1) if "." in xmlid else ("__import__", xmlid)
        ex = models.execute_kw(DB, uid, KEY, "ir.model.data", "search_read",
                               [[["module", "=", mod], ["name", "=", nm], ["model", "=", model]]],
                               {"fields": ["res_id"], "limit": 1})
        if ex:
            models.execute_kw(DB, uid, KEY, model, "write", [[ex[0]["res_id"]], vals])
            return ex[0]["res_id"], "upd"
        rid = models.execute_kw(DB, uid, KEY, model, "create", [vals])
        models.execute_kw(DB, uid, KEY, "ir.model.data", "create",
                          [{"module": mod, "name": nm, "model": model, "res_id": rid}])
        return rid, "new"

    def xmlid_res(xmlid):
        mod, nm = xmlid.split(".", 1)
        r = models.execute_kw(DB, uid, KEY, "ir.model.data", "search_read",
                              [[["module", "=", mod], ["name", "=", nm]]], {"fields": ["res_id"], "limit": 1})
        return r[0]["res_id"] if r else None

    # 1) Warengruppen -> product.category
    n_new = n_upd = 0
    for r in read_csv("WGRUPPE.csv"):
        lfd = (r.get("LFDNR") or "").strip()
        name = (r.get("WGRBEZ") or "").strip() or (r.get("WGRUPPE") or "").strip() or f"WG {lfd}"
        if not lfd:
            continue
        _, st = upsert("product.category", f"__import__.ev_wgrup_{lfd}", {"name": name})
        n_new += st == "new"; n_upd += st == "upd"
    print(f"product.category: {n_new} neu, {n_upd} aktualisiert")

    # Produktfamilien unter K&F-Systems; bei installiertem Add-on inklusive Präfix.
    import yaml
    serial_cfg = yaml.safe_load((ROOT / "02_mappings" / "product_serial_groups.yaml").read_text(encoding="utf-8"))
    root_id, _ = upsert("product.category", "__import__.ev_serial_root", {"name": serial_cfg["root_category"]})
    custom_ready = has_field("product.category", "kf_serial_required")
    for group in serial_cfg["groups"]:
        slug = re.sub(r"[^a-z0-9]+", "_", group["name"].lower()).strip("_")
        vals = {"name": group["name"], "parent_id": root_id}
        if custom_ready:
            vals.update({"kf_serial_required": True, "kf_serial_prefix": group["prefix"]})
        upsert("product.category", f"__import__.ev_serial_group_{slug}", vals)
    print(f"K&F-Seriennummerngruppen: {len(serial_cfg['groups'])} konfiguriert"
          + ("" if custom_ready else " [WARN: Add-on kf_serial_category noch nicht installiert]"))

    # 2) Zahlungsbedingungen -> account.payment.term
    early = has_field("account.payment.term", "early_discount")
    def to_int(v):
        try: return int(float(str(v).replace(",", ".")))
        except: return 0
    def to_pct(v):
        try: return float(str(v).replace(",", "."))
        except: return 0.0
    n_new = n_upd = 0
    for r in read_csv("ZAHLBEDING.csv"):
        zbnr = (r.get("ZBNR") or "").strip()
        name = (r.get("BEDINGUNG") or "").strip() or f"ZB {zbnr}"
        if not zbnr:
            continue
        ntage = to_int(r.get("NTAGE"))
        # eine Zeile: 100% faellig nach NTAGE Tagen (Odoo19: 'percent' + value_amount)
        line = {"value": "percent", "value_amount": 100.0,
                "delay_type": "days_after", "nb_days": ntage}
        vals = {"name": name, "line_ids": [(5, 0, 0), (0, 0, line)]}
        sk1 = to_pct(r.get("SKONTO1")); sk1t = to_int(r.get("SKONTO1TAGE"))
        if early and sk1 > 0 and sk1t > 0:
            vals.update({"early_discount": True, "discount_percentage": sk1, "discount_days": sk1t})
        _, st = upsert("account.payment.term", f"__import__.ev_zbed_{zbnr}", vals)
        n_new += st == "new"; n_upd += st == "upd"
    print(f"account.payment.term: {n_new} neu, {n_upd} aktualisiert (Skonto-Feld: {'ja' if early else 'nein'})")

    # 3) eigene Einheiten Rollen/Set — Odoo19: keine Kategorien mehr, relative Verkettung.
    #    Eigenstaendige Basiseinheit = Name + relative_factor 1.0 (kein relative_uom_id).
    for xid, nm in [("ev_uom_6", "Rollen"), ("ev_uom_8", "Set")]:
        _, st = upsert("uom.uom", f"__import__.{xid}", {"name": nm, "relative_factor": 1.0})
        print(f"uom.uom {nm} ({xid}): {st}")

    # 4) historische 16%-Steuer (COVID-Periode) — fehlt im SKR03; durch Klonen der 19%-Steuer.
    ex = models.execute_kw(DB, uid, KEY, "ir.model.data", "search_read",
                           [[["module", "=", "__import__"], ["name", "=", "ev_tax_16"]]],
                           {"fields": ["res_id"], "limit": 1})
    if ex:
        print("account.tax ev_tax_16: bereits vorhanden")
    else:
        src = xmlid_res("account.1_tax_ust_19_skr03")
        if src:
            new_id = models.execute_kw(DB, uid, KEY, "account.tax", "copy", [[src]])
            new_id = new_id[0] if isinstance(new_id, list) else new_id
            models.execute_kw(DB, uid, KEY, "account.tax", "write",
                              [[new_id], {"name": "16% (historisch)", "amount": 16.0,
                                          "description": "USt 16% (2020)"}])
            models.execute_kw(DB, uid, KEY, "ir.model.data", "create",
                              [{"module": "__import__", "name": "ev_tax_16",
                                "model": "account.tax", "res_id": new_id}])
            print("account.tax ev_tax_16: angelegt (16%)")
        else:
            print("[WARN] 19%-Steuer nicht gefunden -> ev_tax_16 nicht angelegt")

    print("[OK] Konfig-Objekte verarbeitet.")


if __name__ == "__main__":
    main()
