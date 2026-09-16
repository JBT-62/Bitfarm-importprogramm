# 3D-Gesamtprüfung der Migration `kuf-erp-all-data`

Stand: 16.09.2026, Live-Audit 15:08 Uhr  
Prüfart: vollständig read-only gegen eEvolution `KuF` und Odoo `kuf-erp-all-data`

## Ergebnis zuerst

Der bisherige Import ist innerhalb seines dokumentierten Umfangs technisch belastbar.
Stammdaten, historische Einkaufsbelege und Rückverfolgung sind mengenmäßig vollständig,
relational aufgelöst und ohne Lager- oder Buchhaltungswirkung. Der Audit hat jedoch eine
wichtige Stichtagslücke sichtbar gemacht: eEvolution läuft weiter. Nach dem bisherigen
Import entstanden am 16.09.2026 eine neue CRM-Chance und zwei neue Verkaufsbelege.

Das ist kein Fehler in den importierten Daten. Für einen reproduzierbaren Gesamtimport
reicht aber ein Tagesdatum als oberer Stichtag nicht aus. Künftige Läufe benötigen einen
festen Zeitstempel oder eine feste Quellschlüssel-Obergrenze.

Die fachliche Reichweite wurde anschließend mit `REGEL-028` festgelegt: vollständige
Hauptbeleggeschichte, technische Rückverfolgung und Produktionsdetails nur zehn Jahre.

## Prüflogik – die drei Dimensionen

1. **Objekte:** Sind die erwarteten Artikel, Partner, Stücklisten und Belege vorhanden?
2. **Beziehungen:** Sind Artikel, Kunden, Lieferanten, Produktionsaufträge, Serien, Chargen
   und Lieferungen durchgängig miteinander verknüpft?
3. **Zeit und Wirkung:** Welche Daten liegen innerhalb oder außerhalb des Zeitfensters und
   erzeugt die Historie ungewollte Bestände, Bewegungen, Buchungen oder Folgeprozesse?

## 1. Objekt- und Mengenprüfung

| Bereich | Quelle / Erwartung | Odoo | Bewertung |
|---|---:|---:|---|
| Artikel, nicht löschmarkiert | 5.971 | 5.971 | vollständig |
| davon inaktiv | 1.775 | 1.775 archiviert | vollständig und nicht operativ nutzbar |
| ADRESS-Partner | 6.021 importierbar | 6.021 | vollständig |
| Ansprechpartner | 9.393 | 9.393 | vollständig |
| Lieferadressen | 3.189 | 3.189 | vollständig |
| Supplierinfo aus `LIEFERPREISE` | 5.196 sicher | 5.196 | vollständig; 17 Quellfälle blockiert |
| Preislisten | 12 Importlisten | 12 | vollständig |
| Preislistenpositionen | 1.945 sicher | 1.945 | vollständig; 18 ausgewiesene Blocker |
| Stücklisten | 1.481 Quellenköpfe | 1.464 | 17 fehlerhafte Köpfe bewusst komplett blockiert |
| Stücklistenpositionen | 22.576 Quellenzeilen | 21.635 Komponenten + 603 Texte | vollständig für die 1.464 sicheren Köpfe |
| Benutzer | 11 aktiv / 14 einschließlich Systemkonten | identisch zur Referenz | vollständig |
| Mitarbeiter | 34 | 34 | vollständig |
| CRM-Chancen zum Importsnapshot | 1.364 | 1.364 | vollständig zum Snapshot |
| CRM-Historie | 84.467 | 84.467 | vollständig, keine offenen Aktivitäten |
| Verkaufsbelege zum Importsnapshot | 14.156 | 7.992 gesperrt + 6.164 Prüfliste | vollständig zum Snapshot |
| Einkaufsbelege | 8.739 / 18.018 Positionen | 8.739 / 18.018 | vollständig |
| Serien-/Chargenköpfe | 49.472 | 49.472 | vollständig |
| Serien-/Chargenereignisse | 322.386 | 322.386 | vollständig |

Die Wiederholungs-Dry-runs für Partner, Ansprechpartner, Lieferadressen, USt-ID,
Preislisten, Stücklisten, Einkaufsbelege und Rückverfolgung planen keine zusätzlichen
sicheren Datensätze.

## 2. Beziehungsprüfung

Folgende durchgängige Ketten sind technisch belegt:

- Artikelanker: 5.971 von 5.971.
- Stücklistenköpfe und -komponenten: keine fehlenden Produktrelationen in den importierten
  sicheren Stücklisten.
