# Handover: Bitfarm-Importprogramm → Codex / KI-Prüfung

> **Probeimport gestartet – Vollhistorie Einkauf und Verkauf 16.09.2026:**
> `kuf-erp-all-data` enthält jetzt 22.010 informative Einkaufsköpfe mit 41.963
> Positionen sowie alle 37.977 eEvolution-Verkaufsbelegköpfe, aufgeteilt in 17.207
> gesperrte historische `sale.order` und 20.770 vollständige read-only Prüfdokumente.
> Wiederholungs-Dry-runs planen 0 Neuanlagen. Abnahme: 0 ungesperrte historische
> Standardbelege, 0 `stock.move`, 0 `account.move`, 0 `account.move.line`.
> Zwischenbackup vor Verkauf:
> `/var/backups/odoo/kuf-erp-all-data_20260916_163030_post_full_purchase_pre_full_sales_20260916`.
> Bericht: `05_doku/PROBEIMPORT_START_UND_ZWISCHENBERICHT_KUF_ERP_ALL_DATA_20260916.md`.

> **Probeimport-Freigabe 16.09.2026 (`REGEL-030`):** Der vollständige Probeimport ist
> ausschließlich auf `kuf-erp-all-data` freigegeben. Neue restore-getestete
> Vor-Import-Sicherung:
> `/var/backups/odoo/kuf-erp-all-data_20260916_160506_pre_authorized_full_rehearsal_retry_20260916`.
> Vorab-Gate: 7.992/7.992 historische `sale.order` gesperrt, 0 `stock.move`,
> 0 `account.move`, 0 `account.move.line`; eEvolution-Anker für 19 Haupttabellen sind
> festgehalten. Nach jedem Importblock und abschließend dieselben Metriken protokollieren.
> Keine Freigabe für finalen Cutover, Produktion oder eEvolution-Writes. Nachweis:
> `05_doku/PROBEIMPORT_FREIGABE_KUF_ERP_ALL_DATA_20260916.md`.

> **External-ID-Übergang 16.09.2026 (`REGEL-031`):** Zielnamensraum ist `eevolution`.
> Vorhandene `__import__`-Bindings dürfen nicht durch bloßes Umschalten abgeschnitten
> werden. Nach dem aktuellen Probeimport kontrollierte Binding-Migration/Alias-Auflösung,
> danach `pilot_import_angebot.py` umstellen und Idempotenz prüfen.

> **Go-live und Cutoff 16.09.2026 (`REGEL-029`):** Go-live ist der 01.01.2027.
> Oberer Cutoff exklusiv `2027-01-01 00:00:00 Europe/Berlin`; technisches
> Zehnjahresfenster ab inklusive `2017-01-01 00:00:00`. Nach vollständigem Rehearsal
> unveränderliche restore-getestete Golden-Sicherung erstellen und nur eine neutralisierte
> Kopie für Test/Schulung freigeben. Schulungs-DB nie produktiv setzen; Produktivsystem
> reproduzierbar nach finalem eEvolution-Freeze und Cutover neu aufbauen. Ablauf:
> `05_doku/CUTOVER_UND_SCHULUNGSPLAN_GO_LIVE_20270101.md`.

> **Verbindlicher Historienumfang 16.09.2026 (`REGEL-028`):** Vollständige
> Hauptbeleggeschichte für Verkauf, Lieferscheine, Einkauf, Produktionsauftragsköpfe,
> Ausgangs- und Eingangsrechnungen einschließlich Belegpositionen. Technische
> Serien-/Chargenrückverfolgung und Produktionsdetails nur letzte zehn Jahre; ältere
> Produktionsaufträge nur als Kopf. Keine einzelnen operativen Lagerbuchungen und keine
> Buchungssätze aus historischen Rechnungen. CRM-Althistorie sowie exakter oberer Cutoff
> bleiben in `OFFEN-009` separat zu klären.

