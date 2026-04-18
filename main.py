"""
econsur_precios_ipc — Consulta de Precios Argentina
Datasets: data_ipc_indec.db · data_apendice4.db
Backend: FastAPI + SQLite x2
Fuente: INDEC — Apéndice Estadístico (Capítulo 4: Precios)
"""

import sqlite3
import io
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB1_PATH = DATA_DIR / "data_ipc_indec.db"
DB2_PATH = DATA_DIR / "data_apendice4.db"

DB_PATHS = {1: DB1_PATH, 2: DB2_PATH}

# ── Metadata por DB: tabla y columna fuente ─────────────────────────────────
DB_META = {
    1: {"table": "series_ipc_indec",   "col_fuente": "hoja_origen"},
    2: {"table": "series_apendice4",   "col_fuente": "hoja_origen"},
}

# ── Catálogo de fuentes ─────────────────────────────────────────────────────
# (hoja_origen, cuadro, nombre_cuadro, descripcion, db_num)
FUENTES_CATALOG = [
    # ── Dataset 1: IPC Nacional (data_ipc_indec.db) ──────────────────────
    (
        "4.1.1 IPC NG",
        "CUADRO 4.1.1",
        "IPC Nivel General — Nacional y Regiones",
        "Índice de Precios al Consumidor (IPC) Nivel General para el total nacional "
        "y aperturas regionales (GBA, Pampeana, NOA, NEA, Cuyo, Patagónica). "
        "Base Dic-2016=100. Frecuencia mensual y trimestral.",
        1,
    ),
    (
        "4.1.2 IPC Capitulos",
        "CUADRO 4.1.2",
        "IPC por Capítulos — Nacional y Regiones",
        "IPC desagregado por capítulos de la clasificación COICOP "
        "(Alimentos, Vivienda, Salud, Transporte, Educación, etc.) "
        "para el total nacional y regiones.",
        1,
    ),
    (
        "4.1.3 IPC Bs Ss",
        "CUADRO 4.1.3",
        "IPC Bienes y Servicios — Nacional y Regiones",
        "Distinción del IPC entre bienes y servicios para el total nacional y regiones. "
        "Permite analizar la diferente dinámica inflacionaria de cada componente.",
        1,
    ),
    (
        "4.1.4 IPC Incidencia Cap",
        "CUADRO 4.1.4",
        "Incidencia del IPC por Capítulos",
        "Contribución al IPC en puntos porcentuales de cada capítulo COICOP. "
        "Mide el aporte de cada componente a la variación mensual total del índice.",
        1,
    ),
    (
        "4.1.5 IPC Incidencia Bs Ss",
        "CUADRO 4.1.5",
        "Incidencia del IPC — Bienes y Servicios",
        "Contribución al IPC en puntos porcentuales de bienes y servicios. "
        "Fuente: INDEC.",
        1,
    ),
    (
        "4.1.6 IPC Categorias",
        "CUADRO 4.1.6",
        "IPC por Categorías — Nacional y Regiones",
        "IPC clasificado en categorías: Regulados, Estacionales y Núcleo (IPC sin "
        "regulados ni estacionales). Permite identificar factores detrás de la inflación.",
        1,
    ),
    (
        "4.1.7 Incidencia Cat",
        "CUADRO 4.1.7",
        "Incidencia del IPC por Categorías",
        "Contribución al IPC en puntos porcentuales de las categorías Regulados, "
        "Estacionales y Núcleo para el total nacional y regiones.",
        1,
    ),
    (
        "4.1.8 IPC precios canasta",
        "CUADRO 4.1.8",
        "Precios de la Canasta del IPC",
        "Precios en pesos corrientes de los productos representativos de la canasta "
        "del IPC. Publicación trimestral. Fuente: INDEC.",
        1,
    ),
    # ── Dataset 2: IPC GBA e Índices de Precios (data_apendice4.db) ──────
    (
        "4.2.1",
        "CUADRO 4.2.1",
        "IPC por División — Gran Buenos Aires",
        "Índice de Precios al Consumidor del Gran Buenos Aires (GBA) desagregado "
        "por división de la clasificación COICOP. Base Dic 2016=100.",
        2,
    ),
    (
        "4.2.2",
        "CUADRO 4.2.2",
        "IPC GBA — Bienes y Servicios",
        "IPC del Gran Buenos Aires distinguiendo entre bienes y servicios. "
        "Base histórica GBA.",
        2,
    ),
    (
        "4.2.3",
        "CUADRO 4.2.3",
        "IPC GBA — Apertura Geográfica",
        "IPC del Gran Buenos Aires con apertura geográfica (Ciudad de Buenos Aires "
        "y Conurbano Bonaerense). Permite comparar dinámicas de precios locales.",
        2,
    ),
    (
        "4.2.4",
        "CUADRO 4.2.4",
        "IPC GBA — Subgrupos COICOP",
        "IPC del Gran Buenos Aires desagregado a nivel de subgrupos COICOP (mayor "
        "desagregación). Contiene más de 260 series de precios al consumidor.",
        2,
    ),
    (
        "4.3.1 IPIM 4 dígitos",
        "CUADRO 4.3.1",
        "IPIM por Actividad — 4 dígitos CIIU",
        "Índice de Precios Internos al por Mayor (IPIM) desagregado a 4 dígitos CIIU. "
        "Mide la variación de precios de los bienes producidos en el país "
        "en la primera etapa de comercialización. Base Dic 2015=100.",
        2,
    ),
    (
        "4.4.1 IPIB 4 dígitos",
        "CUADRO 4.4.1",
        "IPIB por Actividad — 4 dígitos CIIU",
        "Índice de Precios Internos Básicos al por Mayor (IPIB) desagregado a "
        "4 dígitos CIIU. Excluye márgenes de comercialización e impuestos. "
        "Base Dic 2015=100.",
        2,
    ),
    (
        "4.5.1 IPP 4 dígitos",
        "CUADRO 4.5.1",
        "IPP por Actividad — 4 dígitos CIIU",
        "Índice de Precios al Productor (IPP) desagregado a 4 dígitos CIIU. "
        "Mide la variación de precios recibidos por los productores en la "
        "primera etapa de comercialización. Base Dic 2015=100.",
        2,
    ),
    (
        "4.6 ICC",
        "CUADRO 4.6",
        "Índice del Costo de la Construcción (ICC)",
        "Índice del Costo de la Construcción para edificios destinados a vivienda "
        "en la Ciudad de Buenos Aires. Desagregado en Materiales, Mano de Obra "
        "y Gastos Generales. Variación porcentual mensual.",
        2,
    ),
]

