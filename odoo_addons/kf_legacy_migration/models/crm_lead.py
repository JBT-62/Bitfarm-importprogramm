from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    kf_legacy_created_at = fields.Datetime(string="In eEvolution angelegt", readonly=True, index=True)
    kf_legacy_updated_at = fields.Datetime(string="In eEvolution geändert", readonly=True)
    kf_legacy_closed_at = fields.Datetime(string="In eEvolution abgeschlossen", readonly=True)
    kf_legacy_owner_number = fields.Integer(string="eEvolution-Verantwortlichennr.", readonly=True, index=True)
    kf_legacy_owner_name = fields.Char(string="eEvolution-Verantwortlicher", readonly=True, index=True)
    kf_legacy_product_interest = fields.Text(string="eEvolution-Produktinteresse", readonly=True)
