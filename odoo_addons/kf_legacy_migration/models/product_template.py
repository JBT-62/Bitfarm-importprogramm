from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    kf_eevolution_group_info = fields.Char(
        string="eEvolution-Gruppen (Übergangsinfo)",
        readonly=True,
        copy=False,
        help=(
            "Unveränderte WGRUPPE und AGRUPPE aus eEvolution als Orientierung "
            "während der Übergangszeit. Die Odoo-Kategorie wird unabhängig gepflegt."
        ),
    )