# Lookups rápidos
FUENTE_DB: dict[str, int] = {f[0]: f[4] for f in FUENTES_CATALOG}
FUENTE_INFO: dict[str, dict] = {
    f[0]: {"cuadro": f[1], "nombre_cuadro": f[2], "descripcion": f[3]}
    for f in FUENTES_CATALOG
}

# ── App ─────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="econsur — Precios IPC Argentina",
    description="Consulta integrada de índices de precios — INDEC / Apéndice Cap. 4",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── DB helpers ──────────────────────────────────────────────────────────────
def get_conn(db_num: int) -> sqlite3.Connection:
    path = DB_PATHS.get(db_num)
    if not path:
        raise HTTPException(400, detail=f"db_num={db_num} inválido.")
    if not path.exists():
        raise HTTPException(
            503,
            detail=(
                f"Base de datos '{path.name}' no disponible. "
                "El archivo debe estar en la carpeta data/ del repositorio."
            ),
        )
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def get_table(db_num: int) -> str:
    return DB_META[db_num]["table"]


# ── Normalización de frecuencias ────────────────────────────────────────────
_FREQ_NORMALIZE = {
    "ANUAL": "Anual", "TRIMESTRAL": "Trimestral",
    "MENSUAL": "Mensual", "SEMESTRAL": "Semestral",
    "Anual": "Anual", "Trimestral": "Trimestral",
    "Mensual": "Mensual", "Semestral": "Semestral",
}
_FREQ_ORDER = {"Anual": 0, "Semestral": 1, "Trimestral": 2, "Mensual": 3}


def normalize_freq(raw: str) -> str:
    return _FREQ_NORMALIZE.get(raw, raw.title())


