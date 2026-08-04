# Handover: Bitfarm-Importprogramm → Codex

**Projekt:** Datenmigration eEvolution (MSSQL) → Odoo 19 Enterprise  
**Auftraggeber:** Kling & Freitag GmbH (K&F), Hannover – Hersteller professioneller Beschallungssysteme  
**Branch:** `claude/eevolution-mapping-validation-iemk0y`  
**Stand:** 2026-08-04  

---

## 1. Projektkontext

K&F migriert ihr ERP von eEvolution (MS SQL Server, Eigenentwicklung der Firma Bitfarm) auf Odoo 19 Enterprise. Die Testmigration auf dem Server `kuf-erp-test` ist abgeschlossen (21 Migrationsschritte ✅). Produktiv-Cutover steht noch aus.

**Systemübersicht:**

| System | Details |
|---|---|
| Quelle | eEvolution, MS SQL Server 192.168.120.234, DB: `KuF` |
| Quelle User | `excel_kuf_readonly` / `readonly` (nur lesen, niemals in Code eintragen) |
| Ziel Test | Odoo 19 Enterprise auf `kuf-erp-test` (interner Host) |
| Ziel Prod | erp-intern.kling-freitag.de (nginx + Let's Encrypt) |
| Authentifizierung | XML-RPC mit API-Key (niemals admin-Passwort in Skripten) |
| Kontenrahmen | SKR03 |

---

## 2. Repository-Struktur

```
Bitfarm-importprogramm/
├── README.md
├── HANDOVER_CODEX.md            ← diese Datei
├── profil_eevolution.py         ← lokal ausführen (Windows mit pymssql)
│                                   Verbindet zu 192.168.120.234, schreibt eevo_profil.txt
├── simulate_kunden_mapping.py   ← Simulation eEvolution Kunden → Odoo res.partner
│                                   CLI: --export (CSV), --schema-only
├── mappings/
│   └── 01_kunden.yaml           ← Mapping-Definition ADRESS+KUNDE → res.partner
│                                   Status: SIMULIERT, alle Felder validated: false
└── docs/
    └── pia_prozess.html         ← Odoo 19 Prozessdurchlauf K&F PIA M (vollständig)
                                    Live-Artifact: https://claude.ai/code/artifact/d6fea6a3-d56f-45ac-9bbd-5f92fac7f530
```

Das vollständige Migrationsprojekt (99_scripts/, 05_doku/, etc.) liegt **lokal beim Kunden** und wurde hier aus einem ZIP-Upload ausgewertet — es ist **nicht** in diesem Repo eingecheckt.

---

## 3. Echte eEvolution-Tabellennamen (validiert aus SSMS-Screenshot)

> KRITISCH: Die Tabellennamen in den YAML-Mappings und der Simulation sind noch SIMULIERT.  
> Die echten Namen kommen aus dem SSMS-Screenshot, den der Nutzer gezeigt hat.

| Odoo-Ziel | eEvolution-Tabelle | Alias | Hinweis |
|---|---|---|---|
| res.partner (Firmen) | `ADRESS` | a | Zentrale Adresstabelle |
| res.partner (Kunden-Ext.) | `KUNDE` | k | JOIN auf ADRESS.ADRNR |
| res.partner (Lieferanten) | `LIEFERANT` | l | JOIN auf ADRESS.ADRNR |
| res.partner (Ansprechpartner) | `ADRANSPRECH` | ap | JOIN auf ADRESS.ADRNR |
| product.template | `ARTIKEL` | ar | + ARTIKELLONG für Beschreibung |
| sale.order / account.move | `ANGAUFGUT` | ag | Demultiplex: Angebot/Auftrag/Gutschrift |
| purchase.order | `BESTELLUNG` | b | |
| res.country | `LAND` | | ISO2-Code Lookup |
| account.payment.term | `ZAHLBEDING` | | |
| product.pricelist | `PREISLISTEN` / `PREISLISTKOPF` | | |
| res.users (Vertreter) | `VERTRETER` | | |
| stock.lot / stock.serial | `CHARGEN` / `SERNR` | | |
| mrp.bom (einfach) | `ARTSTUELI` | | Legacy-BOMs |
| mrp.bom (Produktion) | `PRODLIST` + `PRODINHALT` | | 1.461 BOMs, bis 5 Ebenen |
| account.move (Eingangsrechn.) | `LIEFRECH` | | Eingangsrechnungen |

**Schlüsselfeld:** `ADRESS.ADRNR` ist der zentrale Primärschlüssel.  
External ID Schema: `ev_adr_<ADRNR>`, `ev_product_<LFDNR>`, etc.

---

## 4. Vollständige Migrationsskripte (lokal beim Kunden, 99_scripts/)

| Script | Funktion | Status |
|---|---|---|
| `01_profile_source.py` | DB-Profiling eEvolution | ✅ |
| `01b_export_data.py` | CSV-Export aus eEvolution | ✅ |
| `02_load_partners.py` | ADRESS → res.partner (ADRNR-zentrisch) | ✅ |
| `03_load_to_odoo.py` | ARTIKEL → product.template | ✅ |
| `04_load_config.py` | Zahlungsbedingungen, UoM, Steuern (inkl. 16% COVID) | ✅ |
| `05_load_documents.py` | ANGAUFGUT → sale.order / account.move (Demultiplex) | ✅ |
| `06_load_purchase.py` | BESTELLUNG → purchase.order | ✅ |
| `07_load_locations.py` | Lagerorte | ✅ |
| `08_load_crm.py` | CRM-Leads | ✅ |
| `09_load_stock.py` | Lagerbestände (stock.quant) | ✅ |
| `10_load_kundengruppen.py` | Kundengruppen-Tags | ✅ |
| `11_load_pricelists.py` | Preislisten aus RABATTMATRIX | ✅ |
| `12_close_old_documents.py` | Historische Aufträge sperren | ✅ |
| `13_apply_customizing.py` | Odoo-Einstellungen aktivieren | ✅ |
| `14_load_contacts.py` | Ansprechpartner (ADRANSPRECH) | ✅ |
| `15_load_supplierinfo.py` | Lieferantenpreise (product.supplierinfo) | ✅ |
| `16_load_boms.py` | Legacy-BOMs aus ARTSTUELI (11 Stück) | ✅ |
| `17_load_boms_prodlist.py` | Produktions-BOMs aus PRODLIST+PRODINHALT (1.461) | ✅ |
| `18_delete_pre2016.py` | Pre-2016-Datensätze löschen | ✅ |
| `19_load_invoices.py` | Rechnungen (AAGFAKT ab 2016, RECHEINGANG) | ✅ |
| `20_delete_pickings.py` | Auto-erzeugte stock.pickings bereinigen | ✅ |
| `21_load_delivery_addresses.py` | KNDLIEFER → res.partner type=delivery | ✅ |
| `22_load_serial_lots.py` | 15.250 Seriennummern + 5.993 Chargen | ✅ |
| `23_load_open_items.py` | Offene Posten Debitoren | ⚠️ AUSSTEHEND |
| `24_load_vat.py` | USt-IdNr für Lieferanten | ✅ |
| `25_setup_users.py` | Benutzer-Setup | ✅ |
| `26_fix_create_dates.py` | Erstelldaten korrigieren | ✅ |
| `27_load_serial_traceability.py` | Seriennummer-Rückverfolgung | ✅ |
| `28_close_historical_invoices.py` | Historische Rechnungen schließen | ✅ |
| `run_all.py` | Orchestrator mit `--from N` Resume | ✅ |

---

## 5. Odoo 19 Pitfalls (dokumentiert, Stand Juni 2026)

Diese Fallen wurden beim Testlauf entdeckt. **Vor jedem neuen Skript prüfen:**

1. **Kein `mobile` Feld** auf res.partner in Odoo 19 → in `comment` ablegen oder ignorieren
2. **`vat` strenge Validierung** → Format prüfen (DE + 9 Ziffern); ungültige mit `try/except` überspringen
3. **`locked=True`** statt `state='done'` für gesperrte Fertigungsaufträge
4. **`specific_property_product_pricelist`** statt `property_product_pricelist` für partner-spezifische Preislisten
5. **Kein `ir.property`** in Odoo 19 → company-spezifische Properties über `res.config.settings` setzen
6. **`customer_rank` / `supplier_rank`** statt Boolean-Felder `customer` / `supplier`
7. **`account.move` type** muss explizit gesetzt sein: `out_invoice`, `in_invoice`, `out_refund` etc.
8. **Keine direkte `state`-Zuweisung** auf sale.order; über `action_confirm()` bestätigen
9. **stock.picking Validierung** über `button_validate()` nicht direkt über `state`
10. **BOM-Ebenen** in PRODLIST+PRODINHALT bis 5 tief → rekursive Verarbeitung nötig (bottom-up)
11. **16% Steuer** (COVID-Periode 2020-H2) muss als extra Steuersatz angelegt sein
12. **Retry-Pattern** für XML-RPC nötig: Odoo-Worker werden nach ~200 Requests recycelt
13. **`product.supplierinfo` min_qty** Pflichtfeld (0 wenn nicht gesetzt, nicht None)
14. **`account.payment.term` lines** Pflichtfeld – mindestens eine Zeile mit `value='balance'`
15. **Externe IDs** (`ir.model.data`) für Idempotenz: `ev_adr_<ADRNR>` Schema konsequent verwenden
16. **`res.partner` `type`** für Lieferadressen: `'delivery'` (nicht `'shipping'`)
17. **ANGAUFGUT Demultiplex**: Spalte `BELEGTYP` unterscheidet Angebot (1), Auftrag (2), Gutschrift (3)
18. **Preislisten**: `product.pricelist` braucht mindestens eine `item` mit `compute_price='fixed'`
19. **Lohnfertigung** (`mrp_subcontracting`): BOM-Typ `'subcontract'`, Subcontractor als `subcontractor_ids` Many2many
20. **`stock.quant` direkt schreiben** funktioniert in Odoo 19 nur über `_update_available_quantity()` oder Inventuranpassung

---

## 6. Pendende Aufgaben (Offene Punkte vor Produktiv-Go-Live)

### Kritisch
- [ ] **23_load_open_items.py**: FiBu-Workshop-Ergebnis abwarten. Strategie: Pre-2024-Rechnungen als bezahlt markieren, ab 2024 echte OP-Daten (3.603 Posten, ~29,7 Mio € – Validierung nötig, Zahl erscheint zu hoch)
- [ ] **Sonderfarben RAL** (GF-Entscheidung ausstehend): Varianten vs. Einzelartikel auf product.template
- [ ] **Subcontracting-BOMs** noch nicht vollständig validiert/geladen (Cobertec, Systemtechnik)
- [ ] **Let's Encrypt Zertifikat** läuft ca. 8. September 2026 ab → sofort prüfen und Renewal testen

### Mittel
- [ ] **2-Monats-Datenlücke**: Vollständiger Re-Run der Migration nötig vor Cutover (Daten veraltet seit Juni 2026)
- [ ] **Fiskalposition EU**: Innergemeinschaftliche Lieferungen (Sica IT) korrekt konfigurieren
- [ ] **ZUGFeRD / E-Rechnung**: Ab 2025 Pflicht für B2B – Odoo 19 Modul prüfen
- [ ] **Benutzerkonten**: finale Passwörter, 2FA, Zugriffsrechte für alle K&F-Mitarbeiter

### Nice-to-have
- [ ] YAML-Mappings validieren (alle `validated: false` auf `true` setzen nach DB-Profiling)
- [ ] Mapping für Lieferanten (02_lieferanten.yaml), Artikel (03_artikel.yaml) erstellen

---

## 7. Infrastruktur

```
Internet → LANCOM-Router → nginx (HTTPS) → Odoo 19 (Port 8069, intern)
                                         → PostgreSQL (lokal)

nginx: /etc/nginx/sites-available/odoo
SSL:   /etc/letsencrypt/live/erp-intern.kling-freitag.de/
Odoo:  /etc/odoo/odoo.conf
       list_db = False        ← MUSS gesetzt sein
       dbfilter = ^KuF$
       admin_passwd = <sicher, nicht hier>
```

---

## 8. Produkt-Beispiel: K&F PIA M

Wandlautsprecher (Fertigprodukt). Vollständiger Prozessdurchlauf dokumentiert in:
- `docs/pia_prozess.html` (im Repo)
- Live-Artifact: https://claude.ai/code/artifact/d6fea6a3-d56f-45ac-9bbd-5f92fac7f530

**Stückliste PIA M:**

| Komponente | Lieferant | EK-Preis |
|---|---|---|
| Sica 4" Chassis C08N.16.08 | Sica Altoparlanti S.r.l. (IT) | 28,50 € |
| Karton PIA M | deupack GmbH | 3,20 € |
| Kippschalter 250V/6A | Digi-Key Electronics (US) | 1,85 € |
| Anschlusskabel 0,5m 2×0,75 | MTI GmbH | 2,10 € |
| Gehäuse PIA M – Rohteil | Blech-Lieferant | 42,00 € |
| **Lohnfertigung Pulverbeschichtung** | **Cobertec GmbH** | **18,00 €** |

**Lohnfertigung Cobertec:** Pulverbeschichtung der Metallteile (Gitter, Deckplatten, Wandwinkel, BR-Platte, Terminalwand). Beistellteil = Rohteil-Gehäuse. BOM-Typ in Odoo: `subcontract`.

---

## 9. Codex-Aufgaben (mögliche nächste Schritte)

Wenn du (Codex) die Arbeit fortsetzt, sind dies die sinnvollsten Aufgaben:

### A. YAML-Mappings vervollständigen
```
mappings/
  01_kunden.yaml       ← vorhanden, validated: false
  02_lieferanten.yaml  ← fehlt
  03_artikel.yaml      ← fehlt
  04_ansprechpartner.yaml ← fehlt
```
Schema: wie 01_kunden.yaml. Echte Tabellennamen siehe Abschnitt 3.

### B. Migrations-Skripte für dieses Repo erstellen
Die 28 Skripte liegen lokal beim Kunden. Sauberere Variante für dieses Repo:
- `import_partners.py` – basiert auf 02_load_partners.py, aber mit `.env`-Konfiguration
- Vorlage aus `profil_eevolution.py` übernehmen (pymssql-Verbindung)
- Ziel-Verbindung: XML-RPC gegen Odoo (xmlrpc.client), API-Key aus `.env`

### C. Validierungsskript schreiben
Nach jeder Migrationsrunde prüfen:
- Alle ADRNR in Odoo vorhanden?
- Keine doppelten External IDs?
- Stücklisten vollständig (BOM-Komponenten alle vorhanden)?

### D. run_all.py für dieses Repo
Orchestrator mit `--from N --dry-run` Flag.

---

## 10. Sicherheitsregeln (unbedingt einhalten)

- Credentials **nie** in Code oder Dokumentation — ausschließlich `.env` (gitignored)
- DB-Zugriff nur gegen Kopie/Test, **nie gegen Produktiv**
- Odoo-Ports 8069/8072 **nie** direkt öffentlich exponieren
- `list_db = False` in `odoo.conf` vor Go-Live
- XML-RPC immer mit API-Key, nicht mit admin-Passwort
- Vor destruktiven Operationen (DELETE, Archivieren): Backup bestätigen lassen

---

## 11. Kontakt / Kontext

- Auftraggeber: Kling & Freitag GmbH, Hannover
- Hauptansprechpartner: Geschäftsführung (GF)
- Migrationszeitraum: seit Anfang 2026, Cutover geplant Q3/Q4 2026
- Dieses Repo ist der Arbeitsbereich der KI-gestützten Mapping- und Dokumentationsarbeit
