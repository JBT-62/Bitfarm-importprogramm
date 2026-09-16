# Zwischenbericht Odoo-/eEvolution-Migration

Stand: 17.09.2026  
Arbeitsstand: nach abgeschlossenem vollständigem Probeimport und erstem
External-ID-Namensraumaudit

## Kurzfazit

Der vollständige, freigegebene Probeimport in die neutralisierte Datenbank
`kuf-erp-all-data` ist technisch abgeschlossen und durch eine restore-getestete
Golden-Sicherung abgesichert. Die historischen Daten sind informativ und
schreibgeschützt; es wurden keine operativen Lagerbewegungen oder Buchungssätze
erzeugt.

Der nächste technische Block, die kontrollierte Umstellung der eEvolution-
External-IDs von `__import__` nach `eevolution`, wurde am 17.09.2026 mit einem
rein lesenden Bestandsaudit begonnen. Der Bestand ist kollisionsfrei, eine
Umstellung wurde jedoch noch nicht ausgeführt.

## Bereits erledigt

### Projektgrundlagen und Sicherheit

- Projektverfassung, Entscheidungsregister, Mappingstandard und technische
  Guardrails sind eingerichtet.
- eEvolution wird ausschließlich read-only abgefragt.
- Odoo-Schreibzugriffe sind auf freigegebene Zieldatenbanken, Apply-Modus und
  verifizierte Sicherungen begrenzt.
- Der statische Projekt-Preflight vom 17.09.2026 meldet `OK`, 0 Fehler.
- Go-live ist auf den 01.01.2027 festgelegt. Der technische obere Cutoff ist
  `2027-01-01 00:00:00 Europe/Berlin` exklusiv.

### Stammdaten

- 5.971 nicht löschmarkierte Artikel übernommen; 1.775 inaktive Artikel bleiben
  archivierte Referenzartikel ohne operative Ein-/Verkaufsfreigabe.
- 6.021 Partner, 9.393 Ansprechpartner und 3.189 Lieferadressen übernommen.
- 5.196 Lieferanten-Artikelbeziehungen aus der führenden Quelle `LIEFERPREISE`.
- 12 Preislisten mit 1.945 Regeln und 787 Kundenzuordnungen.
- 1.464 Stücklisten mit 21.635 Komponenten und 603 historischen Textpositionen.
- Produkt-UoM und Stücklisten-UoM werden aus den belegten eEvolution-Feldern
  übernommen; stille Odoo-Defaults sind gesperrt.

### Benutzer, Mitarbeiter und Systemstand

- Modulparität zur Referenzdatenbank hergestellt.
- PostgreSQL-Erweiterung `vector` in der Rehearsal-Datenbank aktiviert.
- 11 aktive eingerichtete Benutzer und 34 Mitarbeiter übernommen.
- Kennworthashes wurden ohne Zugriff auf Klartextkennwörter übertragen;
  Sitzungen, API-Schlüssel und Tokens wurden nicht kopiert.

### CRM

- 1.365 Chancen übernommen.
- 84.473 abgeschlossene historische CRM-Nachrichten vorhanden.
- Historische Ereignisse erzeugen keine offenen Aktivitäten.
- Verantwortliche werden nur bei eindeutig vorhandenem Odoo-Konto zugeordnet;
  fehlende Benutzer werden nicht erfunden.

### Historische Hauptbelege

| Bereich | Importierter Bestand |
|---|---:|
| Verkaufsbelege | 37.977 |
| davon gesperrte `sale.order` | 17.207 |
| davon read-only Prüfdokumente | 20.770 |
| Einkaufsbelege | 22.033 Köpfe / 41.986 Positionen |
| Lieferscheine | 31.161 Köpfe / 114.979 Positionen |
| Ausgangsrechnungen | 34.023 Köpfe / 125.790 Positionen |
| Eingangsrechnungen | 23.206 Köpfe / 57.916 Positionen |
| Produktionsaufträge | 30.586 Köpfe |

Historische Rechnungen sind keine `account.move` und erzeugen weder offene Posten
noch Buchungssätze. Ältere Produktionsaufträge außerhalb des technischen
Zehnjahresfensters bleiben informative Köpfe.

### Serien, Chargen und Rückverfolgung

- Festes technisches Fenster: 01.01.2017 inklusive bis 01.01.2027 exklusiv.
- 47.860 Serien-/Chargenköpfe.
- 312.890 Rückverfolgungsereignisse.
- 242.728 Komponentenbuchungen und 30.101 Produktionsausgaben im freigegebenen
  Zehnjahresfenster.
