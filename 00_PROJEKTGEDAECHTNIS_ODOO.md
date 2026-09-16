# Projektgedaechtnis Odoo/eEvolution

Stand: 2026-09-15

Diese Datei ist der zentrale Einstiegspunkt. Sie dupliziert die Detaildokumente nicht, sondern verweist auf die aktuell verbindlichen Quellen.

## A. Aktueller Projektstand

- PIA-Pilotdatenbank: `kuf-erp-2`.
- eEvolution-Quelle: SQL-Datenbank `KuF`, read-only.
- PIA-Legacy-Rueckverfolgung wurde am 15.09.2026 testweise wirkungslos importiert:
  1.276 Serien-/Chargenkoepfe und 8.627 Ereignisse aus dem festen Zeitraum
  15.09.2016 bis 16.09.2026 exklusiv. Es entstanden keine operativen Lager-,
  Fertigungs-, Verkaufs-, Einkaufs- oder Buchhaltungsdatensaetze. Nachweis:
  `05_doku/PIA_LEGACY_TRACEABILITY_PILOTIMPORT_KUF_ERP_2_20260915.md`.
- PIA-S00011-E2E-Test ab Verkaufsauftrag: Auftrag -> PIA-Vollversorgung -> Wareneingang/QS -> interne Vorfertigungen -> Endmontage -> Pick/Pack/Out wurde am 2026-08-24 erfolgreich durchgespielt.
- PIA-S00012-CRM-E2E-Test: eEvolution-CRM-Chance -> Odoo-Opportunity -> Testangebot/-auftrag -> Beschaffung -> Wareneingang/QS -> interne Vorfertigungen -> Endmontage -> Pick/Pack/Out wurde am 2026-08-24 erfolgreich durchgespielt.
- Finaler geprüfter CRM-E2E-Auftrag: `S00012`, Produkt `36289`, Seriennummer `85342600102`.
- Historischer operativer Vorbeleg: `S00011`, Produkt `36289`, Seriennummer `85342600101`.
- CRM-Einschraenkung zu `S00011`: `S00011` hat keine `opportunity_id`; CRM-Opportunity-Import ist erst mit `S00012` Teil eines bewiesenen E2E-Nachweises.
- CRM-/Angebotsanker: `S00001` ist mit CRM-Chance `ev_pilot_crm_39575` verknuepft und basiert auf eEvolution-Angebot `39575`, ist aber nicht als sauberer operativer E2E-Beleg zu verwenden.
- Finales Backup nach `S00012`-CRM-E2E-Abschluss: `/var/backups/odoo/kuf-erp-2_20260824_040736_post_s00012_crm_e2e_done_20260824`.

Details: `05_doku/ODOO_PIA_URLAUBSUEBERGABE_TESTSTAND_20260824.md`.

CRM-/Angebotsdetails: `05_doku/PIA_CRM_ANGEBOT_AUFTRAG_STATUS_20260824.md`.

CRM-E2E-Details: `05_doku/PIA_CRM_E2E_S00012_20260824.md`.

## B. Verbindliche Grundregeln

Maßgeblich:

1. `00_PROJEKTVERFASSUNG_ODOO.md`
2. `AGENTS.md`
3. `ODOO_PROJEKT_ENTSCHEIDUNGSREGISTER.md`
4. `05_doku/ODOO_PROJEKT_REGELCHRONIK_20260824.md`
5. `05_doku/EEVOLUTION_ODOO_MAPPING_STANDARD.md`
6. `ODOO_OFFENE_ENTSCHEIDUNGEN.md`

Kernregeln: Fakt vor Interpretation, keine erfundenen Stammdaten, Odoo-Wert ist kein eEvolution-Quellnachweis, Writes nur mit Zielschutz/Backup/Dry-run bzw. explizitem Apply/Read-back.

## C. Aktive Entscheidungen

Aktive Entscheidungen stehen im Entscheidungsregister:

`ODOO_PROJEKT_ENTSCHEIDUNGSREGISTER.md`

Besonders relevant: Supplierinfo aus `LIEFERPREISE`, Kosten aus `ARTIKEL.DEKPR`, A-Lieferant aus `ARTIKEL.LFDLIEFNR`, B/C nicht erfinden, `EKMENGENSCHL` als belegte Einkaufseinheit behandeln.

Pflicht vor jeder neuen Aufgabe: zuerst das Entscheidungsregister auf thematische Treffer pruefen. Eine neue Aufgabe darf eine `AKTIV`-Regel nicht still ersetzen. Bei Konflikt muss die alte Regel im Register auf `ERSETZT` oder `WIDERRUFEN` gesetzt und die neue Regel mit Faktenbasis dokumentiert werden.

Aktive Kernentscheidungen fuer haeufig wiederkehrende Themen:

