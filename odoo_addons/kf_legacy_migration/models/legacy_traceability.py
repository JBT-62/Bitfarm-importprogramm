from odoo import api, fields, models


class KfLegacyTrace(models.Model):
    _name = "kf.legacy.trace"
    _description = "eEvolution Serien-/Chargenrückverfolgung"
    _order = "last_event_date desc, name, id"

    name = fields.Char(string="Serien-/Chargennummer", required=True, index=True)
    trace_type = fields.Selection(
        [("serial", "Seriennummer"), ("lot", "Charge")],
        string="Typ",
        required=True,
        index=True,
    )
    product_id = fields.Many2one("product.product", string="Odoo-Artikel", index=True, ondelete="restrict")
    eevo_product_key = fields.Integer(string="eEvolution Artikel-ID", required=True, index=True)
    article_number = fields.Char(string="eEvolution Artikelnummer", index=True)
    article_name = fields.Char(string="eEvolution Artikelbezeichnung")
    pia_scope_role = fields.Selection(
        [("root", "Endprodukt"), ("component", "Komponente")],
        string="Produktrolle",
        required=True,
    )
    first_event_date = fields.Datetime(string="Erstes Ereignis", index=True)
    last_event_date = fields.Datetime(string="Letztes Ereignis", index=True)
    first_event_date_display = fields.Char(
        string="Erstes Ereignis", compute="_compute_event_date_display", store=True
    )
    last_event_date_display = fields.Char(
        string="Letztes Ereignis", compute="_compute_event_date_display", store=True
    )
    event_count = fields.Integer(string="Ereignisse", readonly=True)
    quality_status = fields.Selection(
        [("ok", "Eindeutig"), ("review", "Prüfung erforderlich")],
        string="Datenqualität",
        required=True,
        default="ok",
        index=True,
    )
    quality_note = fields.Text(string="Prüfhinweis")
    original_partner_id = fields.Many2one(
        "res.partner", string="Ursprünglicher Kunde", index=True, ondelete="restrict"
    )
    original_eevo_partner_key = fields.Integer(string="eEvolution Kunden-/Adress-ID", index=True)
    original_order_number = fields.Char(string="Ursprünglicher Auftrag", index=True)
    original_delivery_number = fields.Char(string="Ursprünglicher Lieferschein", index=True)
    original_delivery_date = fields.Datetime(string="Ursprüngliches Versanddatum", index=True)
    source_system = fields.Char(default="eEvolution KuF", readonly=True)
    event_ids = fields.One2many("kf.legacy.trace.event", "trace_id", string="Historische Ereignisse")
    usage_ids = fields.One2many(
        "kf.legacy.trace.usage", "trace_id", string="Erzeugte Endserien und -chargen"
    )
    delivery_ids = fields.One2many(
        "kf.legacy.trace.delivery", "trace_id", string="Direkte Chargen-/Serienlieferungen"
    )
    usage_count = fields.Integer(string="Ermittelte Endserien/-chargen", readonly=True)
    direct_delivery_count = fields.Integer(
        string="Direkte Lieferungen", compute="_compute_recall_counts", store=True
    )
    impacted_customer_count = fields.Integer(
        string="Betroffene Kunden", compute="_compute_recall_counts", store=True
    )

    _sql_constraints = [
        (
            "kf_legacy_trace_source_unique",
            "unique(trace_type, eevo_product_key, name)",
            "Die Serien-/Chargennummer ist für diesen eEvolution-Artikel bereits vorhanden.",
        )
    ]

    @api.depends("first_event_date", "last_event_date")
    def _compute_event_date_display(self):
        for record in self:
            record.first_event_date_display = (
                record.first_event_date.strftime("%d.%m.%Y") if record.first_event_date else ""
            )
            record.last_event_date_display = (
                record.last_event_date.strftime("%d.%m.%Y") if record.last_event_date else ""
            )

    @api.depends("delivery_ids.partner_id", "usage_ids.customer_id")
    def _compute_recall_counts(self):
        for record in self:
            record.direct_delivery_count = len(record.delivery_ids)
            record.impacted_customer_count = len(
                (record.delivery_ids.mapped("partner_id") | record.usage_ids.mapped("customer_id"))
            )