> **Historische Einkaufsbelege 16.09.2026:** Auf `kuf-erp-all-data` sind
> 8.739 wirkungsfreie, schreibgeschützte eEvolution-Einkaufsbelege mit 18.018
> Originalpositionen importiert. 8.702 Bestellungen und 37 Rahmenvertragsbelege;
> 513 Belege mit sichtbarem Prüfkennzeichen, 0 Positionen ohne Odoo-Artikelbezug.
> Keine `purchase.order`, `purchase.requisition`, Pickings, Stock Moves,
> Account Moves oder E-Mails erzeugt. Finaler Wiederholungslauf 0/0.
> Modul `kf_legacy_migration` 19.0.11.0.0. Nachweis:
> `05_doku/HISTORISCHE_EINKAUFSBELEGE_KUF_ERP_ALL_DATA_20260916.md`.
> Restore-getestete Abschlusssicherung:
> `/var/backups/odoo/kuf-erp-all-data_20260916_145344_post_historical_purchase_full`.

> **Vollständige Legacy-Rückverfolgung 16.09.2026:** Auf `kuf-erp-all-data`
> sind für den Zeitraum 16.09.2016 bis einschließlich 16.09.2026 exakt 49.472
> Serien-/Chargenköpfe und 322.386 Ereignisse geladen. Dazu gehören 7.784
> informative Produktionsaufträge, 251.767 Komponentenbuchungen, 31.580
> Produktionsausgaben, 178.603 Verwendungsbeziehungen und 41.112 direkte
> Liefernachweise. Quelle/Ziel-Abgleich stimmt; alle inaktiven Artikel sind
> verknüpft; finaler Wiederholungslauf überall 0 Änderungen. Keine Pickings,
> Stock Moves oder Account Moves. Restore-getestete Abschlusssicherung:
> `/var/backups/odoo/kuf-erp-all-data_20260916_142225_post_full_traceability_import`.
> Gesamtbericht:
> `05_doku/GESAMTBERICHT_DATENBESTAND_KUF_ERP_ALL_DATA_20260916.md`.

> **Historische Verkaufsbelege 16.09.2026:** Auf `kuf-erp-all-data` sind 7.992
> wirkungslose, gesperrte eEvolution-Verkaufsbelege, 6.164 vollständige Legacy-Prüffälle
> und 5.055 belegbezogene Lieferadressen importiert. Keine Lieferungen, Lagerbewegungen,
> Rechnungen, Buchungssätze oder E-Mails wurden erzeugt; Idempotenz-Dry-run 0/0/0.
> `kf_legacy_migration` steht auf `19.0.10.0.0` und blockiert Änderungen, Bestätigung,
> Entsperren und Rechnungserzeugung historischer Belege. Nachweis:
> `05_doku/HISTORISCHE_VERKAUFSBELEGE_KUF_ERP_ALL_DATA_20260916.md`.

> **Projektverfassung und Projektgedaechtnis (24.08.2026):** Vor jeder neuen
> Aufgabe zuerst `00_PROJEKTVERFASSUNG_ODOO.md`, danach
> `ODOO_PROJEKT_ENTSCHEIDUNGSREGISTER.md`,
> `05_doku/ODOO_PROJEKT_REGELCHRONIK_20260824.md`,
> `05_doku/EEVOLUTION_ODOO_MAPPING_STANDARD.md` und
> `ODOO_OFFENE_ENTSCHEIDUNGEN.md` lesen. Aktive Regeln stehen im
> Entscheidungsregister mit Status `AKTIV`; ersetzte oder verworfene Regeln
> duerfen nicht weiterverwendet werden. Bei widerspruechlichen oder fehlenden
> Nachweisen gilt Rueckfragepflicht statt Interpretation.

