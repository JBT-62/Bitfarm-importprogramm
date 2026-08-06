from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductCategory(models.Model):
    _inherit = "product.category"

    kf_serial_required = fields.Boolean(string="K&F-Seriennummer erforderlich")
    kf_serial_prefix = fields.Char(
        string="Seriennummern-Präfix",
        size=2,
        help="Genau zwei Ziffern. Format der erzeugten Nummer: GGWWYYNNNNN.",
    )
    kf_serial_sequence_id = fields.Many2one(
        "ir.sequence",
        string="Gemeinsame Seriennummernfolge",
        readonly=True,
        copy=False,
    )

    @api.constrains("kf_serial_required", "kf_serial_prefix")
    def _check_kf_serial_prefix(self):
        for category in self:
            if category.kf_serial_required and (
                not category.kf_serial_prefix
                or len(category.kf_serial_prefix) != 2
                or not category.kf_serial_prefix.isdigit()
            ):
                raise ValidationError(_("Das Seriennummern-Präfix muss aus genau zwei Ziffern bestehen."))
            if category.kf_serial_prefix:
                duplicate = self.search_count([
                    ("id", "!=", category.id),
                    ("kf_serial_required", "=", True),
                    ("kf_serial_prefix", "=", category.kf_serial_prefix),
                ])
                if duplicate:
                    raise ValidationError(_("Das Seriennummern-Präfix %s wird bereits verwendet.", category.kf_serial_prefix))

    def _kf_ensure_serial_sequence(self):
        for category in self.filtered("kf_serial_required"):
            sequence = category.kf_serial_sequence_id
            values = {
                "name": f"K&F {category.complete_name} Seriennummern",
                "code": "stock.lot.serial",
                # Kalenderwoche/Jahr werden bewusst in Python nach ISO 8601
                # ergänzt. Odoos %(woy)s entspricht nicht der ISO-Woche.
                "prefix": False,
                "suffix": False,
                "padding": 5,
                "implementation": "no_gap",
                "company_id": False,
            }
            if sequence:
                sequence.sudo().write(values)
            else:
                category.kf_serial_sequence_id = self.env["ir.sequence"].sudo().create(values)

    def _kf_next_serial(self, serial_date=None):
        """Return GGWWYYNNNNN with an ISO week and permanent group counter."""
        self.ensure_one()
        if not self.kf_serial_required:
            raise ValidationError(_("Für diese Produktgruppe ist keine Seriennummernfolge aktiviert."))
        self._kf_ensure_serial_sequence()
        effective_date = fields.Date.to_date(serial_date) if serial_date else fields.Date.context_today(self)
        iso_year, iso_week, _iso_weekday = effective_date.isocalendar()

        # Alte eEvolution-Nummern bleiben unverändert. Sollte eine vorhandene
        # Nummer zufällig dem neuen Schema entsprechen, wird sie übersprungen.
        for _attempt in range(1000):
            counter = self.kf_serial_sequence_id.next_by_id()
            if not counter:
                raise ValidationError(_("Die Seriennummernfolge konnte keinen Zähler erzeugen."))
            serial = f"{self.kf_serial_prefix}{iso_week:02d}{iso_year % 100:02d}{counter}"
            if not self.env["stock.lot"].search_count([("name", "=", serial)]):
                return serial
        raise ValidationError(_("Es konnten nach 1.000 Versuchen keine freie Seriennummer erzeugt werden."))

    def write(self, values):
        result = super().write(values)
        if {"kf_serial_required", "kf_serial_prefix"} & set(values):
            self._kf_ensure_serial_sequence()
            self.env["product.template"].search([("categ_id", "in", self.ids)])._kf_apply_category_serial_policy()
        return result

    @api.model_create_multi
    def create(self, values_list):
        categories = super().create(values_list)
        categories._kf_ensure_serial_sequence()
        return categories