| Thema | Aktuelle Regel | Quelle | Status |
|---|---|---|---|
| Supplierinfo | `LIEFERPREISE` ist fuehrende Stammdatenquelle; `BESTELLUNG` nur Historie/Rahmenvertrag. | `REGEL-007` | AKTIV |
| Lieferantenprioritaet | A aus `ARTIKEL.LFDLIEFNR`; weitere `LIEFERPREISE`-Lieferanten nicht als B/C behaupten. | `REGEL-008` | AKTIV |
| Kosten | `ARTIKEL.DEKPR` ist AVCO-Startwert; `EKPR` ueberschreibt Kosten nicht. | `REGEL-005` | AKTIV |
| Einkaufseinheit | `LIEFERPREISE.EKMENGENSCHL` muss explizit fuer Supplierinfo-UoM gefuehrt werden. | `REGEL-015` | AKTIV |
| Artikel-/BOM-Einheiten | `ARTIKEL.MENGENSCHL` ist Pflichtquelle fuer Produkt-UoM; `PRODINHALT.MENGENSCHL` ist Pflichtquelle fuer BOM-Zeilen-UoM. Kein stiller Odoo-Default `Unit`. | `05_doku/PIA_ARTIKEL_MENGENEINHEITEN_AUDIT_20260824.md` | AKTIV |
| PIA-Scope | Root-Produkte plus rekursive Stuecklistenkomponenten; Reviewfaelle nicht durch Vermutung schliessen. | `REGEL-003` | AKTIV |
| Odoo-Sollprozesse | PIA-QS, Lagerketten, Serien-/Chargenablaeufe koennen bewusste Odoo-Sollprozesse sein und muessen so gekennzeichnet werden. | Regelchronik 2026-08-12/2026-08-19 | SOLLENTSCHEIDUNG |

## D. Ersetzte Entscheidungen

Historische Supplierinfo aus `BESTELLUNG` ist ersetzt und darf nicht als aktueller allgemeiner Lieferantenstamm reaktiviert werden.

Details: `05_doku/ODOO_PROJEKT_REGELCHRONIK_20260824.md`.

Explizit ersetzt:

| Fruehere Regel | Heutige Regel | Warum ersetzt | Status |
|---|---|---|---|
| Supplierinfo aus historischen `BESTELLUNG`-Zeilen, letzter EK, `min_qty=1`. | Supplierinfo aus `LIEFERPREISE`. | Historische Belege sind keine aktuelle Lieferantenstammdatenquelle. | ERSETZT |
| `EKPR` oder alte Produkt-CSV als Kostenbasis. | `ARTIKEL.DEKPR` fuer AVCO-Startkosten. | DEKPR ist die freigegebene Durchschnittskostenbasis. | ERSETZT |
| Produkt-UoM still als Supplierinfo-UoM verwenden. | `LIEFERPREISE.EKMENGENSCHL` explizit mappen. | 65940/67887 zeigen, dass Quelle und Zielkette sichtbar sein muessen. | ERSETZT |

## E. Verworfene Ansätze

- Supplierinfo aus historischen `BESTELLUNG`-Zeilen als allgemeiner Stammdatenimport: ersetzt durch `LIEFERPREISE`.
- Produkt-UoM still als Supplierinfo-UoM verwenden: ersetzt durch explizite `LIEFERPREISE.EKMENGENSCHL`-Regel.
- Manuelles `mrp.workorder.button_finish()` vor `mrp.production.button_mark_done()` im automatisierten Fertigungsabschluss: verworfen, weil dadurch Fertigbewegungen auf 0 laufen bzw. MOs in `cancel` enden koennen.

DIESEN WEG NICHT ERNEUT GEHEN:

| Ansatz | Ergebnis | Ersetzt durch |
|---|---|---|
| B-/C-Lieferanten aus Sortierung oder Reihenfolge ableiten. | Kein belegtes B-/C-Feld im PIA-Scope; waere erfunden. | A-Lieferant belegt, weitere Lieferanten `UNKNOWN`. |
| Verpackung/Gebinde aus plausiblen Feldnamen pauschal schreiben. | Bedeutung von `GEBINDEEINHEIT`, `EKGEBINDESCHL`, `FAKTOR` nicht ausreichend belegt. | Kein Verpackungswrite ohne Golden Cases/Fachfreigabe. |
| Sichtbaren Odoo-Wert als Quellenbeleg verwenden. | Odoo kann Ergebnis alter Regeln oder Defaults sein. | Rueckkette eEvolution -> Mapping -> Odoo -> Read-back. |

## F. Offene Entscheidungen

Offene fachliche Entscheidungen stehen in:

`ODOO_OFFENE_ENTSCHEIDUNGEN.md`

Unter anderem: Gebinde/Faktor/Verpackung, `DEKPR=0`, Artikel 68148, Supplierinfo-UoM-Differenzen.

Offene Punkte duerfen nicht erneut als erledigt behauptet werden. Wenn ein offener Punkt durch Fakten oder menschliche Freigabe geloest wird, muss zuerst `ODOO_OFFENE_ENTSCHEIDUNGEN.md` bereinigt und das Entscheidungsregister ergaenzt werden.

## G. Bekannte Fehler und Risiken