> **Verbindliches Masterkonzept (23.08.2026):** Vor neuen
> Migrationsaufgaben zuerst
> `05_doku/PROJEKT_GRUNDKONZEPT_MIGRATION_UND_BETA_REBUILD.md` lesen und
> einordnen, in welche Phase die Aufgabe gehoert und welche Abhaengigkeiten
> erfuellt sein muessen. Vor jedem Write pruefen: Discovery, fachliches
> Datenmodell, Mapping, Dry-run, Freigabe, Backup, Read-back-Plan und
> Idempotenzpruefung des betroffenen Blocks muessen abgeschlossen bzw.
> explizit belegt sein. Ein vorhandenes Skript ist allein kein fachlicher
> Vollstaendigkeitsnachweis.

> **Fakten- und Quellenregel (23.08.2026):** Fakt vor Interpretation.
> Ein vorhandener Odoo-Wert ist kein Quellnachweis. Fuer jeden migrierten
> oder zu korrigierenden Wert muss die Kette `eEvolution-Quelle ->
> Quellfeld/Relation -> Quellwert -> Transformationsregel -> Odoo-Zielfeld ->
> Odoo-Wert` belegbar sein. Wenn nicht, gilt:
> `UNGEKLÄRT – KEINE ANNAHME GETROFFEN`. Nachweis und aktueller Audit:
> `05_doku/FAKTEN_QUELLENREGEL_UND_PIA_SCOPE_AUDIT_20260823.md`.

> **Pflichteinstieg für neue Chats (20.08.2026):** Zuerst
> `05_doku/START_HIER_NEUER_CHAT_20260820.md` vollständig lesen. Dort sind der
> konsolidierte Artikelstamm-Stand, bestätigte Fachentscheidungen, ausdrücklich
> noch offene Punkte und der nächste belastbare Arbeitsblock getrennt dokumentiert.
> Ältere Aussagen zur Artikelklassifikation nicht isoliert fortschreiben.

> **Artikelklassifizierung V2.1 (23.08.2026):** Die konservative
> PIA-Artikelklassifizierung ist als wiederverwendbare Engine unter
> `artikelklassifizierung/` verankert. Referenzstand:
> `KF_ARTIKELCLASSIFIER_V2.1`; Regressionstests:
> `artikelklassifizierung/tests/`. Regelwerk und Odoo-Pilotplanung:
> `05_doku/ARTIKELKLASSIFIZIERUNG_REGELWERK_V21_20260823.md` und
> `05_doku/ARTIKELKLASSIFIZIERUNG_ARCHITEKTUR_UND_ODOO_PILOT_20260823.md`.
> Keine produktive Odoo-Freigabe, keine Varianten-/Attributanlage.

> **Einkaufsbeschreibung 18.08.2026:** `ARTIKEL.ABEZ3–8` werden zeilenweise
> nach `product.template.description_purchase` übernommen. Auf `kuf-erp-2`:
> 247 geschrieben, 21 Quelltexte leer, 0 Konflikte, Wiederholungs-Dry-Run 0
> Änderungen. Sicherung:
> `/var/backups/odoo/kuf-erp-2_20260818_131646_pre_purchase_descriptions`.
> Nachweis: `05_doku/EINKAUFSBESCHREIBUNGEN_ABEZ3_8_KUF_ERP_2_20260818.md`.

> **Kritische Artikelstamm-Lücke 18.08.2026:** Vollständiger Live-Audit von
> `dbo.ARTIKEL`: 252 Spalten, 5.958 importfähige Artikel, 17 Felder explizit
> in `product.yaml`, 85 befüllte Felder derzeit ungemappt. In `kuf-erp-2` haben
> 0/268 PIA-Produkte eine interne Beschreibung und nur 9/268 eine Kategorie.
> Keine Odoo-Schreibzugriffe. Nachweis:
> `05_doku/VOLLSTAENDIGKEITSPRUEFUNG_ARTIKELSTAMM_20260818.md`.