class KfLegacyTraceEvent(models.Model):
    _name = "kf.legacy.trace.event"
    _description = "eEvolution Rückverfolgungsereignis"
    _order = "event_date, id"

    trace_id = fields.Many2one(
        "kf.legacy.trace", string="Serien-/Charge", required=True, index=True, ondelete="cascade"
    )
    source_key = fields.Char(string="eEvolution Ereignisschlüssel", required=True, index=True)
    source_table = fields.Selection(
        [("SNRARCHIV", "SNRARCHIV"), ("CHARGENARCHIV", "CHARGENARCHIV")],
        string="Quelltabelle",
        required=True,
    )
    event_date = fields.Datetime(string="Ereignisdatum", required=True, index=True)
    event_date_display = fields.Char(
        string="Ereignisdatum", compute="_compute_event_date_display", store=True
    )
    event_type_code = fields.Char(string="Quelltyp", index=True)
    event_type_name = fields.Char(string="Ereignisart", index=True)
    reference_number = fields.Char(string="Referenznummer", index=True)
    reference_position = fields.Integer(string="Referenzposition")
    document_number = fields.Char(string="Belegnummer", index=True)
    partner_id = fields.Many2one("res.partner", string="Kunde/Lieferant", index=True, ondelete="restrict")
    eevo_partner_key = fields.Integer(string="eEvolution Adress-ID", index=True)
    quantity = fields.Float(string="Menge", digits=(16, 6))
    description = fields.Char(string="Quelltext")
    production_id = fields.Many2one(
        "kf.legacy.production",
        string="Legacy-Produktionsauftrag",
        index=True,
        ondelete="restrict",
        help="Rein informativer Produktionsauftrag aus eEvolution; erzeugt keine Odoo-Buchung.",
    )

    _sql_constraints = [
        (
            "kf_legacy_trace_event_source_unique",
            "unique(source_key)",
            "Das eEvolution-Ereignis wurde bereits importiert.",
        )
    ]

    @api.depends("event_date")
    def _compute_event_date_display(self):
        for record in self:
            record.event_date_display = (
                record.event_date.strftime("%d.%m.%Y") if record.event_date else ""
            )


class KfLegacyProduction(models.Model):
    _name = "kf.legacy.production"
    _description = "eEvolution Produktionsauftrag (informativ)"
    _order = "end_date desc, eevo_order_key desc"

    name = fields.Char(string="Produktionsauftrag", required=True, index=True)
    eevo_order_key = fields.Integer(string="eEvolution Auftrags-ID", required=True, index=True)
    product_id = fields.Many2one("product.product", string="Odoo-Artikel", index=True, ondelete="restrict")
    eevo_product_key = fields.Integer(string="eEvolution Artikel-ID", index=True)
    article_number = fields.Char(string="eEvolution Artikelnummer", index=True)
    article_name = fields.Char(string="eEvolution Artikelbezeichnung")
    status_code = fields.Char(string="eEvolution Status")
    order_type = fields.Char(string="eEvolution Typ")
    quantity_ordered = fields.Float(string="Auftragsmenge", digits=(16, 6))
    quantity_produced = fields.Float(string="Produzierte Menge", digits=(16, 6))
    quantity_scrapped = fields.Float(string="Ausschussmenge", digits=(16, 6))
    planned_date = fields.Datetime(string="Planungsdatum")
    production_date = fields.Datetime(string="Produktionsdatum")
    end_date = fields.Datetime(string="Abschlussdatum", index=True)
    planned_date_display = fields.Char(
        string="Planungsdatum", compute="_compute_date_display", store=True
    )
    production_date_display = fields.Char(
        string="Produktionsdatum", compute="_compute_date_display", store=True
    )
    end_date_display = fields.Char(
        string="Abschlussdatum", compute="_compute_date_display", store=True
    )
    bom_reference = fields.Integer(string="eEvolution Stücklisten-ID")
    component_posting_count = fields.Integer(string="Komponentenbuchungen", readonly=True)
    traced_component_posting_count = fields.Integer(
        string="davon mit Serien-/Chargenbezug", readonly=True
    )
    output_count = fields.Integer(string="Ausgabeserien/-chargen", readonly=True)
    allocation_note = fields.Text(
        string="Zuordnungshinweis",
        default=(
            "Die Komponenten sind als tatsächliche eEvolution-Verbrauchsbuchungen dem gesamten "
            "Produktionsauftrag zugeordnet. Eine Zuordnung zu einem einzelnen produzierten Gerät "
            "wird nur behauptet, wenn eEvolution sie ausdrücklich belegt."
        ),
        readonly=True,
    )
    source_system = fields.Char(default="eEvolution KuF", readonly=True)
    locked = fields.Boolean(string="Gesperrt", default=True, required=True, readonly=True, index=True)
    component_ids = fields.One2many(
        "kf.legacy.production.component", "production_id", string="Tatsächlich gebuchte Komponenten"
    )
    output_ids = fields.One2many(
        "kf.legacy.production.output", "production_id", string="Produzierte Serien und Chargen"
    )

    _sql_constraints = [
        (
            "kf_legacy_production_order_unique",
            "unique(eevo_order_key)",
            "Der eEvolution-Produktionsauftrag ist bereits vorhanden.",
        ),
        (
            "kf_legacy_production_locked",
            "check(locked)",
            "Historische Produktionsaufträge müssen gesperrt bleiben.",
        ),
    ]

    @api.depends("planned_date", "production_date", "end_date")
    def _compute_date_display(self):
        for record in self:
            record.planned_date_display = (
                record.planned_date.strftime("%d.%m.%Y") if record.planned_date else ""
            )
            record.production_date_display = (
                record.production_date.strftime("%d.%m.%Y") if record.production_date else ""
            )
            record.end_date_display = (
                record.end_date.strftime("%d.%m.%Y") if record.end_date else ""
            )


