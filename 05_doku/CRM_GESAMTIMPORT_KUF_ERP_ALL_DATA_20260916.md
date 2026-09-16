# CRM-Gesamtimport `kuf-erp-all-data`

Stand: 16.09.2026

## Ergebnis

- 1.364 eEvolution-Verkaufschancen seit 16.09.2016 wurden mit stabilen
  `__import__.ev_vkchance_*`-External-IDs importiert.
- 361 Chancen sind aktiv; 1.003 verlorene, inaktive oder unbekannte Chancen sind
  archiviert.
- Keine Chance fehlt Kunde, Produktinteresse, eEvolution-Verantwortlichennummer oder
  Verantwortlichenname.
- Sieben eEvolution-Verantwortliche kommen vor. Nur Niklas Goslar besitzt ein eindeutig
  passendes aktives Odoo-Benutzerkonto; deshalb tragen genau seine 51 Chancen einen
  Odoo-Verkäufer. Für die übrigen 1.313 Chancen wurde kein Ersatzbenutzer erfunden.
- 84.467 abgeschlossene CRM-Ereignisse wurden als datierte interne `mail.message`
  übernommen: 7.195 an Verkaufschancen, der Rest an Kunden/Ansprechpartner.
- Es wurden keine offenen `mail.activity`-Datensätze erzeugt und keine E-Mails versendet.
- Drei Ereignisse vom 06.05.2024 mit dem Typ `Eingang Bestellung` besitzen weder Adresse
  noch Verkaufschance. Sie sind keine CRM-Beziehung und bleiben für den
  Einkaufsbelegblock ausgewiesen (`TMNR` 164630, 164636, 164642).

## Technische Korrekturen

- SQL-Datumswerte werden fehlertolerant gelesen; der feste Stichtag wird als Datumswert
  gebunden.
- `kf_legacy_migration` 19.0.9.0.0 ergänzt schreibgeschützte Felder für
  Produktinteresse und historischen Verantwortlichen.
- Odoo-Standardwerte für Verkäufer und Nachrichtenautor werden ausdrücklich auf leer
  gesetzt, wenn kein eindeutiger Quellbenutzer existiert. Dadurch entstehen keine
  falschen Administratorzuordnungen.
- Der Historienimport arbeitet blockweise und ist über External IDs idempotent.

## Prüfungen

- Chancen-Wiederholungs-Dry-run: 0 Creates, 1.364 bestehende Updates.
- Historien-Wiederholungs-Dry-run: 0 Creates, 84.467 bestehende Einträge, drei
  abgegrenzte Bestellereignisse.
- Integritätsaudit: 84.467/84.467 Nachrichten vorhanden; 0 falsche Zielmodelle,
  0 falsche Nachrichtentypen, 0 fehlende Originaldaten, 0 Aktivitätsanker.
- eEvolution blieb durchgehend read-only.

## Sicherungen

- `/var/backups/odoo/kuf-erp-all-data_20260916_123201_pre_crm_opportunities_20260916`
- `/var/backups/odoo/kuf-erp-all-data_20260916_124523_pre_crm_history_full_20260916`
- `/var/backups/odoo/kuf-erp-all-data_20260916_125332_pre_crm_history_author_correction_20260916`

Die Sicherungen enthalten Datenbank und Filestore und wurden jeweils in einer temporären
Datenbank erfolgreich rückgesichert.
