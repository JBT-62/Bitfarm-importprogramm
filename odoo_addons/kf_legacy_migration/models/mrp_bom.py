from odoo import fields, models


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    kf_legacy_text_lines = fields.Text(
        string="eEvolution-Textpositionen",
        readonly=True,
        help="Textpositionen aus PRODINHALT ohne Artikelbezug; rein informativ.",
    )
