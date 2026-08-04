#!/usr/bin/env python3
"""
Simulation: eEvolution Kundentabellen → Odoo 19 res.partner

Zeigt die Tabellenstruktur (Adressen + Kunden), Beispieldaten
und das fertige Mapping – ohne echten DB-Zugriff.

Aufruf:
  python simulate_kunden_mapping.py              # Tabellen + Mapping anzeigen
  python simulate_kunden_mapping.py --export     # CSV-Preview für Odoo-Import
"""

import json
import csv
import io
import argparse
from datetime import date

# ---------------------------------------------------------------------------
# eEvolution Tabellenschema (MSSQL, typische eEvolution-Struktur)
# ---------------------------------------------------------------------------

EEVO_SCHEMA = {
    "Adressen": {
        "description": "Haupt-Adresstabelle – enthält Kunden UND Lieferanten",
        "columns": [
            ("AdressenID",      "int",          False,  "PK"),
            ("AdressenNr",      "varchar(20)",  False,  "Kundennummer / Matchcode"),
            ("Matchcode",       "varchar(40)",  True,   "Kurzbezeichnung für Suche"),
            ("Name1",           "varchar(60)",  False,  "Firma oder Nachname"),
            ("Name2",           "varchar(60)",  True,   "Vorname oder Zusatz"),
            ("Name3",           "varchar(60)",  True,   "Adresszusatz Zeile 3"),
            ("Strasse",         "varchar(60)",  True,   "Straße + Hausnummer"),
            ("PLZ",             "varchar(10)",  True,   "Postleitzahl"),
            ("Ort",             "varchar(60)",  True,   "Stadt"),
            ("LandID",          "int",          True,   "FK → Laender.LandID"),
            ("Telefon",         "varchar(30)",  True,   "Haupttelefon"),
            ("Telefon2",        "varchar(30)",  True,   "Zweites Telefon / Mobil"),
            ("Fax",             "varchar(30)",  True,   "Fax"),
            ("Email",           "varchar(120)", True,   "E-Mail Adresse"),
            ("Internet",        "varchar(120)", True,   "Webseite"),
            ("UStIdNr",         "varchar(20)",  True,   "Umsatzsteuer-ID (USt-IdNr.)"),
            ("Bemerkung",       "ntext",        True,   "Interne Notizen"),
            ("Gesperrt",        "bit",          False,  "0=aktiv, 1=gesperrt"),
            ("IsKunde",         "bit",          False,  "1=Kundendatensatz"),
            ("IsLieferant",     "bit",          False,  "1=Lieferantendatensatz"),
            ("AngelgtAm",       "datetime",     True,   "Erstellungsdatum"),
            ("GeaendertAm",     "datetime",     True,   "Letztes Änderungsdatum"),
        ],
    },
    "Kunden": {
        "description": "Kundenspezifische Konditionen – 1:1 mit Adressen (IsKunde=1)",
        "columns": [
            ("KundenID",            "int",          False,  "PK"),
            ("AdressenID",          "int",          False,  "FK → Adressen.AdressenID"),
            ("KundenNr",            "varchar(20)",  True,   "Kundennummer (oft = AdressenNr)"),
            ("DebitKontoNr",        "varchar(20)",  True,   "Debitorenkonto Buchhaltung"),
            ("WaehrungID",          "int",          True,   "FK → Waehrungen.WaehrungID"),
            ("ZahlungsbedingungID", "int",          True,   "FK → Zahlungsbedingungen.ID"),
            ("VersandartID",        "int",          True,   "FK → Versandarten.ID"),
            ("LieferbedingungID",   "int",          True,   "FK → Lieferbedingungen.ID"),
            ("PreisGruppeID",       "int",          True,   "FK → Preisgruppen.ID"),
            ("RabattGruppe",        "varchar(10)",  True,   "Rabattgruppen-Kürzel"),
            ("Rabatt",              "decimal(5,2)", True,   "Standardrabatt in %"),
            ("Kreditlimit",         "decimal(12,2)",True,   "Kreditlimit in Hauswährung"),
            ("Umsatzsteuerklasse",  "varchar(10)",  True,   "Steuerklasse (z.B. 'I'=Inland)"),
            ("Preisgruppe",         "varchar(10)",  True,   "Preislisten-Zuordnung"),
            ("Sprache",             "varchar(5)",   True,   "Sprachkürzel (z.B. 'DE','EN')"),
            ("Vertreter1ID",        "int",          True,   "FK → Vertreter.ID (Außendienst)"),
        ],
    },
    "AdressenAnsprechpartner": {
        "description": "Ansprechpartner je Adresse (n:1 → Adressen)",
        "columns": [
            ("AnsprechpartnerID",   "int",          False,  "PK"),
            ("AdressenID",          "int",          False,  "FK → Adressen.AdressenID"),
            ("Anrede",              "varchar(10)",  True,   "Herr / Frau / Dr. …"),
            ("Vorname",             "varchar(40)",  True,   "Vorname"),
            ("Nachname",            "varchar(60)",  False,  "Nachname"),
            ("Position",            "varchar(60)",  True,   "Stellenbezeichnung"),
            ("Telefon",             "varchar(30)",  True,   "Direktdurchwahl"),
            ("Mobil",               "varchar(30)",  True,   "Mobilnummer"),
            ("Email",               "varchar(120)", True,   "E-Mail Ansprechpartner"),
            ("IstHaupt",            "bit",          False,  "1=Hauptansprechpartner"),
        ],
    },
}

