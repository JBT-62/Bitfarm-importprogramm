"""
eevo_schema.py
Wiederverwendbares Modul: liest eevo_schema.json und stellt
Hilfsfunktionen bereit, damit andere Skripte nie mehr Spaltennamen raten.

Voraussetzung: build_schema_cache.py einmal ausgeführt haben.

Verwendung:
    from eevo_schema import find, cols, has, pk, info

    fk  = find("ANGAUFPOS",  ["LFDANGAUFGUTNR", "ANGAUFGUTLFDNR"])
    mng = find("ANGAUFPOS",  ["BESTMENGE", "MENGE", "ANZAHL"])
    vk  = find("ANGAUFPOS",  ["PREIS", "VKPR1", "VK1"])
    art = find("ARTIKEL",    ["ARTNR1", "ARTNR"])
    bez = find("ARTIKEL",    ["ABEZ1", "ARTBEZ"])

    if has("ARTIKEL", "EKPR"):
        ...

    for c in cols("ANGAUFGUT"):
        print(c)          # Spaltennamen als Liste

    pk_col = pk("ANGAUFGUT")   # -> "LFDNR"
"""

import json, os, sys
from pathlib import Path

# Schema-Cache suchen: im gleichen Verzeichnis oder Projektordner
_KANDIDATEN = [
    Path(__file__).parent.parent / "eevo_schema.json",   # Projektordner
    Path(__file__).parent       / "eevo_schema.json",    # 99_scripts/
    Path("eevo_schema.json"),                             # cwd
]

_cache = None   # wird beim ersten Aufruf geladen


def _laden():
    global _cache
    if _cache is not None:
        return _cache

    for pfad in _KANDIDATEN:
        if pfad.exists():
            with open(pfad, encoding="utf-8") as f:
                _cache = json.load(f)
            print(f"[Schema] Geladen: {pfad}  "
                  f"({_cache['_meta']['tables']} Tabellen, "
                  f"Stand {_cache['_meta']['generated']})")
            return _cache

    # Kein Cache → Warnung, aber kein Absturz
    print("WARNUNG: eevo_schema.json nicht gefunden.")
    print("Bitte zuerst ausführen:  python 99_scripts/build_schema_cache.py")
    _cache = {"_meta": {}, "tables": {}}
    return _cache


def _tabelle(name: str) -> list:
    """Gibt Liste der Spalten-Dicts für eine Tabelle zurück (leer wenn unbekannt)."""
    return _laden()["tables"].get(name, [])


# ── Öffentliche API ──────────────────────────────────────────────────────────

def cols(tabelle: str) -> list[str]:
    """Alle Spaltennamen einer Tabelle (in Reihenfolge)."""
    return [c["col"] for c in _tabelle(tabelle)]


def cols_upper(tabelle: str) -> set[str]:
    """Spaltennamen als Uppercase-Set (für schnelle Suche)."""
    return {c["col"].upper() for c in _tabelle(tabelle)}


def has(tabelle: str, spalte: str) -> bool:
    """Prüft ob eine Spalte in der Tabelle existiert (case-insensitiv)."""
    return spalte.upper() in cols_upper(tabelle)


def find(tabelle: str, kandidaten: list[str]) -> str | None:
    """
    Gibt den ersten Kandidaten zurück, der in der Tabelle existiert.
    Gibt None zurück wenn kein Kandidat passt.

    Beispiel:
        fk = find("ANGAUFPOS", ["LFDANGAUFGUTNR", "ANGAUFGUTLFDNR", "KOPFLFDNR"])
        # → "LFDANGAUFGUTNR"
    """
    vorhanden = cols_upper(tabelle)
    for k in kandidaten:
        if k.upper() in vorhanden:
            return k
    return None


def pk(tabelle: str) -> str | None:
    """
    Versucht den Primärschlüssel einer Tabelle zu erraten.
    Typische eEvolution-Muster: LFDNR, LFD_NR, LFD<TABELLE>, <TABELLE>LFDNR
    """
    tbl_upper = tabelle.upper()
    kandidaten = [
        "LFDNR",
        "LFD_NR",
        f"LFD{tbl_upper}",
        f"LFD{tbl_upper}NR",
        f"{tbl_upper}LFDNR",
        "ID",
        "_ID",
    ]
    return find(tabelle, kandidaten)


def typ(tabelle: str, spalte: str) -> str | None:
    """Gibt den SQL-Datentyp einer Spalte zurück."""
    for c in _tabelle(tabelle):
        if c["col"].upper() == spalte.upper():
            return c["type"]
    return None


