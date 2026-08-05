#!/usr/bin/env python3
"""
build_schema_cache.py
Einmalig ausführen: liest das komplette INFORMATION_SCHEMA aus eEvolution
und schreibt eevo_schema.json + eevo_schema.md als Referenz.

Ausführen:
    python 99_scripts/build_schema_cache.py

Ergebnisse (im Projektordner):
    eevo_schema.json   ← von anderen Skripten importiert (eevo_schema.py)
    eevo_schema.md     ← lesbare Referenz für Claude / Entwickler
"""

import os, sys, json
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import pyodbc
except ImportError:
    sys.exit("FEHLER: pyodbc fehlt.  pip install pyodbc")


def ee_connect():
    driver   = os.getenv("EV_DRIVER",   "ODBC Driver 18 for SQL Server")
    server   = os.getenv("EV_SERVER",   "192.168.120.234")
    database = os.getenv("EV_DATABASE", "KuF")
    user     = os.getenv("EV_USER",     "excel_kuf_readonly")
    password = os.getenv("EV_PASSWORD", "")
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},1433;"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
    )
    conn = pyodbc.connect(conn_str, timeout=10)
    print(f"[OK] Verbunden mit {server}/{database}")
    return conn, server, database


def main():
    conn, server, database = ee_connect()
    cur = conn.cursor()

    # ── Alle Tabellen + Spalten aus INFORMATION_SCHEMA ───────────────────────
    print("[1] Lese INFORMATION_SCHEMA …")
    cur.execute("""
        SELECT
            t.TABLE_NAME,
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.NUMERIC_PRECISION,
            c.NUMERIC_SCALE,
            c.IS_NULLABLE,
            c.ORDINAL_POSITION
        FROM INFORMATION_SCHEMA.TABLES t
        JOIN INFORMATION_SCHEMA.COLUMNS c
            ON c.TABLE_NAME = t.TABLE_NAME
        WHERE t.TABLE_TYPE = 'BASE TABLE'
        ORDER BY t.TABLE_NAME, c.ORDINAL_POSITION
    """)

    schema = {}   # { "TABELLE": [ {col, type, ...}, ... ] }
    for row in cur.fetchall():
        tbl  = row[0]
        col  = row[1]
        typ  = row[2]
        clen = row[3]
        prec = row[4]
        scal = row[5]
        null = row[6]
        pos  = row[7]

        if typ in ("numeric", "decimal") and prec is not None:
            type_str = f"{typ}({prec},{scal})"
        elif clen and clen != -1:
            type_str = f"{typ}({clen})"
        elif clen == -1:
            type_str = f"{typ}(MAX)"
        else:
            type_str = typ

        schema.setdefault(tbl, []).append({
            "col":      col,
            "type":     type_str,
            "nullable": null == "YES",
            "pos":      pos,
        })

    print(f"    {len(schema)} Tabellen, {sum(len(v) for v in schema.values())} Spalten")

    # ── Echte FK-Constraints (SQL Server sys.*) ───────────────────────────────
    print("[2] Lese FK-Constraints (sys.foreign_keys) …")
    fk_echt = []
    try:
        cur.execute("""
            SELECT
                tp.name  AS von_tabelle,
                cp.name  AS von_spalte,
                tr.name  AS zu_tabelle,
                cr.name  AS zu_spalte,
                fk.name  AS constraint_name
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc
                ON fkc.constraint_object_id = fk.object_id
            JOIN sys.tables tp
                ON tp.object_id = fk.parent_object_id
            JOIN sys.columns cp
                ON cp.object_id = fk.parent_object_id
               AND cp.column_id = fkc.parent_column_id
            JOIN sys.tables tr
                ON tr.object_id = fk.referenced_object_id
            JOIN sys.columns cr
                ON cr.object_id = fk.referenced_object_id
               AND cr.column_id = fkc.referenced_column_id
            ORDER BY tp.name, cp.name
        """)
        for row in cur.fetchall():
            fk_echt.append({
                "von":        row[0],
                "von_spalte": row[1],
                "zu":         row[2],
                "zu_spalte":  row[3],
                "constraint": row[4],
                "quelle":     "db_constraint",
            })
        print(f"    {len(fk_echt)} echte FK-Constraints gefunden")
    except Exception as e:
        print(f"    FK-Constraints nicht lesbar ({e}) – nur Inferenz")

    conn.close()

    # ── Konventions-basierte Beziehungs-Inferenz ──────────────────────────────
    print("[3] Inferiere Beziehungen aus Namenskonventionen …")

    alle_tabellen = set(schema.keys())

    def inferiere_beziehungen(schema, alle_tabellen):
        """
        eEvolution-Namensmuster:
          LFDANGAUFGUTNR  → ANGAUFGUT.LFDNR      (LFD + TABELLE + NR)
          LFDARTNR        → ARTIKEL.LFDNR         (LFD + TABELLE ohne Endung + NR)
          LFDANFRAGE      → ANFRAGE.LFDANFRAGE    (gleicher Name wie PK)
          ADRNR           → ADRESS.ADRNR          (bekannte Schlüsselspalte)
          KNDNR           → ADRESS.ADRNR (Kunden) oder ANGAUFGUT
          LFD_NR          → PK der eigenen Tabelle
        """
        rels = []
        seen = set()

        # Bekannte direkte Mappings (manuell kuratiert)
        DIREKT = {
            "ADRNR":       ("ADRESS", "ADRNR"),
            "KNDNR":       ("ADRESS", "ADRNR"),
            "LIEFNR":      ("LIEFERANT", "ADRNR"),
            "LFDARTNR":    ("ARTIKEL", "LFDNR"),
            "LFDLIEFNR":   ("LIEFERANT", "ADRNR"),
        }

        for tbl, cols_list in schema.items():
            col_namen = [c["col"] for c in cols_list]
            col_upper = {c.upper() for c in col_namen}

            for col in col_namen:
                col_u = col.upper()
                key = (tbl, col)
                if key in seen:
                    continue

                # 1. Direkte bekannte Mappings
                if col_u in DIREKT:
                    zu_tbl, zu_col = DIREKT[col_u]
                    if zu_tbl in alle_tabellen:
                        rels.append({
                            "von": tbl, "von_spalte": col,
                            "zu":  zu_tbl, "zu_spalte": zu_col,
                            "quelle": "bekannt",
                        })
                        seen.add(key)
                        continue

                # 2. Muster: LFD + <TABELLE> + NR  z.B. LFDANGAUFGUTNR → ANGAUFGUT
                if col_u.startswith("LFD") and col_u.endswith("NR") and col_u != "LFDNR":
                    mitte = col_u[3:-2]          # z.B. "ANGAUFGUT"
                    # direkt → ANGAUFGUT
                    if mitte in alle_tabellen:
                        zu_tbl = mitte
                        zu_col = "LFDNR" if "LFDNR" in {c["col"].upper() for c in schema[zu_tbl]} else "LFD_NR"
                        rels.append({
                            "von": tbl, "von_spalte": col,
                            "zu":  zu_tbl, "zu_spalte": zu_col,
                            "quelle": "muster_lfd_tbl_nr",
                        })
                        seen.add(key)
                        continue
                    # ohne Endung versuchen: LFDANFRAGE → ANFRAGE (kein NR am Ende)
                    # (wird über Muster 3 abgedeckt)

                # 3. Muster: LFD + <TABELLE>  (ohne NR) z.B. LFDANFRAGE → ANFRAGE
                if col_u.startswith("LFD") and col_u != "LFDNR":
                    kandidat = col_u[3:]          # z.B. "ANFRAGE"
                    if kandidat in alle_tabellen:
                        zu_tbl = kandidat
                        # PK der Zieltabelle ermitteln
                        zu_pks = [c["col"] for c in schema[zu_tbl]
                                  if c["col"].upper() in (f"LFD{kandidat}", f"LFD{kandidat}NR",
                                                          "LFDNR", "LFD_NR")]
                        zu_col = zu_pks[0] if zu_pks else col   # gleicher Name wie FK
                        rels.append({
                            "von": tbl, "von_spalte": col,
                            "zu":  zu_tbl, "zu_spalte": zu_col,
                            "quelle": "muster_lfd_tbl",
                        })
                        seen.add(key)
                        continue

                # 4. Muster: <TABELLE>LFDNR  z.B. ANGAUFGUTLFDNR → ANGAUFGUT (umgekehrt)
                if col_u.endswith("LFDNR"):
                    kandidat = col_u[:-5]         # z.B. "ANGAUFGUT"
                    if kandidat in alle_tabellen:
                        zu_tbl = kandidat
                        zu_col = "LFDNR" if "LFDNR" in {c["col"].upper() for c in schema[zu_tbl]} else "LFD_NR"
                        rels.append({
                            "von": tbl, "von_spalte": col,
                            "zu":  zu_tbl, "zu_spalte": zu_col,
                            "quelle": "muster_tbl_lfdnr",
                        })
                        seen.add(key)

        return rels

    fk_inferiert = inferiere_beziehungen(schema, alle_tabellen)
    print(f"    {len(fk_inferiert)} inferierte Beziehungen")

    # Deduplizieren: echte FK-Constraints haben Vorrang
    echt_keys = {(r["von"], r["von_spalte"]) for r in fk_echt}
    fk_inferiert_neu = [r for r in fk_inferiert
                        if (r["von"], r["von_spalte"]) not in echt_keys]

    alle_rels = fk_echt + fk_inferiert_neu
    print(f"    {len(alle_rels)} Beziehungen gesamt (echt + inferiert)")

    # ── JSON speichern ────────────────────────────────────────────────────────
    cache = {
        "_meta": {
            "server":          server,
            "database":        database,
            "generated":       datetime.now().isoformat(timespec="seconds"),
            "tables":          len(schema),
            "columns":         sum(len(v) for v in schema.values()),
            "relations":       len(alle_rels),
            "relations_db":    len(fk_echt),
            "relations_infer": len(fk_inferiert_neu),
        },
        "tables":    schema,
        "relations": alle_rels,
    }

    json_pfad = "eevo_schema.json"
    with open(json_pfad, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    print(f"[OK] Gespeichert: {json_pfad}")

    # ── Markdown-Referenz ─────────────────────────────────────────────────────
    print("[4] Erstelle eevo_schema.md …")
    md_pfad = "eevo_schema.md"

    # Wichtige Tabellen zuerst
    WICHTIG = [
        "ARTIKEL", "ARTIKELLONG", "ADRESS", "KUNDE", "LIEFERANT",
        "ADRANSPRECH", "ANGAUFGUT", "ANGAUFPOS", "ANGAUFARCHIV",
        "ANGAUFARCHIVPOS", "ANGEBOT", "ANFRAGE", "ANFRAGEPOS",
        "PRODLIST", "PRODINHALT", "ARTSTUELI",
        "MENGENSCHL", "ZAHLBEDING", "LAND", "VERTRETER",
        "PREISLISTEN", "PREISLISTKOPF", "CHARGEN", "SERNR",
        "LIEFRECH", "BESTELLUNG", "KNDLIEFER",
    ]

    with open(md_pfad, "w", encoding="utf-8") as f:
        m = cache["_meta"]
        f.write(f"# eEvolution Schema – {m['database']} @ {m['server']}\n\n")
        f.write(f"Generiert: {m['generated']}  ·  "
                f"{m['tables']} Tabellen  ·  {m['columns']} Spalten\n\n")
        f.write("> Automatisch generiert von `build_schema_cache.py`.\n"
                "> Neu generieren nach Schema-Änderungen in eEvolution.\n\n")

        # Beziehungs-Index (pro Tabelle)
        rel_von  = {}   # { tbl: [ rel, ... ] }  (ausgehende FKs)
        rel_zu   = {}   # { tbl: [ rel, ... ] }  (eingehende FKs)
        for r in alle_rels:
            rel_von.setdefault(r["von"], []).append(r)
            rel_zu.setdefault(r["zu"],  []).append(r)

        def tabelle_schreiben(name, cols):
            f.write(f"## {name}\n\n")
            f.write(f"| # | Spalte | Typ | Null? | Beziehung |\n")
            f.write(f"|---|--------|-----|-------|----------|\n")
            # Beziehungen pro Spalte
            col_rels = {r["von_spalte"].upper(): r for r in rel_von.get(name, [])}
            for c in cols:
                null    = "✓" if c["nullable"] else ""
                rel_txt = ""
                r = col_rels.get(c["col"].upper())
                if r:
                    q = "✓" if r["quelle"] == "db_constraint" else "~"
                    rel_txt = f"{q} → `{r['zu']}`.`{r['zu_spalte']}`"
                f.write(f"| {c['pos']} | `{c['col']}` | {c['type']} | {null} | {rel_txt} |\n")

            # Tabellen die auf diese Tabelle verweisen
            eingehend = rel_zu.get(name, [])
            if eingehend:
                f.write(f"\n**Referenziert von:** ")
                refs = [f"`{r['von']}`.`{r['von_spalte']}`" for r in eingehend[:8]]
                f.write(", ".join(refs))
                if len(eingehend) > 8:
                    f.write(f" … (+{len(eingehend)-8})")
                f.write("\n")
            f.write("\n")

        # Beziehungs-Übersicht oben
        f.write("---\n\n## Tabellenbeziehungen\n\n")
        f.write(f"| Von | Von-Spalte | Zu | Zu-Spalte | Quelle |\n")
        f.write(f"|-----|-----------|----|-----------|---------|\n")
        quelle_icon = {
            "db_constraint":      "✓ DB",
            "bekannt":            "★ bekannt",
            "muster_lfd_tbl_nr":  "~ Muster",
            "muster_lfd_tbl":     "~ Muster",
            "muster_tbl_lfdnr":   "~ Muster",
        }
        for r in sorted(alle_rels, key=lambda x: (x["von"], x["von_spalte"])):
            icon = quelle_icon.get(r["quelle"], r["quelle"])
            f.write(f"| `{r['von']}` | `{r['von_spalte']}` | "
                    f"`{r['zu']}` | `{r['zu_spalte']}` | {icon} |\n")
        f.write("\n> ✓ DB = echte FK-Constraint  "
                "★ bekannt = manuell kuratiert  "
                "~ Muster = aus Namenskonvention inferiert\n\n")

        # Wichtige Tabellen zuerst
        f.write("---\n\n## Wichtige Tabellen (Kerntabellen)\n\n")
        for name in WICHTIG:
            if name in schema:
                tabelle_schreiben(name, schema[name])

        # Rest alphabetisch
        f.write("---\n\n## Alle weiteren Tabellen (alphabetisch)\n\n")
        for name in sorted(schema.keys()):
            if name not in WICHTIG:
                tabelle_schreiben(name, schema[name])

    print(f"[OK] Gespeichert: {md_pfad}")
    print(f"\nNächster Schritt:")
    print(f"  git add eevo_schema.json eevo_schema.md")
    print(f"  git commit -m 'add: eEvolution Schema-Cache'")
    print(f"  git push")
    print(f"\nDanach in Skripten nutzen:")
    print(f"  from eevo_schema import find, cols, has, pk")


if __name__ == "__main__":
    main()
