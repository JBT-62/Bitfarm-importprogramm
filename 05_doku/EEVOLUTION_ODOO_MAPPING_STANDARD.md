# eEvolution → Odoo 19: Mapping- und External-ID-Standard

Stand: 2026-08-11

## Verbindliche Grundsätze

1. Die eEvolution-Datenbank `KuF` wird ausschließlich read-only analysiert.
2. Nicht jede technische, temporäre, Archiv- oder Sicherungstabelle wird nach Odoo migriert. Das vollständige Quellschema bleibt dennoch im Schema-Katalog dokumentiert.
3. Jeder importierte Odoo-Datensatz erhält vor dem ersten produktiven Import eine stabile External ID in `ir.model.data`.
4. External IDs werden aus unveränderlichen eEvolution-Primär- bzw. Geschäftsschlüsseln erzeugt, niemals aus laufenden Odoo-IDs oder Zeilennummern.
5. Ein erneuter Lauf sucht zuerst nach der External ID und führt anschließend `write` oder `create` aus (idempotenter Upsert).
6. Der verbindliche Zielnamensraum für eEvolution-Bindings ist `eevolution`. Bestehende
   Rehearsal-Bindings im Modul `__import__` werden nicht durch eine isolierte Codeänderung
   abgeschnitten. Sie müssen zuerst kontrolliert und dublettenfrei umgebunden oder durch
   eine explizite Kompatibilitätsauflösung weitergefunden werden. Erst danach dürfen die
   Importer auf `eevolution` umgestellt werden.

## Übergang von `__import__` nach `eevolution`

- Der aktuelle Rehearsal-Datenbestand enthält bereits zahlreiche stabile Bindings in
  `__import__`. Diese bleiben bis zur geprüften Binding-Migration gültige Identitätsanker.
- Eine bloße Änderung von `XML_MODULE = "__import__"` auf `"eevolution"` ist nicht
  ausreichend, weil der Upsert sonst vorhandene Datensätze nicht mehr findet.
- Die Umstellung umfasst Bestandsinventur, eindeutige 1:1-Zuordnung, kollisionsfreie
  Umbindung beziehungsweise Alias-Auflösung, Read-back sowie einen Wiederholungs-Dry-run
  mit null Neuanlagen.
- `99_scripts/pilot_import_angebot.py` wird entsprechend der Freigabe erst nach dem
  aktuellen Probeimport umgestellt.

## Aktuell verbindliche External-ID-Namensräume

| eEvolution-Objekt | Odoo-Modell | External-ID-Name | Quellschlüssel |
|---|---|---|---|
| ADRESS/KUNDE/LIEFERANT | `res.partner` | `ev_adr_<ADRNR>` | `ADRESS.ADRNR` |
| MITARBEITER (aktiv: `INAKTIV=0`, `LOESCHKNZ=0`) | `hr.employee` | `ev_employee_<MITARBNR>` | Mitarbeiternummer; ausdrücklich ohne `user_id` |
| fachlich freigegebene Odoo-Anwender | `res.users` | `ev_user_<MITARBNR>` | nur separate, namentlich freigegebene Benutzerteilmenge; niemals automatisch für alle Mitarbeiter |
| ADRANSPRECH | `res.partner` (`contact`) | `ev_ansprech_<LFDNR>` | Ansprechpartner-PK |
| KNDLIEFER | `res.partner` (`delivery`) | `ev_kndlief_<LFDNR>` | Lieferadress-PK |
| ARTIKEL | `product.template` | `ev_product_<LFDNR>` | `ARTIKEL.LFDNR` |
| ANGAUFGUT | `sale.order` | `ev_vorgang_<LFDNR>` | `ANGAUFGUT.LFDNR` |
| BESTELLUNG | `purchase.order` | `ev_bestellung_<LFDNR>` | Bestellungs-PK |
| AAGFAKT | `account.move` | `ev_fakt_<LFDFAKTNR>` | Faktura-PK |
| RECHEINGANG | `account.move` | `ev_rechein_<LFDNR>` | Rechnungseingangs-PK |
| VERKAUFSCHANCE | `crm.lead` | `ev_vkchance_<LFDNR>` | Chancen-PK |
| LAGERORT | `stock.location` | `ev_lager_<Schlüssel>` | stabiler Lager-Schlüssel |
| LAGERPL | `stock.location` | `ev_lagerpl_<Schlüssel>` | stabiler Lagerplatz-Schlüssel |
| PRODLIST | `mrp.bom` | `ev_prodlist_<LFDNR>` | Produktionslisten-PK |
| ARTSTUELI | `mrp.bom` | `ev_bom_<LFDNR>` | Stücklisten-PK |
| Seriennummer | `stock.lot` | `ev_snr_<Schlüssel>` | stabiler Serien-Schlüssel |
| Charge | `stock.lot` | `ev_chg_<Schlüssel>` | stabiler Chargen-Schlüssel |
| Lieferanteninfo | `product.supplierinfo` | `ev_supinfo_<Schlüssel>` | stabiler zusammengesetzter Schlüssel |
| Kundengruppe | `res.partner.category` | `ev_kgrup_<Code>` | Gruppencode |
| Zahlungsbedingung | `account.payment.term` | `ev_zbed_<Code>` | Bedingungscode |
| Warengruppe | `product.category` | `ev_wgrup_<Code>` | Warengruppencode |