# ---------------------------------------------------------------------------
# Beispieldaten (simulierter DB-Export)
# ---------------------------------------------------------------------------

SAMPLE_DATA = [
    {
        "adressen": {
            "AdressenID": 1001,
            "AdressenNr": "K-10001",
            "Matchcode": "MUSTER GMBH",
            "Name1": "Muster GmbH",
            "Name2": None,
            "Name3": None,
            "Strasse": "Hauptstraße 42",
            "PLZ": "70173",
            "Ort": "Stuttgart",
            "LandID": 1,          # Deutschland
            "Telefon": "+49 711 123456",
            "Telefon2": None,
            "Fax": "+49 711 123457",
            "Email": "info@muster-gmbh.de",
            "Internet": "https://www.muster-gmbh.de",
            "UStIdNr": "DE123456789",
            "Bemerkung": "Langjähriger Stammkunde, bevorzugt Lieferung Di-Do",
            "Gesperrt": 0,
            "IsKunde": 1,
            "IsLieferant": 0,
            "AngelgtAm": "2019-03-15 08:30:00",
            "GeaendertAm": "2025-11-20 14:12:00",
        },
        "kunden": {
            "KundenID": 501,
            "AdressenID": 1001,
            "KundenNr": "K-10001",
            "DebitKontoNr": "10001",
            "WaehrungID": 1,       # EUR
            "ZahlungsbedingungID": 3,  # 14 Tage netto
            "VersandartID": 2,
            "LieferbedingungID": 1,
            "PreisGruppeID": 1,
            "RabattGruppe": "A",
            "Rabatt": 5.00,
            "Kreditlimit": 25000.00,
            "Umsatzsteuerklasse": "I",
            "Preisgruppe": "VK1",
            "Sprache": "DE",
            "Vertreter1ID": 7,
        },
        "ansprechpartner": [
            {
                "AnsprechpartnerID": 2001,
                "AdressenID": 1001,
                "Anrede": "Herr",
                "Vorname": "Thomas",
                "Nachname": "Müller",
                "Position": "Einkaufsleiter",
                "Telefon": "+49 711 123456-12",
                "Mobil": "+49 172 9876543",
                "Email": "t.mueller@muster-gmbh.de",
                "IstHaupt": 1,
            }
        ],
    },
    {
        "adressen": {
            "AdressenID": 1002,
            "AdressenNr": "K-10002",
            "Matchcode": "TECHNIK AG",
            "Name1": "Technik AG",
            "Name2": "Abteilung Beschaffung",
            "Name3": None,
            "Strasse": "Industrieweg 7",
            "PLZ": "80331",
            "Ort": "München",
            "LandID": 1,
            "Telefon": "+49 89 987654",
            "Telefon2": "+49 89 987655",
            "Fax": None,
            "Email": "einkauf@technik-ag.de",
            "Internet": "https://www.technik-ag.de",
            "UStIdNr": "DE987654321",
            "Bemerkung": None,
            "Gesperrt": 0,
            "IsKunde": 1,
            "IsLieferant": 0,
            "AngelgtAm": "2021-07-01 09:00:00",
            "GeaendertAm": "2026-01-10 10:05:00",
        },
        "kunden": {
            "KundenID": 502,
            "AdressenID": 1002,
            "KundenNr": "K-10002",
            "DebitKontoNr": "10002",
            "WaehrungID": 1,
            "ZahlungsbedingungID": 5,  # 30 Tage netto
            "VersandartID": 1,
            "LieferbedingungID": 1,
            "PreisGruppeID": 2,
            "RabattGruppe": "B",
            "Rabatt": 2.50,
            "Kreditlimit": 50000.00,
            "Umsatzsteuerklasse": "I",
            "Preisgruppe": "VK2",
            "Sprache": "DE",
            "Vertreter1ID": 7,
        },
        "ansprechpartner": [],
    },
    {
        "adressen": {
            "AdressenID": 1003,
            "AdressenNr": "K-10003",
            "Matchcode": "SCHMIDT GESPERRT",
            "Name1": "Schmidt KG",
            "Name2": None,
            "Name3": None,
            "Strasse": "Am Markt 1",
            "PLZ": "04109",
            "Ort": "Leipzig",
            "LandID": 1,
            "Telefon": "+49 341 555000",
            "Telefon2": None,
            "Fax": None,
            "Email": "info@schmidt-kg.de",
            "Internet": None,
            "UStIdNr": None,
            "Bemerkung": "GESPERRT wegen offener Forderungen",
            "Gesperrt": 1,
            "IsKunde": 1,
            "IsLieferant": 0,
            "AngelgtAm": "2018-05-10 11:00:00",
            "GeaendertAm": "2025-03-01 08:00:00",
        },
        "kunden": {
            "KundenID": 503,
            "AdressenID": 1003,
            "KundenNr": "K-10003",
            "DebitKontoNr": "10003",
            "WaehrungID": 1,
            "ZahlungsbedingungID": 1,
            "VersandartID": 1,
            "LieferbedingungID": 1,
            "PreisGruppeID": 1,
            "RabattGruppe": None,
            "Rabatt": 0.00,
            "Kreditlimit": 0.00,
            "Umsatzsteuerklasse": "I",
            "Preisgruppe": "VK1",
            "Sprache": "DE",
            "Vertreter1ID": None,
        },
        "ansprechpartner": [],
    },
]