- Alte Testketten `S00009`/`S00010` sind nicht als sauberer E2E-Nachweis zu verwenden.
- Mehrstufige Odoo-Lieferketten koennen neue Pickings erst nach Validierung der Vorstufe an den Auftrag hängen; Read-back muss alle Pickings pruefen.
- Test-Lieferschein- und Herstellerchargennummern aus S00011 sind Sollprozess-Testwerte, keine eEvolution-Historie.
- CRM-Readiness: eEvolution enthaelt Chancen, aber `kuf-erp-2` enthaelt aktuell keine importierten Opportunities; CRM darf nicht als abgeschlossen dargestellt werden.
- CRM-Dry-run: `08_load_crm.py --dry-run --only-id` funktioniert seit 2026-08-24 fuer Einzelchancen. Apply bleibt ohne Stufen-/Benutzerentscheidung gesperrt.
- Supplierinfo-UoM: 65940 ist fachlich korrekt belegt, aber Regressionstest fuer die Pflichtkette `LIEFERPREISE.EKMENGENSCHL -> product.supplierinfo.product_uom_id`. 23 Quell-Differenzen `EKMENGENSCHL != ARTIKEL.MENGENSCHL` bleiben pruefpflichtig.
- Artikel-/BOM-UoM-Audit 2026-08-24: PIA-Scope hat aus eEvolution `ARTIKEL.MENGENSCHL` 261x `STK`, 5x `m`, 2x `l`; PIA-Root-BOM `36289` hat aus `PRODINHALT.MENGENSCHL` quellenbelegte `STK`/`m`-Positionen. `Einheit(en)` in diesen BOM-Zeilen ist dort quellenbelegt `STK`, kein bewiesener Default.
- Importschutz Einheiten: `99_scripts/17_load_boms_prodlist.py` darf seit 2026-08-24 leere/ungemappte `PRODINHALT.MENGENSCHL` nicht mehr auf `uom.product_uom_unit` fallbacken; `99_scripts/02_transform.py` behandelt leere transformierte Pflichtfelder als Fehler.
- UoM-Abschlusspruefung 2026-08-24: Nach Backup `/var/backups/odoo/kuf-erp-2_20260824_135936_pre_uom_acceptance_apply_20260824` wurden `PRODLIST.LFD_NR=1258`, `PRODLIST.LFD_NR=1433` und die UoM-Dublette `68089` kontrolliert korrigiert. Read-back: 830 PIA-BOM-Zeilen geprueft, 828 UoM OK, 2 Strukturblocker wegen fehlender Komponentenprodukte; 268 Produkt-UoM OK. UoM-Migration: abgenommen JA.
- Systemweite UoM-Pruefung 2026-08-24: 336 eEvolution-verankerte Produkte und 7.655 Odoo-Datensaetze wurden read-only geprueft. Ergebnis systemweit: NEIN, weil 3 Einkaufsauftragspositionen fuer `67887` gegen `LIEFERPREISE.EKMENGENSCHL=STK` auf Odoo-UoM `m` stehen und 30 Supplierinfo-Zeilen keine belegte `LIEFERPREISE.EKMENGENSCHL`-Quelle haben. Produktstamm, BOM, Lager, Fertigung, Verkauf, Bestandsanzeigen und PLM-Pruefpunkt waren UoM-seitig OK.
- Artikel-/BOM-UoM-Umsetzung 2026-08-24: Enger Umsetzungslauf ohne `LIEFERPREISE` pruefte `ARTIKEL.MENGENSCHL -> product.template.uom_id`, `ARTIKEL.MENGENSCHL -> mrp.bom.product_uom_id` und `PRODINHALT.MENGENSCHL -> mrp.bom.line.product_uom_id`. Ergebnis: 1.255 relevante Datensaetze, 1.255 unveraendert korrekt, 0 Aenderungen, 0 ungeklart. Bericht: `05_doku/ODOO_UOM_ARTIKEL_BOM_UMSETZUNG_20260824.md`.
- UoM-/Mengenbezuege-Umsetzung 2026-08-24: Erweiterter Lauf `99_scripts/185_apply_proven_uom_and_quantity_refs.py` pruefte zusaetzlich `product.supplierinfo.product_uom_id` aus `LIEFERPREISE.EKMENGENSCHL` und Einkaufsauftragspositionen mit Lieferantenbezug. Ergebnis: 849 Datensaetze, 816 unveraendert korrekt, 0 belegte Schreibaktionen, 33 nicht geschrieben. Nicht geschrieben: 30 Supplierinfo-Zeilen ohne belegte `LIEFERPREISE.EKMENGENSCHL`-Quelle und 3 Einkaufspositionen fuer `67887`, weil Einkaufseinheit `STK` gegen Artikelbasiseinheit `m` belegt ist, aber fuer bestehende Odoo-Zeilen kein freigegebener Mengen-/Preisumrechnungsbezug vorliegt. Bericht: `05_doku/ODOO_UOM_MENGENBEZUEGE_UMSETZUNG_20260824.md`.
- Sichtbare STK-UoM-Anzeige 2026-08-24 korrigiert: `MENGENSCHL.LFDNR=0`, `BEZ=STK`, `LBEZ=Stück` wurde auf den deutschen Anzeigenamen von `uom.product_uom_unit` uebertragen. Vorher zeigte Odoo `Einheit(en)`, nach Apply/Read-back `Stück`. Backup: `/var/backups/odoo/kuf-erp-2_20260824_161531_pre_stueck_uom_display_20260824`. Stichproben-Read-back: `67858`, `65940`, `67915`, `68060`, `68091` = `Stück`; `67887` = `m`; `68148` = `kg`. Bericht: `05_doku/ODOO_UOM_STUECK_DISPLAY_UMSETZUNG_20260824.md`.
- Ungenutzte UoM-Dublette 2026-08-24 archiviert: Odoo-UoM ID `33` (`Stück`, keine External-ID) hatte 0 Referenzen in Produktstamm, BOM, BOM-Zeilen und Supplierinfo und wurde nach Backup `/var/backups/odoo/kuf-erp-2_20260824_161936_pre_archive_unused_stueck_uom_duplicate_20260824` archiviert. Der aktive kanonische UoM-Stammsatz bleibt ID `1` / `uom.product_uom_unit` / `Stück`.
- Direkter Produkt-UoM-Rohdatennachweis 2026-08-24: Die Aussage `336 Produktstaemme geprueft / 336 OK` ist durch frische SQL-Abfrage `ARTIKEL -> ARTIKEL.MENGENSCHL -> MENGENSCHL` bestaetigt. Verteilung: 328x `STK / Stueck`, 5x `m / Meter`, 2x `l / Liter`, 1x `kg / Kilogramm`. Die sichtbaren Akustikschaum-Verdachtsartikel `67827`, `67934`, `67935`, `68060`, `68091`, `68092` sind direkt aus eEvolution als `STK / Stueck` belegt; Odoo `Units` ist fuer diese Produkt-UoM korrekt.
- Offene Strukturpunkte aus UoM-Abschlusspruefung: Komponentenprodukte `67894` und `67911` fehlen in Odoo fuer `PRODLIST.LFD_NR=1258`. Das ist kein UoM-Fehler, sondern Produkt-/Stuecklistenvollstaendigkeit.
- Artikel `68148`: Einheit ist direkt belegt als `ARTIKEL.MENGENSCHL=7` / `kg` / `Kilogramm`; warum der Artikel im `kuf-erp-2`-Scope enthalten ist, bleibt eine offene Scope-Entscheidung.
- Vollstaendiger Urlaubstest: `S00012` belegt CRM/Opportunity, Testauftrag, Beschaffung, Wareneingang/QS, Fertigung, Pick/Pack/Out und Seriennummer bis Kunde. Rechnung/Finance bleibt bewusst ausgeklammert.

