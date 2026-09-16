#!/usr/bin/env python3
"""Capture immutable rehearsal anchors and Odoo side-effect guardrails.

The script is deliberately read-only.  It records source row counts, stable maximum
business keys and row-version/timestamp markers for the main eEvolution tables.  It
also records the Odoo guardrails required before and after the authorized rehearsal:
all historical sale orders locked, zero stock moves and zero accounting entries.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path

import pyodbc

import migration_runtime


ROOT = Path(__file__).resolve().parents[1]

# Table and numeric/business key used as a practical append anchor.  Counts,
# ROWID and TMSTMP are captured as well, because MAX(key) alone cannot detect
# updates to an existing source record.
SOURCE_ANCHORS = (
    ("ADRESS", "ADRNR"),
    ("KUNDE", "KNDNR"),
    ("LIEFERANT", "LIEFNR"),
    ("ARTIKEL", "LFDNR"),
    ("ANGAUFGUT", "LFDNR"),
    ("ANGAUFPOS", "LFDANGAUFGUTNR"),
    ("AAGLS", "LSNR"),
    ("AAGLSPOS", "LSNR"),
    ("AAGFAKT", "LFDFAKTNR"),
    ("AAGFAKTPOS", "LFDFAKTNR"),
    ("BESTELLUNG", "BESTNR"),
    ("RECHEINGANG", "LFDNR"),
    ("RECHEINPOS", "LFDNR"),
    ("PRODUKTION", "LFDNR"),
    ("PRODAUFINHIST", "LFDNR"),
    ("SNRARCHIV", "LFDSNLFDNR"),
    ("CHARGENARCHIV", "LFDCHLFDNR"),
    ("TERMIN", "TMNR"),
    # VERKAUFSCHANCE.ID is not assumed to be a monotonic numeric key.  Its
    # count and technical change markers are still captured below.
    ("VERKAUFSCHANCE", None),
)


def source_connection():
    return pyodbc.connect(
        f"DRIVER={{{os.environ['EV_DRIVER']}}};SERVER={os.environ['EV_SERVER']};"
        f"DATABASE={os.environ['EV_DATABASE']};UID={os.environ['EV_USER']};"
        f"PWD={os.environ['EV_PASSWORD']};Encrypt=yes;TrustServerCertificate=yes;"
        "ApplicationIntent=ReadOnly;",
        readonly=True,
        timeout=30,
    )


class Odoo:
    def __init__(self):
        target = migration_runtime.require_target(os.environ["ODOO_DB"])
        self.db = os.environ["ODOO_DB"]
        self.key = os.environ["ODOO_API_KEY"]
        common = migration_runtime.server_proxy(
            target.url.rstrip("/") + "/xmlrpc/2/common", allow_none=True
        )
        self.uid = common.authenticate(self.db, target.user, self.key, {})
        if not self.uid:
            raise RuntimeError("Odoo-Anmeldung fehlgeschlagen")
        self.models = migration_runtime.server_proxy(
            target.url.rstrip("/") + "/xmlrpc/2/object", allow_none=True
        )

    def count(self, model, domain=None):
        return int(
            self.models.execute_kw(
                self.db,
                self.uid,
                self.key,
                model,
                "search_count",
                [domain or []],
                {"context": {"active_test": False}},
            )
        )


def source_table_columns(cursor, table):
    cursor.execute(
        """
        SELECT COLUMN_NAME
          FROM INFORMATION_SCHEMA.COLUMNS
         WHERE TABLE_SCHEMA='dbo' AND TABLE_NAME=?
        """,
        table,
    )
    return {str(row[0]).upper() for row in cursor.fetchall()}


def source_snapshot():
    result = {}
    with source_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED")
        for table, anchor in SOURCE_ANCHORS:
            columns = source_table_columns(cursor, table)
            if not columns:
                raise RuntimeError(f"Pflichttabelle dbo.{table} fehlt")
            expressions = ["COUNT_BIG(*) AS row_count"]
            if anchor:
                if anchor.upper() not in columns:
                    raise RuntimeError(f"Pflichtanker dbo.{table}.{anchor} fehlt")
                expressions.append(f"MAX([{anchor}]) AS max_anchor")
            if "ROWID" in columns:
                expressions.append("MAX(CONVERT(bigint,[ROWID])) AS max_rowversion")
            if "TMSTMP" in columns:
                expressions.append("MAX([TMSTMP]) AS max_tmstmp")
            cursor.execute(f"SELECT {', '.join(expressions)} FROM dbo.[{table}]")
            row = cursor.fetchone()
            values = {cursor.description[index][0]: row[index] for index in range(len(row))}
            normalized = {}
            for key, value in values.items():
                if isinstance(value, datetime):
                    normalized[key] = value.isoformat(sep=" ", timespec="seconds")
                elif value is None or isinstance(value, (str, int, float, bool)):
                    normalized[key] = value
                else:
                    normalized[key] = str(value)
            normalized["anchor_column"] = anchor
            result[table] = normalized
    return result


def odoo_guardrails():
    odoo = Odoo()
    legacy_sales = odoo.count("sale.order", [("kf_legacy_history", "=", True)])
    legacy_sales_unlocked = odoo.count(
        "sale.order", [("kf_legacy_history", "=", True), ("locked", "=", False)]
    )
    stock_moves = odoo.count("stock.move")
    account_moves = odoo.count("account.move")
    account_move_lines = odoo.count("account.move.line")
    return {
        "historical_sale_orders": legacy_sales,
        "historical_sale_orders_unlocked": legacy_sales_unlocked,
        "historical_documents_locked": legacy_sales_unlocked == 0,
        "legacy_sales_review_documents_read_only": odoo.count("kf.legacy.sales.document"),
        "legacy_purchase_documents_read_only": odoo.count("kf.legacy.purchase.document"),
        "stock_moves": stock_moves,
        "stock_move_lines": odoo.count("stock.move.line"),
        "stock_pickings": odoo.count("stock.picking"),
        "account_moves": account_moves,
        "account_move_lines": account_move_lines,
        "required_metrics_pass": (
            legacy_sales_unlocked == 0 and stock_moves == 0
            and account_moves == 0 and account_move_lines == 0
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("pre", "post"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if migration_runtime.migration_mode() == "apply":
        raise RuntimeError("Dieser Gate-Audit ist ausschließlich read-only")
    if os.environ.get("ODOO_DB") != "kuf-erp-all-data":
        raise RuntimeError("Gate-Audit ist für kuf-erp-all-data freigegeben")

    result = {
        "database": os.environ["ODOO_DB"],
        "phase": args.phase,
        "captured_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_access": "read-only",
        "source_anchors": source_snapshot(),
        "odoo_guardrails": odoo_guardrails(),
        "interpretation": {
            "max_anchor": "Anker für neu angelegte Quellsätze",
            "count_rowversion_tmstmp": (
                "Zusatzanker, weil MAX des Geschäftsschlüssels Änderungen an bestehenden "
                "Sätzen allein nicht erkennt"
            ),
        },
    }
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