# ── API: Diagnóstico ────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    db_status = {f"db{i}_ok": DB_PATHS[i].exists() for i in (1, 2)}
    all_ok = all(db_status.values())
    return {"status": "ok" if all_ok else "degraded", **db_status}


@app.get("/api/debug")
def debug():
    archivos = [f.name for f in DATA_DIR.iterdir()] if DATA_DIR.exists() else []
    counts: dict = {}
    for i, table_name in [(1, "series_ipc_indec"), (2, "series_apendice4")]:
        if DB_PATHS[i].exists():
            try:
                conn = sqlite3.connect(str(DB_PATHS[i]))
                counts[f"db{i}_series"] = conn.execute(
                    f"SELECT COUNT(DISTINCT serie_nombre) FROM {table_name}"
                ).fetchone()[0]
                counts[f"db{i}_rows"] = conn.execute(
                    f"SELECT COUNT(*) FROM {table_name}"
                ).fetchone()[0]
                conn.close()
            except Exception as e:
                counts[f"db{i}_error"] = str(e)
    return {
        "version": "1.0.0",
        "base_dir": str(BASE_DIR),
        "data_dir": str(DATA_DIR),
        "archivos_data": archivos,
        "fuentes_catalogo": len(FUENTES_CATALOG),
        **{f"db{i}_exists": DB_PATHS[i].exists() for i in (1, 2)},
        **counts,
    }


# ── API: Catálogos ──────────────────────────────────────────────────────────
@app.get("/api/fuentes")
def get_fuentes():
    """Lista completa de fuentes/hojas disponibles con su DB de origen."""
    return [
        {
            "fuente":        f[0],
            "cuadro":        f[1],
            "fuente_nombre": f[2],
            "descripcion":   f[3],
            "db_num":        f[4],
        }
        for f in FUENTES_CATALOG
        if DB_PATHS[f[4]].exists()
    ]