## H. Datenquellen und Faktenlage

Quellenstandard:

`05_doku/EEVOLUTION_ODOO_MAPPING_STANDARD.md`

Aktuelle Fakten-/Regel-Audits:

- `05_doku/ODOO_PROJEKT_FAKTEN_UND_REGEL_AUDIT_20260824.md`
- `05_doku/FAKTEN_QUELLENREGEL_UND_PIA_SCOPE_AUDIT_20260824.md`
- `05_doku/REGRESSION_ARTIKEL_65940_EINHEITEN_LIEFERANTEN_20260824.md`

Kurzkette fuer haeufige Felder:

| eEvolution-Quelle | Bedeutung | Odoo-Ziel |
|---|---|---|
| `ARTIKEL.DEKPR` | AVCO-Startkostenwert | `product.template.standard_price` |
| `ARTIKEL.LFDLIEFNR` | belegter A-/Hauptlieferant | `product.supplierinfo.sequence=1` |
| `LIEFERPREISE` | aktuelle Lieferantenstammdaten | `product.supplierinfo` |
| `LIEFERPREISE.EKPR / PREISEINHEIT` | normalisierter Lieferantenpreis | `product.supplierinfo.price` |
| `LIEFERPREISE.EKMENGENSCHL` | Einkaufseinheit der Supplierinfo | `product.supplierinfo.product_uom_id` |
| `ARTIKEL.MENGENSCHL` | Artikel-Basis-/Lager-/Produkteinheit | `product.template.uom_id` |
| `PRODINHALT.MENGENSCHL` | Stuecklistenpositions-Einheit | `mrp.bom.line.product_uom_id` |
| `DOCUMENTS.KEYTABLE='ARTIKEL'`, `KEY1=ARTIKEL.LFDNR` | Artikeldokumentbeziehung | `product.document`/DMS-Zuordnung |

## I. Odoo-Sollprozesse

PIA-Wareneingang, QS, interne Vorfertigung, mehrstufige Lagerbewegungen und Serien-/Chargenablauf sind teilweise bewusst definierte Odoo-Sollprozesse. Sie duerfen nicht als historische eEvolution-Fakten dargestellt werden.

Aktuell belegter Sollprozess-Test: `S00012` mit Seriennummer `85342600102` wurde von eEvolution-CRM-Chance ueber Odoo-Opportunity/Testauftrag, PIA-Vollversorgung, Wareneingang/QS, interne Vorfertigungen, Endmontage, Pick/Pack/Out bis `done` und `Customers` durchgespielt. Das ist ein Odoo-Sollprozessnachweis, kein Beweis einer historischen eEvolution-Transaktion.

## J. Preflight

Vor neuen fachlichen oder schreibenden Aufgaben:

```powershell
python 99_scripts/158_project_guardrails_preflight.py
```

Ein roter Preflight ist ein Stopppunkt fuer Rebuild-/Importarbeiten.

## K. Definition of Done

Fuer relevante Aufgaben gilt: Implementierung + Test/Read-back + Dokumentation + Aktualisierung dieses Projektgedaechtnisses. Wenn eine Aufgabe nur analysiert, gilt entsprechend: Analysebeleg + Quellen + Status im passenden Register.

## L. Initiale Regressionstests

Diese Themen muessen im Projektgedaechtnis/Guardrail wiedererkennbar sein:

