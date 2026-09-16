from odoo import fields, models


class KfLegacySalesDocument(models.Model):
    _name = "kf.legacy.sales.document"
    _description = "eEvolution Verkaufsbeleg zur Datenprüfung"
    _order = "document_date desc, source_id desc"

    name = fields.Char(string="Beleg", required=True, index=True)
    source_id = fields.Integer(string="eEvolution Beleg-ID", required=True, index=True)
    source_identifier = fields.Char(string="eEvolution Kennzeichen", index=True)
    document_type = fields.Selection(
        [("order", "Auftrag"), ("quotation", "Angebot"), ("mixed", "Angebot/Auftrag")],
        string="Belegart",
        required=True,
        index=True,
    )
    document_date = fields.Date(string="Belegdatum", index=True)
    partner_id = fields.Many2one("res.partner", string="Kunde", index=True, ondelete="restrict")
    source_status = fields.Char(string="eEvolution Status")
    source_finished = fields.Boolean(string="In eEvolution erledigt")
    review_reason = fields.Selection(
        [
            ("no_lines", "Keine gültige Position"),
            ("address", "Lieferadresse unvollständig"),
            ("product", "Historischer Artikel nicht auflösbar"),
            ("multiple", "Mehrere Prüfgründe"),
        ],
        string="Prüfgrund",
        required=True,
        index=True,
    )
    review_note = fields.Text(string="Prüfhinweis")
    source_line_count = fields.Integer(string="Quellpositionen", readonly=True)
    valid_line_count = fields.Integer(string="Davon gültig", readonly=True)
    delivery_name = fields.Char(string="Abweichender Empfänger")
    delivery_contact = fields.Char(string="Ansprechpartner")
    delivery_street = fields.Char(string="Straße")
    delivery_zip = fields.Char(string="PLZ")
    delivery_city = fields.Char(string="Ort")
    delivery_country_code = fields.Char(string="eEvolution Land")
    source_system = fields.Char(string="Source System", default="eEvolution KuF", readonly=True)
    line_ids = fields.One2many(
        "kf.legacy.sales.document.line", "document_id", string="Quellpositionen"
    )

    _sql_constraints = [
        ("kf_legacy_sales_document_source_unique", "unique(source_id)",
         "Der eEvolution-Verkaufsbeleg ist bereits in der Prüfliste vorhanden."),
    ]


class KfLegacySalesDocumentLine(models.Model):
    _name = "kf.legacy.sales.document.line"
    _description = "eEvolution Verkaufsbelegposition zur Datenprüfung"
    _order = "position_number, source_line_id, id"

    document_id = fields.Many2one(
        "kf.legacy.sales.document", required=True, index=True, ondelete="cascade"
    )
    source_line_id = fields.Integer(string="eEvolution Positions-ID", index=True)
    position_number = fields.Integer(string="Position")
    valid = fields.Boolean(string="In eEvolution gültig", index=True)
    product_id = fields.Many2one("product.product", string="Odoo-Artikel", ondelete="restrict")
    source_product_id = fields.Integer(string="eEvolution Artikel-ID", index=True)
    article_number = fields.Char(string="eEvolution Artikelnummer", index=True)
    name = fields.Text(string="Positionsbezeichnung")
    quantity = fields.Float(string="Menge", digits=(16, 6))
    price_unit = fields.Float(string="Preis", digits=(16, 6))
    discount = fields.Float(string="Rabatt %", digits=(16, 6))
    source_tax_key = fields.Char(string="eEvolution Steuerschlüssel")
