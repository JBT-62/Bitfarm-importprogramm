# Pilottest: eEvolution-Angebot 39575 in Odoo

**System:** Odoo-Testdatenbank `erp-test-1`

**Odoo-Angebot:** `S00001`

**Quelle:** eEvolution-Angebot 39575

**Stand:** 06.08.2026

## Ergebnis des Imports

Der vorbereitete Vorgang beginnt in Odoo bei der CRM-Chance und dem noch nicht
bestätigten Angebot `S00001`. Ab diesem Punkt führen die Anwender den Prozess im
Odoo-Standard selbst weiter.

| Prüfgröße | Ergebnis |
|---|---:|
| Kunde | Sigma & TBL-Kommunikations GmbH |
| Ansprechpartner | 5 |
| benötigte Lieferanten | 51 |
| Artikel im Abhängigkeitsnetz | 152 |
| ausgewählte Stücklisten | 34 |
| Stücklistenpositionen | 186 |
| Angebotspositionen | 5 |
| Nettosumme | 27.517,11 EUR |
| Umsatzsteuer | 5.228,25 EUR |
| Bruttosumme | 32.745,36 EUR |

Alle importierten Datensätze haben stabile externe IDs. Ein erneuter Import
aktualisiert dieselben Datensätze und erzeugt keine Dubletten. Der nach dem
Import ausgeführte Wiederholungslauf erzeugte null neue Datensätze.

## Verbindliche Artikelregel

`ARTIKEL.INAKTIV` hat bei K&F eine andere fachliche Bedeutung als „nicht mehr
verwenden“. Deshalb werden solche Artikel importiert und in Odoo nicht
automatisch deaktiviert. Nur ein gesetztes `ARTIKEL.LOESCHKNZ` schließt einen
Artikel aus dem Import aus.

Wenn eine für den Piloten benötigte Stückliste auf einen Artikel mit
Löschkennzeichnung verweist, wird nicht stillschweigend eine unvollständige
Stückliste erzeugt. Der Import bricht dann mit einer eindeutigen Fehlermeldung ab.

## Ablauf für den Anwendertest

1. CRM-Chance und Kunde prüfen.
2. Angebot `S00001` einschließlich Texte, Mengen, Preise, Rabatt und Steuer prüfen.
3. Angebot bestätigen.
4. Beschaffung und Fertigung prüfen; insbesondere Fehlmengen, Lieferantenbezüge,
   Stücklistenauflösung und entstehende Fertigungsaufträge.
5. Seriennummern erst im neuen Odoo-Prozess vergeben. Aus eEvolution übernommene
   Serien- und Chargennummern bleiben bei der späteren Migration unverändert.
6. Lieferung und Rechnung ausschließlich im Testsystem durchspielen.
7. Abweichungen mit Odoo-Belegnummer, Artikelnummer und Bildschirmfoto festhalten.

## Abgrenzung und noch fachlich zu prüfen

- Der Pilot importiert Materialstücklisten. Arbeitspläne, Arbeitsplätze und
  Qualitätsprüfpunkte sind noch nicht aus eEvolution übernommen und müssen vor
  einer belastbaren Fertigungsabnahme fachlich festgelegt werden.
- Die 51 benötigten Lieferanten sind vorhanden. Eine strukturierte Kennzeichnung
  einzelner Stücklisten als Fremdfertigung wurde aus den Quelldaten für diesen
  Piloten noch nicht automatisch abgeleitet.
- Als vorläufiger Artikel-EK wurde der eEvolution-Stammwert `ARTIKEL.EKPR`
  übernommen. Die endgültige Berechnung des gewichteten durchschnittlichen EK
  ist noch mit Einkauf und Buchhaltung zu validieren.
- Lagerbestände wurden mit diesem Pilotimport nicht übernommen. Fehlbestände im
  Test sind daher erwartbar und kein Beleg für eine fehlerhafte Stückliste.
- Das Angebot bleibt absichtlich im Entwurf. Vor dem Anwendertest existieren
  keine Lieferungen, Fertigungsaufträge oder Bestellungen.

## Technische Nachweise

- Verifizierte Vorsicherung:
  `/var/backups/odoo/erp-test-1_20260806_125146_pre_pilot39575`
- Verifikationsskript: `99_scripts/verify_pilot_angebot.py`
- Importskript: `99_scripts/pilot_import_angebot.py`
