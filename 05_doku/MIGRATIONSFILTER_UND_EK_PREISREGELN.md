# Migrationsfilter und EK-Preisregeln

Stand: 6. August 2026

## Verbindliche Auswahlregeln

1. Der Cutover-Stichtag wird als Laufparameter übergeben und nicht fest im Code hinterlegt.
2. Geschäftsvorgänge werden nur übernommen, wenn ihr fachliches Belegdatum höchstens zehn Jahre vor dem Cutover liegt.
3. Lagerbewegungen werden nur für die letzten fünf Jahre vor dem Cutover übernommen.
4. `ARTIKEL.INAKTIV` ist bei K&F ausdrücklich **kein Ausschlusskriterium**. Benötigte Artikel werden unabhängig von diesem Kennzeichen importiert.
5. Nur Artikel mit `ARTIKEL.LOESCHKNZ <> 0` werden ausgeschlossen. Verweist eine benötigte Stückliste auf einen löschgekennzeichneten Artikel, muss der Import abbrechen und eine fachliche Ersatzentscheidung verlangen.
6. Jeder importierte Datensatz erhält eine stabile Odoo-External-ID.

## Live ermittelte Filterwirkung

- `ARTIKEL`: 5.957 Datensätze insgesamt, davon 4.182 nach der obigen Regel aktiv.
- `LAGERBEWEGUNG`: 1.015.647 Datensätze insgesamt.
- `LAGERBEWEGUNG` im Fünfjahresfenster: 186.595 Datensätze für 3.461 Artikel.
- Davon besitzen 65 Lagerbewegungen die Menge null und müssen ausgeschlossen oder fachlich geprüft werden.
- Zwischen `LAGERBEWEGUNG.LFDARTNR` und `ARTIKEL.LFDNR` wurden keine verwaisten Referenzen gefunden.

## Durchschnittlicher Einkaufspreis

Die zunächst vermuteten Tabellen `RECHKOPFEINGANG` und `RECHPOSEINGANG` sind in der Datenbank leer und können nicht als historische Preisquelle verwendet werden.

Als belastbare Quelle wird `BESTELLUNG` verwendet:

- `BESTELLUNG.ARTNR` verweist vollständig auf `ARTIKEL.LFDNR` (41.806 von 41.806 Zeilen zuordenbar).
- Innerhalb des rollierenden Zehnjahresfensters liegen 18.015 Bestellzeilen für 2.677 Artikel vor.
- `ARTIKEL.EKPR` bleibt nur ein Fallback für aktive Artikel ohne valide Preisbeobachtung im freigegebenen Zeitraum.

Empfohlene fachliche Definition:

```text
Durchschnitts-EK je Artikel =
Summe(Netto-EK je Basiseinheit × gültige Menge)
÷ Summe(gültige Menge)
```

Vor Umsetzung müssen folgende Bestandteile mit Einkauf/Controlling anhand von mindestens zehn Artikeln geprüft werden:

- Welche Werte von `BESTSTATUS` gelten als abgeschlossen und preiswirksam?
- Ist `RABATTGESAMMT` ein Prozent- oder Betragswert?
- Wie werden `PREISEINHEIT`, `FAKTOR`, `UMRECHKURS` und `UMRECHEINHEIT` exakt angewendet?
- Sollen Rückgaben, Stornos und negative Mengen ausgeschlossen oder gegenläufig berücksichtigt werden?
- Soll der Durchschnitt mengen­gewichtet oder zeitlich gewichtet sein? Empfohlen ist mengen­gewichtet.
- Soll der ermittelte Wert in `product.template.standard_price` geschrieben oder zunächst nur als Prüfwert bereitgestellt werden?

## Zeitfelder

Der Zehnjahresfilter muss je Objekt auf das fachliche Belegdatum angewendet werden. Technische Felder wie `TMSTMP` oder ein zukünftiges Lieferdatum sind dafür nicht geeignet.

Vorläufige Zuordnung:

| Objekt | Fachliches Filterdatum |
|---|---|
| Angebote/Aufträge | `ANGAUFGUT.ERFASSDATUM` |
| Bestellungen/EK-Historie | `COALESCE(BESTELLUNG.BIDAT, BESTELLUNG.BVDAT)` |
| Rechnungen | jeweiliges Rechnungs-/Buchungsdatum |
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
- alte Vorgänge außerhalb des jeweiligen Zeitfensters,
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