| Test | Erwartung |
|---|---|
| Supplierinfo | `BESTELLUNG`-Ansatz ist `ERSETZT`; `LIEFERPREISE` ist `AKTIV`. |
| Lieferanten A/B/C | A ist belegt; B/C duerfen nicht erfunden werden. |
| Einkaufseinheiten | `EKMENGENSCHL` ist relevante Quelle; Gebinde/Faktor bleiben offen. |
| Artikel-/BOM-Einheiten | Kein Default `Unit`: Produkt aus `ARTIKEL.MENGENSCHL`, BOM-Zeile aus `PRODINHALT.MENGENSCHL`; unklarer Wert muss blockieren. |
| Kosten | `DEKPR` ist AVCO-Startwert; `EKPR` ist kein Kostenfallback. |
| PIA-Scope | Scope ist dokumentiert, Reviewfaelle bleiben offen. |
| Odoo-Sollprozesse | Neue QS-/Lager-/Serienprozesse sind Sollentscheidungen, keine eEvolution-Historie. |
# Ergänzung 15.09.2026 – PIA Produktions-Drilldown

- `kuf-erp-2`: `kf_legacy_migration` 19.0.6.1.0, rein informative Legacy-Produktionsaufträge.
- 410 Aufträge, 18.071 eindeutige Ist-Komponentenbuchungen, 785 Ausgabeserien/-chargen, 2.591 verknüpfte Produktionsereignisse.
- Serien-/Chargenkopf zeigt ursprünglichen Kunden, Auftrag, Lieferschein und Versanddatum; Regel: erster nicht stornierter Ausgangs-Lieferschein, Auftrag nur Fallback.
- Rückwärts-Drilldown Komponentennummer/Charge → PIA-Endprodukt: 671 Bezüge, davon 663 aus gleichem Buchungslauf und 8 reine Auftragskandidaten. Golden Case Charge `22.05.2026`: 24 zeitlich zugeordnete und klickbare PIA-LFX-Endseriennummern; 9 ältere Ausgaben derselben Sammelaufträge ausgeschlossen.
- Sichtbare Ereignisdaten werden vollständig als `TT.MM.JJJJ` ausgegeben; originale Zeitstempel bleiben intern erhalten.
- Keine operativen Odoo-Bewegungen oder Buchungen erzeugt. Auftragsverbrauch nicht ungeprüft einem einzelnen Endgerät zuordnen.
- Sicherung der Erweiterung: `/var/backups/odoo/kuf-erp-2_20260915_121111_pre_charge_finished_serial_drilldown_20260915`.
- Detailprotokoll: `05_doku/PIA_PRODUKTION_DRILLDOWN_KUF_ERP_2_20260915.md`.

# Ergänzung 15.09.2026 – PIA Rückruf- und Mehrkundensicht

- `kuf-erp-2`: `kf_legacy_migration` 19.0.6.2.1.
- Serien-/Chargenköpfe zeigen getrennt (a) Einbau in Endserien samt deren
  ursprünglichem Kunden/Lieferschein und (b) alle direkten, nicht stornierten
  Serien-/Chargenlieferungen samt Kunde, Lieferschein, eEvolution-Auftrags-ID und
  Menge.
- Kopfzähler: direkte Lieferungen sowie eindeutige betroffene Kunden; der
  `Ursprüngliche Kunde` ist nur der erste Versand und keine vollständige
  Rückrufliste.
- Prüffall `8G121125037` / Artikel 5037: keine Produktionsverbrauchsbuchung,
  6 direkte Lieferscheine über 18 Stück an 5 Kunden. Produktion 265137/265901
  sind Chargenzugänge und dürfen nicht als Einbau interpretiert werden.
- Gesamt: 987 direkte Lieferbeziehungen; idempotenter Wiederholungslauf 0 neue
  Datensätze; keine operativen oder buchhalterischen Auswirkungen.
- Sicherung: `/var/backups/odoo/kuf-erp-2_20260915_125829_pre_lot_recall_customer_view_20260915`.

# Ergänzung 15.09.2026 – Fertig-Einlagerungscharge im Produktionsauftrag

- `kuf-erp-2`: `kf_legacy_migration` 19.0.6.3.2.
- Produktionsausgaben kommen bevorzugt aus `PRODAUFSERIEN` und
  `PRODAUFCHARGEN`; fehlt dort die Charge, wird sie dublettengeschützt aus
  `PRODAUFEINLAGERN` übernommen.
- Prüffall `P-265960`: Charge `P-265960`, Menge 57, Einlagerung 18.08.2026;
  exakt eine Ausgabe und klickbare Legacy-Rückverfolgung.
- Produktionsformular auf volle Bildschirmbreite erweitert; Ausgabeanzahl im
  Kopf; Reiter `Produzierte Seriennummern / Chargen`.
- Alle sichtbaren Produktions- und Tabellenzeitpunkte im Format `TT.MM.JJJJ`;
  technische Originalzeitstempel unverändert.
- Gesamt: 987 Produktionsausgaben, 750 abgeleitete Endproduktbezüge;
  Wiederholungslauf ohne Änderungen und ohne operative Auswirkungen.
- Sicherung: `/var/backups/odoo/kuf-erp-2_20260915_130638_pre_production_output_lot_fullwidth_dates_20260915`.

# Ergänzung 15.09.2026 – Legacy-UI-Bedienelemente

- `kf_legacy_migration` 19.0.6.4.0 korrigiert die Vollbreite am tatsächlichen
  Odoo-Container `.o_form_sheet_bg`.
