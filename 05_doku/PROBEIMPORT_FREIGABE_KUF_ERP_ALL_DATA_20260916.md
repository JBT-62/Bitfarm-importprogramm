# Freigabe und Start-Gates – Probeimport `kuf-erp-all-data`

Stand: 16.09.2026

## Freigabeumfang

Der vollständige Probeimport ist ausschließlich auf der neutralisierten Testdatenbank
`kuf-erp-all-data` freigegeben.

Nicht freigegeben sind:

- der finale Cutover am 31.12.2026,
- Schreibzugriffe auf eine Produktivdatenbank,
- Schreibzugriffe auf das eEvolution-Quellsystem.

Der finale Cutover benötigt nach Auswertung der Generalprobe eine separate ausdrückliche
Freigabe durch Jonathan/Geschäftsführung.

## Gate 1 – Backup und Restore-Test

Status: **ERFÜLLT**

Verifizierte Vor-Import-Sicherung:

```text
/var/backups/odoo/kuf-erp-all-data_20260916_160506_pre_authorized_full_rehearsal_retry_20260916
```

| Bestandteil | Ergebnis |
|---|---:|
| PostgreSQL Custom Dump | 85.684.439 Bytes |
| Filestore-Archiv | 2.210.147 Bytes |
| Restore in temporäre Datenbank | erfolgreich |
| gelesene Moduldatensätze im Restore | 1.447 |

Der erste lokal gestartete Sicherungsaufruf lieferte innerhalb seines 60-Sekunden-Limits
keine Abschlussmeldung und gilt deshalb ausdrücklich nicht als Nachweis. Ausschließlich
der oben genannte vollständig abgeschlossene Wiederholungslauf ist freigegeben.

## Gate 2 – Vorab-Guardrails

Status: **ERFÜLLT**

Read-only-Audit vom 16.09.2026, 16:07 Uhr:

| Metrik | Ist | Soll |
|---|---:|---:|
| Historische `sale.order` | 7.992 | Information |
| Davon `locked=False` | **0** | **0** |
| `stock.move` | **0** | **0** |
| `stock.move.line` | **0** | **0** |
| `stock.picking` | **0** | **0** |
| `account.move` | **0** | **0** |
| `account.move.line` | **0** | **0** |

Die eigenen Legacy-Prüf- und Einkaufsmodelle sind für normale interne Benutzer per ACL
read-only. Für historische Standardbelege gilt zusätzlich das konkrete Feld
`locked=True`.

Nach jedem schreibenden Importblock und nach dem Gesamtimport wird derselbe Audit erneut
ausgeführt. Der Abschlussbericht muss die drei Kernmetriken ausdrücklich enthalten:

```text
historische Belege ungesperrt = 0
Lagerbewegungen = 0
Buchungseinträge = 0
```

## Gate 3 – eEvolution-Delta-Anker

Status: **ERFÜLLT**

Der vollständige maschinenlesbare Stand liegt in:

```text
05_doku/PROBEIMPORT_GATE_PRE_KUF_ERP_ALL_DATA_20260916.json
```

Er enthält 19 Haupttabellen, darunter `ADRESS` (Quellname ohne abschließendes E),
`KUNDE`, `LIEFERANT`, `ARTIKEL`, `ANGAUFGUT`, `ANGAUFPOS`, `AAGLS`, `AAGFAKT`,
`BESTELLUNG`, `RECHEINGANG`, `PRODUKTION`, `PRODAUFINHIST`, `SNRARCHIV`,
`CHARGENARCHIV`, `TERMIN` und `VERKAUFSCHANCE`.

Wichtige Startanker:

| Tabelle | Zeilen | Ankerspalte | MAX vor Probeimport |
|---|---:|---|---:|
| `ADRESS` | 7.078 | `ADRNR` | 9.928 |
| `ARTIKEL` | 5.971 | `LFDNR` | 6.114 |
| `ANGAUFGUT` | 38.720 | `LFDNR` | 40.386 |
| `AAGLS` | 31.161 | `LSNR` | 242.231 |
| `AAGFAKT` | 34.023 | `LFDFAKTNR` | 34.083 |
| `BESTELLUNG` | 41.963 | `BESTNR` | 317.461 |
| `RECHEINGANG` | 23.206 | `LFDNR` | 24.127 |
| `PRODUKTION` | 30.578 | `LFDNR` | 266.863 |
| `PRODAUFINHIST` | 759.107 | `LFDNR` | 759.547 |
| `TERMIN` | 187.167 | `TMNR` | 189.067 |

`MAX(LFDNR)` beziehungsweise der jeweilige Geschäftsschlüssel ist nur ein Anker für neue
Sätze. Änderungen an vorhandenen Sätzen werden deshalb zusätzlich über Zeilenanzahl,
maximale SQL-Rowversion und – soweit vorhanden – `TMSTMP` abgesichert.

## Freigegebene Importregeln

- Hauptbeleggeschichte vollständig nach `REGEL-028`.
- Technische Rückverfolgung und Produktionsdetails im festen Fenster
  `2017-01-01 00:00:00` inklusive bis `2027-01-01 00:00:00 Europe/Berlin` exklusiv.
- Keine einzelnen operativen Lagerbuchungen.
- Historische Rechnungen nur informativ und gesperrt, ohne `account.move` und ohne
  Buchungssatz.
- Der aktuelle Rehearsal-Lauf behält vorhandene `__import__`-Bindings bei. Die
  kontrollierte Umstellung auf den Zielnamensraum `eevolution` erfolgt nach dem Import,
  bevor `pilot_import_angebot.py` entsprechend geändert wird.

## Nach dem Probeimport

1. `99_scripts/249_capture_probe_import_gates.py` mit `--phase post` ausführen.
2. Pre-/Post-Quellanker vergleichen und den Delta-Ausgangspunkt bestätigen.
3. Drei Kernmetriken und alle Mengenabgleiche in den Generalprobenbericht übernehmen.
4. Passwortrotation aus dem Sicherheitsfinding vor Produktivbetrieb abschließen.
5. `stock.quant` aus `INVPOS` erst nach der eEvolution-Inventur am 31.12.2026 als eigenen
   Cutover-Block ausführen.
6. Ergebnis Jonathan/Geschäftsführung zur separaten Cutover-Freigabe vorlegen.
