#!/usr/bin/env python3
"""Idempotenter Pilotimport eines eEvolution-Angebots nach Odoo 19.

Importiert ausschließlich nach ``erp-test-1``:

* Kunde und aktive Ansprechpartner
* benötigte Lieferanten
* aktive Artikel und rekursiv ausgewählte Fertigungsstücklisten
* Lieferantenbezüge
* CRM-Chance und Angebot im Entwurf

Das Angebot wird niemals bestätigt. eEvolution wird ausschließlich lesend geöffnet.
Historische Geschäftsbelege, Bestände und Buchungen gehören nicht zu diesem Pilotlauf.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import sys
import time
import xmlrpc.client
from collections import deque
from datetime import date, datetime, timedelta
from pathlib import Path

import pyodbc
import yaml


ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if (ROOT / ".env").exists() else []:
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

ODOO_URL = os.getenv("ODOO_URL")
ODOO_DB = os.getenv("ODOO_DB")
ODOO_USER = os.getenv("ODOO_USER")
ODOO_KEY = os.getenv("ODOO_API_KEY")
EV_DRIVER = os.getenv("EV_DRIVER", "ODBC Driver 18 for SQL Server")
EV_SERVER = os.getenv("EV_SERVER", os.getenv("EEVO_SERVER", "192.168.120.234,1433"))
EV_DATABASE = os.getenv("EV_DATABASE", os.getenv("EEVO_DB", "KuF"))
EV_USER = os.getenv("EV_USER", os.getenv("EEVO_USER", "excel_kuf_readonly"))
EV_PASSWORD = os.getenv("EV_PASSWORD", os.getenv("EEVO_PWD", ""))
XML_MODULE = "__import__"


def rows_to_dicts(cursor, sql, *params):
    cursor.execute(sql, *params)
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def row_to_dict(cursor, sql, *params):
    rows = rows_to_dicts(cursor, sql, *params)
    return rows[0] if rows else None


def source_connection():
    if not EV_PASSWORD:
        raise RuntimeError("EV_PASSWORD fehlt; sicheren Credential-Wrapper verwenden.")
    connection_string = (
        f"DRIVER={{{EV_DRIVER}}};SERVER={EV_SERVER};DATABASE={EV_DATABASE};"
        f"UID={EV_USER};PWD={EV_PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=yes;ApplicationIntent=ReadOnly;"
    )
    return pyodbc.connect(connection_string, readonly=True, timeout=30)


class SourceExtractor:
    def __init__(self, connection, offer_id):
        self.connection = connection
        self.cursor = connection.cursor()
        self.offer_id = offer_id
        self.warnings = []

    def _bom_candidates(self, article_id, document_date):
        candidates = rows_to_dicts(
            self.cursor,
            """
            SELECT LFD_NR, ART_NR, BEZEICHNUNG, TYP, LOSGR, GUELTVDAT,
                   GUELTBDAT, ERSTDAT, TMSTMP
            FROM PRODLIST
            WHERE ART_NR=?
              AND (GUELTVDAT IS NULL OR GUELTVDAT<=?)
              AND (GUELTBDAT IS NULL OR GUELTBDAT>=?)
            ORDER BY LFD_NR
            """,
            article_id,
            document_date,
            document_date,
        )
        return candidates

    def _select_bom(self, article_id, document_date, forced_bom_id=None):
        if forced_bom_id:
            bom = row_to_dict(
                self.cursor,
                """
                SELECT LFD_NR, ART_NR, BEZEICHNUNG, TYP, LOSGR, GUELTVDAT,
                       GUELTBDAT, ERSTDAT, TMSTMP
                FROM PRODLIST WHERE LFD_NR=? AND ART_NR=?
                """,
                forced_bom_id,
                article_id,
            )
            if not bom:
                raise RuntimeError(
                    f"Explizite Unterstückliste {forced_bom_id} gehört nicht zu Artikel {article_id}."
                )
            return bom

        candidates = self._bom_candidates(article_id, document_date)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        candidate_ids = [int(candidate["LFD_NR"]) for candidate in candidates]
        placeholders = ",".join("?" for _ in candidate_ids)
        recent = row_to_dict(
            self.cursor,
            f"""
            SELECT TOP (1) PRODLISTLFDNR
            FROM PRODUKTION
            WHERE ARTNR=? AND PRODLISTLFDNR IN ({placeholders})
            ORDER BY COALESCE(SOLLSTART, ENDDAT, TMSTMP) DESC, LFDNR DESC
            """,
            article_id,
            *candidate_ids,
        )
        selected_id = int(recent["PRODLISTLFDNR"]) if recent else max(candidate_ids)
        self.warnings.append(
            f"Artikel {article_id}: mehrere Stücklisten {candidate_ids}; "
            f"nach jüngster Fertigungsverwendung wurde {selected_id} gewählt."
        )
        return next(candidate for candidate in candidates if int(candidate["LFD_NR"]) == selected_id)

    def extract(self):
        header = row_to_dict(
            self.cursor,
            """
            SELECT h.LFDNR, h.KENNZEICHEN, h.KNDNR, h.ERFASSDATUM, h.STATUS,
                   h.ERLEDIGT, h.WAEHRUNG, h.ABWEICH, h.ABWNAME1, h.ABWNAME2,
                   h.ABWSTRASSE, h.ABWPLZ, h.ABWORT, h.ABWLAND,
                   k.ADRNR, k.NAME1, k.NAME2, k.NAME3, k.NAME4, k.STRASSE,
                   k.PLZ, k.ORT, k.LAND, k.EMAIL, k.TELEFON, k.HANDY,
                   k.ZBEDING, k.WAEHRUNG AS KUNDENWAEHRUNG, k.RABATT,
                   k.SPRKZ, k.STEUERNR, k.IDENTNR
            FROM ANGAUFGUT h
            JOIN KUNDE k ON k.KNDNR=h.KNDNR
            WHERE h.LFDNR=? AND h.ANGEBOT=1
            """,
            self.offer_id,
        )
        if not header:
            raise RuntimeError(f"Angebot {self.offer_id} wurde nicht gefunden.")

        positions = rows_to_dicts(
            self.cursor,
            """
            SELECT p.POSNR, p.LFDARTNR, p.BESTMENGE, p.PREIS, p.RABATT,
                   p.POSRABATT1, p.POSRABATT2, p.POSRABATT3, p.POSRABATT4,
                   p.LIEFERTERMIN, p.ALTERNATIV, p.GUELTIG,
                   p.ABWABEZ1, p.ABWABEZ2, p.ABEZ3, p.ABEZ4, p.TEXT1, p.TEXT2,
                   a.ARTNR1, a.ABEZ1, a.ABEZ2, a.MENGENSCHL
            FROM ANGAUFPOS p
            LEFT JOIN ARTIKEL a ON a.LFDNR=p.LFDARTNR
            WHERE p.LFDANGAUFGUTNR=? AND ISNULL(p.GUELTIG,1)<>0
            ORDER BY p.POSNR
            """,
            self.offer_id,
        )
        if not positions:
            raise RuntimeError(f"Angebot {self.offer_id} hat keine gültigen Positionen.")

        contacts = rows_to_dicts(
            self.cursor,
            """
            SELECT LFDNR, ADRNR, VORNAME, NAME, TITEL, FUNKTION, ABTEILUNGKLAR,
                   TELEFON, TELEMOB, EMAIL, AKTIV, NICHTANZEIGEN
            FROM ADRANSPRECH
            WHERE ADRNR=? AND AKTIV=1 AND ISNULL(NICHTANZEIGEN,0)=0
            ORDER BY LFDNR
            """,
            header["ADRNR"],
        )

        direct_article_ids = {
            int(position["LFDARTNR"])
            for position in positions
            if position.get("LFDARTNR") is not None
        }
        article_ids = set(direct_article_ids)
        selected_boms = {}
        bom_lines = {}
        queue = deque((article_id, None) for article_id in sorted(direct_article_ids))
        visited = set()
        document_date = header["ERFASSDATUM"]

        while queue:
            article_id, forced_bom_id = queue.popleft()
            bom = self._select_bom(article_id, document_date, forced_bom_id)
            visit_key = (article_id, int(bom["LFD_NR"]) if bom else None)
            if visit_key in visited:
                continue
            visited.add(visit_key)
            if not bom:
                continue
            bom_id = int(bom["LFD_NR"])
            selected_boms[bom_id] = bom
            lines = rows_to_dicts(
                self.cursor,
                """
                SELECT i.LIST_NR, i.LFD_NR, i.ART_NR, i.MENGE, i.MENGENSCHL,
                       i.POSITION, i.PHANTOMKENN, i.BEREITSTELL,
                       i.PRODLISTLFDNR, i.PRODLISTLFDNRALTERNATIVART
                FROM PRODINHALT i
                WHERE i.LIST_NR=?
                ORDER BY i.LFD_NR
                """,
                bom_id,
            )
            bom_lines[bom_id] = lines
            for line in lines:
                component_id = int(line["ART_NR"])
                article_ids.add(component_id)
                child_bom_id = line.get("PRODLISTLFDNR")
                queue.append((component_id, int(child_bom_id) if child_bom_id else None))

        placeholders = ",".join("?" for _ in article_ids)
        articles = rows_to_dicts(
            self.cursor,
            f"""
            SELECT a.LFDNR, a.ARTNR1, a.ABEZ1, a.ABEZ2, a.ABEZ3, a.ABEZ4,
                   a.MENGENSCHL, a.VKPR1, a.EKPR, a.LFDLIEFNR, a.WGRUPNR,
                   a.LAGERFUEHRUNG, a.SERIENNR, a.CHARGENFAEHIG,
                   a.INAKTIV, a.LOESCHKNZ, a.DIENSTLEISTUNG,
                   al.CONTENT AS LANGTEXT
            FROM ARTIKEL a
            LEFT JOIN (
                SELECT LFDARTNR, MAX(CONTENT) AS CONTENT
                FROM ARTIKELLONG GROUP BY LFDARTNR
            ) al ON al.LFDARTNR=a.LFDNR
            WHERE a.LFDNR IN ({placeholders})
            ORDER BY a.ARTNR1
            """,
            *sorted(article_ids),
        )
        article_by_id = {int(article["LFDNR"]): article for article in articles}
        missing = article_ids - set(article_by_id)
        if missing:
            raise RuntimeError(f"Stücklisten verweisen auf fehlende Artikel: {sorted(missing)}")

        deleted_articles = []
        for article in articles:
            if article["LOESCHKNZ"]:
                deleted_articles.append((int(article["LFDNR"]), article["ARTNR1"]))
        if deleted_articles:
            raise RuntimeError(
                "Benötigte Stückliste enthält löschgekennzeichnete Artikel; "
                f"fachliche Ersatzentscheidung erforderlich: {deleted_articles}"
            )

        vendor_numbers = sorted(
            {int(article["LFDLIEFNR"]) for article in articles if article.get("LFDLIEFNR")}
        )
        vendors = []
        if vendor_numbers:
            vendor_placeholders = ",".join("?" for _ in vendor_numbers)
            vendors = rows_to_dicts(
                self.cursor,
                f"""
                SELECT ADRNR, LIEFNR, NAME1, NAME2, NAME3, NAME4, STRASSE,
                       PLZ, ORT, LAND, EMAIL, TELEFON, HANDY, LOESCHKNZ,
                       BESTELLSPERRE, SUB_AUTOBESTELL, SUB_DIENSTART
                FROM LIEFERANT
                WHERE LIEFNR IN ({vendor_placeholders})
                ORDER BY NAME1
                """,
                *vendor_numbers,
            )
        vendor_by_number = {int(vendor["LIEFNR"]): vendor for vendor in vendors}
        missing_vendors = sorted(set(vendor_numbers) - set(vendor_by_number))
        if missing_vendors:
            self.warnings.append(f"Nicht auflösbare Standardlieferanten: {missing_vendors}")

        uom_codes = {int(article["MENGENSCHL"]) for article in articles if article.get("MENGENSCHL") is not None}
        for lines in bom_lines.values():
            uom_codes.update(int(line["MENGENSCHL"]) for line in lines if line.get("MENGENSCHL") is not None)
        uom_placeholders = ",".join("?" for _ in uom_codes)
        uoms = rows_to_dicts(
            self.cursor,
            f"SELECT LFDNR, BEZ, LBEZ FROM MENGENSCHL WHERE LFDNR IN ({uom_placeholders})",
            *sorted(uom_codes),
        ) if uom_codes else []

        return {
            "header": header,
            "positions": positions,
            "contacts": contacts,
            "direct_article_ids": direct_article_ids,
            "articles": articles,
            "article_by_id": article_by_id,
            "boms": selected_boms,
            "bom_lines": bom_lines,
            "vendors": vendors,
            "vendor_by_number": vendor_by_number,
            "uoms": uoms,
            "deleted_articles": deleted_articles,
            "warnings": self.warnings,
        }


class OdooClient:
    def __init__(self, dry_run):
        if not all([ODOO_URL, ODOO_DB, ODOO_USER, ODOO_KEY]):
            raise RuntimeError("ODOO_URL/DB/USER/API_KEY fehlen in .env.")
        if ODOO_DB != "erp-test-1":
            raise RuntimeError(f"Pilotimport ist nur für erp-test-1 erlaubt, nicht {ODOO_DB!r}.")
        self.dry_run = dry_run
        self.uid = None
        self.models = None
        self.connect()
        self.ext_cache = {}
        self.stats = {"create": 0, "update": 0, "bind": 0, "existing": 0}

    def connect(self):
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_KEY, {})
        if not self.uid:
            raise RuntimeError("Odoo-Authentifizierung fehlgeschlagen.")
        self.models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, args=None, kwargs=None):
        last_error = None
        for attempt in range(5):
            try:
                return self.models.execute_kw(
                    ODOO_DB, self.uid, ODOO_KEY, model, method, args or [], kwargs or {}
                )
            except xmlrpc.client.Fault:
                raise
            except (ConnectionError, OSError, socket.error) as error:
                last_error = error
                time.sleep(2 ** attempt)
                self.connect()
        raise RuntimeError(f"Odoo blieb unerreichbar: {last_error!r}")

    def external_id(self, model, name):
        key = (model, name)
        if key not in self.ext_cache:
            records = self.call(
                "ir.model.data",
                "search_read",
                [[("module", "=", XML_MODULE), ("name", "=", name), ("model", "=", model)]],
                {"fields": ["res_id"], "limit": 1},
            )
            self.ext_cache[key] = records[0]["res_id"] if records else None
        return self.ext_cache[key]

    def attach_external_id(self, model, record_id, name):
        self.call(
            "ir.model.data",
            "create",
            [{"module": XML_MODULE, "name": name, "model": model, "res_id": record_id}],
        )
        self.ext_cache[(model, name)] = record_id

    def upsert(self, model, name, values, natural_domain=None):
        record_id = self.external_id(model, name)
        if record_id:
            if self.dry_run:
                self.stats["existing"] += 1
                return record_id
            self.call(model, "write", [[record_id], values])
            self.stats["update"] += 1
            return record_id

        natural_id = None
        if natural_domain:
            natural_ids = self.call(model, "search", [natural_domain], {"limit": 2})
            if len(natural_ids) > 1:
                raise RuntimeError(f"Mehrdeutige natürliche Zuordnung für {model}/{name}: {natural_ids}")
            natural_id = natural_ids[0] if natural_ids else None
        if self.dry_run:
            self.stats["bind" if natural_id else "create"] += 1
            return natural_id
        if natural_id:
            self.call(model, "write", [[natural_id], values])
            self.attach_external_id(model, natural_id, name)
            self.stats["bind"] += 1
            return natural_id

        record_id = self.call(model, "create", [values])
        try:
            self.attach_external_id(model, record_id, name)
        except Exception:
            self.call(model, "unlink", [[record_id]])
            raise
        self.stats["create"] += 1
        return record_id

    def resolve(self, model, name):
        return self.external_id(model, name)


COUNTRY_ALIASES = {"USA": "US", "VRC": "CN", "GB": "GB", "D": "DE"}
UOM_ALIASES = {
    "STK": ["Units", "Unit", "Stück"],
    "ST": ["Units", "Unit", "Stück"],
    "KG": ["kg", "Kilograms", "Kilogramm"],
    "G": ["g", "Grams", "Gramm"],
    "M": ["m", "Meters", "Meter"],
    "M2": ["m²", "m2"],
    "M3": ["m³", "m3"],
    "L": ["L", "Liters", "Liter"],
}


def country_id(odoo, source_code):
    code = COUNTRY_ALIASES.get((source_code or "DE").strip().upper(), (source_code or "DE").strip().upper())
    ids = odoo.call("res.country", "search", [[("code", "=", code)]], {"limit": 1})
    return ids[0] if ids else None


def resolve_uoms(odoo, source_uoms):
    mapping = {}
    missing = []
    for source_uom in source_uoms:
        code = str(source_uom.get("BEZ") or "").strip()
        candidates = UOM_ALIASES.get(code.upper(), [code])
        ids = odoo.call("uom.uom", "search", [[("name", "in", candidates)]], {"limit": 1})
        if not ids:
            missing.append((source_uom["LFDNR"], code, source_uom.get("LBEZ")))
        else:
            mapping[int(source_uom["LFDNR"])] = ids[0]
    if missing:
        raise RuntimeError(f"Nicht zugeordnete Mengeneinheiten: {missing}")
    return mapping


def serial_category(odoo, article):
    if not article.get("SERIENNR"):
        return None
    config = yaml.safe_load((ROOT / "02_mappings" / "product_serial_groups.yaml").read_text(encoding="utf-8"))
    text = " ".join(str(article.get(key) or "") for key in ("ABEZ1", "ABEZ2")).upper()
    for group in config["groups"]:
        if any(pattern.upper() in text for pattern in group["patterns"]):
            slug = re.sub(r"[^a-z0-9]+", "_", group["name"].lower()).strip("_")
            return odoo.resolve("product.category", f"ev_serial_group_{slug}")
    return None


def product_name(article):
    return " ".join(filter(None, [str(article.get("ABEZ1") or "").strip(), str(article.get("ABEZ2") or "").strip()])).strip()


def line_name(position):
    parts = [
        position.get("ABWABEZ1") or position.get("ABEZ1"),
        position.get("ABWABEZ2") or position.get("ABEZ2"),
        position.get("ABEZ3"),
        position.get("ABEZ4"),
        position.get("TEXT1"),
        position.get("TEXT2"),
    ]
    result = "\n".join(str(part).strip() for part in parts if part and str(part).strip())
    return result or str(position.get("ARTNR1") or "Freie Position")


def import_data(data, odoo, offer_id):
    dry_run = odoo.dry_run
    uom_map = resolve_uoms(odoo, data["uoms"])
    unit_ids = odoo.call("uom.uom", "search", [[("name", "in", ["Units", "Unit", "Stück"])]], {"limit": 1})
    if not unit_ids:
        raise RuntimeError("Odoo-Standardeinheit Stück/Units fehlt.")
    unit_id = unit_ids[0]

    header = data["header"]
    customer_name = " ".join(filter(None, [header.get("NAME1"), header.get("NAME2"), header.get("NAME3"), header.get("NAME4")])).strip()
    payment_term_id = odoo.resolve("account.payment.term", f"ev_zbed_{int(header['ZBEDING'])}") if header.get("ZBEDING") else None
    customer_values = {
        "name": customer_name,
        "ref": f"EV-ADR-{int(header['ADRNR'])}",
        "customer_rank": 1,
        "is_company": True,
        "street": header.get("STRASSE") or "",
        "zip": header.get("PLZ") or "",
        "city": header.get("ORT") or "",
        "country_id": country_id(odoo, header.get("LAND")),
        "email": header.get("EMAIL") or "",
        "phone": header.get("TELEFON") or "",
        "comment": f"eEvolution ADRNR={int(header['ADRNR'])}, KNDNR={int(header['KNDNR'])}",
    }
    if payment_term_id:
        customer_values["property_payment_term_id"] = payment_term_id
    customer_id = odoo.upsert(
        "res.partner",
        f"ev_adr_{int(header['ADRNR'])}",
        customer_values,
        [("ref", "=", customer_values["ref"])],
    )

    contact_ids = []
    for contact in data["contacts"]:
        values = {
            "name": " ".join(filter(None, [contact.get("VORNAME"), contact.get("NAME")])).strip(),
            "parent_id": customer_id,
            "type": "contact",
            "function": contact.get("FUNKTION") or contact.get("ABTEILUNGKLAR") or "",
            "phone": contact.get("TELEFON") or "",
            "email": contact.get("EMAIL") or "",
            "comment": f"eEvolution ADRANSPRECH.LFDNR={int(contact['LFDNR'])}",
        }
        if contact.get("TELEMOB"):
            values["comment"] += f"\nMobil: {contact['TELEMOB']}"
        contact_id = odoo.upsert(
            "res.partner",
            f"ev_contact_{int(contact['LFDNR'])}",
            values,
        )
        if contact_id:
            contact_ids.append((contact, contact_id))

    vendor_partner_by_number = {}
    for vendor in data["vendors"]:
        name = " ".join(filter(None, [vendor.get("NAME1"), vendor.get("NAME2"), vendor.get("NAME3"), vendor.get("NAME4")])).strip()
        values = {
            "name": name,
            "ref": f"EV-ADR-{int(vendor['ADRNR'])}",
            "supplier_rank": 1,
            "is_company": True,
            "street": vendor.get("STRASSE") or "",
            "zip": vendor.get("PLZ") or "",
            "city": vendor.get("ORT") or "",
            "country_id": country_id(odoo, vendor.get("LAND")),
            "email": vendor.get("EMAIL") or "",
            "phone": vendor.get("TELEFON") or "",
            "comment": f"eEvolution ADRNR={int(vendor['ADRNR'])}, LIEFNR={int(vendor['LIEFNR'])}",
        }
        partner_id = odoo.upsert(
            "res.partner",
            f"ev_adr_{int(vendor['ADRNR'])}",
            values,
            [("ref", "=", values["ref"])],
        )
        vendor_partner_by_number[int(vendor["LIEFNR"])] = partner_id

    mto_routes = odoo.call(
        "stock.route", "search", [[("name", "ilike", "Replenish on Order")]],
        {"limit": 1, "context": {"active_test": False}},
    )
    if mto_routes and not dry_run:
        odoo.call("stock.route", "write", [mto_routes, {"active": True}])
    products_with_bom = {int(bom["ART_NR"]) for bom in data["boms"].values()}
    product_template_by_source = {}
    product_variant_by_source = {}
    tax_ids = odoo.call(
        "account.tax", "search",
        [[("type_tax_use", "=", "sale"), ("amount", "=", 19), ("active", "=", True)]],
        {"limit": 1},
    )

    for article in data["articles"]:
        article_id = int(article["LFDNR"])
        vendor_number = int(article["LFDLIEFNR"]) if article.get("LFDLIEFNR") else None
        is_service = bool(article.get("DIENSTLEISTUNG"))
        is_storable = bool(article.get("LAGERFUEHRUNG")) and not is_service
        tracking = "serial" if article.get("SERIENNR") else "lot" if article.get("CHARGENFAEHIG") else "none"
        category_id = serial_category(odoo, article)
        route_ids = []
        # In Odoo 19 sind Fertigen/Einkaufen lagerbezogene Routen. Am Produkt
        # wird nur MTO gesetzt; die passende Lagerregel entscheidet anhand von
        # Stückliste bzw. Lieferantenbezug über Fertigung oder Einkauf.
        if article_id in products_with_bom and article_id in data["direct_article_ids"]:
            route_ids.extend(mto_routes)
        values = {
            "name": product_name(article),
            "default_code": article.get("ARTNR1") or str(article_id),
            "type": "service" if is_service else "consu",
            "is_storable": is_storable,
            "tracking": tracking,
            "uom_id": uom_map.get(int(article["MENGENSCHL"])) if article.get("MENGENSCHL") is not None else unit_id,
            "list_price": float(article.get("VKPR1") or 0),
            "standard_price": float(article.get("EKPR") or 0),
            "description": article.get("LANGTEXT") or "",
            "sale_ok": article_id in data["direct_article_ids"],
            "purchase_ok": bool(vendor_number),
            "active": True,
        }
        if category_id:
            values["categ_id"] = category_id
        if route_ids:
            values["route_ids"] = [(6, 0, sorted(set(route_ids)))]
        if tax_ids:
            values["taxes_id"] = [(6, 0, tax_ids)]
        template_id = odoo.upsert(
            "product.template",
            f"ev_product_{article_id}",
            values,
            [("default_code", "=", values["default_code"])],
        )
        product_template_by_source[article_id] = template_id
        if template_id:
            variant_ids = odoo.call("product.product", "search", [[("product_tmpl_id", "=", template_id)]], {"limit": 1})
            if not variant_ids and not dry_run:
                raise RuntimeError(f"Produktvariante fehlt für Artikel {article['ARTNR1']}")
            product_variant_by_source[article_id] = variant_ids[0] if variant_ids else None

        partner_id = vendor_partner_by_number.get(vendor_number)
        if template_id and partner_id and vendor_number:
            supplier_values = {
                "product_tmpl_id": template_id,
                "partner_id": partner_id,
                "min_qty": 0.0,
                "price": float(article.get("EKPR") or 0),
            }
            odoo.upsert(
                "product.supplierinfo",
                f"ev_supinfo_{article_id}_{vendor_number}",
                supplier_values,
                [("product_tmpl_id", "=", template_id), ("partner_id", "=", partner_id)],
            )

    bom_id_by_source = {}
    for source_bom_id, bom in sorted(data["boms"].items()):
        article_id = int(bom["ART_NR"])
        template_id = product_template_by_source.get(article_id)
        if not template_id and dry_run:
            continue
        article = data["article_by_id"][article_id]
        values = {
            "product_tmpl_id": template_id,
            "product_qty": float(bom.get("LOSGR") or 1),
            "product_uom_id": uom_map.get(int(article["MENGENSCHL"]), unit_id),
            "type": "normal",
            "code": f"eEvolution SL {source_bom_id}",
        }
        bom_id = odoo.upsert("mrp.bom", f"ev_bom_{source_bom_id}", values)
        bom_id_by_source[source_bom_id] = bom_id
        for line in data["bom_lines"].get(source_bom_id, []):
            component_id = int(line["ART_NR"])
            variant_id = product_variant_by_source.get(component_id)
            if dry_run and not variant_id:
                continue
            if not variant_id:
                raise RuntimeError(f"Produktvariante für Stücklistenkomponente {component_id} fehlt.")
            line_values = {
                "bom_id": bom_id,
                "product_id": variant_id,
                "product_qty": float(line.get("MENGE") or 0),
                "product_uom_id": uom_map.get(int(line["MENGENSCHL"]), unit_id) if line.get("MENGENSCHL") is not None else unit_id,
                "sequence": int(float(line.get("POSITION") or line.get("LFD_NR") or 10)),
            }
            odoo.upsert(
                "mrp.bom.line",
                f"ev_bom_line_{source_bom_id}_{int(line['LFD_NR'])}",
                line_values,
            )

    if dry_run:
        return

    theatre_contacts = [item for item in contact_ids if "theater" in str(item[0].get("ABTEILUNGKLAR") or "").lower()]
    primary_contact = theatre_contacts[0] if theatre_contacts else (contact_ids[0] if contact_ids else None)
    contact_record = primary_contact[0] if primary_contact else None
    net_total = sum(
        float(position.get("BESTMENGE") or 0)
        * float(position.get("PREIS") or 0)
        * (1 - float(position.get("RABATT") or 0) / 100)
        for position in data["positions"]
        if not position.get("ALTERNATIV")
    )
    opportunity_values = {
        "name": f"Pilot {offer_id} – {header.get('KENNZEICHEN') or customer_name}",
        "type": "opportunity",
        "partner_id": customer_id,
        "contact_name": " ".join(filter(None, [contact_record.get("VORNAME"), contact_record.get("NAME")])).strip() if contact_record else "",
        "email_from": contact_record.get("EMAIL") or "" if contact_record else "",
        "phone": contact_record.get("TELEFON") or "" if contact_record else "",
        "expected_revenue": net_total,
        "description": f"Pilotdurchlauf auf Basis eEvolution-Angebot {offer_id}. Nicht automatisch gewinnen/abschließen.",
    }
    lead_fields = odoo.call("crm.lead", "fields_get", [], {"attributes": ["type"]})
    if "kf_legacy_created_at" in lead_fields:
        opportunity_values["kf_legacy_created_at"] = header["ERFASSDATUM"]
    opportunity_id = odoo.upsert("crm.lead", f"ev_pilot_crm_{offer_id}", opportunity_values)

    currencies = odoo.call("res.currency", "search", [[("name", "=", "EUR")]], {"limit": 1})
    if not currencies:
        raise RuntimeError("EUR-Währung fehlt in Odoo.")
    pricelists = odoo.call("product.pricelist", "search", [[("currency_id", "=", currencies[0])]], {"limit": 1})
    if not pricelists:
        raise RuntimeError("EUR-Preisliste fehlt in Odoo.")
    sale_values = {
        "partner_id": customer_id,
        "partner_invoice_id": customer_id,
        "partner_shipping_id": customer_id,
        "opportunity_id": opportunity_id,
        "pricelist_id": pricelists[0],
        "date_order": header["ERFASSDATUM"],
        "client_order_ref": f"eEvolution Angebot {offer_id}",
        "origin": f"eEvolution Pilot {offer_id}",
        "note": (
            "Pilotangebot für den Benutzer-Durchlauf. Nicht automatisch importierte Folgebelege; "
            "ab Bestätigung arbeiten die Benutzer im Odoo-Standardprozess weiter."
        ),
    }
    if payment_term_id:
        sale_values["payment_term_id"] = payment_term_id
    existing_sale_id = odoo.external_id("sale.order", f"ev_pilot_offer_{offer_id}")
    if existing_sale_id:
        state = odoo.call("sale.order", "read", [[existing_sale_id]], {"fields": ["state"]})[0]["state"]
        if state not in ("draft", "sent"):
            raise RuntimeError(
                f"Pilotangebot wurde bereits bearbeitet (Status {state}); ein Wiederholungslauf darf es nicht überschreiben."
            )
    sale_id = odoo.upsert(
        "sale.order",
        f"ev_pilot_offer_{offer_id}",
        sale_values,
        [("client_order_ref", "=", sale_values["client_order_ref"]), ("state", "in", ["draft", "sent"])],
    )

    current_line_ext_names = set()
    for position in data["positions"]:
        article_id = int(position["LFDARTNR"]) if position.get("LFDARTNR") else None
        variant_id = product_variant_by_source.get(article_id)
        if not variant_id:
            raise RuntimeError(f"Angebotsposition {position['POSNR']} hat kein Odoo-Produkt.")
        ext_name = f"ev_pilot_offer_line_{offer_id}_{int(position['POSNR'])}"
        current_line_ext_names.add(ext_name)
        values = {
            "order_id": sale_id,
            "product_id": variant_id,
            "name": line_name(position),
            "product_uom_qty": float(position.get("BESTMENGE") or 0),
            "product_uom_id": uom_map.get(int(position["MENGENSCHL"]), unit_id) if position.get("MENGENSCHL") is not None else unit_id,
            "price_unit": float(position.get("PREIS") or 0),
            "discount": float(position.get("RABATT") or 0),
        }
        if tax_ids:
            values["tax_ids"] = [(6, 0, tax_ids)]
        odoo.upsert("sale.order.line", ext_name, values)


def print_summary(data, offer_id):
    print(f"Angebot {offer_id}: {data['header']['KENNZEICHEN']}")
    print(f"Kunde: {data['header']['NAME1']} (ADRNR {int(data['header']['ADRNR'])})")
    print(f"Positionen: {len(data['positions'])}")
    print(f"Aktive Ansprechpartner: {len(data['contacts'])}")
    print(f"Artikel im Abhängigkeitsnetz: {len(data['articles'])}")
    print(f"Ausgewählte Stücklisten: {len(data['boms'])}")
    print(f"Stücklistenpositionen: {sum(len(lines) for lines in data['bom_lines'].values())}")
    print(f"Lieferanten: {len(data['vendors'])}")
    print(f"Mengeneinheiten: {len(data['uoms'])}")
    print("Produktfilter: INAKTIV wird übernommen; nur LOESCHKNZ wird ausgeschlossen")
    for warning in data["warnings"]:
        print(f"  WARNUNG: {warning}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nr", type=int, default=39575)
    parser.add_argument("--import", dest="do_import", action="store_true")
    args = parser.parse_args()

    mode = "IMPORT" if args.do_import else "DRY-RUN"
    print(f"=== Pilotangebot {args.nr} – {mode} ===")
    with source_connection() as connection:
        data = SourceExtractor(connection, args.nr).extract()
    print_summary(data, args.nr)

    odoo = OdooClient(dry_run=not args.do_import)
    import_data(data, odoo, args.nr)
    print("Odoo-Aktionen:", ", ".join(f"{key}={value}" for key, value in odoo.stats.items()))
    if not args.do_import:
        print("DRY_RUN_OK – es wurde nichts geschrieben.")
    else:
        print("IMPORT_OK – CRM-Chance und Angebot bleiben im Entwurf.")


if __name__ == "__main__":
    main()
