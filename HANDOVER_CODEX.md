# Handover: Bitfarm-Importprogramm → Codex / KI-Prüfung

**Projekt:** Datenmigration eEvolution (MS SQL Server) → Odoo 19 Enterprise  
**Auftraggeber:** Kling & Freitag GmbH (K&F), Hannover – Hersteller professioneller Beschallungssysteme  
**Branch:** `claude/eevolution-mapping-validation-iemk0y`  
**Stand:** 2026-08-06

---

## 1. Projektkontext

K&F migriert ihr ERP von eEvolution (MS SQL Server, Eigenentwicklung Bitfarm AG) auf Odoo 19 Enterprise.
Testmigration auf `erp-test-1` läuft. Produktiv-Cutover Q3/Q4 2026.

| System | Details |
|---|---|
| Quelle | eEvolution, MS SQL 192.168.120.234, DB: `KuF` |
| Quelle User | `excel_kuf_readonly` / `readonly` – **niemals** in Code eintragen |
| Ziel Test | Odoo 19 Enterprise 192.168.120.225:8069, DB: `erp-test-1` |
| Ziel Prod | erp-intern.kling-freitag.de (nginx + Let's Encrypt) |
| Authentifizierung | XML-RPC mit API-Key (`ODOO_API_KEY` aus `.env`) |
| Kontenrahmen | SKR03 |

---

## 2. Repository-Struktur

```
Bitfarm-importprogramm/
├── README.md
├── HANDOVER_CODEX.md              ← diese Datei
├── AGENTS.md                      ← OpenAI Codex Einstieg
├── setup_env.cmd                  ← erstellt .env interaktiv (Windows CMD)
├── .gitignore                     ← .env, *.xlsx, odoo_schema.json sind ignoriert
│
├── 99_scripts/
│   ├── build_schema_cache.py      ← [1] eEvolution-Schema → eevo_schema.json (lokal ausführen)
│   ├── eevo_schema.py             ← Wiederverwendbares Modul: Spaltennamen, FKs, KNOWN-Dict
│   ├── validate_eevo_schema.py    ← [2] KI-Logikprüfung ohne DB-Zugriff → validate_report.json
│   ├── build_odoo_schema.py       ← [3] Odoo 19 Schema via XML-RPC → odoo_schema.json
│   ├── mapping_report.py          ← [4] Mapping eEvolution→Odoo → Excel
│   │
│   ├── export_pia_pruefung.py     ← Stückliste/Artikel-Export (PIA-Produkte) → Excel
│   ├── export_angebote_pruefung.py ← Kunden-Angebote nach Wert filtern → Excel
│   ├── export_anfrage_pruefung.py  ← Lieferantenanfragen-Export → Excel
│   └── suche_pia_anfrage.py       ← CRM-Suche (veraltet, nur Referenz)
│
├── mappings/
│   └── 01_kunden.yaml             ← ADRESS+KUNDE → res.partner (validated: false)
│
└── docs/
    └── pia_prozess.html           ← K&F PIA M Prozessdurchlauf Odoo 19
```

---

## 3. Workflow: Schema-Aufbau und Validierung

Die vier Skripte in `99_scripts/` bauen aufeinander auf:

```
[1] build_schema_cache.py   → eevo_schema.json   (lokal, braucht ODBC + DB-Zugang)
[2] validate_eevo_schema.py → validate_report.json (read-only, kein DB nötig)
[3] build_odoo_schema.py    → odoo_schema.json   (braucht .env mit Odoo-Credentials)
[4] mapping_report.py       → mapping_report_DATUM.xlsx
```

### Ausführung (Windows CMD aus Projektordner):
```cmd
python 99_scripts\validate_eevo_schema.py
python 99_scripts\build_odoo_schema.py
python 99_scripts\mapping_report.py
```

### .env Datei (Projektordner, nicht committen):
```
ODOO_URL=http://192.168.120.225:8069
ODOO_DB=erp-test-1
ODOO_USER=admin
ODOO_API_KEY=<api-key aus Odoo>
```
Setup-Hilfe: `setup_env.cmd` ausführen.

---

## 4. Validierungsergebnisse (Stand 2026-08-05)

Validierung mit `validate_eevo_schema.py` gegen `eevo_schema.json` (1504 Tabellen, 27715 Spalten, 2345 Beziehungen):

| Prüfung | Ergebnis | Bewertung |
|---|---|---|
| FK-Konsistenz | 2325 OK, **0 Fehler**, 20 Warnungen | ✅ Warnungen = Namens-Varianten (LFD_NR statt LFDNR) |
| PKs erkannt | 7 Tabellen ohne PK | ✅ Alle sind Backup-/Temp-Tabellen |
| Pflichtfelder | Alle vorhanden | ✅ |
| Migrations-Tabellen | 22/23 gefunden | ⚠️ nur SERNR fehlt (wahrsch. in CHARGEN integriert) |
| Offene LFD\*-FKs | 491 | ℹ️ Großteils AAG\*-Bereich, nicht migration-kritisch |
| Archiv-Paare | 24 | ℹ️ KOPF+POS-Paare, erwartet |

---

## 5. Echte eEvolution-Tabellennamen und -Spalten

### 5.1 Primärschlüssel-Muster

| Tabelle | PK-Spalte | Besonderheit |
|---|---|---|
| ADRESS | `ADRNR` | Zentrale Adress-ID, kein LFDNR |
| LIEFERANT | `ADRNR` | FK auf ADRESS |
| ARTIKEL | `LFDNR` | Numerisch |
| ARTIKELLONG | – | FK: `LFDARTNR` → ARTIKEL.LFDNR |
| ANGAUFGUT | `LFDNR` | Angebot+Auftrag+Gutschrift kombiniert |
| ANGAUFPOS | – | FK: `LFDANGAUFGUTNR` → ANGAUFGUT.LFDNR |
| PRODLIST | `LFD_NR` | Mit Unterstrich! |
| PRODINHALT | – | FK: `LIST_NR` → PRODLIST.LFD_NR |
| ANFRAGE | `LFDANFRAGE` | Lieferantenanfragen (nicht Kunden-CRM!) |

### 5.2 KNOWN-Feldverzeichnis (aus `eevo_schema.py`)

```python
# ARTIKEL
ARTIKEL.PK          → LFDNR
ARTIKEL.ARTNR       → ARTNR1
ARTIKEL.BEZ         → ABEZ1
ARTIKEL.BEZ2        → ABEZ2
ARTIKEL.EINHEIT     → MENGENSCHL   # direktes Code-Feld
ARTIKEL.VK          → VKPR1
ARTIKEL.EK          → EKPR
ARTIKEL.LIEFNR_DEF  → LFDLIEFNR   # FK → LIEFERANT

# ARTIKELLONG
ARTIKELLONG.FK      → LFDARTNR    # → ARTIKEL.LFDNR
ARTIKELLONG.TEXT    → CONTENT

# ANGAUFGUT
ANGAUFGUT.PK        → LFDNR
ANGAUFGUT.FLAG_ANG  → ANGEBOT      # =1 wenn Angebot
ANGAUFGUT.FLAG_AUF  → AUFTRAG      # =1 wenn Auftrag
ANGAUFGUT.FLAG_GUT  → GUTSCHRIFT   # =1 wenn Gutschrift
ANGAUFGUT.KND       → KNDNR
ANGAUFGUT.DATUM     → ERFASSDATUM

# ANGAUFPOS
ANGAUFPOS.FK        → LFDANGAUFGUTNR   # → ANGAUFGUT.LFDNR
ANGAUFPOS.ART_FK    → LFDARTNR          # → ARTIKEL.LFDNR (numerisch, kein String!)
ANGAUFPOS.MENGE     → BESTMENGE
ANGAUFPOS.PREIS     → PREIS
ANGAUFPOS.POS       → POSNR
ANGAUFPOS.TEXT      → LANGTEXT

# PRODLIST / PRODINHALT
PRODLIST.PK         → LFD_NR
PRODLIST.ART_FK     → ART_NR
PRODINHALT.FK       → LIST_NR
PRODINHALT.ART_FK   → ART_NR

# ADRESS (nur Flags!)
ADRESS.PK           → ADRNR
ADRESS.KUND_FLAG    → KUNDE         # =1 wenn Kunde
ADRESS.LIEF_FLAG    → LIEFERANT     # =1 wenn Lieferant

# LIEFERANT
LIEFERANT.PK        → ADRNR
LIEFERANT.NAME      → NAME1
LIEFERANT.ORT       → ORT
LIEFERANT.EMAIL     → EMAIL

# MENGENSCHL
MENGENSCHL.CODE     → BEZ           # Kürzel (Stk, m, kg …)
MENGENSCHL.NAME     → LBEZ
```

### 5.3 Wichtige JOIN-Muster

```sql
-- Artikel mit Langtext
SELECT a.LFDNR, a.ARTNR1, a.ABEZ1, al.CONTENT
FROM ARTIKEL a
LEFT JOIN ARTIKELLONG al ON al.LFDARTNR = a.LFDNR

-- Angebote mit Positionen + Artikeldaten (LFDARTNR ist numerischer FK!)
SELECT ag.LFDNR, p.POSNR, ar.ARTNR1, ar.ABEZ1, p.BESTMENGE, p.PREIS
FROM ANGAUFGUT ag
JOIN ANGAUFPOS p ON p.LFDANGAUFGUTNR = ag.LFDNR
LEFT JOIN ARTIKEL ar ON ar.LFDNR = p.LFDARTNR
WHERE ag.ANGEBOT = 1

-- Stücklisten
SELECT p.LFD_NR, a_end.ARTNR1, a_komp.ARTNR1, i.MENGE
FROM PRODLIST p
JOIN ARTIKEL a_end ON a_end.LFDNR = p.ART_NR
JOIN PRODINHALT i ON i.LIST_NR = p.LFD_NR
JOIN ARTIKEL a_komp ON a_komp.LFDNR = i.ART_NR
```

---

## 6. Mapping eEvolution → Odoo 19

| eEvolution-Quellen | Odoo-Ziel | Hinweis |
|---|---|---|
| ADRESS + KUNDE | res.partner | customer_rank=1 |
| ADRESS + LIEFERANT | res.partner | supplier_rank=1 |
| ADRANSPRECH | res.partner | type='contact' |
| KNDLIEFER | res.partner | type='delivery' |
| ARTIKEL + ARTIKELLONG | product.template | CONTENT → description |
| PRODLIST + PRODINHALT | mrp.bom + mrp.bom.line | bis 5 Ebenen, bottom-up |
| ARTSTUELI | mrp.bom + mrp.bom.line | Legacy (11 Stück) |
| ANGAUFGUT (ANGEBOT=1) + ANGAUFPOS | sale.order (draft) | |
| ANGAUFGUT (AUFTRAG=1) + ANGAUFPOS | sale.order (confirmed) | action_confirm() |
| ANGAUFGUT (GUTSCHRIFT=1) | account.move (out_refund) | |
| BESTELLUNG | purchase.order | |
| LIEFRECH | account.move (in_invoice) | |
| ZAHLBEDING | account.payment.term | min. 1 Line mit value='balance' |
| MENGENSCHL | uom.uom | BEZ = Kürzel |
| LAND | res.country | ISO2-Lookup |
| CHARGEN | stock.lot | tracking='lot' |
| SERNR | stock.lot | tracking='serial' – Tabelle ggf. nicht vorhanden |
| PREISLISTEN / PREISLISTKOPF | product.pricelist | |
| VERTRETER | res.users | |

---

## 7. Odoo 19 Pitfalls (dokumentiert)

1. **Kein `mobile` Feld** auf res.partner → in `comment` ablegen
2. **`vat` strenge Validierung** → DE + 9 Ziffern; ungültige überspringen
3. **`locked=True`** statt `state='done'` für gesperrte Fertigungsaufträge
4. **`specific_property_product_pricelist`** statt `property_product_pricelist`
5. **Kein `ir.property`** in Odoo 19 → über `res.config.settings`
6. **`customer_rank` / `supplier_rank`** statt Boolean `customer` / `supplier`
7. **`account.move` type** explizit: `out_invoice`, `in_invoice`, `out_refund`
8. **Keine direkte `state`-Zuweisung** auf sale.order → `action_confirm()`
9. **stock.picking** → `button_validate()`, nicht direkt state
10. **BOM-Ebenen** bis 5 tief → rekursive Verarbeitung bottom-up
11. **16% Steuer** (COVID 2020-H2) als extra Steuersatz
12. **Retry-Pattern** für XML-RPC: Odoo-Worker recyceln nach ~200 Requests
13. **`product.supplierinfo` min_qty** Pflichtfeld (0, nicht None)
14. **`account.payment.term` lines** Pflichtfeld
15. **Externe IDs** für Idempotenz: `ev_kuf_adr_<ADRNR>`, `ev_kuf_art_<LFDNR>`
16. **`res.partner` `type`** für Lieferadressen: `'delivery'` (nicht `'shipping'`)
17. **ANGAUFGUT Demultiplex**: **KEIN** `BELEGTYP`-Feld! Stattdessen Boolean-Flags:
    `ANGEBOT=1` → Angebot, `AUFTRAG=1` → Auftrag, `GUTSCHRIFT=1` → Gutschrift
18. **Preislisten**: min. eine `item` mit `compute_price='fixed'`
19. **Lohnfertigung**: BOM-Typ `'subcontract'`, `subcontractor_ids` Many2many
20. **`stock.quant`** nur über `_update_available_quantity()` oder Inventuranpassung

---

## 8. Vollständige Migrationsskripte (lokal beim Kunden, 99_scripts/)

| Schritt | Script | Funktion | Status |
|---|---|---|---|
| 01 | 01_profile_source.py | DB-Profiling eEvolution | ✅ |
| 02 | 02_load_partners.py | ADRESS → res.partner | ✅ |
| 03 | 03_load_to_odoo.py | ARTIKEL → product.template | ✅ |
| 04 | 04_load_config.py | Zahlbeding, UoM, Steuern | ✅ |
| 05 | 05_load_documents.py | ANGAUFGUT → sale.order / account.move | ✅ |
| 06 | 06_load_purchase.py | BESTELLUNG → purchase.order | ✅ |
| 07 | 07_load_locations.py | Lagerorte | ✅ |
| 08 | 08_load_crm.py | CRM-Leads | ✅ |
| 09 | 09_load_stock.py | Lagerbestände | ✅ |
| 10 | 10_load_kundengruppen.py | Kundengruppen-Tags | ✅ |
| 11 | 11_load_pricelists.py | Preislisten | ✅ |
| 12 | 12_close_old_documents.py | Historische Aufträge sperren | ✅ |
| 13 | 13_apply_customizing.py | Odoo-Einstellungen | ✅ |
| 14 | 14_load_contacts.py | ADRANSPRECH → res.partner | ✅ |
| 15 | 15_load_supplierinfo.py | Lieferantenpreise | ✅ |
| 16 | 16_load_boms.py | Legacy-BOMs ARTSTUELI | ✅ |
| 17 | 17_load_boms_prodlist.py | PRODLIST+PRODINHALT (1.461 BOMs) | ✅ |
| 18 | 18_delete_pre2016.py | Pre-2016-Daten löschen | ✅ |
| 19 | 19_load_invoices.py | Rechnungen ab 2016 | ✅ |
| 20 | 20_delete_pickings.py | Auto-Pickings bereinigen | ✅ |
| 21 | 21_load_delivery_addresses.py | KNDLIEFER → res.partner delivery | ✅ |
| 22 | 22_load_serial_lots.py | 15.250 Sernr + 5.993 Chargen | ✅ |
| 23 | 23_load_open_items.py | Offene Posten Debitoren | ⚠️ AUSSTEHEND |
| 24 | 24_load_vat.py | USt-IdNr Lieferanten | ✅ |
| 25 | 25_setup_users.py | Benutzer-Setup | ✅ |
| 26 | 26_fix_create_dates.py | Erstelldaten korrigieren | ✅ |
| 27 | 27_load_serial_traceability.py | Seriennummer-Rückverfolgung | ✅ |
| 28 | 28_close_historical_invoices.py | Historische Rechnungen schließen | ✅ |
| – | run_all.py | Orchestrator mit `--from N` Resume | ✅ |

---

## 9. Offene Punkte vor Produktiv-Go-Live

### Kritisch
- [ ] **23_load_open_items.py**: FiBu-Workshop abwarten. 3.603 OP-Posten (~29,7 Mio €)
- [ ] **Sonderfarben RAL**: Varianten vs. Einzelartikel (GF-Entscheidung)
- [ ] **Subcontracting-BOMs**: Cobertec, Systemtechnik nicht vollständig validiert
- [ ] **Let's Encrypt**: Zertifikat läuft ~8. September 2026 ab → Renewal testen
- [ ] **2-Monats-Datenlücke**: Vollständiger Re-Run vor Cutover nötig

### Mittel
- [ ] **Fiskalposition EU**: Innergemeinschaftliche Lieferungen (Sica IT)
- [ ] **ZUGFeRD / E-Rechnung**: Ab 2025 B2B-Pflicht – Odoo 19 Modul prüfen
- [ ] **Benutzerkonten**: Passwörter, 2FA, Zugriffsrechte

### Schemaprüfung (neu)
- [ ] `odoo_schema.json` generieren (build_odoo_schema.py)
- [ ] `mapping_report.py` ausführen und Stimmigkeit prüfen
- [ ] SERNR-Tabelle klären: In CHARGEN integriert oder separate Seriennummern-Tabelle?

---

## 10. Infrastruktur

```
Internet → LANCOM-Router → nginx (HTTPS) → Odoo 19 (Port 8069, intern)
                                         → PostgreSQL (lokal)

nginx:  /etc/nginx/sites-available/odoo
SSL:    /etc/letsencrypt/live/erp-intern.kling-freitag.de/
Odoo:   /etc/odoo/odoo.conf
        list_db = False        ← VOR Go-Live setzen
        dbfilter = ^KuF$
```

---

## 11. Sicherheitsregeln (unbedingt einhalten)

- Credentials **nie** in Code oder Dokumentation – ausschließlich `.env` (gitignored)
- DB-Zugriff **nur** gegen Kopie/Test `KuF` auf 192.168.120.234, **nie** gegen Produktiv
- Odoo-Ports 8069/8072 **nie** direkt öffentlich exponieren
- `list_db = False` in `odoo.conf` vor Go-Live
- XML-RPC immer mit API-Key, nicht mit admin-Passwort
- Vor DELETE/Archivieren: Backup bestätigen lassen

---

## 12. Codex-Prüfaufgaben

Folgende Punkte sollte Codex überprüfen:

### A. Spaltenamen-Konsistenz in allen Skripten
Prüfe ob alle `.py`-Dateien in `99_scripts/` die korrekten Spaltennamen verwenden:
- ANGAUFPOS: `LFDANGAUFGUTNR` (FK), `LFDARTNR` (Artikel-FK numerisch), `BESTMENGE`, `PREIS`, `POSNR`, `LANGTEXT`
- ARTIKEL: `ARTNR1`, `ABEZ1`, `VKPR1`, `EKPR`, `MENGENSCHL`, `LFDLIEFNR`, `LFDNR`
- ARTIKELLONG: `LFDARTNR`, `CONTENT`
- ANGAUFGUT: `LFDNR`, `ANGEBOT`, `AUFTRAG`, `GUTSCHRIFT`, `KNDNR`, `ERFASSDATUM`
- PRODLIST: `LFD_NR`, `ART_NR` (mit Unterstrich!)
- PRODINHALT: `LIST_NR`, `ART_NR`

### B. BELEGTYP-Fehler aufspüren
Prüfe ob irgendwo `BELEGTYP` als Spaltenname verwendet wird → **existiert nicht!**
Stattdessen: `WHERE ag.ANGEBOT = 1` / `WHERE ag.AUFTRAG = 1` / `WHERE ag.GUTSCHRIFT = 1`

### C. Odoo-Felder validieren
Prüfe ob alle verwendeten Odoo-Felder in `odoo_schema.json` vorhanden sind.
Insbesondere die Pitfalls aus Abschnitt 7 beachten.

### D. Externe IDs
Prüfe ob das Schema `ev_kuf_adr_<ADRNR>` und `ev_kuf_art_<LFDNR>` konsistent verwendet wird.

### E. Sicherheit
- Keine Credentials in Code
- Alle DB-Verbindungen gegen 192.168.120.234 (nicht 192.168.120.225)
- `.env`-Dateien nirgends committet

---

## 13. Produkt-Beispiel: K&F PIA M

Wandlautsprecher. Vollständiger Prozessdurchlauf: `docs/pia_prozess.html`

**Stückliste PIA M (Lohnfertigung Cobertec = Subcontracting BOM):**

| Komponente | Lieferant | EK |
|---|---|---|
| Sica 4" Chassis C08N.16.08 | Sica Altoparlanti S.r.l. (IT) | 28,50 € |
| Karton PIA M | deupack GmbH | 3,20 € |
| Kippschalter 250V/6A | Digi-Key Electronics (US) | 1,85 € |
| Anschlusskabel 0,5m 2×0,75 | MTI GmbH | 2,10 € |
| Gehäuse PIA M – Rohteil | Blech-Lieferant | 42,00 € |
| **Lohnfertigung Pulverbeschichtung** | **Cobertec GmbH** | **18,00 €** |