> **Verbindliche Lieferanten-Importregel 20.08.2026:**
> `ARTIKEL.LFDLIEFNR` ist immer der erste/A-Lieferant in Odoo. Weitere aktuelle
> Beziehungen stammen aus `LIEFERPREISE` und folgen mangels eines nachgewiesenen
> B-/C-Rangfelds deterministisch nach Lieferantennummer. Hauptlieferanten auch
> ohne Preis- oder Bestellhistorie anlegen; Odoo-only-/historische Zeilen
> erhalten und ab Sequenz 900 nachordnen. Die vollständige Kontrollfolge steht
> in `05_doku/START_HIER_NEUER_CHAT_20260820.md`, Abschnitt 7. Referenz:
> `99_scripts/113_sync_supplier_priority.py` und
> `05_doku/LIEFERANTENPRIORITAET_ABC_KAUFTEILE_KUF_ERP_2_20260820.md`.

> **Verbindliche Rahmenvertrags-Importregel 20.08.2026:** 114 Einkaufsrahmen-
> verträge aus `BESTRAHMEN` und 171 Positionen aus `BESTELLUNG` mit `RAHMEN=1`
> wurden migriert. Bei aktiven Verträgen ist ausschließlich
> `max(BESTMENGE-GELMENGE-RESMENGE,0)` erneut abrufbar. Vertragspreise bleiben
> getrennt von allgemeinen `product.supplierinfo`-Konditionen. Erledigte und
> abgelaufene Verträge nur geschlossen/archiviert übernehmen; bestehende Abrufe
> später separat als offene Bestellungen migrieren. Vollständige Regel:
> `05_doku/START_HIER_NEUER_CHAT_20260820.md`, Abschnitt 8. Nachweis:
> `05_doku/RAHMENVERTRAEGE_EINKAUF_KUF_ERP_2_20260820.md`.

> **Buchhaltungsantworten 18.08.2026:** `840500`/`840100` sind als reguläre
> Produkt-Erlöskonten bestätigt; `812500`/`812000` sollen über Fiskalpositionen
> gesteuert werden. `390000`–`392000` sind als Produkt-Aufwandskonten verworfen;
> die richtigen Konten liegen im 34er-Bereich und fehlen noch aus der SuSa-Liste.
> Bestandsveränderungen wurden mit `896000`/`898000` benannt, die konkrete
> Odoo-Verwendung ist noch offen. Der Kontensync sperrt Aufwands-Schreibvorgänge
> bis zur Allowlist-Freigabe. Nachweis:
> `05_doku/BUCHHALTUNGSANTWORTEN_KONTIERUNG_20260818.md`.

> **AVCO/DEKPR 18.08.2026:** Auf `kuf-erp-2` wurden 17 K&F-Kategorien auf
> Durchschnittskosten (AVCO) gestellt und 115 abweichende positive Werte aus
> `ARTIKEL.DEKPR` nach `product.template.standard_price` übernommen. 18
> `DEKPR=0`-Fälle bleiben bewusst ungeändert. Wiederholungs-Dry-Run: 0 Änderungen.
> Nachweis: `05_doku/AVCO_DEKPR_UMSTELLUNG_KUF_ERP_2_20260818.md`.

> **Abrufbarer nächster Schritt (17.08.2026):** Wenn der Benutzer **„Testlauf“**
> schreibt, den in `05_doku/NEXT_STEP_TESTLAUF_PIA.md` definierten operativen
> PIA-Ende-zu-Ende-Test auf `kuf-erp-2` fortsetzen. Vor Schreibzugriff Live-Preflight,
> Anpassungsprüfung der alten Testskripte, Dry-Run und neue verifizierte Vollsicherung.
>
> **Sicherheitsarchitektur 17.08.2026:** Zieldatenbanken werden zentral über
> `02_mappings/allowed_target_databases.yaml` freigegeben. Alle direkten Odoo-RPC-
> Proxies laufen über `99_scripts/migration_runtime.py`; der Guard arbeitet
> fail-closed mit Lesemethoden-Positivliste und erzeugt keine Fake-Dry-Run-Werte
> mehr. Umsetzung und Nachweise:
> `05_doku/ZENTRALE_ZIELDATENBANK_SICHERHEIT_20260817.md`.