# Lookup-Tabellen (simuliert)
LAND_MAP   = {1: "DE", 2: "AT", 3: "CH"}
LANG_MAP   = {"DE": "de_DE", "EN": "en_US", "FR": "fr_FR"}
ZAHLBED_MAP = {1: "Sofort", 3: "14 Tage netto", 5: "30 Tage netto"}
ZAHLBED_ODOO = {
    1: "Sofortige Zahlung",
    3: "14 Tage",
    5: "30 Tage",
}

# ---------------------------------------------------------------------------
# Mapping-Logik: eEvolution → Odoo 19 res.partner
# ---------------------------------------------------------------------------

FIELD_MAPPING = [
    # (eevo_quelle,           odoo_feld,                   transform_hinweis)
    ("Adressen.Name1",         "name",                      "Direkt – Firmenname"),
    ("Adressen.Name2",         "name (Zusatz)",             "Anhängen an name falls vorhanden"),
    ("Adressen.AdressenNr",    "ref",                       "Kundennummer als interne Referenz"),
    ("Adressen.Strasse",       "street",                    "Straße + Hausnummer kombiniert"),
    ("Adressen.PLZ",           "zip",                       "Direkt"),
    ("Adressen.Ort",           "city",                      "Direkt"),
    ("Adressen.LandID",        "country_id",                "Lookup LAND_MAP → res.country"),
    ("Adressen.Telefon",       "phone",                     "Direkt"),
    ("Adressen.Telefon2",      "mobile",                    "Zweites Telefon als Mobile"),
    ("Adressen.Email",         "email",                     "Direkt"),
    ("Adressen.Internet",      "website",                   "Direkt"),
    ("Adressen.UStIdNr",       "vat",                       "Direkt – EU-Format prüfen"),
    ("Adressen.Bemerkung",     "comment",                   "Als HTML-Notiz übernehmen"),
    ("Adressen.Gesperrt",      "active",                    "Invertieren: 0→True, 1→False"),
    ("Kunden.ZahlungsbedingungID", "property_payment_term_id", "FK → account.payment.term"),
    ("Kunden.Kreditlimit",     "credit_limit",              "Direkt decimal"),
    ("Kunden.Sprache",         "lang",                      "Mapping: DE→de_DE, EN→en_US"),
    ("—",                      "customer_rank",             "Fest: 1 (ist Kunde)"),
    ("—",                      "is_company",                "Fest: True (Firmendatensatz)"),
    ("—",                      "company_type",              "Fest: 'company'"),
]

