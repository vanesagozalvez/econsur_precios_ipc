# econsur · Precios IPC Argentina

Aplicación web de consulta de índices de precios de Argentina publicados por el **INDEC**.  
Backend **FastAPI + SQLite** · Frontend HTML/JS · Deploy en **Render**.

---

## 📦 Estructura del proyecto

```
econsur_precios_ipc/
├── main.py                  # Backend FastAPI (API REST + sirve el frontend)
├── requirements.txt         # Dependencias Python
├── render.yaml              # Configuración de deploy en Render
├── check_data.py            # Script de verificación de las bases de datos
├── etl_precios_ipc.py       # Script ETL para actualización manual de datos
├── static/
│   └── index.html           # Frontend (HTML + JS vanilla + Chart.js)
└── data/                    # ← Bases de datos SQLite (cargadas manualmente)
    ├── data_ipc_indec.db    #   IPC Nacional y por Regiones (Cuadros 4.1.x)
    └── data_apendice4.db    #   IPC GBA + Índices de Precios (Cuadros 4.2.x–4.6)
```

---

## 🗃️ Bases de datos

| Archivo | Tabla | Cuadros INDEC | Contenido |
|---|---|---|---|
| `data_ipc_indec.db` | `series_ipc_indec` | 4.1.1 – 4.1.8 | IPC Nacional, por regiones, capítulos, categorías |
| `data_apendice4.db` | `series_apendice4` | 4.2.1 – 4.6 | IPC GBA, IPIM, IPIB, IPP, ICC |

**Esquema de tablas (ambas):**

```sql
CREATE TABLE series_XXX (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    periodo      TEXT    NOT NULL,   -- 'YYYY-MM-DD'
    año          INTEGER,
    frecuencia   TEXT,               -- 'Mensual' | 'Trimestral'
    cuadro       TEXT,
    hoja_origen  TEXT,               -- identificador del cuadro
    serie_id     TEXT,
    serie_nombre TEXT,
    unidad       TEXT,
    valor        REAL,
    UNIQUE(hoja_origen, frecuencia, serie_nombre, periodo)
);
```

---

## 🚀 Deploy en Render

### 1. Preparar el repositorio GitHub

```
econsur_precios_ipc/       ← raíz del repo
├── main.py
├── requirements.txt
├── render.yaml
├── static/index.html
└── data/
    ├── data_ipc_indec.db
    └── data_apendice4.db
```

> ⚠️ Los archivos `.db` **se suben al repositorio** junto con el código.  
> Render los copia al **disco persistente** en cada deploy.

### 2. Configurar en Render

1. Crear cuenta en [render.com](https://render.com)
2. **New → Web Service** → conectar el repositorio GitHub
3. Render detecta automáticamente el `render.yaml` con estos parámetros:

| Setting | Valor |
|---|---|
| **Name** | `econsur-precios-ipc` |
| **Runtime** | Python |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Python version** | `3.11.0` |

4. En la sección **Disks** (plan Starter o superior):

| Setting | Valor |
|---|---|
| **Name** | `data-disk` |
| **Mount Path** | `/opt/render/project/src/data` |
| **Size** | 2 GB |

> 💡 El disco persistente evita perder los datos entre deploys.  
> Si usás el plan **Free**, los archivos `.db` se sirven directamente desde el repo (sin disco).

### 3. Variables de entorno

No se requieren variables de entorno adicionales.

### 4. Primer deploy

```bash
git add .
git commit -m "Initial deploy econsur_precios_ipc"
git push origin main
```

Render ejecutará automáticamente el build y el servicio quedará en:  
`https://econsur-precios-ipc.onrender.com`

---

## 🔄 Actualización de datos

Los datos se actualizan **manualmente** descargando los archivos del INDEC y regenerando las bases SQLite.

### Opción A — Reemplazar el archivo `.db` directamente

1. Generar el nuevo `.db` con `etl_precios_ipc.py` (ver abajo)
2. Reemplazar `data/data_ipc_indec.db` o `data/data_apendice4.db`
3. Hacer commit y push → Render redeploya automáticamente

### Opción B — Usar el ETL incluido

```bash
# Ver estadísticas actuales
python etl_precios_ipc.py --stats

# Cargar nuevos datos desde JSON exportado
python etl_precios_ipc.py --db ipc       --json nuevos_ipc.json
python etl_precios_ipc.py --db apendice4 --json nuevos_apendice4.json
```

El JSON de entrada debe ser una lista de objetos con los campos de la tabla.

### Verificar integridad antes del deploy

```bash
python check_data.py
```

---

## 🖥️ Correr localmente

```bash
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000
```

---

## 📡 API REST

| Endpoint | Descripción |
|---|---|
| `GET /api/health` | Estado de las bases de datos |
| `GET /api/debug` | Diagnóstico detallado |
| `GET /api/fuentes` | Catálogo completo de cuadros disponibles |
| `GET /api/frecuencias?fuente=...` | Frecuencias disponibles para un cuadro |
| `GET /api/series?fuente=...&frecuencia=...` | Series de una fuente/frecuencia |
| `GET /api/periodos?fuente=...&frecuencia=...&serie=...` | Rango de fechas de una serie |
| `GET /api/datos?fuente=...&frecuencia=...&serie=...&desde=...&hasta=...` | Datos de la consulta |
| `GET /api/export/csv?...` | Exportar datos en CSV |

---

## 📋 Cuadros disponibles

### Dataset 1 — IPC Nacional (`data_ipc_indec.db`)
| Cuadro | Contenido |
|---|---|
| 4.1.1 | IPC Nivel General — Nacional y Regiones |
| 4.1.2 | IPC por Capítulos — Nacional y Regiones |
| 4.1.3 | IPC Bienes y Servicios — Nacional y Regiones |
| 4.1.4 | Incidencia del IPC por Capítulos |
| 4.1.5 | Incidencia del IPC — Bienes y Servicios |
| 4.1.6 | IPC por Categorías (Regulados, Estacionales, Núcleo) |
| 4.1.7 | Incidencia del IPC por Categorías |
| 4.1.8 | Precios de la Canasta del IPC |

### Dataset 2 — IPC GBA e Índices (`data_apendice4.db`)
| Cuadro | Contenido |
|---|---|
| 4.2.1 | IPC por División — Gran Buenos Aires |
| 4.2.2 | IPC GBA — Bienes y Servicios |
| 4.2.3 | IPC GBA — Apertura Geográfica |
| 4.2.4 | IPC GBA — Subgrupos COICOP |
| 4.3.1 | IPIM por Actividad — 4 dígitos CIIU |
| 4.4.1 | IPIB por Actividad — 4 dígitos CIIU |
| 4.5.1 | IPP por Actividad — 4 dígitos CIIU |
| 4.6   | Índice del Costo de la Construcción (ICC) |

---

## 🛠️ Stack técnico

- **Backend**: FastAPI 0.115 + Uvicorn
- **Base de datos**: SQLite (2 archivos)
- **Frontend**: HTML5 + JavaScript vanilla + Chart.js 4.4
- **Deploy**: Render (Web Service + Persistent Disk)
- **Fuente de datos**: INDEC — Apéndice Estadístico, Capítulo 4: Precios

---

*Proyecto econsur · Datos macroeconómicos de Argentina*
