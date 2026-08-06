# Odoo 19 - Soll-Ist-Abgleich zum Pflichtenheft

Stand: 06.08.2026, nach Modulinstallation und Customizing  
Prüfobjekt: Testdatenbank `erp-test-1` (gesichert, angepasst und erneut geprüft)  
Primärquelle: `Pflichtenheft – Einführung eines ERP-Systems.pdf`, 6 Seiten, Stand 25.11.2025.

## Management-Ergebnis

Die technische Basis und die Kernanwendungen CRM, Verkauf, Einkauf, Lager, Fertigung,
Werkstatt, Projekt, Planung, Barcode und Buchhaltung sind vorhanden. Die Testdatenbank
ist jedoch noch **nicht abnahme- oder go-live-fertig**. Wesentliche Pflichtheft-Bausteine
sind unvollständig oder ungeprüft: Versanddienstleister, DATEV/GoBD-Prozess,
fachliche Prüfpläne, vollständige Lager-/Fertigungsstammdaten,
Rollen/Rechte, E-Mail, Beleglayouts, Performance-, Integrations- und Abnahmetests.

Technisch installiert sind inzwischen Qualität in Fertigung und Shop Floor,
Fremdfertigung, Einkaufsvereinbarungen, Versandmethoden, deutsche Lokalisierung,
UBL/CII-E-Rechnung, Peppol sowie die beiden K&F-Add-ons. Die Installation allein ist
noch kein fachlicher Abnahmenachweis.

Die ältere Datei `ODOO_CUSTOMIZING.md` beschreibt zum Teil einen früheren Probelauf und
darf nicht mehr als Nachweis des aktuellen Datenbankstands verwendet werden.

## Verbindliche Migrations- und Buchhaltungsregel

- Historische Vorgänge werden nur als abgeschlossene, gesperrte Referenz übernommen.
- Aus historischen Verkäufen und Einkäufen dürfen keine Lieferungen, Beschaffungen,
  Reservierungen oder sonstigen operativen Folgeprozesse entstehen.
- Historische Rechnungen dürfen in Odoo nicht als echte offene Posten erscheinen.
- Der Standard-Migrationslauf importiert **keine** OP aus `OP_DEBITOR` oder `OP_KREDITOR`.
- Echte offene Debitoren/Kreditoren sowie Eröffnungssalden werden ausschließlich zum
  Go-live-Stichtag aus einer von der Buchhaltung freigegebenen Cutover-Datei angelegt.
- Der alte direkte SQL-Eingriff in `payment_state`, Restbeträge und Abstimmungsfelder ist
  deaktiviert. Buchhalterische Abschlüsse müssen über reguläre Odoo-Buchungen erfolgen.

## Aktueller Ist-Stand der Testdatenbank

| Bereich | Nachweis 06.08.2026 | Bewertung |
|---|---:|---|
| Unternehmen / Sprachen / Währungen | 1 / 2 / 2 | Basis vorhanden |
| CRM-Stufen | 4 | Abweichung zur früher dokumentierten Zahl 9 |
| Lager / Lagerorte / Vorgangsarten | 1 / 13 / geprüft | 3-stufiger Ein- und Ausgang sowie Vor-/Nachproduktion eingerichtet |
| Arbeitsplätze / Stücklisten | 0 / 0 | Fertigung fachlich noch nicht eingerichtet |
| Qualitätsprüfpunkte | 0 | Module vorhanden; Prüfpläne fachlich noch zu definieren |
| Seriennummerngruppen | 16 | Präfix, ISO-Woche/Jahr und permanente Gruppenfolge eingerichtet |
| Verkauf / Einkauf / Rechnungen | jeweils 0 operative Datensätze | sauberer Ausgangszustand |
| offene gebuchte Rechnungen | 0 | entspricht aktueller Vorgabe |

## Modulprüfung

| Pflichtenheft-Bereich | Installiert | Noch erforderlich |
|---|---|---|
| CRM | ja | 9 Zielstufen, Leads, E-Mail, Dubletten- und Rechtekonzept prüfen |
| Verkauf | ja | Rahmenaufträge, Projektfluss, DE/EN-Belege, Vorschau, CI testen |
| Einkauf | ja | `purchase_requisition` installiert; 3-Wege-Abgleich fachlich testen |
| Lager | ja | vollständige Lagerhierarchie, Scannerabläufe, Pick/Pack testen |
| Barcode | ja | Geräte-, Etiketten- und Code-128-Test fehlt |
| Fertigung | ja | Arbeitsplätze, Stücklisten, Arbeitsgänge, Planung aufbauen |
| Werkstatt | ja | Rückmeldungen und CS6-Seriennummern testen |
| Fremdfertigung | ja | `mrp_subcontracting` installiert; Prozess und Beistellteile abnehmen |
| Qualität | ja | Quality, MRP Quality und Shop Floor Quality installiert; Prüfpläne/QC-Labels definieren |
| Projekt / Planung | ja | Feinplanung und Projektbezug fachlich konfigurieren |
| Buchhaltung / deutsche Lokalisierung | ja | DATEV-Modulstand, Konten, Steuern und Go-live-Cutover freigeben |
| DATEV / EDI | UBL/CII und Peppol installiert | DATEV-Funktion über deutsche Reports sowie E-Rechnung separat nachweisen |
| Versandmethoden | ja | Odoo-Basismodul `delivery` installiert |
| DHL / UPS / FedEx | nein | Connectorwahl, Verträge, Zugangsdaten, Testlabels und Tracking fehlen |