- Odoo-Iconfonts sind serverseitig erreichbar und fehlerfrei; das Custom-Asset
  enthält einen absoluten Font-Fallback gegen veraltete relative Browserpfade.
- Keine relevanten Asset-/SCSS-/Fontfehler im Serverprotokoll; Browser muss den
  neuen Backend-Asset-Hash laden.
- Sicherung: `/var/backups/odoo/kuf-erp-2_20260915_131753_pre_legacy_ui_controls_cleanup_20260915`.
- Nachkorrektur `19.0.6.4.1`: Vollbreitenanker liegt direkt am gerenderten
  `<sheet>`; Serien-/Chargen- und Produktionsformular werden beide erfasst.

# Ergänzung 15.09.2026 – Allgemeine Rückverfolgung

- `kf_legacy_migration` 19.0.7.0.0: Anwendung heißt `Rückverfolgung`.
- Zwei Hauptbereiche `Seriennummern` und `Chargennummern`; jeweils getrennte
  Einstiege `eEvolution-Historie` und `Odoo aktuell`.
- Neue operative Odoo-Nummern bleiben ausschließlich in `stock.lot` und den
  nativen Lager-/MRP-Beziehungen; keine Schattenkopie in `kf.legacy.trace`.
- Historische Liste ohne redundante eEvolution-Artikelbezeichnung; allgemeine
  `Produktrolle` mit `Endprodukt`/`Komponente`; Zusatzspalten optional.
- Bestände: historisch 1.113 Serien / 163 Chargen, nativ 106 Serien / 65 Chargen.
- Sicherung: `/var/backups/odoo/kuf-erp-2_20260915_134053_pre_generic_trace_navigation_20260915`.

# Ergänzung 15.09.2026 – Vollsicherung und Rebuild-Lücken-Audit

- Neue verifizierte Vollsicherung:
  `/var/backups/odoo/kuf-erp-2_20260915_152716_full_before_rebuild_gap_analysis_20260915`
  (`database.dump` 29.132.203 Byte, `filestore.tar.gz` 41.252.003 Byte).
- Vollständige Restore-Probe in temporärer Datenbank erfolgreich; sieben
  Kontrollzähler einschließlich Benutzer, Mitarbeiter, Legacy-Traceability und
  `account.move.line` identisch; temporäre Datenbank danach entfernt.
- Datenbankvergleich gegen den Abschlussstand 24.08.2026 und die unmittelbar
  vorherige Sicherung 15.09.2026 durchgeführt; Rohbefund:
  `outputs/odoo_rebuild_gap_audit_20260915.json`.
- Rebuild-Manifest auf `kf_odoo_complete_pilot_rebuild_v3` aktualisiert:
  `kf_legacy_migration` 19.0.7.0.0, neuere installierte Hauptmodule,
  Pflichtmodelle der Rückverfolgung, Los-/Serienbewertung und PIA-Legacy-Schritt.
- Read-only-Rebuild-Verifikation danach `PREFLIGHT_OK`.
- Noch offen vor Gesamt-Rehearsal: vollständiger Lagerplatzimport statt nur
  K-16-A, Generalisierung der Lager-Skripte auf eine neue freigegebene DB,
  Traceability über den PIA-Scope hinaus, Ablösung der alten nativen
  Legacy-Schritte 22/27 sowie generalisierte Benutzerübernahme.
- Benutzerentscheidung `REGEL-023`: alle menschlichen internen und externen
  Konten einschließlich Mitarbeiterzuordnung, Firmen und Rechten übernehmen;
  vorhandene Kennwort-Hashes ohne Klartextzugriff erhalten. Systemkonten,
  Sitzungen, API-Schlüssel und Zugriffstoken nicht ungeprüft kopieren.
- Detailnachweis:
  `05_doku/ODOO_REBUILD_LUECKEN_AUDIT_UND_VOLLSICHERUNG_20260915.md`.

# Ergänzung 16.09.2026 – Gesamtartikelstamm in `kuf-erp-all-data`

- Benutzerentscheidung `REGEL-025`: alle 5.971 nicht löschmarkierten Artikel
  importieren; davon 4.196 aktiv und 1.775 mit eEvolution-`INAKTIV<>0` als
  archivierte Referenzartikel (`active=False`, `sale_ok=False`,
  `purchase_ok=False`).
- Begründung aus Live-Auswirkungsanalyse: Ein vollständiger Ausschluss hätte
  unter anderem 67 aktive Stücklistenartikel/155 Positionen sowie zahlreiche
  historische Beleg-, Produktions- und Rückverfolgungsrelationen getrennt.
- Produktimport nach `kuf-erp-all-data` abgeschlossen: 5.971 stabile
  `__import__.ev_product_<LFDNR>`-External-IDs; Read-back/Dry-run danach
  `create=0`, `update=0`, `keep=5971`, `blocked=0`.
- Kategorien und Produktrollen wurden anschließend für alle 5.971
  eEvolution-Produkte gesetzt; drei Odoo-Systemprodukte blieben unberührt.
- Sicherungen mit erfolgreicher Restore-Probe:
  `/var/backups/odoo/kuf-erp-all-data_20260916_020102_pre_product_master_20260916`
  und
  `/var/backups/odoo/kuf-erp-all-data_20260916_020606_post_product_pre_roles_20260916`.

