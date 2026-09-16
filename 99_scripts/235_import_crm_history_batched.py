#!/usr/bin/env python3
"""Import completed eEvolution CRM events as inert, dated Odoo chatter history."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import html
import os
import re

import migration_runtime
import pyodbc


def norm(value):
    return str(value or "").strip().casefold()


def source_connection():
    cs = (
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
        f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "ApplicationIntent=ReadOnly;"
    )
    return pyodbc.connect(cs, readonly=True, timeout=30)


class Odoo:
    def __init__(self):
        self.db = os.environ["ODOO_DB"]
        self.url = os.environ["ODOO_URL"].rstrip("/")
        self.user = os.environ["ODOO_USER"]
        self.key = os.environ["ODOO_API_KEY"]
        migration_runtime.require_target(self.db)
        common = migration_runtime.server_proxy(self.url + "/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, self.user, self.key, {})
        if not self.uid:
            raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
        self.models = migration_runtime.server_proxy(self.url + "/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args=None, kwargs=None):
        return self.models.execute_kw(self.db, self.uid, self.key, model, method, args or [], kwargs or {})

    def external_cache(self, model, prefix):
        result, offset = {}, 0
        while True:
            batch = self.call("ir.model.data", "search_read", [[
                ("module", "=", "__import__"), ("model", "=", model), ("name", "like", prefix + "%")
            ]], {"fields": ["name", "res_id"], "limit": 5000, "offset": offset})
            for row in batch:
                result[row["name"]] = int(row["res_id"])
            if len(batch) < 5000:
                return result
            offset += len(batch)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff", default="2016-09-16")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--correct-existing-authors", action="store_true")
    parser.add_argument("--backup")
    args = parser.parse_args()
    cutoff = datetime.fromisoformat(args.cutoff)
    target = migration_runtime.require_target(os.environ.get("ODOO_DB", ""))
    if not args.dry_run and (not args.backup or not args.backup.startswith(target.backup_prefix)):
        raise SystemExit("Apply verlangt eine passende verifizierte Sicherung")
    if args.batch_size < 1 or args.batch_size > 500:
        raise SystemExit("batch-size muss zwischen 1 und 500 liegen")

    odoo = Odoo()
    opportunities = odoo.external_cache("crm.lead", "ev_vkchance_")
    partners = odoo.external_cache("res.partner", "ev_adr_")
    existing_history = odoo.external_cache("mail.message", "ev_crm_history_")
    note = odoo.call("ir.model.data", "search_read", [[
        ("module", "=", "mail"), ("name", "=", "mt_note"), ("model", "=", "mail.message.subtype")
    ]], {"fields": ["res_id"], "limit": 1})
    note_subtype = int(note[0]["res_id"]) if note else False
    target_users = odoo.call("res.users", "search_read", [[("active", "=", True)]], {
        "fields": ["login", "partner_id"], "context": {"active_test": False}, "limit": 10000,
    })
    author_by_login = {
        norm(row["login"]): row["partner_id"][0]
        for row in target_users if row.get("partner_id") and norm(row.get("login"))
    }

    with source_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("""
            SELECT MITARBNR,NAME1,NAME2,EMAILINTERN FROM dbo.MITARBEITER
        """)
        owners = {
            int(row[0]): {
                "name": " ".join(x for x in ((row[1] or "").strip(), (row[2] or "").strip()) if x),
                "email": norm(row[3]),
            }
            for row in cursor.fetchall()
        }
        cursor.execute("""
            SELECT COUNT_BIG(*)
              FROM dbo.TERMIN t
             WHERE t.ANFTERMIN>=? AND t.ANFTERMIN<DATEADD(day,1,CAST(GETDATE() AS date))
        """, cutoff)
        total_source = int(cursor.fetchone()[0])
        top = f"TOP {args.limit} " if args.limit else ""
        cursor.execute(f"""
            SELECT {top}
                   t.TMNR,t.ANFTERMIN,t.ENDTERMIN,t.TMKURZ,t.TMLANG,t.BESUCHSZIEL,
                   t.ERLEDIGT,t.BETREUER,t.VERKAUFSCHANCE,
                   COALESCE(k.ADRNR,t.KNDNR) AS ADRNR,
                   ta.TERMKURZ AS ART_KURZ,ta.TERMTEXT AS ART_TEXT
              FROM dbo.TERMIN t
              LEFT JOIN dbo.TERMINART ta ON ta.TMART=t.TMART
              OUTER APPLY (
                  SELECT TOP 1 ko.ADRNR FROM dbo.KONTAKT ko
                   WHERE ko.TMNR=t.TMNR ORDER BY ko.TMSTMP
              ) k
             WHERE t.ANFTERMIN>=? AND t.ANFTERMIN<DATEADD(day,1,CAST(GETDATE() AS date))
             ORDER BY t.ANFTERMIN,t.TMNR
        """, cutoff)

        planned_create = existing = linked_opportunity = linked_partner = skipped = 0
        skipped_examples = []
        created = corrected_authors = 0
        author_corrections = defaultdict(list)
        pending_values, pending_names = [], []

        def flush():
            nonlocal created, pending_values, pending_names
            if not pending_values:
                return
            created_ids = odoo.call("mail.message", "create", [pending_values], {
                "context": {"mail_create_nosubscribe": True, "mail_notrack": True, "tracking_disable": True}
            })
            if isinstance(created_ids, int):
                created_ids = [created_ids]
            if len(created_ids) != len(pending_values):
                raise RuntimeError("Batch-Anlage der CRM-Historie lieferte unerwartete ID-Anzahl")
            anchor_values = [{
                "module": "__import__", "name": name, "model": "mail.message", "res_id": record_id,
            } for name, record_id in zip(pending_names, created_ids)]
            odoo.call("ir.model.data", "create", [anchor_values])
            created += len(created_ids)
            pending_values, pending_names = [], []

        while True:
            batch = cursor.fetchmany(1000)
            if not batch:
                break
            for row in batch:
                xml_name = f"ev_crm_history_{int(row.TMNR)}"
                owner = owners.get(int(row.BETREUER), {}) if row.BETREUER else {}
                author_id = author_by_login.get(owner.get("email", ""), False)
                if xml_name in existing_history:
                    existing += 1
                    if args.correct_existing_authors:
                        author_corrections[author_id or False].append(existing_history[xml_name])
                    continue
                opportunity_id = False
                if row.VERKAUFSCHANCE:
                    suffix = re.sub("[^0-9A-Fa-f]", "", str(row.VERKAUFSCHANCE))[:16]
                    opportunity_id = opportunities.get(f"ev_vkchance_{suffix}", False)
                partner_id = partners.get(f"ev_adr_{int(row.ADRNR)}", False) if row.ADRNR else False
                if opportunity_id:
                    target_model, target_id = "crm.lead", opportunity_id
                    linked_opportunity += 1
                elif partner_id:
                    target_model, target_id = "res.partner", partner_id
                    linked_partner += 1
                else:
                    skipped += 1
                    if len(skipped_examples) < 20:
                        skipped_examples.append({
                            "tmnr": int(row.TMNR),
                            "adrnr": int(row.ADRNR) if row.ADRNR else None,
                            "verkaufschance": str(row.VERKAUFSCHANCE or ""),
                            "datum": row.ANFTERMIN.isoformat() if row.ANFTERMIN else "",
                            "kurz": str(row.TMKURZ or ""),
                            "art": str(row.ART_TEXT or row.ART_KURZ or ""),
                        })
                    continue
                activity_type = row.ART_TEXT or row.ART_KURZ or "CRM-Aktivität"
                subject = row.TMKURZ or activity_type
                body = [f"<p><strong>{html.escape(str(activity_type))}</strong></p>"]
                if row.TMLANG:
                    body.append(f"<p>{html.escape(str(row.TMLANG)).replace(chr(10), '<br>')}</p>")
                if row.BESUCHSZIEL:
                    body.append(f"<p><strong>Besuchsziel:</strong> {html.escape(str(row.BESUCHSZIEL))}</p>")
                if row.BETREUER:
                    owner_text = owner.get("name") or "Unbekannt"
                    body.append(f"<p><strong>eEvolution-Verantwortlicher:</strong> "
                                f"{html.escape(owner_text)} (Nr. {int(row.BETREUER)})</p>")
                body.append("<p><em>Abgeschlossene Historie aus eEvolution.</em></p>")
                values = {
                    "model": target_model, "res_id": target_id, "message_type": "comment",
                    "subject": str(subject)[:255], "body": "".join(body), "author_id": author_id or False,
                    "date": row.ANFTERMIN.strftime("%Y-%m-%d %H:%M:%S"),
                }
                if note_subtype:
                    values["subtype_id"] = note_subtype
                planned_create += 1
                if not args.dry_run:
                    pending_values.append(values)
                    pending_names.append(xml_name)
                    if len(pending_values) >= args.batch_size:
                        flush()
        if not args.dry_run:
            flush()
            if args.correct_existing_authors:
                for author_id, message_ids in author_corrections.items():
                    for start in range(0, len(message_ids), 1000):
                        ids = message_ids[start:start + 1000]
                        odoo.call("mail.message", "write", [ids, {"author_id": author_id or False}], {
                            "context": {"mail_notrack": True, "tracking_disable": True}
                        })
                        corrected_authors += len(ids)

    mode = "DRY_RUN" if args.dry_run else "APPLY"
    print(f"CRM_HISTORY_{mode}_OK cutoff={args.cutoff} source_total={total_source} "
          f"selected={planned_create+existing+skipped} create={planned_create} existing={existing} "
          f"linked_opportunity={linked_opportunity} linked_partner={linked_partner} skipped={skipped} "
          f"created={created} author_corrections={sum(len(v) for v in author_corrections.values())} "
          f"authors_corrected={corrected_authors}")
    if skipped_examples:
        print("CRM_HISTORY_SKIPPED " + repr(skipped_examples))


if __name__ == "__main__":
    main()
