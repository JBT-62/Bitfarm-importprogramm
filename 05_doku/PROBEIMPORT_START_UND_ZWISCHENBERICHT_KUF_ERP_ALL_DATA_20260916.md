# Probeimport – Start- und Zwischenbericht `kuf-erp-all-data`

Stand: 16.09.2026, 16:43 Uhr

## Ergebnis

Der nach `REGEL-030` freigegebene Probeimport wurde gestartet. Die vollständige
Einkaufs- und Verkaufsbeleggeschichte ist jetzt bis zum aktuellen eEvolution-Stand in
`kuf-erp-all-data` vorhanden und abgenommen.

Der Gesamtimport ist damit noch nicht abgeschlossen. Als nächste Hauptbelegblöcke folgen
Lieferscheine, vollständige Produktionsauftragsköpfe sowie Ausgangs- und
Eingangsrechnungen in wirkungslosen Legacy-Modellen.

## Sicherungen

Vor Start:

```text
/var/backups/odoo/kuf-erp-all-data_20260916_160506_pre_authorized_full_rehearsal_retry_20260916
```

Nach vollständigem Einkauf und vor vollständigem Verkauf:

```text
/var/backups/odoo/kuf-erp-all-data_20260916_163030_post_full_purchase_pre_full_sales_20260916
```

Beide Sicherungen enthalten PostgreSQL-Dump und Filestore. Beide Restore-Tests waren
erfolgreich und lieferten jeweils 1.447 Moduldatensätze.

## Vollständige Einkaufshistorie

Importzeitraum: `1900-01-01` inklusive bis `2027-01-01` exklusiv. Tatsächlich enthalten
die Quelldaten 41.963 datierte Positionen und keine Datensätze nach dem aktuellen
Importsnapshot.

| Metrik | Ergebnis |
|---|---:|
| Einkaufsbelegköpfe | 22.010 |
| normale Bestellbelege | 21.897 |
| Rahmenvertragsbelege | 113 |
| Positionen | 41.963 |
| Belege mit Prüfkennzeichen | 717 |
| External-ID-Bindings Kopf + Position | 63.973 |
| Fehlende Bindings | 0 |
| Falsch zugeordnete Bindings | 0 |
| Doppelte Quellschlüssel | 0 |
| Verwaiste Positionen | 0 |

### Kontrollierter Unterbrechungsfall

Der erste lokale Apply-Aufruf wurde durch ein zu kurzes Ausführungszeitlimit beendet,
während sein Kindprozess kurzzeitig weiterarbeitete. Ein parallel gestarteter
Fortsetzungslauf erzeugte dadurch 500 identische, noch nicht extern gebundene
Positionsdubletten.

Vor einer Korrektur wurden für alle 500 Fälle nachgewiesen:

- exakt zwei Zeilen mit demselben stabilen Quellschlüssel,
- vollständige Feldgleichheit,
- derselbe Belegkopf,
- genau eine korrekt extern gebundene Zeile,
- genau eine ungebundene Dublette.

Nur die 500 ungebundenen Dubletten wurden über das Odoo-ORM entfernt. Danach bestätigte
`99_scripts/250_audit_full_purchase_history.py` exakt 22.010 Köpfe, 41.963 Positionen,
vollständige Bindings und keine Dubletten. Der Wiederholungs-Dry-run plant keine neuen
Datensätze.

## Vollständige Verkaufsbeleggeschichte

| Metrik | Vorher | Zusätzlich | Jetzt |
|---|---:|---:|---:|
| gesperrte historische `sale.order` | 7.992 | 9.215 | 17.207 |
| vollständige Legacy-Prüfdokumente | 6.164 | 14.606 | 20.770 |
| abgedeckte eEvolution-Köpfe | 14.156 | 23.821 | 37.977 |
| neue belegbezogene Lieferadressen | – | 8.226 | 8.226 |

Alle neuen Standardbelege wurden mit `kf_legacy_history=True` und `locked=True`
angelegt. Das Modul blockiert Änderung, Entsperrung, Bestätigung, Lieferung und
Rechnungserzeugung. Prüfdokumente sind für normale interne Benutzer read-only.

Wiederholungs-Dry-run:

```text
sales_new=0
review_new=0
delivery_new=0
missing=0
```

## Pflicht-Guardrails nach den Importblöcken

Auditzeitpunkt: 16.09.2026, 16:43 Uhr.

| Metrik | Ergebnis | Soll |
|---|---:|---:|
| historische Standardbelege `locked=False` | **0** | **0** |
| `stock.move` | **0** | **0** |
| `stock.move.line` | **0** | **0** |
| `stock.picking` | **0** | **0** |
| `account.move` | **0** | **0** |
| `account.move.line` | **0** | **0** |

Damit sind die drei von der Freigabe verlangten Kernmetriken erfüllt:

```text
historische Belege ungesperrt = 0
Lagerbewegungen = 0
Buchungseinträge = 0
```

## Unveränderte Grenzen

- eEvolution wurde ausschließlich read-only abgefragt.
- Es gab keine Schreibzugriffe auf eine Produktivdatenbank.
- Der finale Cutover ist nicht freigegeben.
- CRM-Termine vor dem Zehnjahresfenster bleiben bis zur Entscheidung `OFFEN-009`
  ausgeschlossen.
- Bestände, `stock.quant`, offene Posten und Finanzeröffnungen bleiben Cutover-Daten.
- Die Umstellung bestehender External IDs von `__import__` nach `eevolution` erfolgt
  kontrolliert nach dem aktuellen Probeimport gemäß `REGEL-031`.

## Technische Nachweise

- Vorab-/Nachlauf-Gate: `99_scripts/249_capture_probe_import_gates.py`
- Einkauf-Vollimport: `99_scripts/246_import_historical_purchase_documents.py`
- Einkaufs-Abnahme: `99_scripts/250_audit_full_purchase_history.py`
- kontrollierte Dublettenbereinigung:
  `99_scripts/251_cleanup_interrupted_purchase_line_duplicates.py`
- Verkauf-Vollimport: `99_scripts/240_import_historical_sales_documents.py`
- Maschinenlesbarer Abschlussstand:
  `05_doku/PROBEIMPORT_GATE_POST_SALES_FULL_KUF_ERP_ALL_DATA_20260916.json`