# Ergänzung 16.09.2026 – Partnerergänzungen, Preislisten und Stücklisten

- Partnerstamm in `kuf-erp-all-data`: 6.021 ADRESS-zentrierte Firmen-/Adresssätze,
  9.393 Ansprechpartner und 3.189 Lieferadressen; Wiederholungs-Dry-run ohne Änderungen.
- 462 formal eindeutige USt-IDs sind idempotent übernommen; eine von Odoo akzeptierte
  ungewöhnliche Quellschreibweise bleibt als solche gekennzeichnet. 22 ungültige Formate
  und drei widersprüchliche Kunden-/Lieferantenwerte bleiben blockiert.
- Supplierinfo: 5.196 Beziehungen aus `LIEFERPREISE`, danach 5.196 `KEEP`; 17 fachlich
  unklare Währungs-/Einheitenfälle bleiben blockiert.
- Verkaufspreislisten: 12 Preislisten, 1.945 Rabattpositionen und 787 Kundenzuordnungen;
  Wiederholungs-Dry-run `0` Änderungen. Ein nicht zuordenbarer RABATTMATRIX-Satz sowie
  nicht auflösbare Altartikel-/Leergruppenbezüge bleiben ausgewiesen.
- `kf_legacy_migration` 19.0.8.0.0 bewahrt eEvolution-Textpositionen an `mrp.bom`.
- PRODLIST: 1.464 Stücklisten und 21.635 Komponentenpositionen importiert; 603
  Text-/Montagehinweise erhalten. 17 Stücklisten mit negativen Quellmengen vollständig
  blockiert. Neueste datierte Revision aktiv, ältere Revisionen archiviert.
- Stücklisten-Wiederholungs-Dry-run: 1.464 Köpfe und 21.635 Zeilen unverändert, keine
  Creates/Updates. Eine Quellmenge `0,077` wird entsprechend Odoo-UoM-Rundung operativ
  als `0,08` gespeichert und zusätzlich im Herkunftshinweis exakt dokumentiert.
- Restore-geprüfte Sicherungen:
  `/var/backups/odoo/kuf-erp-all-data_20260916_110325_pre_partner_vat_20260916`,
  `/var/backups/odoo/kuf-erp-all-data_20260916_111033_pre_pricelists_20260916`,
  `/var/backups/odoo/kuf-erp-all-data_20260916_111846_pre_bom_legacy_notes_module_20260916`,
  `/var/backups/odoo/kuf-erp-all-data_20260916_112259_pre_bom_master_20260916`.
- Detailnachweis: `05_doku/GESAMTIMPORT_STAMMDATENBLOCK_KUF_ERP_ALL_DATA_20260916.md`.

# Ergänzung 16.09.2026 – Lagergrundstruktur in `kuf-erp-all-data`

- Die bestätigte Lagergrundstruktur wurde nach Restore-geprüfter Sicherung
  `/var/backups/odoo/kuf-erp-all-data_20260916_115217_pre_confirmed_warehouse_scaffold_20260916`
  idempotent aufgebaut: VIDA, B-Ware, Demoware, Showroom, Gang K, Fach 16 und
  Endplatz `K-16-A`.
- Read-back an den neuen Orten: 0 Quants, 0 Bewegungen, 0 Lagerregeln und
  0 Verräumregeln; Wiederholungs-Dry-run ohne Änderungen.
- Vollständige Lagerplätze bleiben fachlich blockiert: aktueller Live-Stand
  1.103 logische Plätze, 71 lagerübergreifende Barcode-Dublettengruppen,
  23 Sammelplatzkandidaten, 8 Schreibvariantengruppen und 17 unvollständige
  Artikel-Platz-Zuordnungen.
- Nachweis: `05_doku/LAGERGRUNDSTRUKTUR_KUF_ERP_ALL_DATA_20260916.md`.

# Ergänzung 16.09.2026 – Module, Identitäten und CRM in `kuf-erp-all-data`

- Modulparität zur Referenz `kuf-erp-2` hergestellt: 313/313 installierte Module;
  PostgreSQL-Erweiterung `vector` 0.6.0 in der Ziel-DB aktiviert und geprüft.
- Gesellschaft auf `KLING & FREITAG GmbH` übertragen; 11 aktive eingerichtete
  Benutzer mit identischen Modulrechten und Kennworthashes sowie 34 Mitarbeiter
  übernommen. Klartextkennwörter, API-Schlüssel, Sitzungen und Token wurden nicht kopiert.
- CRM: 1.364 Chancen mit stabilen External IDs importiert, davon 361 aktiv und
  1.003 archiviert. Kunden-, Produktinteresse- und historische Verantwortlichenfelder
  sind vollständig; 51 Chancen sind dem einzig eindeutig vorhandenen Odoo-Verkäufer
  Niklas Goslar zugeordnet, 1.313 bleiben ohne erfundene Odoo-Zuständigkeit.
- Abgeschlossene CRM-Historie: 84.467 Ereignisse als datierte `mail.message`
  übernommen; 0 offene Aktivitäten. Drei technische Bestellereignisse ohne Adresse
  oder Chance sind bewusst für den Einkaufsbelegblock abgegrenzt.