- Einkaufspositionen: 0 von 18.018 ohne Odoo-Artikel.
- Rückverfolgungsköpfe: 0 von 49.472 ohne Odoo-Artikel.
- Direkte Serien-/Chargenlieferungen: 0 von 41.112 ohne Kunde.
- CRM-Chancen im Importsnapshot: 0 ohne Kundenbezug und 0 ohne bewahrtes
  eEvolution-Produktinteresse.
- Benutzer-/Mitarbeiterübernahme: alle 34 Mitarbeiteranker vorhanden; alle menschlichen
  Benutzer der Referenz vorhanden. Kennworthashes wurden übernommen, Klartextkennwörter
  nicht gelesen.

Bewusst sichtbare Unschärfen bleiben erhalten und werden nicht als sichere Einzelrelation
ausgegeben:

- 428 Komponentenverwendungen sind nur auf Ebene desselben Produktionsauftrags ableitbar.
- 178.175 Verwendungen sind über denselben Buchungslauf ableitbar.
- 281 Produktionsausgaben haben im Zehnjahresfenster keinen passenden Rückverfolgungskopf.
- 5.702 Ereignisse besitzen keinen bekannten eEvolution-Typtext.
- 5.964 Serien-/Chargennummern kommen bei mehreren eEvolution-Artikeln vor und werden
  deshalb nicht artikelübergreifend zusammengeführt.

## 3. Zeitfensterprüfung

Der aktuelle Import verwendet den Zeitraum 16.09.2016 bis einschließlich 16.09.2026.

| Bereich | im Zehnjahresfenster | vor dem 16.09.2016 | Folgewirkung bei anderer Entscheidung |
|---|---:|---:|---|
| CRM-Chancen | 1.365 aktuell in der Quelle | 0 | Zehnjahresregel ändert den CRM-Umfang nicht |
| Verkaufsbelegköpfe | 14.158 aktuell in der Quelle | 23.819 | bei „alle Belege“ ist ein großer Altblock zusätzlich zu planen |
| Einkaufspositionen | 18.018 | 23.945 | bei „alle Belege“ ist der Altblock zusätzlich zu planen |
| Serien-/Chargenereignisse | 322.386 | 552.821 | bleibt ausgeschlossen, falls zehn Jahre nur für Rückverfolgung gelten |

Die beiden Verkaufszahlen und die CRM-Zahl liegen aktuell über dem Importsnapshot, weil
eEvolution nach dem Import weiter beschrieben wurde. Neu, aber nicht still nachimportiert:

- CRM-Chance `2DEA6FE0-BCB1-F111-B9C8-00155D0E7000`, „VN, Demo-Bestellung“, angelegt
  am 16.09.2026 um 12:53 Uhr.
- Verkaufsbeleg-ID `40385`, angelegt am 16.09.2026 um 14:19 Uhr.
- Verkaufsbeleg-ID `40386`, angelegt am 16.09.2026 um 14:29 Uhr.

Die beiden Verkaufsbelege sind laut Quelle noch nicht erledigt. Sie gehören deshalb nicht
ungeprüft in einen historischen, vollständig abgeschlossenen Belegimport.

## Wirkungsprüfung

Der Live-Abgleich nach allen bisherigen Historienimporten zeigt:

| Operativer Bereich | Bestand |
|---|---:|
| Einkaufsbestellungen | 0 |
| Lagertransfers | 0 |
| Lagerbewegungen | 0 |
| Buchhaltungsbelege | 0 |
| Wartende E-Mails | 115, gegenüber den Historienimporten unverändert |

Die 7.992 historischen Verkaufsbelege liegen gesperrt vor und haben keine Lieferungen,
Lagerbewegungen oder Rechnungen erzeugt. Einkaufs- und Rückverfolgungshistorie liegen in
eigenen `kf.legacy.*`-Modellen.

## Sicher, offen und gesperrt

### Sicher übernommen

- vollständiger Artikelstamm einschließlich archivierter Artikel,
- Partner, Kontakte und Lieferadressen,
- sichere USt-IDs, Supplierinfo und Preislisten,
- sichere Stücklisten einschließlich Textpositionen,
- Benutzer, Kennworthashes und Mitarbeiter,
- CRM und CRM-Historie bis zum festen Importsnapshot,
- Verkaufs- und Einkaufsbelege bis zum festen Importsnapshot,
- Serien-/Chargen- und Produktionsrückverfolgung im Zehnjahresfenster.

### Fachlich zu prüfen, aber vollständig bewahrt

