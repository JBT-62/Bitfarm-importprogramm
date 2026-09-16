from odoo import fields, models


class KfLegacyBusinessDocument(models.Model):
    _name = "kf.legacy.business.document"
    _description = "eEvolution Hauptbeleg (informativ)"
    _order = "document_date desc, document_type, source_id desc"

    name = fields.Char(string="Belegnummer", required=True, index=True)
    source_id = fields.Char(string="eEvolution Quell-ID", required=True, index=True)
    document_type = fields.Selection(
        [
            ("delivery", "Lieferschein"),
            ("out_invoice", "Ausgangsrechnung"),
            ("out_refund", "Ausgangsgutschrift"),
            ("in_invoice", "Eingangsrechnung"),
        ],
        string="Belegart", required=True, index=True,
    )
    document_date = fields.Datetime(string="Belegdatum", index=True)
    partner_id = fields.Many2one("res.partner", string="Kunde/Lieferant", index=True, ondelete="restrict")
    source_partner_number = fields.Char(string="eEvolution Partnernummer", index=True)
    source_partner_name = fields.Char(string="Partnername aus Beleg")
    source_order_id = fields.Integer(string="eEvolution Auftrags-ID", index=True)
    source_order_number = fields.Char(string="Auftragsnummer", index=True)
    source_status = fields.Char(string="eEvolution Status")
    currency_symbol = fields.Char(string="Währung")
    amount_net = fields.Float(string="Netto", digits=(16, 2))
    amount_tax = fields.Float(string="Steuer", digits=(16, 2))
    amount_gross = fields.Float(string="Brutto", digits=(16, 2))
    cancelled = fields.Boolean(string="Storniert", index=True)
    cancellation_date = fields.Datetime(string="Stornozeitpunkt")
    locked = fields.Boolean(string="Gesperrt", default=True, required=True, readonly=True, index=True)
    source_line_count = fields.Integer(string="Quellpositionen", readonly=True)
    review_status = fields.Selection(
        [("ok", "Eindeutig"), ("review", "Prüfung erforderlich")],
        string="Datenqualität", required=True, default="ok", index=True,
    )
    review_note = fields.Text(string="Prüfhinweis")
    source_system = fields.Char(default="eEvolution KuF", readonly=True)
    line_ids = fields.One2many("kf.legacy.business.document.line", "document_id", string="Positionen")

    _sql_constraints = [
        ("kf_legacy_business_document_source_unique", "unique(document_type, source_id)",
         "Dieser eEvolution-Hauptbeleg ist bereits vorhanden."),
        ("kf_legacy_business_document_locked", "check(locked)",
         "Historische Hauptbelege müssen gesperrt bleiben."),
    ]


class KfLegacyBusinessDocumentLine(models.Model):
    _name = "kf.legacy.business.document.line"
    _description = "eEvolution Hauptbelegposition (informativ)"
    _order = "position_number, id"

    document_id = fields.Many2one(
        "kf.legacy.business.document", required=True, index=True, ondelete="cascade"
    )
    source_key = fields.Char(string="eEvolution Quellschlüssel", required=True, index=True)
    position_number = fields.Integer(string="Position", index=True)
    product_id = fields.Many2one("product.product", string="Odoo-Artikel", index=True, ondelete="restrict")
    source_product_id = fields.Integer(string="eEvolution Artikel-ID", index=True)
    article_number = fields.Char(string="Artikelnummer", index=True)
    name = fields.Text(string="Positionsbezeichnung")
    quantity = fields.Float(string="Menge", digits=(16, 6))
    price_unit = fields.Float(string="Quellpreis", digits=(16, 6))
    amount = fields.Float(string="Quellbetrag", digits=(16, 2))
    tax_rate = fields.Float(string="Steuersatz %", digits=(16, 4))
    uom_name = fields.Char(string="Mengeneinheit")
    cancelled = fields.Boolean(string="Storniert", index=True)

    _sql_constraints = [
        ("kf_legacy_business_document_line_source_unique", "unique(source_key)",
         "Diese eEvolution-Hauptbelegposition ist bereits vorhanden."),
    ]
