# Historische Verkaufsbelege `kuf-erp-all-data`

Stand: 16.09.2026

## Ergebnis

- Quellschnitt: eEvolution `ANGAUFGUT`/`ANGAUFPOS`, ab 16.09.2016,
  ohne Belegart 8 und ohne reine Gutschriften.
- 14.156 Quellköpfe wurden klassifiziert.
- 7.992 Köpfe wurden als historische `sale.order` übernommen.
- 6.164 Köpfe wurden als `kf.legacy.sales.document` vollständig in die Prüfliste übernommen.
- 5.055 vollständige abweichende Lieferadressen wurden belegbezogen angelegt.
- Wiederholungs-Dry-run: 0 neue Aufträge, 0 neue Prüffälle, 0 neue Lieferadressen,
  0 ungelöste Pflichtreferenzen.

## Wirkungsfreiheit

Historische Odoo-Verkaufsbelege tragen `kf_legacy_history=True`, die originale
eEvolution-ID, das Kennzeichen und den Originalstatus. Sie sind gesperrt. Das Modul
`kf_legacy_migration` in Version `19.0.10.0.0` blockiert Änderungen, Entsperren,
Bestätigen und Rechnungserzeugung. Der Pilot bewies zusätzlich:

- 0 erzeugte Lieferungen,
- 0 erzeugte Lagerbewegungen,
- 0 erzeugte Rechnungen oder Buchungssätze,
- 0 erzeugte E-Mails.

## Prüfliste

Ein Beleg wird nicht als Odoo-Auftrag angelegt, wenn mindestens einer dieser Gründe gilt:

- keine gültige Quellposition,
- unvollständige abweichende Lieferadresse,
- mindestens ein historischer Artikel ohne heutigen Odoo-Artikelanker.

Alle vorhandenen Quellpositionen bleiben in der Prüfliste erhalten, einschließlich
ungültiger/gelöschter Positionen. Mehrere Gründe werden gemeinsam ausgewiesen. Es gibt
keinen stillen Rückfall auf die Kundenhauptadresse und keine erfundenen Artikel.

## Technische Nachweise

- Import: `99_scripts/240_import_historical_sales_documents.py`
- Readiness: `99_scripts/239_audit_sales_import_readiness.py`
- Pilot/Schutztest: `99_scripts/242_audit_historical_sales_pilot.py`
- Fortschritt/Endstand: `99_scripts/243_monitor_historical_sales_import.py`
- Sicherung vor Vollimport:
  `/var/backups/odoo/kuf-erp-all-data_20260916_131135_pre_historical_sales_full`
- Wiederherstellungsgeprüfte Sicherung des fertigen Stands:
  `/var/backups/odoo/kuf-erp-all-data_20260916_132228_post_historical_sales_full`

Der Import ist über stabile External IDs idempotent. eEvolution wurde ausschließlich
read-only gelesen.
