# Probeimport-Abschlussbericht `kuf-erp-all-data`

Stand: 16.09.2026, Schlussaudit 23:36 Uhr (Europe/Berlin)

## Ergebnis

Der freigegebene vollständige Probeimport auf der neutralisierten Testdatenbank
`kuf-erp-all-data` ist technisch abgeschlossen. eEvolution wurde ausschließlich
read-only abgefragt. Es gab keine Schreibzugriffe auf eine Produktivdatenbank.

Die historische Hauptbeleggeschichte ist vollständig bis zum freigegebenen oberen
Cutoff `2027-01-01 00:00:00` übernommen. Technische Serien-/Chargenrückverfolgung und
Produktionsdetails liegen im festen Halbintervall `2017-01-01` inklusive bis
`2027-01-01` exklusiv vor. Ältere Produktionsaufträge sind nur als informative Köpfe
enthalten.

## Importierter Bestand

| Bereich | Köpfe | Positionen/Ereignisse |
|---|---:|---:|
| Verkauf | 37.977 | aufgeteilt in 17.207 gesperrte `sale.order` und 20.770 read-only Prüfdokumente |
| Einkauf | 22.033 | 41.986 Positionen |
| Lieferscheine | 31.161 | 114.979 Positionen |
| Ausgangsrechnungen | 34.023 | 125.790 Positionen |
| Eingangsrechnungen | 23.206 | 57.916 Positionen |
| Produktionsaufträge, vollständige Kopfgeschichte | 30.586 | 242.728 Komponentenbuchungen und 30.101 Ausgaben nur im Zehnjahresfenster |
| Serien-/Chargenköpfe | 47.860 | 312.890 Ereignisse |
| Abgeleitete Verwendungen | – | 169.698 |
| Direkte Serien-/Chargenlieferungen | – | 39.620 |
| CRM-Chancen | 1.365 | 84.473 abgeschlossene historische Nachrichten |

Bei den Rückverfolgungsköpfen sind 47.859 Köpfe direkt aus Ereignissen belegt. Ein
zusätzlicher Kopf bleibt als notwendiger Anker einer aktuellen Produktionsausgabe
erhalten. Der Quellen-/Zielabgleich berücksichtigt diesen belegten Sonderfall.

## Idempotenz und Zeitfenster

Der abschließende Wiederholungs-Dry-run der Rückverfolgung meldet jeweils `0` neu und
`0` nicht im festen Quellfenster für Komponenten, Produktionsausgaben, Verwendungen
und direkte Lieferungen. Der Bereinigungs-Dry-run meldet ebenfalls in allen
Löschkategorien `0`.

Die Produktionsdetail-Abfrage wurde zusätzlich abgesichert: Komponenten werden nach
`PRODAUFINHIST.BELEGDAT`, Ausgaben nach dem jeweiligen `EINLAGDAT` auf das feste
Zehnjahresfenster begrenzt. Damit können spätere Wiederholungsläufe keine älteren
Produktionsdetails erneut anlegen.

Die CRM-Historie folgt weiterhin der bestehenden Testregel ab 16.09.2016. Deshalb
enthält sie 1.735 Ereignisse aus dem Zeitraum 16.09.2016 bis 31.12.2016 zusätzlich zu
dem technischen 2017–2026-Fenster. Das ist kein technischer Rückverfolgungsbestand.
Der CRM-Wiederholungs-Dry-run ergibt `0` Neuanlagen. Drei adress- und chancenlose
Bestellereignisse bleiben bewusst dem Einkaufsbelegblock zugeordnet.

## Pflicht-Guardrails

| Metrik | Ist | Soll |
|---|---:|---:|
| historische `sale.order` mit `locked=False` | 0 | 0 |
| Legacy-Geschäftsbelege ungesperrt | 0 | 0 |
| Produktionsköpfe ungesperrt | 0 | 0 |
| `stock.picking` | 0 | 0 |
| `stock.move` | 0 | 0 |
| `stock.move.line` | 0 | 0 |
| `account.move` | 0 | 0 |
| `account.move.line` | 0 | 0 |

Historische Rechnungen sind damit ausschließlich informative, schreibgeschützte
Legacy-Belege. Sie erzeugen weder offene Posten noch Buchungssätze.

Maschinenlesbarer Schlussnachweis:
`05_doku/PROBEIMPORT_GATE_FINAL_KUF_ERP_ALL_DATA_20260916.json`.

## Transparente Prüffälle

- 740 Einkaufsbelege tragen fachliche Prüfhinweise aus der Quelle.
- Sieben Geschäftsbelege haben keinen eindeutig auflösbaren Partnerbezug (drei
  Lieferscheine, drei Ausgangsrechnungen, eine Eingangsrechnung); die Quellwerte sind
  erhalten.
- 3.424 ältere Produktionsauftragsköpfe haben keinen Odoo-Produktbezug. Sie bleiben
  über eEvolution-Artikel-ID, Artikelnummer und -bezeichnung recherchierbar; es wurde
  kein Ersatzprodukt erfunden.
- 222 Produktionsausgaben besitzen keinen passenden Rückverfolgungskopf und bleiben
  als sichtbare Prüffälle erhalten.
- 17.040 Serien-/Chargenköpfe sind wegen belegter Mehrdeutigkeiten beziehungsweise
  unbekannter Ereignistypen als prüfpflichtig markiert; die Quelldaten wurden nicht
  zusammengeführt oder geraten.

## Golden-Sicherung

Unveränderliche Abschluss-Sicherung:

`/var/backups/odoo/kuf-erp-all-data_20260916_233656_golden_full_rehearsal_20260916`

- PostgreSQL-Dump: 120.915.643 Byte
- Filestore-Archiv: 2.210.147 Byte
- Restore-Test: erfolgreich
- Module im Restore-Probe: 1.447

Die Golden-Sicherung ist der freigegebene Ausgangspunkt für eine separat erzeugte,
neutralisierte Test-/Schulungskopie. Sie ist keine Freigabe für den finalen Cutover
und darf nicht zur Produktivdatenbank hochgestuft werden.

## Verbleibende Punkte vor Produktivbetrieb

1. Kontrollierte External-ID-Migration von `__import__` nach `eevolution` gemäß
   `REGEL-031`, anschließend erneute Idempotenzprüfung.
2. Benutzer-Passwortrotation und Sicherheitsabnahme.
3. Fachliche Entscheidung, ob die CRM-Termin-/Freitexthistorie beim Produktivlauf ab
   16.09.2016, ab 01.01.2017 oder vollständig übernommen werden soll.
4. Bestandsimport aus der Inventur zum 31.12.2026 sowie offene Vorgänge und
   Finanzeröffnungen nur im separat freizugebenden Cutover-Block.
5. Separater finaler Cutover nach Freigabe durch Jonathan/Geschäftsführung.