@app.get("/api/frecuencias")
def get_frecuencias(fuente: str = Query(...)):
    db_num = FUENTE_DB.get(fuente)
    if db_num is None:
        raise HTTPException(404, detail=f"Fuente '{fuente}' no encontrada.")
    conn = get_conn(db_num)
    table = get_table(db_num)
    try:
        rows = conn.execute(
            f"SELECT DISTINCT frecuencia FROM {table} "
            f"WHERE hoja_origen=? ORDER BY frecuencia",
            [fuente],
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        raise HTTPException(404, detail=f"No hay frecuencias para la fuente '{fuente}'.")
    normed = sorted(
        set(normalize_freq(r["frecuencia"]) for r in rows),
        key=lambda x: _FREQ_ORDER.get(x, 99),
    )
    return normed


@app.get("/api/series")
def get_series(fuente: str = Query(...), frecuencia: str = Query(...)):
    db_num = FUENTE_DB.get(fuente)
    if db_num is None:
        raise HTTPException(404, detail=f"Fuente '{fuente}' no encontrada.")
    conn = get_conn(db_num)
    table = get_table(db_num)
    try:
        rows = conn.execute(
            f"""SELECT DISTINCT serie_nombre
               FROM {table}
               WHERE hoja_origen=? AND frecuencia=? AND serie_nombre != ''
               ORDER BY serie_nombre""",
            [fuente, frecuencia],
        ).fetchall()
    finally:
        conn.close()
    return [{"serie_nombre": r["serie_nombre"]} for r in rows]


@app.get("/api/periodos")
def get_periodos(
    fuente: str = Query(...),
    frecuencia: str = Query(...),
    serie: str = Query(...),
):
    db_num = FUENTE_DB.get(fuente)
    if db_num is None:
        raise HTTPException(404, detail=f"Fuente '{fuente}' no encontrada.")
    conn = get_conn(db_num)
    table = get_table(db_num)
    try:
        rows = conn.execute(
            f"""SELECT periodo FROM {table}
               WHERE hoja_origen=? AND frecuencia=? AND serie_nombre=?
               ORDER BY periodo""",
            [fuente, frecuencia, serie],
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return {"desde": None, "hasta": None}
    periodos = [r["periodo"][:10] for r in rows if r["periodo"]]
    return {"desde": min(periodos), "hasta": max(periodos)}


@app.get("/api/datos/")
@app.get("/api/datos")
def get_datos(
    fuente: str = Query(...),
    frecuencia: str = Query(...),
    serie: str = Query(...),
    desde: str = Query(...),
    hasta: str = Query(...),
):
    if desde > hasta:
        raise HTTPException(400, detail="'desde' debe ser ≤ 'hasta'.")
    db_num = FUENTE_DB.get(fuente)
    if db_num is None:
        raise HTTPException(404, detail=f"Fuente '{fuente}' no encontrada.")
    conn = get_conn(db_num)
    table = get_table(db_num)
    info = FUENTE_INFO.get(fuente, {})
    try:
        rows = conn.execute(
            f"""SELECT periodo, año, frecuencia, cuadro,
                       hoja_origen, serie_nombre, unidad, valor
               FROM {table}
               WHERE hoja_origen=? AND frecuencia=? AND serie_nombre=?
                 AND periodo >= ? AND periodo <= ?
               ORDER BY periodo""",
            [fuente, frecuencia, serie, desde, hasta],
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return {"datos": [], "meta": {}}

    first = dict(rows[0])
    meta = {
        "serie_nombre":    first["serie_nombre"],
        "fuente":          first["hoja_origen"],
        "cuadro":          info.get("cuadro", first.get("cuadro", "")),
        "nombre_cuadro":   info.get("nombre_cuadro", ""),
        "unidad":          first.get("unidad", ""),
        "frecuencia":      frecuencia,
        "db_num":          db_num,
        "total_registros": len(rows),
    }
    datos = [
        {
            "periodo":     r["periodo"][:10] if r["periodo"] else None,
            "año":         r["año"],
            "valor":       r["valor"],
        }
        for r in rows
    ]
    return {"datos": datos, "meta": meta}


@app.get("/api/export/csv")
def export_csv(
    fuente: str = Query(...),
    frecuencia: str = Query(...),
    serie: str = Query(...),
    desde: str = Query(...),
    hasta: str = Query(...),
):
    result = get_datos(
        fuente=fuente, frecuencia=frecuencia,
        serie=serie, desde=desde, hasta=hasta,
    )
    datos, meta = result["datos"], result["meta"]

    buf = io.StringIO()
    buf.write(f"# Serie: {meta.get('serie_nombre', '')}\n")
    buf.write(f"# Cuadro: {meta.get('cuadro', '')} — {meta.get('nombre_cuadro', '')}\n")
    buf.write(f"# Fuente: {meta.get('fuente', '')}\n")
    buf.write(f"# Frecuencia: {meta.get('frecuencia', '')}\n")
    buf.write(f"# Unidad: {meta.get('unidad', '')}\n")
    buf.write(f"# Fuente original: INDEC — Apéndice Estadístico, Capítulo 4: Precios\n")
    buf.write("periodo,año,valor\n")
    for row in datos:
        buf.write(f"{row['periodo']},{row['año']},{row['valor']}\n")
    buf.seek(0)

    fname = (
        f"IPC_{meta.get('cuadro', fuente)[:20]}_{serie[:30]}"
        f"_{desde}_{hasta}.csv"
    ).replace(" ", "_").replace("/", "-").replace(".", "-")

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


# ── Frontend ────────────────────────────────────────────────────────────────
# Soporta dos layouts:
#   A) index.html en static/index.html  (layout preferido)
#   B) index.html en la raíz del proyecto (cuando static/ no existe en Render)
_STATIC_DIR  = BASE_DIR / "static"
_INDEX_PATHS = [
    _STATIC_DIR / "index.html",   # A: subcarpeta static/
    BASE_DIR    / "index.html",   # B: raíz del proyecto
]

def _find_index() -> Path:
    for p in _INDEX_PATHS:
        if p.exists():
            return p
    raise RuntimeError(
        "index.html no encontrado. Debe estar en static/index.html o en la raíz del proyecto."
    )

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    log.info("Sirviendo archivos estáticos desde: %s", _STATIC_DIR)
else:
    # Fallback: servir archivos desde la raíz (Render sin carpeta static/)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")
    log.warning("Carpeta static/ no encontrada — sirviendo desde raíz: %s", BASE_DIR)


@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse(_find_index().read_text(encoding="utf-8"))
