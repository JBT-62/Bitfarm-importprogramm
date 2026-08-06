from odoo import api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _kf_apply_category_serial_policy(self):
        for template in self:
            category = template.categ_id
            if not category.kf_serial_required:
                continue
            category._kf_ensure_serial_sequence()
            values = {
                "tracking": "serial",
                "lot_sequence_id": category.kf_serial_sequence_id.id,
            }
            super(ProductTemplate, template).write(values)

    @api.model_create_multi
    def create(self, values_list):
        templates = super().create(values_list)
        templates._kf_apply_category_serial_policy()
        return templates

    def write(self, values):
        result = super().write(values)
        if "categ_id" in values:
            self._kf_apply_category_serial_policy()
        return result
