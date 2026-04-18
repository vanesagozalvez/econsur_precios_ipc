"""
check_data.py — Verificación rápida de las bases de datos

Uso:
    python check_data.py

Reporta el estado de cada DB: tablas, columnas, cantidad de registros y series.
Útil para verificar antes de hacer deploy o luego de actualizar las bases.
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

DBS = {
    1: {
        "filename": "data_ipc_indec.db",
        "table":    "series_ipc_indec",
    },
    2: {
        "filename": "data_apendice4.db",
        "table":    "series_apendice4",
    },
}

SEP = "─" * 65


def check_db(db_num: int, meta: dict):
    path  = DATA_DIR / meta["filename"]
    table = meta["table"]

    print(f"\n{SEP}")
    print(f"  DB{db_num}: {meta['filename']}")
    print(SEP)

    if not path.exists():
        print(f"  ✗ ARCHIVO NO ENCONTRADO en {path}")
        return

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    try:
        size_mb = path.stat().st_size / 1024 / 1024
        print(f"  ✓ Archivo encontrado ({size_mb:.1f} MB)")

        cols = [c[1] for c in conn.execute(f"PRAGMA table_info('{table}')")]
        rows = conn.execute(f"SELECT COUNT(*) FROM '{table}'").fetchone()[0]
        series = conn.execute(
            f"SELECT COUNT(DISTINCT serie_nombre) FROM '{table}'"
        ).fetchone()[0]
        freqs = conn.execute(
            f"SELECT DISTINCT frecuencia FROM '{table}' ORDER BY frecuencia"
        ).fetchall()
        desde = conn.execute(f"SELECT MIN(periodo) FROM '{table}'").fetchone()[0]
        hasta = conn.execute(f"SELECT MAX(periodo) FROM '{table}'").fetchone()[0]

        print(f"\n  Tabla:       {table}")
        print(f"    Columnas:    {cols}")
        print(f"    Registros:   {rows:,}")
        print(f"    Series:      {series:,}")
        print(f"    Frecuencias: {[f['frecuencia'] for f in freqs]}")
        print(f"    Rango:       {desde} → {hasta}")

        hojas = conn.execute(
            f"SELECT DISTINCT hoja_origen FROM '{table}' ORDER BY hoja_origen"
        ).fetchall()
        print(f"\n  Hojas / Fuentes ({len(hojas)}):")
        for h in hojas:
            cnt = conn.execute(
                f"SELECT COUNT(DISTINCT serie_nombre) FROM '{table}' WHERE hoja_origen=?",
                [h["hoja_origen"]],
            ).fetchone()[0]
            print(f"    · {h['hoja_origen']:<40s} {cnt:>4} series")
    finally:
        conn.close()


if __name__ == "__main__":
    print("\n" + "═" * 65)
    print("  Verificación de bases de datos — Precios IPC Argentina")
    print("═" * 65)
    print(f"  Directorio data/: {DATA_DIR}")

    for num, meta in DBS.items():
        check_db(num, meta)

    print(f"\n{SEP}")
    print("  Verificación completada.")
    print(SEP + "\n")