CONTACT_MAPPING = [
    # Ansprechpartner → res.partner (type='contact', parent_id=Firma)
    ("AnsprechpartnerID",   "—",            "Nicht übertragen (interner PK)"),
    ("Anrede",              "title",        "Lookup: Herr→res.partner.title(Herr), Frau→Frau"),
    ("Vorname + Nachname",  "name",         "Verketten: Vorname + ' ' + Nachname"),
    ("Position",            "function",     "Direkt"),
    ("Telefon",             "phone",        "Direkt"),
    ("Mobil",               "mobile",       "Direkt"),
    ("Email",               "email",        "Direkt"),
    ("—",                   "type",         "Fest: 'contact'"),
    ("—",                   "parent_id",    "Ref auf die Firma (res.partner.id)"),
]


def transform(record: dict) -> dict:
    """Wendet das Mapping auf einen eEvolution-Datensatz an."""
    a = record["adressen"]
    k = record["kunden"]

    name = a["Name1"]
    if a.get("Name2"):
        name = f"{name} – {a['Name2']}"

    land_code = LAND_MAP.get(a.get("LandID"), "DE")
    lang_code  = LANG_MAP.get(k.get("Sprache", "DE"), "de_DE")

    return {
        # res.partner Felder
        "name":                     name,
        "ref":                      a["AdressenNr"],
        "is_company":               True,
        "company_type":             "company",
        "customer_rank":            1,
        "street":                   a.get("Strasse"),
        "zip":                      a.get("PLZ"),
        "city":                     a.get("Ort"),
        "country_id/id":            f"base.{land_code}",
        "phone":                    a.get("Telefon"),
        "mobile":                   a.get("Telefon2"),
        "email":                    a.get("Email"),
        "website":                  a.get("Internet"),
        "vat":                      a.get("UStIdNr"),
        "comment":                  a.get("Bemerkung"),
        "active":                   not bool(a.get("Gesperrt", 0)),
        "lang":                     lang_code,
        "credit_limit":             k.get("Kreditlimit", 0),
        # payment term als XML-ID Referenz (muss in Odoo existieren)
        "property_payment_term_id": ZAHLBED_ODOO.get(k.get("ZahlungsbedingungID")),
        # Quelldaten für Protokoll
        "_source_AdressenID":       a["AdressenID"],
        "_source_KundenNr":         k.get("KundenNr"),
    }


def transform_contact(contact: dict, parent_ref: str) -> dict:
    vorname  = contact.get("Vorname", "") or ""
    nachname = contact.get("Nachname", "") or ""
    name = f"{vorname} {nachname}".strip()

    anrede = contact.get("Anrede", "")
    title_map = {"Herr": "Herr", "Frau": "Frau", "Dr.": "Dr.", "Prof.": "Prof."}

    return {
        "name":       name,
        "type":       "contact",
        "parent_id":  f"[ref={parent_ref}]",
        "title":      title_map.get(anrede, ""),
        "function":   contact.get("Position"),
        "phone":      contact.get("Telefon"),
        "mobile":     contact.get("Mobil"),
        "email":      contact.get("Email"),
        "is_company": False,
    }


# ---------------------------------------------------------------------------
# Ausgabe-Funktionen
# ---------------------------------------------------------------------------

def print_schema():
    print("\n" + "="*70)
    print("  eEvolution Tabellenstruktur (MSSQL-Simulation)")
    print("="*70)
    for table, info in EEVO_SCHEMA.items():
        print(f"\n┌─ {table} ─ {info['description']}")
        print(f"│  {'Spalte':<30} {'Typ':<18} {'Null':<6} Beschreibung")
        print(f"│  {'─'*30} {'─'*18} {'─'*6} {'─'*30}")
        for col in info["columns"]:
            name, dtype, nullable, desc = col
            null_str = "NULL" if nullable else "NOT NULL"
            print(f"│  {name:<30} {dtype:<18} {null_str:<6} {desc}")
    print()


