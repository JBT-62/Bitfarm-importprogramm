{
    "name": "K&F eEvolution Migrationsfelder",
    "version": "19.0.12.0.0",
    "category": "Sales/CRM",
    "summary": "Bewahrt fachliche Originalzeitpunkte aus eEvolution",
    "license": "LGPL-3",
    "depends": ["crm", "stock", "mrp", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        "views/crm_lead_views.xml",
        "views/product_template_views.xml",
        "views/mrp_bom_views.xml",
        "views/legacy_traceability_views.xml",
        "views/legacy_sales_views.xml",
        "views/legacy_purchase_views.xml",
        "views/legacy_business_document_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "kf_legacy_migration/static/src/scss/legacy_traceability.scss",
        ],
    },
    "installable": True,
}