**Projekt:** Datenmigration eEvolution (MS SQL Server) → Odoo 19 Enterprise  
**Auftraggeber:** Kling & Freitag GmbH (K&F), Hannover – Hersteller professioneller Beschallungssysteme  
**Branch:** `claude/eevolution-mapping-validation-iemk0y`  
**Stand:** 2026-08-06

---

## 0. AKTUELLE AUFGABE FÜR CODEX (Stand 2026-08-06)

> **Aktualisierung 06.08.2026:** Maßgebliche Arbeitskopie ist ausschließlich
> `V:\Claude-Projekte\odoo_projekt`. Die nachstehenden Hinweise zu
> `C:\temp\bitfarm-repo`, Kopierarbeiten und einem Einzelangebot sind überholt.
>
> Aktueller Stand:
> - 32 aktive TimeInfo-Personen sind auf `erp-test-1` ausschließlich als
>   `hr.employee` importiert: 27 neu, 5 vorhandene eindeutig verknüpft,
>   0 Benutzerkonten und 0 Zeiterfassungsbuchungen. Die Wiederholung ist
>   idempotent (`create=0`, 32 unverändert). Reproduzierbar über
>   `02_mappings/timeinfo_employees.yaml` und
>   `99_scripts/45_import_timeinfo_employees.py` als Schritt 5 von `run_all.py`.
>   `02_load_partners.py` legt standardmäßig keine Mitarbeiter-Benutzer mehr an.
> - Pilotangebot eEvolution 39575 wurde idempotent nach `erp-test-1` importiert:
>   CRM-Chance, Kunde, 5 Ansprechpartner, 51 Lieferanten, 152 Artikel,
>   34 Stücklisten mit 186 Positionen und Odoo-Angebot `S00001` mit 5 Positionen.
> - Abschlussprüfung erfolgreich: netto 27.517,11 EUR, Steuer 5.228,25 EUR,
>   brutto 32.745,36 EUR. Angebot bleibt im Entwurf; keine Lieferungen,
>   Fertigungsaufträge oder Bestellungen wurden erzeugt.
> - Der Wiederholungslauf erzeugt keine Dubletten (`create=0`); alle Datensätze
>   besitzen stabile externe IDs im Namensraum `__import__`.
> - Verifizierte Sicherung unmittelbar vor dem Pilotimport:
>   `/var/backups/odoo/erp-test-1_20260806_125146_pre_pilot39575`.
> - Verbindliche Artikelregel: `ARTIKEL.INAKTIV` ist bei K&F kein Löschkriterium
>   und wird importiert. Ausschließlich gesetztes `ARTIKEL.LOESCHKNZ` schließt
>   einen Artikel aus. Benötigt eine ausgewählte Stückliste einen gelöschten
>   Artikel, bricht der Pilotimport kontrolliert ab.
> - Original-Pflichtenheft vollständig geprüft.
> - Read-only-Soll-Ist-Prüfung der Testdatenbank `erp-test-1` dokumentiert in
>   `05_doku/ODOO_PFLICHTENHEFT_SOLL_IST_20260806.md`.
> - Verifizierte Vollsicherung von `erp-test-1` vor Änderungen liegt auf dem Odoo-Server
>   unter `/var/backups/odoo/erp-test-1_20260806_114539`.
> - Pflichtmodule für Qualität, Fertigungs-QS, Shop-Floor-QS, Fremdfertigung,
>   Einkaufsvereinbarungen und Versandmethoden sind auf `erp-test-1` installiert.
> - Lager `K&F Hannover` ist auf 3-stufigen Ein-/Ausgang und Vor-/Nachproduktion gestellt.
> - `kf_serial_category` und `kf_legacy_migration` sind installiert; 16 Seriennummerngruppen
>   sind eingerichtet.
> - Neue Seriennummern verwenden `GGWWYYNNNNN` mit echter ISO-Kalenderwoche und dauerhaftem
>   fünfstelligem Gruppenzähler. Aktuelles Datum und ISO-Jahresgrenze wurden transaktional
>   getestet; alle Testdaten und Zählerbewegungen wurden zurückgerollt.
> - Historischer OP-Import deaktiviert; echte OP/Eröffnungssalden nur zum Go-live.
> - Produktfamilien/Präfixe in `02_mappings/product_serial_groups.yaml`.
> - Artikeltransform ordnet Familien zu. Inaktive eEvolution-Artikel werden
>   ausdrücklich mit übernommen; nur Artikel mit Löschkennzeichnung entfallen.
> - Odoo HTTP, SSH, GitHub und eEvolution SQL sind erreichbar und authentifiziert.
>   `excel_kuf_readonly` ist nachweislich `db_datareader`, nicht `db_datawriter`/`db_owner`.
>   Das Kennwort liegt ausschließlich Windows-benutzergebunden verschlüsselt außerhalb von Git.
> - Noch offen: vollständigen eEvolution-Export mit der korrigierten Löschregel
>   wiederholen sowie CRM-Stufen und weitere Quelldaten laden.
> - Arbeitsplätze, Qualitätsprüfpläne, Rollen, DATEV-Testexport und konkrete Carrier-Connectoren
>   benötigen fachliche Daten/Entscheidungen und Ende-zu-Ende-Abnahme.
> - Der in `erp-test` vorbereitete sechsstellige SKR03-Kontenrahmen wurde am 06.08.2026
>   kontrolliert nach `erp-test-1` synchronisiert: 1.354 Konten, keine Code-Dubletten,
>   keine temporären Codes, 72 stabile External IDs für K&F-Zusatzkonten und weiterhin
>   null Buchungen/Buchungszeilen. Sicherung davor:
>   `/var/backups/odoo/erp-test-1_20260806_202214_pre_coa_sync`. Nachweis:
>   `05_doku/KONTENRAHMEN_SYNC_ERP_TEST_NACH_ERP_TEST_1_20260806.md`.
> - Alle früher im Repository abgelegten Klartext-Serverkennwörter wurden entfernt;
>   das betroffene Kennwort muss rotiert werden.
> - Finanz-Audit 06.08.2026: Die laufende Buchführung in Odoo und das interne
>   GF-Berichtswesen sind als vorgeschlagenes Zielbild dokumentiert; das Steuerbüro
>   bleibt Prüfer. Eine GF-Freigabe und endgültige Rollenvergabe stehen noch aus.
> - Der Entscheidungs- und Fragenkatalog liegt als MD und DOCX unter
>   `05_doku/FRAGENKATALOG_INTERNE_BUCHFUEHRUNG_ODOO.*` vor.
> - Eine sachliche GF-Entscheidungsgrundlage mit risikobegrenztem Pilot,
>   konkreten Sicherheitskontrollen, Stop-Kriterien, Beschlussvorschlag und
>   Gesprächseinstieg liegt unter
>   `05_doku/GF_ENTSCHEIDUNGSGRUNDLAGE_INTERNE_BUCHFUEHRUNG_ODOO.*` vor.
> - Produktkontierungs-Dry-Run: 152 Pilotartikel, davon Erlös 840500 (146) bzw.
>   840100 (6). Acht benötigte Aufwandskonten fehlen noch in Odoo; die vorbereitete
>   wiederholbare Synchronisierung liegt in `99_scripts/30_sync_product_accounts.py`.
>   Vorratskonten werden wegen drei mehrdeutigen Quellregeln und fehlender Konten
>   397100/397200/397300 noch nicht geschrieben.

