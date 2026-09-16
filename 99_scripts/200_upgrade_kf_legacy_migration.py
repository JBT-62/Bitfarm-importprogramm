#!/usr/bin/env python3
"""Upgrade only kf_legacy_migration after a guarded deployment."""
import argparse
import os
import time

import migration_runtime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", default="")
    args = parser.parse_args()
    target = migration_runtime.require_target(os.environ.get("ODOO_DB", ""))
    if args.apply and (not args.backup or not args.backup.startswith(target.backup_prefix)):
        raise SystemExit("Apply verlangt eine passende verifizierte Sicherung")
    url, db, user, key = [os.environ[x] for x in ("ODOO_URL", "ODOO_DB", "ODOO_USER", "ODOO_API_KEY")]
    common = migration_runtime.server_proxy(url + "/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(db, user, key, {})
    models = migration_runtime.server_proxy(url + "/xmlrpc/2/object", allow_none=True)
    call = lambda model, method, a=None, kw=None: models.execute_kw(db, uid, key, model, method, a or [], kw or {})
    if args.apply:
        call("ir.module.module", "update_list")
    row = call("ir.module.module", "search_read", [[("name", "=", "kf_legacy_migration")]], {"fields": ["state", "installed_version"], "limit": 1})[0]
    print(f"kf_legacy_migration state={row['state']} version={row.get('installed_version')}")
    if not args.apply:
        print("DRY_RUN_OK")
        return
    call("ir.module.module", "button_immediate_upgrade", [[row["id"]]])
    time.sleep(3)
    row = call("ir.module.module", "search_read", [[("name", "=", "kf_legacy_migration")]], {"fields": ["state", "installed_version"], "limit": 1})[0]
    if row["state"] != "installed" or row.get("installed_version") != "19.0.12.0.0":
        raise SystemExit(f"Modulprüfung fehlgeschlagen: {row}")
    print("UPGRADE_OK", row.get("installed_version"), "backup=" + args.backup)


if __name__ == "__main__":
    main()
