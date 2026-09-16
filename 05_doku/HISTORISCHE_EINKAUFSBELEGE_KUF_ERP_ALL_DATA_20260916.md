# Historische Einkaufsbelege in `kuf-erp-all-data`

Stand: 16.09.2026

## Ergebnis

Die eEvolution-Einkaufshistorie vom 16.09.2016 bis einschließlich 16.09.2026 wurde
vollständig und wirkungsfrei in eigene, schreibgeschützte Odoo-Legacy-Modelle übernommen.

| Bereich | Anzahl |
|---|---:|
| Einkaufsbelege gesamt | 8.739 |
| davon normale Bestellungen | 8.702 |
| davon Rahmenvertragsbelege | 37 |
| Originalpositionen | 18.018 |
| Belege mit sichtbarem Prüfkennzeichen | 513 |
| Positionen ohne Odoo-Artikelbezug | 0 |
| Stornierte Positionen | 512 |

Alle Quellpositionen wurden bewahrt. Die 69 Rahmenvertragspositionen im Zeitraum sind in
37 eigenen historischen Rahmenvertragsbelegen enthalten. Sie wurden nicht als operative
`purchase.requisition` angelegt.

## Wirkungsfreiheit

Der Import verwendet ausschließlich:

- `kf.legacy.purchase.document`
- `kf.legacy.purchase.document.line`

Er erzeugt ausdrücklich keine:

- `purchase.order` oder `purchase.order.line`,
- `purchase.requisition`,
- Wareneingänge oder Lagerbewegungen,
- Rechnungen oder Buchungssätze,
- E-Mails.

Der Vorher-/Nachher-Abgleich bestätigte:

| Operatives Modell | Bestand nach Import |
|---|---:|
| `purchase.order` | 0 |
| `purchase.requisition` | 0 |
| `stock.picking` | 0 |
| `stock.move` | 0 |
| `account.move` | 0 |
| `mail.mail` | 115, unverändert |

## Datenqualität

513 Belege tragen `Prüfung erforderlich`. Die Ursachen überschneiden sich:

- 426 Belege enthalten auf Positionsebene unterschiedliche Belegdaten; im Kopf wird das
  früheste Datum gezeigt, jedes Positionsdatum bleibt zusätzlich erhalten.
- 39 Belege enthalten unterschiedliche eEvolution-Statuscodes.
- 24 Belege enthalten mindestens eine Position ohne Währungskennzeichen.
- 53 Einzelpositionen besitzen keine Sammelbestellnummer und wurden deshalb anhand ihrer
  eindeutigen `BESTELLUNG.BESTNR` als eigenständige Belege bewahrt.
- 2 Beleggruppen besitzen keinen eindeutig auflösbaren Lieferantenbezug; die
  eEvolution-Lieferantennummer bleibt am Beleg erhalten.

Das Prüfkennzeichen verwirft keine Daten und ergänzt keine Vermutungen. Preise und
Preiseinheiten werden als getrennte Quellwerte angezeigt und nicht ungeprüft
normalisiert.

## Zeitfilter

- Übernommen: 16.09.2016 bis einschließlich 16.09.2026.
- Fachliches Filterdatum: `COALESCE(BESTELLUNG.BIDAT, BESTELLUNG.BVDAT)`.
- Bewusst ausgeschlossen: 23.945 ältere Positionen vor dem Stichtag.
- `BESTELLUNG.LIEFERDAT` wurde nicht als Altersfilter verwendet, weil es Planwerte und
  zukünftige Termine enthalten kann.

## Wiederholbarkeit und Sicherung

- Modulstand: `kf_legacy_migration` 19.0.11.0.0.
- External IDs: stabile Schlüssel im Namensraum `__import__` für Köpfe und Positionen.
- Wiederholungslauf: 0 neue Belege, 0 neue Positionen, 0 Nebenwirkungen.
- Sicherung vor Modulaktualisierung und Import:
  `/var/backups/odoo/kuf-erp-all-data_20260916_145009_pre_historical_purchase_model_and_import`.
- Restore-getestete Abschlusssicherung:
  `/var/backups/odoo/kuf-erp-all-data_20260916_145344_post_historical_purchase_full`.

## Bedienung

Die Belege befinden sich unter:

`Rückverfolgung → Einkaufsbelege (Historie)`

Die Listenansicht kann nach Lieferant, Belegart und Jahr gruppiert werden. Im Beleg sind
Bestellmenge, gelieferte und reservierte Menge, Quellpreis, Preiseinheit, Währung,
Artikelbezug, Status, Termine und Stornokennzeichen sichtbar.

## Technische Nachweise

- Quellaudit: `99_scripts/245_audit_historical_purchase_source.py`
- Import: `99_scripts/246_import_historical_purchase_documents.py`
- Datenmodell: `odoo_addons/kf_legacy_migration/models/legacy_purchase_document.py`
- Ansicht: `odoo_addons/kf_legacy_migration/views/legacy_purchase_views.xml`