**Ziel erreicht:** Stammdaten, CRM-Chance und Angebot 39575 wurden nach Odoo 19
importiert. Die Mitarbeiter beginnen den manuellen Prozess beim Entwurfsangebot
`S00001`. Siehe `05_doku/PILOTTEST_ANGEBOT_39575.md`.

### Lokale Umgebung (Windows)
```
Projektordner:  Z:\Claude-Projekte\odoo_projekt\
Git-Repo:       C:\temp\bitfarm-repo\  (Branch: claude/eevolution-mapping-validation-iemk0y)
eEvolution:     192.168.120.234 / KuF  (Read-only-Zugang ausschließlich lokal)
Odoo Test:      192.168.120.225:8069   (DB: erp-test-1, admin + API-Key aus .env)
```

### Schritte die Codex ausführen soll

**1. Git-Repo aktualisieren:**
```cmd
cd C:\temp\bitfarm-repo
git commit --no-edit          # hängenden Merge abschließen (falls MERGE_HEAD existiert)
git pull
```

**2. Skript ins Projektverzeichnis kopieren:**
```cmd
copy 99_scripts\pilot_import_angebot.py Z:\Claude-Projekte\odoo_projekt\99_scripts\pilot_import_angebot.py
```

**3. .env prüfen / anlegen** (falls nicht vorhanden):
```cmd
cd /d Z:\Claude-Projekte\odoo_projekt
setup_env.cmd
```
Inhalt `.env`:
```
ODOO_URL=http://192.168.120.225:8069
ODOO_DB=erp-test-1
ODOO_USER=admin
ODOO_API_KEY=<api-key>
```

