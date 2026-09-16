# Migrationsfilter und EK-Preisregeln

Stand: 16. September 2026

## Verbindliche Auswahlregeln

1. Produktiver Go-live ist der 01.01.2027. Der fachliche Cutoff ist das Ende des 31.12.2026; technisch gilt als obere exklusive Grenze `2027-01-01 00:00:00 Europe/Berlin`. Diese Grenze wird als Laufparameter übergeben und nicht still aus dem Laufdatum abgeleitet.
2. Historische Hauptbelege werden über die vollständige belegte eEvolution-Historie übernommen: Verkaufsbelege, Lieferscheine, Einkaufsbelege, Produktionsauftragsköpfe, Ausgangsrechnungen und Eingangsrechnungen einschließlich ihrer Belegpositionen.
3. Technische Serien-/Chargenrückverfolgung und Produktionsdetails werden für das feste Halbintervall `2017-01-01 00:00:00` inklusive bis `2027-01-01 00:00:00 Europe/Berlin` exklusiv übernommen. Dazu gehören tatsächliche Komponentenbuchungen, Produktionsausgaben mit Serien/Chargen und abgeleitete Verwendungsbeziehungen. Ältere Produktionsaufträge erhalten nur den informativen Kopf.
4. Einzelne historische Lagerbuchungen werden nicht operativ nachgebaut. Sollte später ein gesonderter Lagerbewegungsblock beschlossen werden, gilt dafür weiterhin maximal das Fünfjahresfenster.
5. Historische Rechnungen werden ausschließlich als schreibgeschützte Referenzbelege ohne `account.move`, offene Posten oder Buchungssätze übernommen.
6. CRM-Termine und CRM-Freitexthistorie bleiben bis zur gesonderten Aufbewahrungsentscheidung im Zehnjahresfenster; CRM ist kein Hauptbeleg im Sinne von Regel 2.
7. Artikel mit `ARTIKEL.INAKTIV <> 0` werden als archivierte Referenzartikel übernommen (`active=False`, `sale_ok=False`, `purchase_ok=False`).
8. Artikel mit `ARTIKEL.LOESCHKNZ <> 0` werden ausgeschlossen. Verweist eine benötigte Stückliste auf einen ausgeschlossenen Artikel, muss der Import abbrechen und eine fachliche Ersatzentscheidung verlangen.
9. Jeder importierte Datensatz erhält eine stabile Odoo-External-ID.

## Live ermittelte Filterwirkung

- `ARTIKEL`: 5.957 Datensätze insgesamt, davon 4.182 nach der obigen Regel aktiv.
- `LAGERBEWEGUNG`: 1.015.647 Datensätze insgesamt.
- `LAGERBEWEGUNG` im Fünfjahresfenster: 186.595 Datensätze für 3.461 Artikel.
- Davon besitzen 65 Lagerbewegungen die Menge null und müssen ausgeschlossen oder fachlich geprüft werden.
- Zwischen `LAGERBEWEGUNG.LFDARTNR` und `ARTIKEL.LFDNR` wurden keine verwaisten Referenzen gefunden.

## Durchschnittlicher Einkaufspreis

eEvolution führt den gleitenden Durchschnitts-Einkaufspreis bereits in
`ARTIKEL.DEKPR`. Dieser Wert wird als Startkostenwert nach
`product.template.standard_price` übernommen. Die Odoo-Produktkategorien werden
auf **Durchschnittskosten (AVCO)** gestellt; zukünftige bewertete Zugänge führen
den mengengewichteten Durchschnitt in Odoo fort.

`ARTIKEL.EKPR` ist der letzte beziehungsweise aktuelle Einkaufspreis und darf den
AVCO-Kostenwert nicht regelmäßig überschreiben. Lieferantenspezifische Preise
werden getrennt in `product.supplierinfo` geführt.

`DEKPR <= 0` wird nicht automatisch als Kostenwert geschrieben. Solche Artikel
bleiben fachliche Prüffälle; ein positiver `EKPR` darf nur nach ausdrücklich
freigegebener Fallback-Regel verwendet werden.

## Zeitfelder

Der Zehnjahresfilter wird nur auf technische Rückverfolgung, Produktionsdetails und vorläufig auf CRM-Historie angewendet. Hauptbelege werden vollständig übernommen. Technische Felder wie `TMSTMP` oder ein zukünftiges Lieferdatum sind weder als fachliches Belegdatum noch als unterer Altersfilter geeignet.

Vorläufige Zuordnung:

| Objekt | Fachliches Filterdatum |
|---|---|
| Angebote/Aufträge | `ANGAUFGUT.ERFASSDATUM`; vollständige Historie |
| Lieferscheine | `AAGLS.LSDATUM`; vollständige Historie |
| Bestellungen/EK-Historie | `COALESCE(BESTELLUNG.BIDAT, BESTELLUNG.BVDAT)`; vollständige Historie |
| Produktionsauftragskopf | fachlich freizugebende Produktionsdatumspriorität; vollständige Historie |
| Produktionsdetails | jeweiliges Buchungs-/Einlagerungsdatum; zehn Jahre |
| Ausgangs-/Eingangsrechnungen | `AAGFAKT.FAKTDATUM` / `RECHEINGANG.RECHDATUM`; vollständige Historie |
| Lagerbewegungen | `LAGERBEWEGUNG.BUCHDATUM` |
| Seriennummern | `INVARTSERIE.EINKAUFSDATUM` |
| Chargen | `COALESCE(INVARTCHARGE.EINKAUFSDATUM, INVARTCHARGE.HERSTELLDATUM)` |
| Seriennummern-Bewegungshistorie | `SNRARCHIV.BUCHDATUM` |
| CRM-Aktivitäten/-Termine | `TERMIN.ANFTERMIN` |
| CRM | Erfassungs-/Abschlussdatum der Verkaufschance |

`BESTELLUNG.LIEFERDAT` darf nicht als allgemeines Alterskriterium verwendet werden: Es enthält Planwerte und aktuell 16 Datensätze, die mehr als ein Jahr in der Zukunft liegen.

## Nicht zu übernehmende Daten

- technische Felder wie `ROWID`, `_ID`, `usn` und technische Zeitstempel,
- Backup-, Temp-, Reparatur- und Sicherungstabellen,
- von Odoo berechnete Summen, Restbeträge und Lagerbewertungen,
- wirkungslose Lagerbewegungen mit Menge null,
- Artikel mit gesetztem `LOESCHKNZ`,
- Serien-/Chargen- und Produktionsdetaildaten außerhalb des Zehnjahresfensters,
- Legacy-Integrationsfelder wie Outlook-IDs und lokale Datei-/Bildpfade ohne bestätigten Nutzen.

## External IDs

Beispiele:

```text
eevolution.partner_<ADRNR>
eevolution.product_<LFDNR>
eevolution.bom_<LFD_NR>
eevolution.sale_order_<LFDNR>
eevolution.stock_move_<stabiler Bewegungsschlüssel>
eevolution.serial_<stabiler Seriennummernschlüssel>
```

Ein produktiver Import darf nicht fortfahren, wenn ein Datensatz angelegt wurde, aber die zugehörige External-ID nicht erfolgreich registriert werden konnte.
