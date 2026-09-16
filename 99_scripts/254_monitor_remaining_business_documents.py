#!/usr/bin/env python3
"""Read-only progress monitor for effect-free remaining-history records."""
import os
import migration_runtime


def main():
    target = migration_runtime.require_target(os.environ["ODOO_DB"])
    common = migration_runtime.server_proxy(target.url.rstrip("/") + "/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(os.environ["ODOO_DB"], target.user, os.environ["ODOO_API_KEY"], {})
    models = migration_runtime.server_proxy(target.url.rstrip("/") + "/xmlrpc/2/object", allow_none=True)
    call = lambda model, method, args=None, kw=None: models.execute_kw(
        os.environ["ODOO_DB"], uid, os.environ["ODOO_API_KEY"], model, method, args or [], kw or {}
    )
    counts = {
        "heads": call("kf.legacy.business.document", "search_count", [[]]),
        "lines": call("kf.legacy.business.document.line", "search_count", [[]]),
        "deliveries": call("kf.legacy.business.document", "search_count", [[("document_type", "=", "delivery")]]),
        "outgoing_invoices": call("kf.legacy.business.document", "search_count", [[("document_type", "in", ["out_invoice", "out_refund"])] ]),
        "incoming_invoices": call("kf.legacy.business.document", "search_count", [[("document_type", "=", "in_invoice")]]),
        "unlocked": call("kf.legacy.business.document", "search_count", [[("locked", "=", False)]]),
        "production_heads": call("kf.legacy.production", "search_count", [[]]),
        "production_heads_unlocked": call("kf.legacy.production", "search_count", [[("locked", "=", False)]]),
        "production_heads_without_product": call("kf.legacy.production", "search_count", [[("product_id", "=", False)]]),
        "stock_moves": call("stock.move", "search_count", [[]]),
        "account_moves": call("account.move", "search_count", [[]]),
        "account_move_lines": call("account.move.line", "search_count", [[]]),
    }
    print(counts)
    print("MONITOR_OK_NO_WRITES")


if __name__ == "__main__":
    main()