- Wiederholungs-Dry-runs: 0 neue Chancen und 0 neue CRM-Historienereignisse.
- Nachweis: `05_doku/CRM_GESAMTIMPORT_KUF_ERP_ALL_DATA_20260916.md`.

# Ergänzung 16.09.2026 – 3D-Gesamtprüfung und Stichtagsdrift

- Read-only-Gesamtprüfung über Objektmengen, Relationen, Zeitfenster und operative
  Nebenwirkungen durchgeführt. Artikel, Partnerkinder, Preislisten, sichere Stücklisten,
  Einkaufshistorie und Rückverfolgung stimmen zum dokumentierten Importsnapshot.
- eEvolution läuft weiter: nach dem Importsnapshot wurden am 16.09.2026 eine neue
  CRM-Chance und zwei noch nicht erledigte Verkaufsbelege angelegt. Sie wurden bewusst
  nicht still nachimportiert.
- Tagesdatum allein ist kein reproduzierbarer oberer Cutoff. Vor weiteren zeitabhängigen
  Imports muss die Reichweite der Zehnjahresregel sowie ein exakter oberer Zeitstempel mit
  Quellschlüssel-Obergrenzen festgelegt werden (`OFFEN-009`).
- Nachweis: `05_doku/3D_GESAMTPRUEFUNG_MIGRATION_KUF_ERP_ALL_DATA_20260916.md`;
  Prüfer: `99_scripts/247_audit_migration_3d.py`.

# Ergänzung 16.09.2026 – Verbindlicher Umfang Hauptbelege und Produktionsdetails

- Benutzerentscheidung `REGEL-028`: Verkaufsbelege, Lieferscheine, Einkaufsbelege,
  Produktionsauftragsköpfe, Ausgangsrechnungen und Eingangsrechnungen werden mit ihren
  Belegpositionen über die vollständige belegte eEvolution-Historie übernommen.
- Technische Serien-/Chargenrückverfolgung und Produktionsdetails bleiben auf zehn Jahre
  begrenzt. Ältere Produktionsaufträge werden nur als informative Köpfe übernommen.
- Einzelne Lagerbuchungen werden nicht operativ nachgebaut. Historische Rechnungen bleiben
  schreibgeschützte Legacy-Referenzen ohne `account.move`, offene Posten oder Buchungssatz.
- CRM-Freitext/-Terminhistorie vor dem Zehnjahresfenster ist nicht Teil dieser
  Hauptbelegentscheidung und bleibt zusammen mit dem exakten oberen Cutoff in `OFFEN-009`.
- Mengennachweis: `99_scripts/248_audit_full_history_scope_delta.py`.

# Ergänzung 16.09.2026 – Go-live 01.01.2027 und Schulungsstand

- Benutzerentscheidung `REGEL-029`: Go-live zum 01.01.2027; produktiver Cutoff ist
  exklusiv `2027-01-01 00:00:00 Europe/Berlin`, also einschließlich aller freigegebenen
  Geschäftsdaten bis Ende 31.12.2026.
- Das Zehnjahresfenster für technische Rückverfolgung und Produktionsdetails ist fest
  `2017-01-01 00:00:00` inklusive bis `2027-01-01 00:00:00` exklusiv.
- Nach vollständigem Rehearsal wird eine unveränderliche, restore-getestete Golden-Backup-
  Sicherung erstellt. Test und Schulung finden ausschließlich in einer daraus erzeugten,
  neutralisierten Kopie statt.
- Die Schulungsdatenbank wird nicht produktiv gesetzt. Produktiv wird mit identischen
  Modulen, Mappings und Importskripten reproduzierbar neu aufgebaut; der finale Lauf folgt
  nach eEvolution-Freeze und umfasst Cutover-Bestand, echte offene Vorgänge und
  finance-freigegebene Eröffnungen.
- Ablauf: `05_doku/CUTOVER_UND_SCHULUNGSPLAN_GO_LIVE_20270101.md`.

# Ergänzung 16.09.2026 – Probeimport-Freigabe und Delta-Anker

- Der vollständige Probeimport ist ausschließlich für die neutralisierte Datenbank
  `kuf-erp-all-data` freigegeben (`REGEL-030`).
- Die Sicherung
  `/var/backups/odoo/kuf-erp-all-data_20260916_160506_pre_authorized_full_rehearsal_retry_20260916`
  enthält PostgreSQL-Dump und Filestore; die Wiederherstellung wurde mit 1.447
  Moduldatensätzen erfolgreich geprüft.
- Vorab-Metriken: 0 ungesperrte historische `sale.order`, 0 `stock.move`,
  0 `account.move`, 0 `account.move.line`.
- Der maschinenlesbare Delta-Anker enthält für 19 eEvolution-Haupttabellen mindestens
  Zeilenanzahl und, soweit technisch vorhanden, maximalen Geschäftsschlüssel,
  Rowversion und Zeitstempel. `MAX(LFDNR)` allein reicht nicht aus, weil Änderungen an
  bestehenden Sätzen sonst unentdeckt blieben.
- Der finale Cutover, Produktionswrites und eEvolution-Writes sind nicht freigegeben.
- Zielnamensraum für eEvolution-External-IDs ist `eevolution` (`REGEL-031`). Bestehende
  `__import__`-Bindings werden erst kontrolliert migriert beziehungsweise kompatibel
  aufgelöst; keine isolierte String-Änderung während des laufenden Probeimports.