- 22 fehlerhafte USt-ID-Formate und 3 Quellenkonflikte,
- 17 Supplierinfo-Währungs-/Einheitenfälle,
- 17 Stücklistenköpfe mit negativen Quellmengen,
- 6.164 Verkaufsbelege in der Prüfliste,
- 513 Einkaufsbelege mit sichtbarem Prüfkennzeichen,
- 17.457 Serien-/Chargenköpfe mit sichtbarem Prüfkennzeichen.

### Noch nicht übernommen beziehungsweise weiterhin gesperrt

- historische Ausgangs- und Eingangsrechnungen als wirkungsfreie Referenzbelege,
- Haupt-Lagerbelege außerhalb der bereits vorhandenen Rückverfolgungsreferenzen,
- vollständige Lagerplätze und Barcodes,
- Bestände, Bewertungen, offene Vorgänge und buchhalterische Eröffnungen,
- zeitabhängige Altbestände vor dem 16.09.2016 bis zur Entscheidung über die Reichweite
  der Zehnjahresregel.

## Festgelegte Entscheidung und verbleibender Stichtag

Festgelegt ist:

1. Hauptbelege und deren Belegpositionen werden vollständig übernommen.
2. Serien-/Chargenrückverfolgung und Produktionsdetails bleiben auf zehn Jahre begrenzt;
   ältere Produktionsaufträge erhalten nur den Kopf.

Noch festzulegen ist, welcher exakte obere Stichtag für den Rehearsal- und späteren Produktivimport gilt.
   Empfehlung: UTC-/Serverzeitstempel plus dokumentierte Quellschlüssel-Obergrenzen je
   Haupttabelle.

Bis zu dieser technischen Cutoff-Festlegung werden nach dem Importsnapshot neu entstandene
Datensätze nicht still in historische Blöcke gemischt.

## Mengenauswirkung: Vollhistorie, Serien und Chargen weiter nur zehn Jahre

Der ergänzende Live-Audit vergleicht die komplette belegte Geschäftshistorie mit dem
aktuellen Zielbestand. Serien- und Chargenarchive vor dem 16.09.2016 bleiben ausdrücklich
ausgeschlossen.

| Zusätzlicher Bereich gegenüber dem aktuellen Odoo-Stand | Köpfe / Ereignisse | Positionen / Details |
|---|---:|---:|
| CRM | 1 Chance | 102.700 Historienereignisse |
| Verkauf | 23.821 Belege | 104.244 Positionen |
| Lieferscheine | 29.483 Belege | 107.928 Positionen |
| Einkauf | 13.271 Belege | 23.945 Positionen |
| Ausgangsrechnungen | 28.167 Belege | 101.217 Positionen |
| Eingangsrechnungen | 23.037 Belege | 57.408 Positionen |
| Produktion | 22.794 Aufträge | 507.340 Komponentenbuchungen |

Damit entstehen zusätzlich rund **1.145.356** Kopf-, Positions- und Historienzeilen.
Werden auch stornierte Liefer- und Rechnungsbelege mit Status und Positionen bewahrt,
kommen weitere **39.835** Zeilen hinzu; Gesamtgröße dann rund **1.185.191** zusätzliche
Datensätze vor technischen Relations-/External-ID-Hilfszeilen.

Ohne die einzelnen Produktions-Komponentenbuchungen läge die Mehrmenge bei **638.016**
Datensätzen. Die älteren **552.821** Serien-/Chargenereignisse bleiben in beiden Varianten
ausgeschlossen.

Technischer Nachweis: `99_scripts/248_audit_full_history_scope_delta.py`.

## Technischer Nachweis

- Gesamtprüfer: `99_scripts/247_audit_migration_3d.py`
- Produktstatus: `99_scripts/216_audit_imported_product_status.py`
- Stücklisten: `99_scripts/222_audit_bom_source.py` und `223_import_boms.py --dry-run`
- Identitäten: `99_scripts/227_audit_user_employee_transfer.py`
- CRM: `99_scripts/233_audit_crm_full_import.py` und `236_audit_crm_history_import.py`
- Verkauf: `99_scripts/239_audit_sales_import_readiness.py` und
  `240_import_historical_sales_documents.py` im Dry-run
- Rückverfolgung: `99_scripts/244_audit_full_traceability_import.py`
- Einkauf: `99_scripts/245_audit_historical_purchase_source.py` und
  `246_import_historical_purchase_documents.py` im Dry-run
- Vollhistorie gegenüber Zehnjahresumfang: `99_scripts/248_audit_full_history_scope_delta.py`
