# Gesamtbericht Datenbestand `kuf-erp-all-data`

Stand: 16.09.2026
Zweck: belastbarer Zwischenstand des vollständigen eEvolution-Imports in die neutralisierte
Odoo-Rehearsal-Datenbank.

## Kurzfazit

Die Datenbank enthält die für den bisherigen Migrationsstand vorgesehenen Stammdaten,
Benutzer/Mitarbeiter, CRM-Daten, historischen Verkaufsbelege und nun auch die vollständige
Serien-/Chargenhistorie der letzten zehn Jahre. Die zuvor leere Ansicht war ein
Zwischenstand vor dem Vollimport.

Der Rückverfolgungsblock ist mengenmäßig vollständig abgeglichen: **322.386 von 322.386
Quellereignissen** und **49.472 von 49.472 Serien-/Chargenköpfen** sind in Odoo vorhanden.
Die Wiederholung des Vollimports erzeugte in allen sieben Legacy-Objektarten **0 neue
Datensätze**. Es wurden keine operativen Lagerbewegungen, Rechnungen oder Buchungssätze
erzeugt.

## Vorhandener Datenbestand

| Bereich | In Odoo vorhanden | Einordnung |
|---|---:|---|
| Installations-/Modulstand | 313 / 313 | Parität zur bisherigen Referenzdatenbank |
| Artikel | 5.971 | aktive und inaktive Artikel; inaktive bleiben archiviert |
| Partner | 6.021 | Kunden und Lieferanten |
| Ansprechpartner | 9.393 | den Partnern zugeordnet |
| Lieferadressen | 3.189 | Partnerstamm |
| Lieferanten-Artikelbeziehungen | 5.196 | Supplierinfo |
| Preislisten | 12 | mit 1.945 Preisregeln und 787 Kundenzuordnungen |
| Stücklistenköpfe | 1.464 | 21.635 Komponenten und 603 historische Textpositionen |
| Aktive Odoo-Benutzer | 11 | einschließlich übernommener Kennwort-Hashes |
| Mitarbeiter | 34 | Benutzer-/Mitarbeiterbezug geprüft |
| CRM-Chancen | 1.364 | historische Vertriebsfälle |
| CRM-Historienereignisse | 84.467 | informativ, ohne operative Folgeaktion |
| Historische Verkaufsbelege | 7.992 | gesperrt und rein informativ |
| Verkaufsbelege in Prüfliste | 6.164 | vollständige Quellpositionen bewahrt, aber nicht als operative Aufträge angelegt |
| Historische Einkaufsbelege | 8.739 | 18.018 Positionen, rein informativ und schreibgeschützt |
| Serien-/Chargenköpfe | 49.472 | 43.626 Seriennummern, 5.846 Chargen |
| Historische Serien-/Chargenereignisse | 322.386 | 264.546 Serien- und 57.840 Chargenereignisse |
| Legacy-Produktionsaufträge | 7.784 | rein informativ |
| Tatsächliche Komponentenbuchungen | 251.767 | Produktionsauftragsebene |
| Produzierte Serien/Chargen | 31.580 | Ausgabe der Legacy-Produktionsaufträge |
| Abgeleitete Verwendungsbeziehungen | 178.603 | Komponente/Charge zu Endserie/-charge |
| Direkte Liefernachweise | 41.112 | alle mit aufgelöstem Kunden |

## Rückverfolgung: Was belastbar funktioniert

- Suche nach Seriennummer und Chargennummer in getrennten Odoo-Menüs.
- Drilldown vom Serien-/Chargenkopf auf alle historischen Ereignisse.
- Drilldown auf den informativen eEvolution-Produktionsauftrag mit tatsächlich gebuchten
  Komponenten sowie produzierten Serien und Chargen.
- Rückwärtsverfolgung vom Endprodukt auf verbaute Serien/Chargen.
- Vorwärtsverfolgung von einer Komponentencharge auf produzierte Endserien/-chargen und,
  soweit der Lieferbezug vorhanden ist, auf Kunde, Auftrag und Lieferschein.
