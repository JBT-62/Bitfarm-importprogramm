from odoo import fields, models


class KfLegacyPurchaseDocument(models.Model):
    _name = "kf.legacy.purchase.document"
    _description = "eEvolution Einkaufsbeleg (informativ)"
    _order = "document_date desc, source_group_key desc"

    name = fields.Char(string="Beleg", required=True, index=True)
    source_group_key = fields.Char(
        string="eEvolution Gruppenschlüssel", required=True, index=True
    )
    source_collective_number = fields.Integer(string="Sammelbestellnummer", index=True)
    document_type = fields.Selection(
        [("purchase", "Bestellung"), ("framework", "Rahmenvertrag")],
        string="Belegart", required=True, index=True,
    )
    document_date = fields.Date(string="Belegdatum", index=True)
    vendor_id = fields.Many2one(
        "res.partner", string="Lieferant", index=True, ondelete="restrict"
    )
    source_vendor_number = fields.Integer(string="eEvolution Lieferantennummer", index=True)
    source_status_summary = fields.Char(string="eEvolution Statuscodes")
    currency_summary = fields.Char(string="Währungen")
    source_line_count = fields.Integer(string="Quellpositionen", readonly=True)
    cancelled_line_count = fields.Integer(string="Stornierte Positionen", readonly=True)
    review_status = fields.Selection(
        [("ok", "Eindeutig"), ("review", "Prüfung erforderlich")],
        string="Datenqualität", required=True, default="ok", index=True,
    )
    review_note = fields.Text(string="Prüfhinweis")
    source_system = fields.Char(default="eEvolution KuF", readonly=True)
    line_ids = fields.One2many(
        "kf.legacy.purchase.document.line", "document_id", string="Quellpositionen"
    )

    _sql_constraints = [
        (
            "kf_legacy_purchase_document_source_unique",
            "unique(source_group_key)",
            "Dieser eEvolution-Einkaufsbeleg ist bereits vorhanden.",
        )
    ]


class KfLegacyPurchaseDocumentLine(models.Model):
    _name = "kf.legacy.purchase.document.line"
    _description = "eEvolution Einkaufsbelegposition (informativ)"
    _order = "position_number, source_order_number, id"

    document_id = fields.Many2one(
        "kf.legacy.purchase.document", required=True, index=True, ondelete="cascade"
    )
    source_key = fields.Char(string="eEvolution Quellschlüssel", required=True, index=True)
    source_order_number = fields.Integer(string="eEvolution Bestellnummer", index=True)
    position_number = fields.Integer(string="Position")
    product_id = fields.Many2one(
        "product.product", string="Odoo-Artikel", index=True, ondelete="restrict"
    )
    source_product_id = fields.Integer(string="eEvolution Artikel-ID", index=True)
    article_number = fields.Char(string="Artikelnummer", index=True)
    name = fields.Text(string="Positionsbezeichnung")
    source_vendor_article_number = fields.Char(string="Lieferanten-Artikelnummer")
    source_vendor_description = fields.Char(string="Lieferantenbezeichnung")
    quantity_ordered = fields.Float(string="Bestellmenge", digits=(16, 6))
    quantity_delivered = fields.Float(string="Gelieferte Menge", digits=(16, 6))
    quantity_reserved = fields.Float(string="Reservierte Menge", digits=(16, 6))
    price_raw = fields.Float(string="Quellpreis", digits=(16, 6))
    price_unit_raw = fields.Float(string="Quell-Preiseinheit", digits=(16, 6))
    source_uom_key = fields.Integer(string="eEvolution Einkaufseinheit")
    currency_symbol = fields.Char(string="Währung")
    source_status = fields.Char(string="Statuscode", index=True)
    source_order_type = fields.Char(string="Bestelltyp")
    document_date = fields.Date(string="Belegdatum", index=True)
    internal_date = fields.Date(string="Internes Datum")
    vendor_date = fields.Date(string="Lieferantendatum")
    planned_date = fields.Date(string="Geplanter Termin")
    delivery_date = fields.Date(string="Lieferdatum")
    source_framework_id = fields.Integer(string="eEvolution Rahmenvertrags-ID", index=True)
    cancelled = fields.Boolean(string="Storniert", index=True)
    cancellation_date = fields.Datetime(string="Stornozeitpunkt")

    _sql_constraints = [
        (
            "kf_legacy_purchase_document_line_source_unique",
            "unique(source_key)",
            "Diese eEvolution-Einkaufsposition ist bereits vorhanden.",
        )
    ]
