from odoo import Command, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def _prepare_stock_lot_values(self):
        self.ensure_one()
        category = self.product_id.categ_id
        if not category.kf_serial_required or self.product_tracking != "serial":
            return super()._prepare_stock_lot_values()
        planned_datetime = fields.Datetime.to_datetime(self.date_start) or fields.Datetime.now()
        local_date = fields.Datetime.context_timestamp(self, planned_datetime).date()
        return {
            "product_id": self.product_id.id,
            "name": category._kf_next_serial(local_date),
        }

    def action_confirm(self):
        result = super().action_confirm()
        for production in self:
            category = production.product_id.categ_id
            if not category.kf_serial_required or production.product_tracking != "serial":
                continue
            if production.lot_producing_ids:
                continue
            rounded = production.product_uom_id.round(production.product_qty)
            count = int(rounded)
            if count < 1 or float_compare(rounded, count, precision_rounding=production.product_uom_id.rounding):
                raise ValidationError(_("Seriennummernpflichtige Fertigungsaufträge benötigen eine ganzzahlige Menge."))
            production.lot_producing_ids = [
                Command.create(production._prepare_stock_lot_values())
                for _index in range(count)
            ]
        return result