def print_mapping_table():
    print("\n" + "="*70)
    print("  Mapping: eEvolution → Odoo 19 (res.partner)")
    print("="*70)
    print(f"\n  {'eEvolution Quelle':<35} {'Odoo 19 Feld':<30} {'Transformation'}")
    print(f"  {'─'*35} {'─'*30} {'─'*35}")
    for src, dst, note in FIELD_MAPPING:
        print(f"  {src:<35} {dst:<30} {note}")

    print(f"\n  Ansprechpartner → res.partner (type='contact')")
    print(f"  {'─'*35} {'─'*30} {'─'*35}")
    for src, dst, note in CONTACT_MAPPING:
        print(f"  {src:<35} {dst:<30} {note}")
    print()


def print_transformed_records():
    print("\n" + "="*70)
    print("  Transformierte Datensätze (Vorschau Odoo-Import)")
    print("="*70)
    for i, rec in enumerate(SAMPLE_DATA):
        result = transform(rec)
        print(f"\n  Datensatz {i+1}: {result['name']}")
        print(f"  {'─'*60}")
        for k, v in result.items():
            if not k.startswith("_"):
                status = ""
                if v is None:
                    status = "  ← LEER (kein Wert in eEvolution)"
                elif v is False:
                    status = "  ← active=False (gesperrt)"
                print(f"    {k:<40} {str(v):<25}{status}")

        # Ansprechpartner
        for ap in rec.get("ansprechpartner", []):
            ct = transform_contact(ap, result["ref"])
            print(f"\n    → Ansprechpartner: {ct['name']}")
            for k, v in ct.items():
                if v:
                    print(f"      {k:<38} {v}")
    print()


def export_csv():
    print("\n" + "="*70)
    print("  CSV-Export (Odoo-kompatibles Format für res.partner Import)")
    print("="*70)

    rows = []
    for rec in SAMPLE_DATA:
        r = transform(rec)
        rows.append({k: v for k, v in r.items() if not k.startswith("_")})
        for ap in rec.get("ansprechpartner", []):
            ct = transform_contact(ap, r["ref"])
            rows.append(ct)

    if rows:
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=rows[0].keys(), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        print(out.getvalue())


def print_issues():
    print("\n" + "="*70)
    print("  Bekannte Probleme / offene Klärungspunkte")
    print("="*70)
    issues = [
        ("KRITISCH",  "Feldnamen in Adressen/Kunden sind simuliert – "
                      "müssen gegen eure echte DB validiert werden"),
        ("KRITISCH",  "Zahlungsbedingungen: IDs müssen mit eurer DB abgeglichen werden "
                      "(ZahlungsbedingungID 3 = '14 Tage'?)"),
        ("MITTEL",    "Steuerklasse (Umsatzsteuerklasse) → kein direktes Odoo-Feld, "
                      "ggf. fiscal.position"),
        ("MITTEL",    "Preisgruppe / Rabattgruppe → Odoo Preisliste (product.pricelist), "
                      "muss vorher angelegt werden"),
        ("MITTEL",    "Vertreter (Vertreter1ID) → Odoo Außendienst (CRM user_id), "
                      "FK-Auflösung nötig"),
        ("NIEDRIG",   "Name2 als Adresszusatz vs. Unterabteilung – Konvention festlegen"),
        ("NIEDRIG",   "Fax-Feld existiert in Odoo 19 nicht mehr standardmäßig"),
        ("INFO",      "DebitKontoNr → nur relevant wenn Buchhaltungskonten migriert werden"),
    ]
    for prio, text in issues:
        marker = {"KRITISCH": "🔴", "MITTEL": "🟡", "NIEDRIG": "🔵", "INFO": "⚪"}.get(prio, " ")
        print(f"\n  {marker} [{prio}]")
        print(f"     {text}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="eEvolution → Odoo 19 Kunden-Mapping Simulation"
    )
    parser.add_argument("--export", action="store_true",
                        help="CSV-Preview für Odoo-Import ausgeben")
    parser.add_argument("--schema-only", action="store_true",
                        help="Nur Tabellenstruktur anzeigen")
    args = parser.parse_args()

    if args.schema_only:
        print_schema()
    elif args.export:
        print_schema()
        print_mapping_table()
        export_csv()
        print_issues()
    else:
        print_schema()
        print_mapping_table()
        print_transformed_records()
        print_issues()