Die vollständige External ID lautet nach abgeschlossener Umstellung zum Beispiel
`eevolution.ev_product_<LFDNR>`. Die früher dokumentierten Präfixe `ev_partner_*`,
`ev_supplier_*` und `ev_kuf_*` sind nicht verbindlich, sofern sie denselben Datensatz wie
`ev_adr_*` bezeichnen. Kunden- und Lieferantenrolle werden am gemeinsamen ADRESS-Datensatz
zusammengeführt, damit keine Partnerdubletten entstehen.

## Schema- und Qualitätsstand

Quelle ist der Cache `eevo_schema.json`, erzeugt am 2026-08-05 aus SQL-Server-Metadaten:

- 1.504 Basistabellen
- 27.715 Spalten
- 2.345 erfasste Beziehungen
- 2.325 konsistente Beziehungen
- 20 fragliche/inferierte Beziehungen
- 491 noch nicht aufgelöste potenzielle `LFD*`-Beziehungen
- 7 technische bzw. Sicherungstabellen ohne erkennbaren Schlüssel

`eevo_schema.md` ist der vollständige menschenlesbare Katalog aller Tabellen, Spalten und erkannten Beziehungen. `validate_report.json` enthält die maschinenlesbaren Qualitätsbefunde.

## Freigaberegel für ein Feld-Mapping

Ein Mapping gilt erst als freigegeben, wenn folgende Angaben vorhanden und geprüft sind:

- Quelltabelle, Quellspalte und Datentyp
- Quellschlüssel und Datensatz-Grain
- Join-Pfad zu Kopf-, Positions- und Lookup-Tabellen
- Odoo-Modell und technischer Feldname
- Transformations-, Lookup- oder Bereinigungsregel
- Null-/Pflichtfeldregel
- External-ID-Regel für den Zieldatensatz und alle relationalen Referenzen
- Stichprobenprüfung gegen Quelldaten und Odoo-Testinstanz
- dokumentiertes Verhalten bei erneutem Import

## Aktueller Prüfzugang

Der read-only Zugriff auf eEvolution `KuF` und der read-only XML-RPC-Abgleich mit
`erp-test-1` wurden am 11.08.2026 erfolgreich geprüft. Zugangsdaten bleiben lokal
geschützt und dürfen weder dokumentiert noch ausgegeben werden. Live-Abfragen sind
weiterhin nur gezielt und read-only zulässig.

Der PIA-Mappingtest bleibt dennoch blockiert, bis die vollständige Feld-Ziel-Tabelle,
die fehlenden Artikel-/Logistikfelder und die fachliche Auswahl der Lieferadressen
geklärt sind.