- Direkte Lieferung einer Charge oder Seriennummer als Ersatzteil mit Kunde und
  Lieferschein.
- Inaktive Artikel bleiben als archivierte Odoo-Artikel verknüpft; die Historie wird nicht
  verworfen.
- Datumsanzeige im Format `TT.MM.JJJJ` ohne störende Uhrzeit in den Übersichten.

Die Stichprobe der Charge `22.05.2026` (eEvolution-Artikel-ID 5.111) ergibt 24
Endseriennummern. Alle 24 Beziehungen beruhen auf demselben belegten Buchungslauf.

Im Abschlussaudit wurden 112 inaktive Artikel erkannt, deren Varianten Odoo bei der
Standardauflösung zunächst ausgeblendet hatte. Daraufhin wurden 3.206 Serien-/Chargenköpfe,
225 Legacy-Produktionsaufträge und 1.652 Komponentenbuchungen mit den bereits vorhandenen
archivierten Odoo-Artikeln verknüpft. Danach verbleiben **0 Serien-/Chargenköpfe ohne
Odoo-Artikelbezug**.

## Datenqualität und fachliche Grenzen

| Befund | Anzahl | Bedeutung / Maßnahme |
|---|---:|---|
| Serien-/Chargenköpfe mit Prüfkennzeichen | 17.457 | Kennzeichnung, keine Sperre der Historie |
| Nummern, die bei mehreren eEvolution-Artikeln vorkommen | 5.964 | absichtlich nicht zusammengeführt; Artikelbezug beachten |
| Ereignisse ohne bekannten eEvolution-Typtext | 5.702 | Quellcode/Quelltext ist erhalten; Typbezeichnung fachlich ergänzen |
| Verwendungen „gleicher Buchungslauf“ | 178.175 | stärkste ableitbare Zuordnung |
| Verwendungen nur „gleicher Produktionsauftrag“ | 428 | Kandidat, keine sichere Einzelgerätezuordnung behaupten |
| Produktionsausgaben ohne passenden Rückverfolgungskopf im 10-Jahres-Fenster | 281 | Produktionsausgabe bewahrt; Serien-/Chargenereignis fehlt im gewählten Zeitraum |
| Ereignisse vor dem Stichtag, bewusst nicht übernommen | 552.821 | außerhalb der vereinbarten zehn Jahre |

`Prüfung erforderlich` bedeutet daher nicht, dass der Datensatz unbrauchbar ist. Es
bedeutet, dass mindestens eine Mehrdeutigkeit aus der Quelle sichtbar bleibt, zum Beispiel
dieselbe Nummer bei mehreren Artikeln oder ein unbekannter eEvolution-Ereignistyp.

## Was noch nicht importiert beziehungsweise bewusst nicht operativ ist

1. **Historische Einkaufsbelege:** vollständig als wirkungsfreie Legacy-Belege übernommen;
   513 Belege tragen ein sichtbares Prüfkennzeichen.
2. **Historische Haupt-Lagerbelege:** Lieferscheine und weitere Hauptdokumente sind in der
   Rückverfolgung referenziert, aber noch nicht als operative Odoo-Lagerbelege angelegt.
3. **Historische Rechnungen und Eingangsrechnungen:** noch nicht als rein informative,
   vollständig erledigte Belege übernommen. Sie dürfen später keine Buchungssätze erzeugen.
4. **Einzelne Lagerbuchungen:** werden entsprechend der Vorgabe nicht als operative
   Odoo-Buchungen übernommen. Für die geplante Lagerhistorie gilt zusätzlich das bestätigte
   Fünfjahresfenster; Serien-/Chargen- und allgemeine Beleggeschichte verwenden zehn Jahre.
5. **Vollständige physische Lagerplätze:** nur die bestätigte Lagergrundstruktur ist
   eingerichtet. Der Vollimport bleibt wegen Barcode-Dubletten, Sammelplatzkandidaten und
   Schreibvarianten bis zur Fachentscheidung gesperrt.
6. **Eröffnungsbestände und Lagerbewertung:** erst zum Go-live-Stichtag; im Rehearsal nicht
   erzeugt.
