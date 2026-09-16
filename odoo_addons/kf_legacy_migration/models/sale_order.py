from odoo import _, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    kf_legacy_history = fields.Boolean(
        string="Historischer eEvolution-Beleg",
        readonly=True,
        index=True,
        copy=False,
        help="Rein informativer Altbeleg. Er darf keine Lieferung oder Rechnung erzeugen.",
    )
    kf_legacy_source_id = fields.Integer(
        string="eEvolution Beleg-ID", readonly=True, index=True, copy=False
    )
    kf_legacy_identifier = fields.Char(
        string="eEvolution Kennzeichen", readonly=True, copy=False
    )
    kf_legacy_original_status = fields.Char(
        string="eEvolution Originalstatus", readonly=True, copy=False
    )

    def _kf_assert_not_legacy_operational(self):
        if self.filtered("kf_legacy_history"):
            raise UserError(_(
                "Historische eEvolution-Belege sind rein informativ und dürfen keine "
                "Lieferung, Rechnung oder sonstige operative Buchung erzeugen."
            ))

    def action_confirm(self):
        self._kf_assert_not_legacy_operational()
        return super().action_confirm()

    def _action_confirm(self):
        self._kf_assert_not_legacy_operational()
        return super()._action_confirm()

    def _create_invoices(self, *args, **kwargs):
        self._kf_assert_not_legacy_operational()
        return super()._create_invoices(*args, **kwargs)

    def action_unlock(self):
        self._kf_assert_not_legacy_operational()
        return super().action_unlock()

    def write(self, vals):
        if self.filtered("kf_legacy_history") and not self.env.context.get("kf_legacy_import"):
            raise UserError(_("Historische eEvolution-Belege sind schreibgeschützt."))
        return super().write(vals)

    def unlink(self):
        if self.filtered("kf_legacy_history") and not self.env.context.get("kf_legacy_import"):
            raise UserError(_("Historische eEvolution-Belege dürfen nicht gelöscht werden."))
        return super().unlink()