- 169.698 abgeleitete Verwendungen und 39.620 direkte Lieferbeziehungen.
- Rückwärts- und Vorwärtsverfolgung bis Kunde, Auftrag und Lieferschein ist
  verfügbar, soweit die Quelle eine belastbare Beziehung enthält.
- Unsichere Zuordnungen bleiben sichtbar als Prüffall und werden nicht geraten.

### Abschlusskontrollen des Probeimports

| Pflichtmetrik | Ergebnis |
|---|---:|
| ungesperrte historische `sale.order` | 0 |
| ungesperrte Legacy-Geschäftsbelege | 0 |
| `stock.picking` | 0 |
| `stock.move` | 0 |
| `stock.move.line` | 0 |
| `account.move` | 0 |
| `account.move.line` | 0 |

Die Wiederholungs-Dry-runs melden 0 Neuanlagen. Die Golden-Sicherung wurde
erfolgreich wiederhergestellt und geprüft:

`/var/backups/odoo/kuf-erp-all-data_20260916_233656_golden_full_rehearsal_20260916`

## Neuer Stand External-ID-Namensraum

Am 17.09.2026 wurde `99_scripts/257_audit_external_id_namespace.py` rein lesend
gegen `kuf-erp-all-data` ausgeführt.

| Prüfkriterium | Ergebnis |
|---|---:|
| Bindings in beiden geprüften Namensräumen | 1.034.598 |
| vorhandene Bindings in `__import__` | 1.034.598 |
| vorhandene Bindings in `eevolution` | 0 |
| `ev_*`-Kandidaten für die Umstellung | 1.034.488 |
| Nicht-`ev_*`-Bindings zur Einzelprüfung | 110 |
| Namenskollisionen mit unterschiedlichem Ziel | 0 |
| verwaiste Bindings | 0 |
| technisch nicht prüfbare Modelle | 0 |

Größte Binding-Blöcke sind 312.890 Trace-Ereignisse, 298.685 historische
Geschäftsbelegpositionen, 88.390 Geschäftsdokumente, 84.473 CRM-Nachrichten und
47.860 Trace-Köpfe.

Bewertung: Der Bestand ist für die Vorbereitung eines kontrollierten
Umstellungsplans geeignet. Eine direkte Änderung der Modulnamen ist noch nicht
sicher, weil zahlreiche Import- und Audit-Skripte `__import__` fest verwenden.
Die 110 Nicht-`ev_*`-Bindings, darunter lokale Benutzer- und Kontenanker, dürfen
nicht pauschal nach `eevolution` verschoben werden.

Maschinenlesbarer Nachweis:
`outputs/external_id_namespace_audit_20260917.json`.

## Noch offen vor dem Produktivbetrieb

1. Gemeinsame Resolver-/Kompatibilitätslogik für `eevolution` und bestehende
   `__import__`-Bindings implementieren und testen.
2. Exakte, unveränderliche Apply-Liste der 1.034.488 `ev_*`-Bindings erzeugen;
   Nicht-`ev_*`-Bindings ausgeschlossen lassen.
3. Namespace-Apply erst nach neuer Restore-Sicherung und ausdrücklicher
   Write-Freigabe ausführen; anschließend Read-back und Wiederholungs-Dry-run.
4. CRM-Aufbewahrungsentscheidung für Termine/Freitexte vor 01.01.2017 treffen.
5. Benutzer-Passwortrotation und Sicherheitsabnahme durchführen.
6. Lagerplatz-Dubletten, Sammelplätze und Schreibvarianten fachlich klären.
7. Offene Datenqualitätslisten bearbeiten, insbesondere negative
   Stücklistenmengen, USt-ID-Fälle, Supplierinfo-Einheiten und mehrdeutige
   Rückverfolgungsdaten.
8. Cutover-Block separat freigeben: Inventurbestand 31.12.2026, echte offene
   Vorgänge, offene Posten, Bewertungen und Finanzeröffnungen.

## Nächster sicherer Arbeitsschritt

Als Nächstes wird eine zentrale read-only External-ID-Auflösung vorbereitet, die
zuerst `eevolution` und während der Übergangsphase kontrolliert `__import__`
auflöst. Danach können die betroffenen Importer schrittweise umgestellt und gegen
den unveränderten Rehearsal-Bestand getestet werden. Ein Namespace-Write ist in
diesem Zwischenstand ausdrücklich noch nicht erfolgt.