class KfLegacyProductionComponent(models.Model):
    _name = "kf.legacy.production.component"
    _description = "eEvolution Komponentenverbrauch (informativ)"
    _order = "booking_date, source_posting_key, id"

    production_id = fields.Many2one(
        "kf.legacy.production", string="Produktionsauftrag", required=True, index=True, ondelete="cascade"
    )
    source_key = fields.Char(string="eEvolution Quellschlüssel", required=True, index=True)
    source_posting_key = fields.Integer(string="eEvolution Buchungs-ID", required=True, index=True)
    source_position_key = fields.Integer(string="eEvolution Positions-ID", index=True)
    product_id = fields.Many2one("product.product", string="Odoo-Komponente", index=True, ondelete="restrict")
    eevo_product_key = fields.Integer(string="eEvolution Artikel-ID", required=True, index=True)
    article_number = fields.Char(string="Artikelnummer", index=True)
    article_name = fields.Char(string="Artikelbezeichnung")
    booking_date = fields.Datetime(string="Buchungsdatum", index=True)
    booking_date_display = fields.Char(
        string="Buchungsdatum", compute="_compute_booking_date_display", store=True
    )
    document_number = fields.Char(string="Belegnummer", index=True)
    quantity = fields.Float(string="Tatsächlich gebuchte Menge", digits=(16, 6))
    serial_number = fields.Char(string="Komponenten-Seriennummer", index=True)
    lot_number = fields.Char(string="Komponenten-Charge", index=True)
    is_cancelled = fields.Boolean(string="Storniert", index=True)

    _sql_constraints = [
        (
            "kf_legacy_production_component_source_unique",
            "unique(source_key)",
            "Die eEvolution-Komponentenbuchung ist bereits vorhanden.",
        )
    ]

    @api.depends("booking_date")
    def _compute_booking_date_display(self):
        for record in self:
            record.booking_date_display = (
                record.booking_date.strftime("%d.%m.%Y") if record.booking_date else ""
            )


class KfLegacyProductionOutput(models.Model):
    _name = "kf.legacy.production.output"
    _description = "eEvolution Produktionsausgabe (informativ)"
    _order = "storage_date, number, id"

    production_id = fields.Many2one(
        "kf.legacy.production", string="Produktionsauftrag", required=True, index=True, ondelete="cascade"
    )
    source_key = fields.Char(string="eEvolution Quellschlüssel", required=True, index=True)
    output_type = fields.Selection(
        [("serial", "Seriennummer"), ("lot", "Charge")], string="Typ", required=True, index=True
    )
    number = fields.Char(string="Serien-/Chargennummer", required=True, index=True)
    quantity = fields.Float(string="Menge", digits=(16, 6))
    storage_date = fields.Datetime(string="Einlagerungsdatum", index=True)
    storage_date_display = fields.Char(
        string="Einlagerungsdatum", compute="_compute_storage_date_display", store=True
    )
    trace_id = fields.Many2one(
        "kf.legacy.trace", string="Legacy-Rückverfolgung", index=True, ondelete="restrict"
    )

    _sql_constraints = [
        (
            "kf_legacy_production_output_source_unique",
            "unique(source_key)",
            "Die eEvolution-Produktionsausgabe ist bereits vorhanden.",
        )
    ]

    @api.depends("storage_date")
    def _compute_storage_date_display(self):
        for record in self:
            record.storage_date_display = (
                record.storage_date.strftime("%d.%m.%Y") if record.storage_date else ""
            )


