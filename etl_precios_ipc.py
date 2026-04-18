"""
etl_precios_ipc.py — ETL de actualización manual de las bases de datos de precios

Uso:
    python etl_precios_ipc.py --source <archivo_indec.xlsx> --db <ipc|apendice4>

Descripción:
    Script de apoyo para actualizar manualmente las bases SQLite a partir de los
    archivos Excel publicados por el INDEC en su Apéndice Estadístico (Capítulo 4).

    Los archivos de datos se colocan en data/ y se suben al repositorio de GitHub.
    El deploy en Render monta el disco persistente apuntando a esa carpeta.

Bases de datos generadas:
    data/data_ipc_indec.db   — series_ipc_indec  (Cuadros 4.1.x)
    data/data_apendice4.db   — series_apendice4  (Cuadros 4.2.x – 4.6)

Columnas de cada tabla:
    periodo      TEXT  — fecha ISO 8601 (YYYY-MM-DD), primer día del período
    año          INT   — año del período
    frecuencia   TEXT  — 'Mensual' | 'Trimestral' | 'Anual'
    cuadro       TEXT  — número de cuadro (ej: 'CUADRO 4.1.1')
    hoja_origen  TEXT  — nombre de la hoja Excel de origen
    serie_id     TEXT  — identificador interno de la serie (o 'N/A')
    serie_nombre TEXT  — nombre descriptivo de la serie
    unidad       TEXT  — unidad de medida
    valor        REAL  — valor numérico observado
"""

import argparse
import sqlite3
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_CONFIG = {
    "ipc": {
        "path":  DATA_DIR / "data_ipc_indec.db",
        "table": "series_ipc_indec",
    },
    "apendice4": {
        "path":  DATA_DIR / "data_apendice4.db",
        "table": "series_apendice4",
    },
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS {table} (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    periodo      TEXT    NOT NULL,
    año          INTEGER,
    frecuencia   TEXT,
    cuadro       TEXT,
    hoja_origen  TEXT,
    serie_id     TEXT,
    serie_nombre TEXT,
    unidad       TEXT,
    valor        REAL,
    UNIQUE(hoja_origen, frecuencia, serie_nombre, periodo)
);
"""

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_{table}_hoja_freq_serie
    ON {table}(hoja_origen, frecuencia, serie_nombre);
CREATE INDEX IF NOT EXISTS idx_{table}_periodo
    ON {table}(periodo);
"""


def init_db(db_key: str):
    cfg   = DB_CONFIG[db_key]
    conn  = sqlite3.connect(str(cfg["path"]))
    table = cfg["table"]
    conn.executescript(CREATE_TABLE_SQL.format(table=table))
    conn.executescript(INDEX_SQL.format(table=table))
    conn.commit()
    print(f"  ✓ DB inicializada: {cfg['path']}")
    return conn, table


def load_from_json(json_path: Path, db_key: str):
    """
    Carga registros desde un JSON exportado por el ETL fuente.
    El JSON debe ser una lista de objetos con los campos de la tabla.
    """
    cfg   = DB_CONFIG[db_key]
    conn, table = init_db(db_key)

    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    inserted = updated = skipped = 0
    for rec in records:
        try:
            conn.execute(
                f"""INSERT OR REPLACE INTO {table}
                   (periodo, año, frecuencia, cuadro, hoja_origen,
                    serie_id, serie_nombre, unidad, valor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rec.get("periodo"),
                    rec.get("año"),
                    rec.get("frecuencia"),
                    rec.get("cuadro"),
                    rec.get("hoja_origen"),
                    rec.get("serie_id", "N/A"),
                    rec.get("serie_nombre"),
                    rec.get("unidad"),
                    rec.get("valor"),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            skipped += 1

    conn.commit()
    conn.close()
    print(f"  Insertados: {inserted:,}  |  Omitidos: {skipped:,}")
    print(f"  ✓ Carga completada en {cfg['path']}")


def show_stats(db_key: str):
    cfg   = DB_CONFIG[db_key]
    table = cfg["table"]
    if not cfg["path"].exists():
        print(f"  ✗ No existe: {cfg['path']}")
        return
    conn = sqlite3.connect(str(cfg["path"]))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    series = conn.execute(f"SELECT COUNT(DISTINCT serie_nombre) FROM {table}").fetchone()[0]
    hojas  = conn.execute(
        f"SELECT hoja_origen, COUNT(DISTINCT serie_nombre) as n FROM {table} "
        f"GROUP BY hoja_origen ORDER BY hoja_origen"
    ).fetchall()
    conn.close()
    print(f"  DB: {cfg['path'].name}  |  Registros: {rows:,}  |  Series: {series:,}")
    for h in hojas:
        print(f"    · {h['hoja_origen']:<40s} {h['n']:>4} series")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ETL — Precios IPC Argentina")
    parser.add_argument("--db",     choices=["ipc", "apendice4"], help="Base de datos destino")
    parser.add_argument("--json",   help="Archivo JSON de entrada")
    parser.add_argument("--stats",  action="store_true", help="Mostrar estadísticas de las DBs")
    args = parser.parse_args()

    if args.stats:
        for key in DB_CONFIG:
            print(f"\n── {key.upper()} ──────────────────────────")
            show_stats(key)
    elif args.json and args.db:
        json_path = Path(args.json)
        if not json_path.exists():
            print(f"  ✗ Archivo no encontrado: {json_path}")
        else:
            print(f"\nCargando {json_path} → {args.db} …")
            load_from_json(json_path, args.db)
    else:
        parser.print_help()
