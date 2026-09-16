#!/usr/bin/env python3
"""Import historical eEvolution sales documents without operational side effects.

Documents with at least one valid line and a usable delivery address become locked
``sale.order`` records. Empty/invalid documents and incomplete alternate delivery
addresses are retained in ``kf.legacy.sales.document`` for review.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import os
import socket
import time
import xmlrpc.client

import pyodbc

import migration_runtime


TAX_XMLIDS = {
    1: "__import__.ev_tax_16",
    2: "account.1_tax_not_taxable_skr03",
    3: "account.1_tax_ust_7_skr03",
    4: "account.1_tax_eu_sale_skr03",
    5: "account.1_tax_ust_19_skr03",
    6: "account.1_tax_eu_sale_skr03",
}
COUNTRY_ALIASES = {
    "D": "DE", "A": "AT", "F": "FR", "B": "BE", "I": "IT", "E": "ES",
    "S": "SE", "N": "NO", "H": "HU", "FIN": "FI", "CDN": "CA", "USA": "US",
    "AUS": "AU", "J": "JP", "CHN": "CN", "VRC": "CN", "PRC": "CN",
    "UAE": "AE", "ROK": "KR", "TWN": "TW", "WAN": "TW", "SGP": "SG",
    "IND": "IN", "MAL": "MY", "SLO": "SI", "RL": "LB", "RI": "ID",
    "MEX": "MX", "ARM": "AM", "SRB": "RS", "EST": "EE", "NCL": "NC",
    "GCA": "GT", "LAR": "LY", "YV": "VE", "HKJ": "JO", "BIH": "BA",
    "RP": "PH", "IRL": "IE", "P": "PT", "SP": "ES", "FLA": "BE",
    "EIR": "IE", "KRO": "HR", "TÜR": "TR", "YU": "RS", "YUG": "RS",
    "RUS": "RU",
}


def clean(value):
    return str(value or "").strip()


def as_int(value):
    return int(value) if value is not None else None


def chunks(values, size):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def source_connection():
    cs = (
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
        f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "ApplicationIntent=ReadOnly;"
    )
    return pyodbc.connect(cs, readonly=True, timeout=30)


class Odoo:
    def __init__(self):
        self.url, self.db, self.user, self.key = [
            os.environ[name] for name in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_API_KEY")
        ]
        migration_runtime.require_target(self.db)
        common = migration_runtime.server_proxy(self.url + "/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, self.user, self.key, {})
        if not self.uid:
            raise RuntimeError("Odoo-Authentifizierung fehlgeschlagen")
        self.models = migration_runtime.server_proxy(self.url + "/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args=None, kwargs=None):
        last = None
        for attempt in range(6):
            try:
                return self.models.execute_kw(
                    self.db, self.uid, self.key, model, method, args or [], kwargs or {}
                )
            except xmlrpc.client.Fault:
                raise
            except (ConnectionError, OSError, socket.error) as exc:
                last = exc
                time.sleep(min(20, 2 ** attempt))
                self.models = migration_runtime.server_proxy(
                    self.url + "/xmlrpc/2/object", allow_none=True
                )
        raise RuntimeError(f"Odoo nicht erreichbar: {last!r}")

    def external_ids(self, prefixes):
        result = {}
        for prefix in prefixes:
            rows = self.call(
                "ir.model.data", "search_read",
                [[("module", "=", "__import__"), ("name", "like", prefix + "%")]],
                {"fields": ["name", "model", "res_id"], "limit": 100000},
            )
            result.update({row["name"]: row for row in rows})
        return result

    def resolve_xmlid(self, xmlid):
        module, name = xmlid.split(".", 1)
        rows = self.call(
            "ir.model.data", "search_read",
            [[("module", "=", module), ("name", "=", name)]],
            {"fields": ["res_id"], "limit": 1},
        )
        return rows[0]["res_id"] if rows else None

    def register_many(self, model, names, ids):
        values = [
            {"module": "__import__", "name": name, "model": model, "res_id": record_id}
            for name, record_id in zip(names, ids)
        ]
        if values:
            self.call("ir.model.data", "create", [values])


def load_source(cutoff, only_ids, limit):
    with source_connection() as cn:
        cur = cn.cursor()
        sql = """
            SELECT h.LFDNR,h.KNDNR,h.ANGEBOT,h.AUFTRAG,h.GUTSCHRIFT,h.KENNZEICHEN,
                   h.STATUS,h.ERLEDIGT,h.ERFASSDATUM,h.ABWEICH,h.ABWNAME1,h.ABWNAME2,
                   h.ABWNAME3,h.ABWNAME4,h.ABWANSPRECH,h.ABWSTRASSE,h.ABWPLZ,h.ABWORT,
                   h.ABWLAND
              FROM dbo.ANGAUFGUT h
             WHERE h.AAGAUFART<>8 AND h.ERFASSDATUM>=?
               AND NOT (h.GUTSCHRIFT=1 AND h.AUFTRAG=0 AND h.ANGEBOT=0)
        """
        params = [cutoff]
        if only_ids:
            marks = ",".join("?" for _ in only_ids)
            sql += f" AND h.LFDNR IN ({marks})"
            params.extend(sorted(only_ids))
        sql += " ORDER BY h.LFDNR"
        cur.execute(sql, *params)
        columns = [item[0] for item in cur.description]
        heads = [dict(zip(columns, row)) for row in cur.fetchall()]
        if limit:
            heads = heads[:limit]
        head_ids = [as_int(row["LFDNR"]) for row in heads]
        if not head_ids:
            return [], {}, {}

        cur.execute("SELECT KNDNR,ADRNR FROM dbo.KUNDE WHERE ADRNR IS NOT NULL")
        customer_to_address = {as_int(row[0]): as_int(row[1]) for row in cur.fetchall()}
        positions = defaultdict(list)
        for part in chunks(head_ids, 500):
            marks = ",".join("?" for _ in part)
            cur.execute(
                f"""
                SELECT p.LFDANGAUFGUTNR,p.POSNR,p.LFDARTNR,p.BESTMENGE,p.PREIS,p.RABATT,
                       p.MWSTSCHL,p.GUELTIG,p.ABWABEZ1,p.ABWABEZ2,p.ABEZ3,p.ABEZ4,
                       p.TEXT1,p.TEXT2,a.ARTNR1,a.ABEZ1
                  FROM dbo.ANGAUFPOS p
                  LEFT JOIN dbo.ARTIKEL a ON a.LFDNR=p.LFDARTNR
                 WHERE p.LFDANGAUFGUTNR IN ({marks})
                 ORDER BY p.LFDANGAUFGUTNR,p.POSNR
                """,
                *part,
            )
            cols = [item[0] for item in cur.description]
            for row in cur.fetchall():
                item = dict(zip(cols, row))
                positions[as_int(item["LFDANGAUFGUTNR"])].append(item)
    return heads, positions, customer_to_address


def line_name(line):
    parts = [
        line.get("ABWABEZ1") or line.get("ABEZ1"), line.get("ABWABEZ2"),
        line.get("ABEZ3"), line.get("ABEZ4"), line.get("TEXT1"), line.get("TEXT2"),
    ]
    return "\n".join(clean(part) for part in parts if clean(part)) or "Historische Position"


def document_type(head):
    if head["AUFTRAG"] and head["ANGEBOT"]:
        return "mixed"
    return "order" if head["AUFTRAG"] else "quotation"


def address_incomplete(head):
    return bool(head["ABWEICH"]) and not (
        clean(head["ABWNAME1"]) and clean(head["ABWSTRASSE"]) and clean(head["ABWORT"])
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="")
    parser.add_argument("--cutoff", default="2016-09-16")
    parser.add_argument("--only-id", type=int, action="append", default=[])
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cutoff = datetime.strptime(args.cutoff, "%Y-%m-%d")
    target = migration_runtime.require_target(os.environ["ODOO_DB"])
    if args.apply and (not args.backup or not args.backup.startswith(target.backup_prefix)):
        raise SystemExit("Apply verlangt eine passende verifizierte Sicherung")

    heads, positions, customer_to_address = load_source(cutoff, set(args.only_id), args.limit)
    odoo = Odoo()
    links = odoo.external_ids((
        "ev_adr_", "ev_product_", "ev_vorgang_", "ev_sale_delivery_", "ev_legacy_sales_review_"
    ))
    partner_by_address = {
        int(name.removeprefix("ev_adr_")): row["res_id"]
        for name, row in links.items() if name.startswith("ev_adr_") and name.removeprefix("ev_adr_").isdigit()
    }
    template_by_source = {
        int(name.removeprefix("ev_product_")): row["res_id"]
        for name, row in links.items() if name.startswith("ev_product_") and name.removeprefix("ev_product_").isdigit()
    }
    templates = {}
    for part in chunks(list(template_by_source.values()), 500):
        for row in odoo.call("product.template", "read", [part], {"fields": ["product_variant_id", "uom_id"]}):
            templates[row["id"]] = row
    product_by_source = {}
    uom_by_source = {}
    for source_id, template_id in template_by_source.items():
        row = templates.get(template_id, {})
        if row.get("product_variant_id"):
            product_by_source[source_id] = row["product_variant_id"][0]
            uom_by_source[source_id] = row["uom_id"][0]

    taxes = {code: odoo.resolve_xmlid(xmlid) for code, xmlid in TAX_XMLIDS.items()}
    countries = {
        clean(row["code"]).upper(): row["id"]
        for row in odoo.call("res.country", "search_read", [[]], {"fields": ["code"], "limit": 1000})
    }
    missing = []
    sales = []
    reviews = []
    address_plans = []
    existing_sales = existing_reviews = 0
    for head in heads:
        source_id = as_int(head["LFDNR"])
        source_lines = positions.get(source_id, [])
        valid_lines = [line for line in source_lines if as_int(line["GUELTIG"]) == 1]
        incomplete = address_incomplete(head)
        unresolved_lines = []
        for line in valid_lines:
            article_id = as_int(line["LFDARTNR"])
            tax_key = as_int(line["MWSTSCHL"])
            if not product_by_source.get(article_id) or not uom_by_source.get(article_id) or not taxes.get(tax_key):
                unresolved_lines.append(line)
        partner = partner_by_address.get(customer_to_address.get(as_int(head["KNDNR"])))
        if not partner:
            missing.append(f"Beleg {source_id}: Kunde {head['KNDNR']}")
            continue
        if not valid_lines or incomplete or unresolved_lines:
            name = f"ev_legacy_sales_review_{source_id}"
            if name in links:
                existing_reviews += 1
                continue
            reasons = []
            note_parts = []
            if not valid_lines:
                reasons.append("no_lines")
                note_parts.append("Keine in eEvolution gültige Position; nicht als operativer Odoo-Auftrag angelegt.")
            if incomplete:
                reasons.append("address")
                note_parts.append("Abweichende Lieferadresse unvollständig; keine stille Ersetzung durch die Hauptadresse.")
            if unresolved_lines:
                reasons.append("product")
                refs = ", ".join(
                    f"Pos. {as_int(line['POSNR'])}: Artikel-ID {as_int(line['LFDARTNR'])}"
                    for line in unresolved_lines[:20]
                )
                note_parts.append(
                    "Mindestens ein historischer Artikel ist im heutigen Odoo-Artikelstamm nicht auflösbar: " + refs
                )
            reason = reasons[0] if len(reasons) == 1 else "multiple"
            review_lines = []
            for line in source_lines:
                article_id = as_int(line["LFDARTNR"])
                review_lines.append((0, 0, {
                    "source_line_id": as_int(line["POSNR"]),
                    "position_number": as_int(line["POSNR"]),
                    "valid": as_int(line["GUELTIG"]) == 1,
                    "product_id": product_by_source.get(article_id) or False,
                    "source_product_id": article_id,
                    "article_number": clean(line["ARTNR1"]),
                    "name": line_name(line),
                    "quantity": float(line["BESTMENGE"] or 0),
                    "price_unit": float(line["PREIS"] or 0),
                    "discount": float(line["RABATT"] or 0),
                    "source_tax_key": clean(line["MWSTSCHL"]),
                }))
            reviews.append((name, {
                "name": str(source_id), "source_id": source_id,
                "source_identifier": clean(head["KENNZEICHEN"]),
                "document_type": document_type(head),
                "document_date": head["ERFASSDATUM"].date().isoformat() if head["ERFASSDATUM"] else False,
                "partner_id": partner, "source_status": clean(head["STATUS"]),
                "source_finished": bool(head["ERLEDIGT"]), "review_reason": reason,
                "review_note": "\n".join(note_parts), "source_line_count": len(source_lines),
                "valid_line_count": len(valid_lines),
                "delivery_name": " ".join(filter(None, [clean(head["ABWNAME1"]), clean(head["ABWNAME2"]), clean(head["ABWNAME3"]), clean(head["ABWNAME4"])])),
                "delivery_contact": clean(head["ABWANSPRECH"]), "delivery_street": clean(head["ABWSTRASSE"]),
                "delivery_zip": clean(head["ABWPLZ"]), "delivery_city": clean(head["ABWORT"]),
                "delivery_country_code": clean(head["ABWLAND"]), "line_ids": review_lines,
            }))
            continue

        external_name = f"ev_vorgang_{source_id}"
        if external_name in links:
            existing_sales += 1
            continue
        order_lines = []
        for line in valid_lines:
            article_id = as_int(line["LFDARTNR"])
            product_id = product_by_source.get(article_id)
            uom_id = uom_by_source.get(article_id)
            tax_key = as_int(line["MWSTSCHL"])
            if not product_id or not uom_id or tax_key not in taxes or not taxes[tax_key]:
                missing.append(f"Beleg {source_id}, Pos {line['POSNR']}: Artikel/UoM/Steuer {article_id}/{tax_key}")
                continue
            order_lines.append((0, 0, {
                "product_id": product_id, "product_uom_id": uom_id,
                "name": line_name(line), "product_uom_qty": float(line["BESTMENGE"] or 0),
                "price_unit": float(line["PREIS"] or 0), "discount": float(line["RABATT"] or 0),
                "tax_ids": [(6, 0, [taxes[tax_key]])],
            }))
        if len(order_lines) != len(valid_lines):
            continue
        shipping_id = partner
        address_name = f"ev_sale_delivery_{source_id}"
        if head["ABWEICH"]:
            if address_name in links:
                shipping_id = links[address_name]["res_id"]
            else:
                raw_country = clean(head["ABWLAND"]).upper()
                iso = COUNTRY_ALIASES.get(raw_country, raw_country)
                country_id = countries.get(iso)
                if raw_country and not country_id:
                    missing.append(f"Beleg {source_id}: unbekanntes Lieferland {raw_country}")
                    continue
                address_plans.append((source_id, address_name, {
                    "name": " ".join(filter(None, [clean(head["ABWNAME1"]), clean(head["ABWNAME2"]), clean(head["ABWNAME3"]), clean(head["ABWNAME4"])])),
                    "parent_id": partner, "type": "delivery", "street": clean(head["ABWSTRASSE"]),
                    "zip": clean(head["ABWPLZ"]), "city": clean(head["ABWORT"]),
                    "country_id": country_id or False, "comment": f"eEvolution Beleg {source_id}; Landcode {raw_country}",
                }))
                shipping_id = None
        sales.append({
            "source_id": source_id, "external_name": external_name, "address_name": address_name,
            "values": {
                "name": str(source_id), "partner_id": partner, "partner_invoice_id": partner,
                "partner_shipping_id": shipping_id or partner,
                "date_order": head["ERFASSDATUM"].strftime("%Y-%m-%d %H:%M:%S") if head["ERFASSDATUM"] else False,
                "client_order_ref": clean(head["KENNZEICHEN"]) or False,
                "origin": f"eEvolution LFDNR {source_id}", "user_id": False, "team_id": False,
                "state": "sale" if head["AUFTRAG"] else "draft", "locked": True,
                "kf_legacy_history": True, "kf_legacy_source_id": source_id,
                "kf_legacy_identifier": clean(head["KENNZEICHEN"]),
                "kf_legacy_original_status": f"Status={clean(head['STATUS'])}; Erledigt={as_int(head['ERLEDIGT']) or 0}",
                "order_line": order_lines,
            },
        })

    print(
        f"PLAN heads={len(heads)} sales_new={len(sales)} review_new={len(reviews)} "
        f"delivery_new={len(address_plans)} sales_existing={existing_sales} "
        f"review_existing={existing_reviews} missing={len(missing)}"
    )
    if missing:
        print("MISSING_SAMPLES=" + " | ".join(missing[:20]))
        raise SystemExit("Abbruch: unaufgelöste Pflichtreferenzen")
    if not args.apply:
        print("DRY_RUN_OK")
        return

    module = odoo.call("ir.module.module", "search_read", [[("name", "=", "kf_legacy_migration")]], {"fields": ["state", "installed_version"], "limit": 1})
    if not module or module[0]["state"] != "installed" or module[0].get("installed_version") != "19.0.11.0.0":
        raise SystemExit("kf_legacy_migration 19.0.11.0.0 muss vor dem Apply installiert sein")
    before = {
        model: odoo.call(model, "search_count", [[]])
        for model in ("stock.picking", "stock.move", "account.move", "mail.mail")
    }
    context = {"kf_legacy_import": True, "tracking_disable": True, "mail_create_nosubscribe": True, "mail_notrack": True}

    address_by_name = {name: links[name]["res_id"] for _, name, _ in address_plans if name in links}
    for batch in chunks([plan for plan in address_plans if plan[1] not in address_by_name], 100):
        ids = odoo.call("res.partner", "create", [[item[2] for item in batch]], {"context": context})
        if isinstance(ids, int):
            ids = [ids]
        names = [item[1] for item in batch]
        odoo.register_many("res.partner", names, ids)
        address_by_name.update(dict(zip(names, ids)))
    for sale in sales:
        if sale["address_name"] in address_by_name:
            sale["values"]["partner_shipping_id"] = address_by_name[sale["address_name"]]

    created_sales = 0
    for batch in chunks(sales, 20):
        ids = odoo.call("sale.order", "create", [[item["values"] for item in batch]], {"context": context})
        if isinstance(ids, int):
            ids = [ids]
        odoo.register_many("sale.order", [item["external_name"] for item in batch], ids)
        created_sales += len(ids)
        print(f"SALE_PROGRESS={created_sales}/{len(sales)}")

    created_reviews = 0
    for batch in chunks(reviews, 25):
        ids = odoo.call("kf.legacy.sales.document", "create", [[item[1] for item in batch]], {"context": context})
        if isinstance(ids, int):
            ids = [ids]
        odoo.register_many("kf.legacy.sales.document", [item[0] for item in batch], ids)
        created_reviews += len(ids)
        print(f"REVIEW_PROGRESS={created_reviews}/{len(reviews)}")

    after = {
        model: odoo.call(model, "search_count", [[]])
        for model in ("stock.picking", "stock.move", "account.move", "mail.mail")
    }
    if before != after:
        raise SystemExit(f"SIDE_EFFECT_DETECTED before={before} after={after}")
    print(f"APPLY_OK sales={created_sales} reviews={created_reviews} addresses={len(address_plans)} side_effects=0")


if __name__ == "__main__":
    main()