def tabellen() -> list[str]:
    """Alle Tabellennamen sortiert."""
    return sorted(_laden()["tables"].keys())


def suche_tabellen(muster: str) -> list[str]:
    """Tabellen deren Name das Muster enthält (case-insensitiv)."""
    m = muster.upper()
    return [t for t in tabellen() if m in t.upper()]


def info(tabelle: str) -> None:
    """Gibt Schema einer Tabelle auf der Konsole aus (für Debugging)."""
    spalten = _tabelle(tabelle)
    if not spalten:
        print(f"Tabelle '{tabelle}' nicht im Cache.")
        return
    print(f"\n{'─'*55}")
    print(f"  {tabelle}  ({len(spalten)} Spalten)")
    print(f"{'─'*55}")
    for c in spalten:
        null = " (NULL)" if c["nullable"] else ""
        print(f"  {c['pos']:>3}.  {c['col']:<35} {c['type']}{null}")
    print()


# ── Kurzreferenz der bekannten eEvolution-Felder ────────────────────────────
# Einmal entdeckt und hier dokumentiert. Wird von Skripten genutzt.

KNOWN = {
    # ARTIKEL
    "ARTIKEL.PK":          "LFDNR",
    "ARTIKEL.ARTNR":       "ARTNR1",
    "ARTIKEL.BEZ":         "ABEZ1",
    "ARTIKEL.BEZ2":        "ABEZ2",
    "ARTIKEL.EINHEIT":     "MENGENSCHL",   # direktes Code-Feld, kein FK
    "ARTIKEL.VK":          "VKPR1",
    "ARTIKEL.EK":          "EKPR",
    "ARTIKEL.LIEFNR_DEF":  "LFDLIEFNR",   # Standard-Lieferant FK

    # ARTIKELLONG
    "ARTIKELLONG.FK":      "LFDARTNR",    # → ARTIKEL.LFDNR
    "ARTIKELLONG.TEXT":    "CONTENT",

    # ANGAUFGUT (Angebot/Auftrag)
    "ANGAUFGUT.PK":        "LFDNR",
    "ANGAUFGUT.FLAG_ANG":  "ANGEBOT",
    "ANGAUFGUT.FLAG_AUF":  "AUFTRAG",
    "ANGAUFGUT.FLAG_GUT":  "GUTSCHRIFT",
    "ANGAUFGUT.KND":       "KNDNR",
    "ANGAUFGUT.DATUM":     "ERFASSDATUM",

    # ANGAUFPOS (Positionen zu ANGAUFGUT)
    "ANGAUFPOS.FK":        "LFDANGAUFGUTNR",   # → ANGAUFGUT.LFDNR
    "ANGAUFPOS.ART_FK":    "LFDARTNR",          # → ARTIKEL.LFDNR
    "ANGAUFPOS.MENGE":     "BESTMENGE",
    "ANGAUFPOS.PREIS":     "PREIS",
    "ANGAUFPOS.POS":       "POSNR",
    "ANGAUFPOS.TEXT":      "LANGTEXT",

    # ANFRAGE (Lieferantenanfragen – NICHT Kunden-CRM!)
    "ANFRAGE.PK":          "LFDANFRAGE",
    "ANFRAGEPOS.FK":       "LFDANFRAGE",        # gleicher Name wie PK Kopf

    # PRODLIST / PRODINHALT
    "PRODLIST.PK":         "LFD_NR",
    "PRODLIST.ART_FK":     "ART_NR",
    "PRODINHALT.FK":       "LIST_NR",
    "PRODINHALT.ART_FK":   "ART_NR",
    "PRODINHALT.EINHEIT":  "MENGENSCHL",

    # ARTSTUELI (Legacy-Stückliste)
    "ARTSTUELI.PARENT":    "LFDARTNR1",
    "ARTSTUELI.CHILD":     "LFDARTNR2",

    # ADRESS (nur Flags!)
    "ADRESS.PK":           "ADRNR",
    "ADRESS.KUND_FLAG":    "KUNDE",
    "ADRESS.LIEF_FLAG":    "LIEFERANT",

    # LIEFERANT (echte Lieferanten-Stammdaten)
    "LIEFERANT.PK":        "ADRNR",
    "LIEFERANT.NAME":      "NAME1",
    "LIEFERANT.ORT":       "ORT",
    "LIEFERANT.EMAIL":     "EMAIL",

    # MENGENSCHL (Mengeneinheiten)
    "MENGENSCHL.CODE":     "BEZ",      # = Kürzel (Stk, m, kg …)
    "MENGENSCHL.NAME":     "LBEZ",
}


