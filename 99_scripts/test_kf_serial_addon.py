"""Run inside ``odoo shell``; always rolls back the test transaction."""
from datetime import datetime
import re

from odoo import fields


def run(env):
    category = env["product.category"].search([
        ("name", "=", "Gravis"),
        ("kf_serial_required", "=", True),
    ], limit=1)
    assert category, "Seriennummerngruppe Gravis fehlt"
    assert category.kf_serial_prefix == "36", category.kf_serial_prefix
    product_tmpl = env["product.template"].create({
        "name": "K&F Seriennummern-Transaktionstest",
        "type": "consu",
        "is_storable": True,
        "categ_id": category.id,
    })
    assert product_tmpl.tracking == "serial", product_tmpl.tracking
    assert product_tmpl.lot_sequence_id == category.kf_serial_sequence_id
    bom = env["mrp.bom"].create({
        "product_tmpl_id": product_tmpl.id,
        "product_qty": 1.0,
        "product_uom_id": product_tmpl.uom_id.id,
    })
    production = env["mrp.production"].create({
        "product_id": product_tmpl.product_variant_id.id,
        "product_qty": 2.0,
        "product_uom_id": product_tmpl.uom_id.id,
        "bom_id": bom.id,
    })
    production.action_confirm()
    serials = production.lot_producing_ids.mapped("name")
    planned_datetime = fields.Datetime.to_datetime(production.date_start) or datetime.now()
    local_date = fields.Datetime.context_timestamp(production, planned_datetime).date()
    iso_year, iso_week, _iso_weekday = local_date.isocalendar()
    expected_prefix = f"36{iso_week:02d}{iso_year % 100:02d}"
    assert len(serials) == 2, serials
    assert len(set(serials)) == 2, serials
    assert all(re.fullmatch(r"36\d{9}", value) for value in serials), serials
    assert all(value.startswith(expected_prefix) for value in serials), (expected_prefix, serials)

    # ISO-Jahresgrenze: 01.01.2027 liegt in ISO-Woche 53 des ISO-Jahres 2026.
    boundary_production = env["mrp.production"].create({
        "product_id": product_tmpl.product_variant_id.id,
        "product_qty": 1.0,
        "product_uom_id": product_tmpl.uom_id.id,
        "bom_id": bom.id,
        "date_start": "2027-01-01 12:00:00",
    })
    boundary_production.action_confirm()
    boundary_serials = boundary_production.lot_producing_ids.mapped("name")
    assert len(boundary_serials) == 1, boundary_serials
    assert boundary_serials[0].startswith("365326"), boundary_serials
    print("KF_SERIAL_TEST_OK=" + ",".join(serials))
    print("KF_SERIAL_BOUNDARY_TEST_OK=" + boundary_serials[0])


try:
    run(env)
finally:
    env.cr.rollback()
    print("KF_SERIAL_TEST_ROLLBACK_OK")