class KfLegacyTraceUsage(models.Model):
    _name = "kf.legacy.trace.usage"
    _description = "Abgeleitete eEvolution Chargen-/Serienverwendung"
    _order = "output_storage_date, output_number, id"

    trace_id = fields.Many2one(
        "kf.legacy.trace", string="Komponenten-Serien/-Chargennummer",
        required=True, index=True, ondelete="cascade"
    )
    source_key = fields.Char(string="Ableitungsschlüssel", required=True, index=True)
    production_id = fields.Many2one(
        "kf.legacy.production", string="Legacy-Produktionsauftrag",
        required=True, index=True, ondelete="cascade"
    )
    component_id = fields.Many2one(
        "kf.legacy.production.component", string="Verbrauchsbuchung",
        index=True, ondelete="cascade"
    )
    output_id = fields.Many2one(
        "kf.legacy.production.output", string="Produzierte Serien-/Charge",
        required=True, index=True, ondelete="cascade"
    )
    allocation_basis = fields.Selection(
        [
            ("booking_batch", "Abgeleitet – gleicher Buchungslauf"),
            ("production_order", "Kandidat – gleicher Produktionsauftrag"),
        ],
        string="Zuordnungsbasis", required=True, index=True,
    )
    allocation_note = fields.Char(string="Bewertung", required=True)
    consumption_date = fields.Datetime(
        related="component_id.booking_date", string="Verbrauchsbuchung", readonly=True, store=True
    )
    output_storage_date = fields.Datetime(
        related="output_id.storage_date", string="Fertigmeldung", readonly=True, store=True
    )
    output_type = fields.Selection(
        related="output_id.output_type", string="Ausgabetyp", readonly=True, store=True
    )
    output_number = fields.Char(
        related="output_id.number", string="Endserien-/Chargennummer", readonly=True, store=True
    )
    output_trace_id = fields.Many2one(
        related="output_id.trace_id", string="Rückverfolgung Endprodukt", readonly=True, store=True
    )
    customer_id = fields.Many2one(
        related="output_trace_id.original_partner_id", string="Ursprünglicher Kunde",
        readonly=True, store=True
    )
    customer_order_number = fields.Char(
        related="output_trace_id.original_order_number", string="Kundenauftrag",
        readonly=True, store=True
    )
    customer_delivery_number = fields.Char(
        related="output_trace_id.original_delivery_number", string="Lieferschein",
        readonly=True, store=True
    )
    customer_delivery_date = fields.Datetime(
        related="output_trace_id.original_delivery_date", string="Versanddatum",
        readonly=True, store=True
    )
    customer_delivery_date_display = fields.Char(
        string="Versanddatum", compute="_compute_customer_delivery_date_display", store=True
    )

    _sql_constraints = [
        (
            "kf_legacy_trace_usage_source_unique",
            "unique(source_key)",
            "Diese abgeleitete eEvolution-Verwendung ist bereits vorhanden.",
        )
    ]

    @api.depends("customer_delivery_date")
    def _compute_customer_delivery_date_display(self):
        for record in self:
            record.customer_delivery_date_display = (
                record.customer_delivery_date.strftime("%d.%m.%Y")
                if record.customer_delivery_date else ""
            )


class KfLegacyTraceDelivery(models.Model):
    _name = "kf.legacy.trace.delivery"
    _description = "Direkte eEvolution Chargen-/Serienlieferung"
    _order = "delivery_date, delivery_number, id"

    trace_id = fields.Many2one(
        "kf.legacy.trace", string="Serien-/Charge", required=True, index=True, ondelete="cascade"
    )
    source_key = fields.Char(string="eEvolution Ereignisschlüssel", required=True, index=True)
    delivery_date = fields.Datetime(string="Versanddatum", required=True, index=True)
    delivery_date_display = fields.Char(
        string="Versanddatum", compute="_compute_delivery_date_display", store=True
    )
    delivery_number = fields.Char(string="Lieferschein", required=True, index=True)
    order_key = fields.Integer(string="eEvolution Auftrags-ID", index=True)
    order_number = fields.Char(string="Auftrag", index=True)
    partner_id = fields.Many2one(
        "res.partner", string="Kunde", required=True, index=True, ondelete="restrict"
    )
    eevo_partner_key = fields.Integer(string="eEvolution Adress-ID", required=True, index=True)
    quantity = fields.Float(string="Gelieferte Menge", digits=(16, 6))
    classification = fields.Char(
        string="Lieferweg", default="Direkte Lieferung der Serien-/Chargennummer", readonly=True
    )

    _sql_constraints = [
        (
            "kf_legacy_trace_delivery_source_unique",
            "unique(source_key)",
            "Diese direkte eEvolution-Lieferung wurde bereits importiert.",
        )
    ]

    @api.depends("delivery_date")
    def _compute_delivery_date_display(self):
        for record in self:
            record.delivery_date_display = (
                record.delivery_date.strftime("%d.%m.%Y") if record.delivery_date else ""
            )
