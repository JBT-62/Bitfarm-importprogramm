#!/usr/bin/env python3
"""Compact read-only progress snapshot for the historical sales import."""
import os
import migration_runtime

url, db, user, key = [os.environ[name] for name in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_API_KEY")]
common = migration_runtime.server_proxy(url + "/xmlrpc/2/common", allow_none=True)
uid = common.authenticate(db, user, key, {})
models = migration_runtime.server_proxy(url + "/xmlrpc/2/object", allow_none=True)
call = lambda model, method, a=None, kw=None: models.execute_kw(db, uid, key, model, method, a or [], kw or {})
print("HISTORICAL_SALES=" + str(call("sale.order", "search_count", [[("kf_legacy_history", "=", True)]])))
print("REVIEW_DOCUMENTS=" + str(call("kf.legacy.sales.document", "search_count", [[]])))
print("DELIVERY_EXTERNAL_IDS=" + str(call("ir.model.data", "search_count", [[("module", "=", "__import__"), ("name", "like", "ev_sale_delivery_%")]])))
for model in (
    "kf.legacy.trace", "kf.legacy.trace.event", "kf.legacy.production",
    "kf.legacy.production.component", "kf.legacy.production.output",
    "kf.legacy.trace.usage", "kf.legacy.trace.delivery",
):
    print(model.upper().replace(".", "_") + "=" + str(call(model, "search_count", [[]])))
for model in ("stock.picking", "stock.move", "account.move", "mail.mail"):
    print("SIDE_EFFECT_BASE_" + model.upper().replace(".", "_") + "=" + str(call(model, "search_count", [[]])))
print("READ_ONLY")