def relations(tabelle: str, richtung: str = "von") -> list[dict]:
    """
    Gibt Beziehungen einer Tabelle zurück.

    richtung="von"  → ausgehende FKs (diese Tabelle verweist auf andere)
    richtung="zu"   → eingehende FKs (andere Tabellen verweisen hierher)
    richtung="alle" → beides

    Jede Relation ist ein Dict:
      { von, von_spalte, zu, zu_spalte, quelle }
    quelle: "db_constraint" | "bekannt" | "muster_lfd_tbl_nr" | ...

    Beispiel:
        for r in relations("ANGAUFPOS", "von"):
            print(f"{r['von_spalte']} → {r['zu']}.{r['zu_spalte']}")
        # LFDANGAUFGUTNR → ANGAUFGUT.LFDNR
        # LFDARTNR       → ARTIKEL.LFDNR
    """
    alle = _laden().get("relations", [])
    if richtung == "von":
        return [r for r in alle if r["von"] == tabelle]
    if richtung == "zu":
        return [r for r in alle if r["zu"] == tabelle]
    return [r for r in alle if r["von"] == tabelle or r["zu"] == tabelle]


def refs(tabelle: str) -> list[str]:
    """
    Gibt alle Tabellen zurück auf die `tabelle` direkt verweist (FK-Ziele).

    Beispiel:
        refs("ANGAUFPOS")   # → ["ANGAUFGUT", "ARTIKEL"]
    """
    return list({r["zu"] for r in relations(tabelle, "von")})


def ref_col(von_tabelle: str, zu_tabelle: str) -> str | None:
    """
    Gibt die FK-Spalte zurück mit der von_tabelle auf zu_tabelle zeigt.

    Beispiel:
        ref_col("ANGAUFPOS", "ANGAUFGUT")  # → "LFDANGAUFGUTNR"
        ref_col("ANGAUFPOS", "ARTIKEL")    # → "LFDARTNR"
    """
    for r in relations(von_tabelle, "von"):
        if r["zu"] == zu_tabelle:
            return r["von_spalte"]
    return None


def join_sql(von: str, zu: str, von_alias="a", zu_alias="b") -> str | None:
    """
    Erzeugt einen JOIN-Ausdruck wenn eine direkte Beziehung existiert.

    Beispiel:
        join_sql("ANGAUFPOS", "ANGAUFGUT", "p", "h")
        # → "JOIN ANGAUFGUT h ON h.LFDNR = p.LFDANGAUFGUTNR"

        join_sql("ANGAUFPOS", "ARTIKEL", "p", "ar")
        # → "LEFT JOIN ARTIKEL ar ON ar.LFDNR = p.LFDARTNR"
    """
    for r in relations(von, "von"):
        if r["zu"] == zu:
            verif = "JOIN" if r["quelle"] == "db_constraint" else "LEFT JOIN"
            return (f"{verif} {zu} {zu_alias} "
                    f"ON {zu_alias}.{r['zu_spalte']} = {von_alias}.{r['von_spalte']}")
    return None


def known(schluessel: str) -> str | None:
    """
    Gibt den bekannten Spaltennamen für einen semantischen Schlüssel zurück.

    Beispiel:
        fk  = known("ANGAUFPOS.FK")      # → "LFDANGAUFGUTNR"
        art = known("ARTIKEL.ARTNR")     # → "ARTNR1"
    """
    return KNOWN.get(schluessel)


# ── Selbsttest ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== eevo_schema Selbsttest ===\n")

    # Schema laden
    _laden()

    # Wichtige Tabellen
    for t in ["ARTIKEL", "ANGAUFGUT", "ANGAUFPOS", "ANFRAGE", "ANFRAGEPOS"]:
        spalt = cols(t)
        pk_c  = pk(t)
        print(f"{t:<20} {len(spalt):>3} Spalten  PK={pk_c}")
        print(f"  {', '.join(spalt[:8])}{'...' if len(spalt)>8 else ''}")

    print("\n--- KNOWN-Referenz ---")
    for k, v in KNOWN.items():
        print(f"  {k:<30} → {v}")

    print("\n--- Suche Tabellen mit 'ANG' ---")
    print(f"  {suche_tabellen('ANG')}")
