from odoo import fields, models


class CrmLead(models.Model):
    _inherit = "crm.lead"

    kf_legacy_created_at = fields.Datetime(string="In eEvolution angelegt", readonly=True, index=True)
    kf_legacy_updated_at = fields.Datetime(string="In eEvolution geändert", readonly=True)
    kf_legacy_closed_at = fields.Datetime(string="In eEvolution abgeschlossen", readonly=True)