7. **Buchhaltungs-Cutover:** Konten-/Steuerkonzept und offene Posten folgen dem gesonderten
   Finance-Plan.

## Weitere offene Prüflisten

- 17 Stücklistenköpfe mit negativen Quellmengen bleiben gesperrt.
- 22 USt-ID-Formatfehler und 3 widersprüchliche USt-IDs bleiben zur fachlichen Klärung
  gesperrt.
- 6.164 historische Verkaufsbelege befinden sich in der Prüfliste. Darin enthalten sind
  4.661 Köpfe ohne gültige Position, 69 unvollständige abweichende Lieferadressen und 1.439
  weitere Belege mit mindestens einem heute nicht mehr auflösbaren historischen
  Artikelbezug; die Kategorien können sich überschneiden.
- 6 historische CRM-Verantwortliche besitzen kein Odoo-Konto; 3 Bestellereignisse haben
  kein CRM-Ziel.

## Technische Sicherheitsnachweise

- eEvolution wurde ausschließlich read-only gelesen.
- Ziel war ausschließlich `kuf-erp-all-data`.
- Zeitfenster der Rückverfolgung: 16.09.2016 bis einschließlich 16.09.2026.
- Mengenabgleich: Quelle und Odoo stimmen bei Köpfen und Ereignissen exakt überein.
- Idempotenztest nach dem Vollimport: überall 0 Neuanlagen.
- Nebenwirkungsprüfung nach dem Import: `stock.picking = 0`, `stock.move = 0`,
  `account.move = 0`; die vorhandenen 115 Maildatensätze wurden nicht durch diesen Import
  erzeugt.
- Das additive Modul `kf_legacy_migration` speichert die Historie in eigenen Modellen; der
  Odoo-Originalquellcode wurde nicht verändert.
- Restore-getestete Abschlusssicherung:
  `/var/backups/odoo/kuf-erp-all-data_20260916_142225_post_full_traceability_import`.

## Empfohlene nächste Reihenfolge

1. Haupt-Liefer- und Produktionsbelege vervollständigen, ohne einzelne operative
   Lagerbuchungen nachzubauen.
2. Ausgangs- und Eingangsrechnungen als erledigte, rein informative Legacy-Belege
   übernehmen; Buchungssätze explizit technisch verhindern und prüfen.
3. Den vereinbarten Lagerbelegblock der letzten fünf Jahre ergänzen.
4. Alle Prüflisten fachlich abarbeiten und danach einen erneuten Vollabgleich ausführen.
5. Erst am Go-live-Stichtag Bestände, Bewertungen und buchhalterische Eröffnungen laden.

## Quellen

- eEvolution: `dbo.ARTIKEL`, `dbo.SNRARCHIV`, `dbo.CHARGENARCHIV`, `dbo.SNREFTYP`,
  `dbo.PRODUKTION`, `dbo.PRODAUFINHIST`, Produktions-Serien-/Chargenausgaben sowie die
  Vertriebs-, Partner-, Preis- und Stücklistentabellen.
- Odoo: `product.template`, `res.partner`, `res.users`, `hr.employee`, `crm.lead`,
  `sale.order` und die additiven Modelle `kf.legacy.*`.
- Technischer Prüflauf: `99_scripts/244_audit_full_traceability_import.py`.
- Importlauf: `99_scripts/198_import_pia_legacy_traceability.py`.

## Weiterführende Fragen

- Sollen die 5.702 unbekannten Ereignistypen mit der Fachabteilung katalogisiert und in
  verständliche Bezeichnungen übersetzt werden?
- Reicht für die 428 Kandidaten die Kennzeichnung „gleicher Produktionsauftrag“, oder gibt
  es eine zusätzliche eEvolution-Quelle für eine sichere Einzelgerätezuordnung?
- Sollen die 281 Produktionsausgaben ohne Ereigniskopf als eigenständige historische
  Serien-/Chargenköpfe sichtbar gemacht werden, obwohl im vereinbarten Zeitraum kein
  passendes Archivereignis vorliegt?
