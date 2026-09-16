# Cutover- und Schulungsplan – Go-live 01.01.2027

Stand: 16.09.2026

## Verbindliche Stichtage

- Go-live Odoo: **01.01.2027**.
- Oberer Migrations-Cutoff: **`2027-01-01 00:00:00 Europe/Berlin` exklusiv**.
- Damit enthalten die freigegebenen Hauptbelege alle Geschäftsdaten bis zum Ende des
  **31.12.2026**.
- Technische Serien-/Chargenrückverfolgung und Produktionsdetails:
  **`2017-01-01 00:00:00` inklusive bis `2027-01-01 00:00:00` exklusiv**.

## Rehearsal, Sicherung und Schulung

1. Vollständigen Rehearsal-Import in `kuf-erp-all-data` mit einem dokumentierten
   Zwischen-Cutoff durchführen.
2. Alle Mengen-, Relations-, Nebenwirkungs-, Idempotenz- und End-to-End-Prüfungen
   abschließen.
3. PostgreSQL und Filestore vollständig sichern und die Wiederherstellung in einer
   temporären Datenbank nachweisen.
4. Diese Sicherung unveränderlich als **Golden Backup** kennzeichnen.
5. Für Test und Schulung eine separate Datenbank aus dem Golden Backup wiederherstellen.
6. Die Schulungsdatenbank neutralisieren: E-Mail-Versand, Zahlungsanbieter, Carrier,
   externe Integrationen und unerwünschte Scheduler deaktivieren; Datenbankname und Banner
   eindeutig als Schulung kennzeichnen.
7. Schulungstests und Schulungsbuchungen nur in dieser Kopie durchführen. Das Golden Backup
   und die Rehearsal-Basis bleiben unverändert.

## Freigabe der Generalprobe am 16.09.2026

Der vollständige Probeimport auf `kuf-erp-all-data` ist freigegeben. Die Freigabe gilt
ausschließlich für diese neutralisierte Testdatenbank und nicht für den finalen Cutover.

Vor dem ersten Schreiblauf müssen drei Gates grün sein:

1. Eine aktuelle Sicherung aus PostgreSQL-Dump und Filestore wurde in einer temporären
   Datenbank wiederhergestellt und der Nachweis dokumentiert.
2. Der Read-only-Gate-Audit weist vor dem Import null ungesperrte historische
   Standardbelege, null `stock.move` und null `account.move`/`account.move.line` aus.
3. Für die eEvolution-Haupttabellen sind Zeilenanzahl, maximaler Geschäftsschlüssel,
   maximale Rowversion und – soweit vorhanden – maximaler Zeitstempel festgehalten.

Nach dem Import wird derselbe Gate-Audit erneut ausgeführt. Die Freigabe ist nur dann
erfolgreich genutzt, wenn folgende drei Abnahmemetriken im Import-Log stehen:

```text
historische Belege ungesperrt = 0
stock.move = 0
account.move = 0 und account.move.line = 0
```

Der dokumentierte Vorab-Nachweis steht in
`05_doku/PROBEIMPORT_FREIGABE_KUF_ERP_ALL_DATA_20260916.md`. Der maschinenlesbare
Ankerstand steht in `05_doku/PROBEIMPORT_GATE_PRE_KUF_ERP_ALL_DATA_20260916.json`.

## Finaler Cutover

1. eEvolution nach Geschäftsschluss am 31.12.2026 für fachliche Buchungen sperren und den
   Freeze-Zeitpunkt protokollieren.
2. Quellschlüssel-Obergrenzen und Maximalzeitstempel der Haupttabellen dokumentieren.
3. Produktive Odoo-Datenbank mit den freigegebenen Modulständen und Einstellungen frisch
   und reproduzierbar aufbauen; keine Schulungsdatenbank umbenennen oder produktiv setzen.
4. Stammdaten und vollständige historische Hauptbelege bis zur exklusiven Cutoff-Grenze
   importieren.
5. Technische Rückverfolgung und Produktionsdetails nur im festen Zehnjahresfenster laden.
6. Finance-freigegebene offene Debitoren/Kreditoren, Eröffnungswerte und Stichtagsbestände
   separat als Cutover-Daten übernehmen. Historische Rechnungsreferenzen erzeugen keine
   Buchungssätze.
7. Abschlussaudit, Stichproben, Restore-/Rollback-Nachweis und fachliche Freigabe durchführen.
8. Benutzer, E-Mail, Scheduler, Carrier und externe Integrationen kontrolliert aktivieren.

Der finale Cutover benötigt nach Auswertung der Generalprobe eine eigene ausdrückliche
Freigabe durch Jonathan/Geschäftsführung. Die Probeimport-Freigabe ersetzt diese Freigabe
nicht.

## Abnahmekriterien

- Quelle/Ziel-Mengenabgleich je Objekt und Zeitraum.
- Keine Dubletten und keine fehlenden Pflichtrelationen.
- Historische Belege schreibgeschützt und ohne operative Lager-/Buchhaltungswirkung.
- Serien-/Chargen- und Produktionsdetaildaten ausschließlich im festen Zehnjahresfenster.
- Reale offene Vorgänge und Finanzanfangswerte ausschließlich aus dem freigegebenen
  Cutover-Snapshot.
- Benutzerrechte, Kennworthashes, E-Mail-Neutralisierung und Integrationsstatus geprüft.
- Vollständige, restore-getestete Pre-Go-live- und Post-Go-live-Sicherungen vorhanden.
