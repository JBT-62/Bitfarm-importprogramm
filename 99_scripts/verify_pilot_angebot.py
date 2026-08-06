#!/usr/bin/env python3
"""Quelle/Ziel-Abnahme für den Pilotimport eines Angebots."""

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import pilot_import_angebot as pilot  # noqa: E402


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nr", type=int, default=39575)
    args = parser.parse_args()

    with pilot.source_connection() as connection:
        data = pilot.SourceExtractor(connection, args.nr).extract()
    odoo = pilot.OdooClient(dry_run=True)

    customer_id = odoo.resolve("res.partner", f"ev_adr_{int(data['header']['ADRNR'])}")
    require(customer_id, "Kunde fehlt")
    for contact in data["contacts"]:
        require(
            odoo.resolve("res.partner", f"ev_contact_{int(contact['LFDNR'])}"),
            f"Ansprechpartner {contact['LFDNR']} fehlt",
        )
    for vendor in data["vendors"]:
        require(
            odoo.resolve("res.partner", f"ev_adr_{int(vendor['ADRNR'])}"),
            f"Lieferant ADRNR {vendor['ADRNR']} fehlt",
        )
    for article in data["articles"]:
        require(
            odoo.resolve("product.template", f"ev_product_{int(article['LFDNR'])}"),
            f"Artikel {article['ARTNR1']} fehlt",
        )
    for bom_id, lines in data["bom_lines"].items():
        require(odoo.resolve("mrp.bom", f"ev_bom_{bom_id}"), f"Stückliste {bom_id} fehlt")
        for line in lines:
            require(
                odoo.resolve("mrp.bom.line", f"ev_bom_line_{bom_id}_{int(line['LFD_NR'])}"),
                f"Stücklistenposition {bom_id}/{line['LFD_NR']} fehlt",
            )

    opportunity_id = odoo.resolve("crm.lead", f"ev_pilot_crm_{args.nr}")
    sale_id = odoo.resolve("sale.order", f"ev_pilot_offer_{args.nr}")
    require(opportunity_id, "CRM-Chance fehlt")
    require(sale_id, "Angebot fehlt")
    sale = odoo.call(
        "sale.order", "read", [[sale_id]],
        {"fields": ["name", "state", "partner_id", "opportunity_id", "order_line", "amount_untaxed", "amount_tax", "amount_total"]},
    )[0]
    require(sale["state"] == "draft", f"Angebot ist nicht im Entwurf: {sale['state']}")
    require(sale["partner_id"][0] == customer_id, "Angebot hat falschen Kunden")
    require(sale["opportunity_id"][0] == opportunity_id, "CRM-Verknüpfung fehlt")
    require(len(sale["order_line"]) == len(data["positions"]), "Falsche Anzahl Angebotspositionen")
    require(abs(sale["amount_untaxed"] - 27517.11) < 0.02, sale["amount_untaxed"])
    require(abs(sale["amount_tax"] - 5228.25) < 0.02, sale["amount_tax"])
    require(abs(sale["amount_total"] - 32745.36) < 0.02, sale["amount_total"])

    direct_products = []
    for article_id in sorted(data["direct_article_ids"]):
        template_id = odoo.resolve("product.template", f"ev_product_{article_id}")
        direct_products.extend(
            odoo.call(
                "product.template", "read", [[template_id]],
                {"fields": ["default_code", "tracking", "categ_id", "route_ids"]},
            )
        )
    manufacture_route = odoo.call("stock.route", "search", [[("name", "=", "Manufacture")]], {"limit": 1})
    buy_route = odoo.call("stock.route", "search", [[("name", "=", "Buy")]], {"limit": 1})
    mto_route = odoo.call(
        "stock.route", "search", [[("name", "ilike", "Replenish on Order")]],
        {"limit": 1, "context": {"active_test": False}},
    )
    for product in direct_products:
        if product["default_code"] == "35414":
            continue
        require(mto_route[0] in product["route_ids"], f"MTO-Route fehlt: {product['default_code']}")

    warehouse = odoo.call("stock.warehouse", "search", [[]], {"limit": 1})
    manufacture_values = odoo.call("stock.route", "read", [manufacture_route], {"fields": ["warehouse_ids"]})[0]
    buy_values = odoo.call("stock.route", "read", [buy_route], {"fields": ["warehouse_ids"]})[0]
    require(warehouse[0] in manufacture_values["warehouse_ids"], "Fertigungsroute ist nicht dem Lager zugeordnet")
    require(warehouse[0] in buy_values["warehouse_ids"], "Einkaufsroute ist nicht dem Lager zugeordnet")

    pickings = odoo.call("stock.picking", "search_count", [[("origin", "=", sale["name"])]] )
    productions = odoo.call("mrp.production", "search_count", [[("origin", "=", sale["name"])]] )
    purchases = odoo.call("purchase.order", "search_count", [[("origin", "=", sale["name"])]] )
    require(not pickings and not productions and not purchases, "Entwurfsangebot hat unerwartete Folgebelege")

    print(f"VERIFY_OK sale={sale['name']} state={sale['state']}")
    print(
        f"COUNTS contacts={len(data['contacts'])} vendors={len(data['vendors'])} "
        f"products={len(data['articles'])} boms={len(data['boms'])} "
        f"bom_lines={sum(len(lines) for lines in data['bom_lines'].values())} offer_lines={len(sale['order_line'])}"
    )
    print(
        f"TOTALS untaxed={sale['amount_untaxed']:.2f} tax={sale['amount_tax']:.2f} "
        f"total={sale['amount_total']:.2f}"
    )
    print(f"FOLLOW_UP_DOCS pickings={pickings} productions={productions} purchases={purchases}")


if __name__ == "__main__":
    main()