Hinweis: Die erwarteten Module `l10n_de_skr03` und `l10n_de_datev` wurden unter diesen
technischen Namen in der Odoo-19-Modulliste nicht gefunden. Vor einer Bewertung ist zu
klären, ob Odoo 19 diese Funktionen in andere deutsche Enterprise-Module integriert hat.

## Seriennummern nach Produktgruppe

Die umgesetzte Lösung erweitert `product.category`; ein zusätzliches fachliches Modell
"Seriennummerngruppe" ist nicht nötig. Unter `K&F-Systems` werden Produktfamilien wie
Gravis, VIDA oder Sequenza geführt. Jede seriennummernpflichtige Kategorie besitzt:

- ein eindeutiges zweistelliges Präfix,
- eine gemeinsame permanente Odoo-Sequenz für alle Artikel der Familie,
- automatische Produktverfolgung `Seriennummer`,
- automatische Vergabe bei Bestätigung des Fertigungsauftrags.

Format: `GGWWYYNNNNN`, zum Beispiel `36322600001` für Gravis, KW 32, Jahr 2026.
Der fünfstellige Zähler wird **nicht** pro Woche oder Jahr zurückgesetzt. Historische
Seriennummern bleiben unverändert. Die Artikeltransformation ordnet bekannte Namen
automatisch den Familien zu und setzt ihre externe ID weiterhin aus `ARTIKEL.LFDNR`.

Technischer Nachweis am 06.08.2026: Ein transaktionaler Fertigungsauftragstest erzeugte
für Gravis `36322600001` und `36322600002`. Ein zusätzlicher Jahresgrenzentest für den
01.01.2027 erzeugte korrekt das ISO-Präfix `365326`. Anschließend wurden Testartikel,
Testaufträge, Seriennummern und Sequenzverbrauch zurückgerollt; der Gravis-Zähler stand
weiterhin auf `00001`.

Die initialen Familienpräfixe wurden aus der bisherigen Liste konsolidiert. Vor dem
produktiven Start ist eine einmalige Freigabe der Tabelle
`02_mappings/product_serial_groups.yaml` durch Jonathan erforderlich; danach dürfen
verwendete Präfixe nicht wiedervergeben werden.

## Priorisierte Restarbeiten

1. Familien-/Präfixtabelle fachlich freigeben; nicht eindeutig erkannte Artikel als
   Fehlerliste ausgeben und manuell zuordnen.
2. Arbeitsplätze, Stücklisten, CRM-Stufen, Qualitätsprüfpläne und Rollen aus dem freigegebenen Soll
   aufbauen; ältere Dokumentationszahlen nicht ungeprüft übernehmen.
3. DATEV, E-Rechnung, Versandetiketten, Tracking, E-Mail und Bitfarm jeweils mit einem
   Ende-zu-Ende-Integrationstest nachweisen.
4. Funktions-, Rechte-, Performance-, Backup/Restore-, Cutover- und Abnahmetests mit
   Verantwortlichem, Datum und Ergebnis protokollieren.

## Abnahmekriterien für den historischen Import

- Kein historischer Verkaufs- oder Einkaufsbeleg ist operativ offen oder entsperrt.
- Keine unerwarteten Pickings, Bestellungen, Reservierungen oder Rechnungsentwürfe.
- Keine historischen offenen Forderungen/Verbindlichkeiten.
- Jeder importierte Stammdatensatz besitzt eine stabile eEvolution-External-ID.
- Wiederholung desselben Imports aktualisiert Datensätze und erzeugt keine Dubletten.
- Go-live-OP und Eröffnungssalden sind technisch und organisatorisch getrennt.

## CRM-Datumsregel

- Vergangene `TERMIN`-/`KONTAKT`-Datensätze der letzten zehn Jahre werden als
  abgeschlossene Chatter-Historie mit `mail.message.date = TERMIN.ANFTERMIN` übernommen.
- Sie werden nicht als offene `mail.activity` angelegt und erscheinen daher nicht mit
  dem Importdatum als angeblich neue Aufgabe.
- Zuständiger Mitarbeiter und Bezug zur Verkaufschance beziehungsweise Adresse werden
  soweit vorhanden übernommen; External ID ist `ev_crm_history_<TMNR>`.
- Nur zum Go-live tatsächlich offene Wiedervorlagen dürfen in einem getrennten,
  fachlich freigegebenen Schritt als `mail.activity` importiert werden.

## Abhängigkeitsreihenfolge des Imports

1. Odoo-Module, Einstellungen und Referenzkonfiguration
2. Partner, Mitarbeiter, Ansprechpartner, Lieferadressen und USt-IdNr
3. ausschließlich aktive Produkte, Lieferanteninformationen und Preislisten
4. Stücklisten, Lagerorte und Bestandsmomentaufnahme
5. Seriennummern, Chargen und Rückverfolgung der letzten zehn Jahre
6. CRM-Chancen und anschließend die datierte abgeschlossene CRM-Historie
7. historische Verkaufs-/Einkaufsbelege und Rechnungen
8. Sperren aller historischen Vorgänge und Ausgleich aller historischen Rechnungen
9. Benutzerzuordnungen und Bereinigung ausschließlich technischer Chatter-Meldungen

Kein Schritt darf bei fehlenden External-ID-Ankern stillschweigend weiterlaufen. Der
Produktivlauf benötigt vor jedem Block einen Vollständigkeits- und Dubletten-Preflight.