**4. Dry-Run – zeigt was importiert werden würde:**
```cmd
cd /d Z:\Claude-Projekte\odoo_projekt
python 99_scripts\pilot_import_angebot.py
```

**5. Import ausführen** (nach Prüfung des Dry-Run):
```cmd
python 99_scripts\pilot_import_angebot.py --import
```

### Was das Skript importiert
- Mengeneinheiten (uom.uom)
- Lieferanten/Lohnfertiger (res.partner, supplier_rank=1)
- Artikel + Beschreibungen (product.template)
- Stücklisten rekursiv über alle Ebenen (mrp.bom + mrp.bom.line)

### Was das Skript NICHT macht (händisch durch Mitarbeiter)
- Angebot nicht bestätigen
- Keine Lieferungen, Fertigungsaufträge oder Bestellungen auslösen
- Keine Buchungen oder Rechnungen erzeugen

### Fehlerquellen die auftreten können
- `MERGE_HEAD exists` → `git commit --no-edit` ausführen
- `.env` fehlt → `setup_env.cmd` ausführen
- `ODOO_DB` falsch → muss `erp-test-1` sein (nicht `kuf-erp-test`)
- Spaltenname falsch → Spaltenliste in Abschnitt 5.2 prüfen
- BOM-Typ `subcontract` für Lohnfertigung (Cobertec) ggf. manuell anpassen

---

## 1. Projektkontext

K&F migriert ihr ERP von eEvolution (MS SQL Server, Eigenentwicklung Bitfarm AG) auf Odoo 19 Enterprise.
Testmigration auf `erp-test-1` läuft. Produktiv-Cutover Q3/Q4 2026.

| System | Details |
|---|---|
| Quelle | eEvolution, MS SQL 192.168.120.234, DB: `KuF` |
| Quelle User | Read-only-SQL-Benutzer ausschließlich lokal in `EV_USER` hinterlegen |
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
LIEFERANT.PK        → LIEFNR        # ADRNR ist nicht der Primärschlüssel
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
15. **Externe IDs** für Idempotenz: verbindlich gemäß
    `05_doku/EEVOLUTION_ODOO_MAPPING_STANDARD.md`, insbesondere
    `ev_adr_<ADRNR>` und `ev_product_<LFDNR>` im Modul `__import__`
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
Prüfe, ob die verbindlichen Namensräume aus
`05_doku/EEVOLUTION_ODOO_MAPPING_STANDARD.md` konsistent verwendet werden,
insbesondere `ev_adr_<ADRNR>` und `ev_product_<LFDNR>`.

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
