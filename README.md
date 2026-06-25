# SmartSack

[![CI](https://github.com/dduenas2/smartsack/actions/workflows/ci.yml/badge.svg)](https://github.com/dduenas2/smartsack/actions/workflows/ci.yml)

> Plataforma web inteligente para la **gestión de producción** en plantas de fabricación de sacos de papel.
>
> Trabajo de grado — Ingeniería de Software, **Politécnico Grancolombiano**.

---

## Descripción

SmartSack integra en una única plataforma tres capacidades clave para una planta industrial moderna:

1. **Digital Twin** de la línea de producción — vista en tiempo real para operarios y supervisores con WebSockets.
2. **Motor de ML predictivo** — predicción de retrasos en órdenes con Random Forest y XGBoost, dashboard de KPIs (OEE).
3. **Chatbot conversacional con IA** — consultas en lenguaje natural traducidas a SQL mediante la API de Claude (Anthropic) + LangChain.

---

## Stack tecnológico

| Capa             | Tecnologías                                                                |
| ---------------- | -------------------------------------------------------------------------- |
| Frontend         | React 18 · JavaScript · Vite · Tailwind CSS · Recharts                     |
| Backend          | Python 3.11 · FastAPI · SQLAlchemy · Pydantic · PyJWT · WebSockets         |
| Base de datos    | PostgreSQL 16 · Redis (caché de estado de máquinas)                        |
| ETL              | Pandas (CSV del ERP → PostgreSQL)                                          |
| Machine Learning | Scikit-learn · XGBoost · Joblib · Matplotlib · Seaborn · Jupyter           |
| IA Generativa    | API Claude (Anthropic) · LangChain · Function calling                      |
| Infraestructura  | Docker · Docker Compose · Nginx (reverse proxy) · Pytest · Git / GitHub    |

---

## Arquitectura

```
                    ┌──────────────────────────────┐
                    │       Nginx (puerto 80)      │
                    │   reverse proxy / unificador  │
                    └──────────────┬───────────────┘
                  /  /api/, /docs  │  /ws/
                  │                │
        ┌─────────▼────────┐  ┌────▼──────────┐
        │  Frontend React  │  │  Backend      │
        │  Vite · Tailwind │  │  FastAPI      │
        └──────────────────┘  └────┬──────────┘
                                   │
                  ┌────────────────┼────────────────┐
                  │                │                │
            ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
            │ Postgres  │    │   Redis   │    │  ML / IA  │
            │     16    │    │  (caché)  │    │  Claude   │
            └───────────┘    └───────────┘    └───────────┘
```

### Doble fuente de datos

- **ETL por lotes**: CSVs exportados del ERP (SAP) procesados con Pandas e insertados en PostgreSQL con validación y log de errores.
- **Captura en tiempo real**: los operarios registran eventos (paradas, cambios de formato, incidencias, fin de orden) que viajan vía REST y se propagan a supervisores por WebSockets.

---

## Estructura del repositorio

```
smartsack/
├── docker-compose.yml      # Orquestación de los 5 servicios
├── .env / .env.example     # Variables de entorno (no se versiona .env)
├── README.md               # Este archivo
│
├── backend/                # API FastAPI + ML + ETL
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/                # main, config, database, models, schemas, routers, services
│
├── frontend/               # SPA React 18 + Vite + Tailwind
│   ├── Dockerfile
│   ├── package.json
│   └── src/                # main, App, api, hooks, context, components, pages
│
├── docs/                   # Documentación del trabajo de grado (ver abajo)
│
└── nginx/                  # Reverse proxy
    ├── Dockerfile
    └── nginx.conf
```

---

## Documentación

La carpeta [`docs/`](docs/) reúne la documentación del trabajo de grado:

| Documento | Contenido |
|---|---|
| [`Documento_Final.md`](docs/Documento_Final.md) | Cierre del proyecto: resultados, cumplimiento de objetivos, lecciones y conclusiones |
| [`Manual_Usuario.md`](docs/Manual_Usuario.md) | Manual de usuario (con capturas) |
| [`Manual_Tecnico.md`](docs/Manual_Tecnico.md) | Manual técnico (despliegue y operación) |
| [`DATASET.md`](docs/DATASET.md) | Conjunto de datos sintético y su generación |
| [`Informe_Validacion_ML.md`](docs/Informe_Validacion_ML.md) | Evaluación del modelo de ML |
| [`Informe_Validacion_E7.md`](docs/Informe_Validacion_E7.md) | Validación consolidada (4 dimensiones) |
| [`Instrumento_SUS.md`](docs/Instrumento_SUS.md) | Cuestionario de usabilidad (SUS) |
| [`Instrumento_Impacto_Operativo.md`](docs/Instrumento_Impacto_Operativo.md) | Medición de impacto y satisfacción |
| [`Guion_Sustentacion.md`](docs/Guion_Sustentacion.md) | Material de apoyo para la defensa |

---

## Puesta en marcha (desarrollo)

### Requisitos previos

- Docker + Docker Compose (v2)
- Git
- (Opcional) API Key de Anthropic para usar el chatbot — [console.anthropic.com](https://console.anthropic.com)

### Pasos

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd smartsack

# 2. Crear el archivo de variables de entorno
cp .env.example .env
# Editar .env y completar JWT_SECRET_KEY y ANTHROPIC_API_KEY

# 3. Levantar todos los servicios
docker compose up -d --build

# 4. Aplicar las migraciones de base de datos
docker compose exec backend alembic upgrade head

# 5. Cargar los datos demo (8 máquinas, ~6 meses de historia, 24 operarios)
#    REQUERIDO para poder iniciar sesión: crea los usuarios de prueba.
docker compose exec backend python -m scripts.seed

# 6. Verificar que todo funciona
curl http://localhost/api/health
# → {"status":"ok","service":"SmartSack","timestamp":"..."}

# 7. Abrir la SPA en el navegador e iniciar sesión (ver "Usuarios de prueba")
# http://localhost
```

> **Importante:** una base de datos recién creada está vacía. Los pasos 4 y 5
> (migraciones + seed) son obligatorios antes del primer inicio de sesión; sin
> ellos la SPA carga pero no existe ningún usuario para autenticarse.

### Endpoints útiles

| Recurso              | URL                              |
| -------------------- | -------------------------------- |
| SPA (frontend)       | http://localhost                 |
| API REST             | http://localhost/api             |
| Health check         | http://localhost/api/health      |
| Documentación API    | http://localhost/docs            |
| Documentación ReDoc  | http://localhost/redoc           |
| WebSockets           | ws://localhost/ws/               |

### Comandos frecuentes

```bash
docker compose logs -f backend                              # Logs del backend
docker compose logs -f frontend                             # Logs del frontend
docker compose exec backend pytest                          # 187 tests del backend
docker compose exec frontend npm run test                   # 30 tests del frontend (Vitest)
docker compose exec frontend npm run lint                   # ESLint (flat config)
(cd frontend/e2e && npm test)                               # 12 tests E2E (Playwright, contra el stack)
docker compose exec backend alembic upgrade head            # Aplicar migraciones
docker compose exec backend python -m scripts.seed          # Cargar datos demo (8 máquinas, 6 meses de historia)
docker compose exec backend python -m scripts.generate_sample_csvs  # Crear CSVs de ejemplo en /app/samples/
docker compose exec backend python -m scripts.demo_two_operators    # Demo de 2 operarios trabajando operaciones
docker compose exec backend bash                            # Shell dentro del backend
docker compose down                                         # Detener
docker compose down -v                                      # Detener y borrar la BD (reset)
```

### Usuarios de prueba (después del seed)

| Rol         | Usuario          | Contraseña      | Notas                          |
| ----------- | ---------------- | --------------- | ------------------------------ |
| Admin       | `admin`          | `smartsack123`  | Acceso total                   |
| Supervisor  | `supervisor1`    | `smartsack123`  | Línea A                        |
| Supervisor  | `supervisor2`    | `smartsack123`  | Línea B                        |
| Operario    | `op_imp-01_1`    | `smartsack123`  | IMP-01 (Impresora línea A)     |
| Operario    | `op_tub-01_1`    | `smartsack123`  | TUB-01 (Tubuladora línea A)    |
| Operario    | `op_emp-02_1`    | `smartsack123`  | EMP-02 (Empacadora línea B)    |

> El seed crea 24 operarios (3 turnos × 8 máquinas). Patrón: `op_<machine-code>_<n>`.

### Ejecutar el modelo de ML

```bash
docker compose exec backend python -m ml.train         # Entrena Random Forest + XGBoost, guarda en ml/models/
docker compose exec backend python -m ml.train --quick  # Variante con grid reducido (más rápida)
```

> Las predicciones en runtime las sirve la API (`/api/predictions/...`): el
> servicio carga el modelo entrenado de `ml/models/` de forma perezosa.

### Cargar datos por ETL

Los CSVs viven en `backend/samples/` y se pueden subir desde:

- **UI**: `http://localhost/etl` (rol admin/supervisor)
- **API**: `POST /api/etl/upload` (form-data: `file`, `kind`)
- **Plantillas**: `GET /api/etl/sample-csv/{kind}` para descargar la cabecera vacía.

---

## Integración Continua (CI)

El repositorio incluye un pipeline de **GitHub Actions** (`.github/workflows/ci.yml`)
que se ejecuta en cada `push` a `main`, en cada *pull request* y de forma manual
(`workflow_dispatch`). Valida automáticamente:

| Job                | Qué valida                                                                                                                          |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| `frontend-quality` | ESLint (flat config) + Vitest (pruebas de componentes React).                                                                     |
| `integration`      | Levanta el stack completo con Docker Compose, migra y siembra la BD, corre los tests del backend (Pytest) y los 4 flujos E2E (Playwright) contra Nginx. |

El chatbot corre en **modo fallback** (sin `ANTHROPIC_API_KEY`), que es justo lo
que verifican las pruebas E2E: **el CI no requiere ningún secret para pasar**. El
modelo de ML tampoco se entrena en CI; los tests de predicción que dependen del
`.joblib` se saltan automáticamente (`pytest.skipif`).

### Cómo activarlo

El workflow ya está listo en el repositorio. Solo hay que subirlo a GitHub:

```bash
git remote add origin git@github.com:dduenas2/smartsack.git
git push -u origin main
```

Desde el primer push, GitHub Actions ejecuta el pipeline automáticamente y el
badge de estado del encabezado refleja el resultado. Sustituye `dduenas2` por
tu usuario u organización de GitHub (en el badge y en el comando de arriba).

---

## Convenciones de desarrollo

- **Idioma**: identificadores y código en inglés; UI y mensajes para usuarios en español.
- **Comentarios**: cada archivo lleva docstring inicial; las funciones complejas también.
- **Commits**: descriptivos, en español, uno por funcionalidad completada.
- **Configuración**: nunca hardcoded — siempre vía `.env`.
- **Validación**: Pydantic en backend, validación en frontend con feedback al usuario.
- **Errores**: nunca silenciar — `try/except` con logging apropiado.
- **Documentación de API**: Swagger se genera automáticamente; añadir descripciones a cada endpoint.

---

## Roadmap del proyecto

| Paso | Entregable                                                                    | Estado    |
| ---- | ----------------------------------------------------------------------------- | --------- |
| 1    | Entorno Docker (postgres, redis, backend, frontend, nginx) + health check     | ✅ Listo  |
| 2    | Modelo de datos (SQLAlchemy + Alembic + seed con 6 meses de historia)         | ✅ Listo  |
| 3    | Autenticación JWT + roles (operario, supervisor, admin)                       | ✅ Listo  |
| 4    | ETL desde CSV de SAP (production_orders, confirmations, materials, shipments) | ✅ Listo  |
| 5    | API REST: máquinas, órdenes, operaciones, eventos, dashboard, predicciones    | ✅ Listo  |
| 6    | Vista operario y vista supervisor (Digital Twin con WebSockets)               | ✅ Listo  |
| 7    | Cálculo de OEE + dashboard de KPIs (scrap Pareto, yield, WIP)                 | ✅ Listo  |
| 8    | Motor de ML (XGBoost) + predicciones proactivas                               | ✅ Listo  |
| 9    | Chatbot con API de Claude + LangChain + function calling (9 tools)            | ✅ Listo  |
| 10   | Pruebas (187 backend + 30 Vitest + 12 E2E) + CI (GitHub Actions), docs        | ✅ Listo  |
| 11   | Dataset a escala con señal ML + validación E7 (modelo, SUS, impacto)           | ✅ Listo  |
| 12   | Manuales de usuario y técnico (con capturas)                                   | ✅ Listo  |
| 13   | Documento final + guion de sustentación                                        | ✅ Listo  |

---

## Autor

David — estudiante de Ingeniería de Software, Politécnico Grancolombiano.

## Licencia

Proyecto académico. Uso restringido a fines educativos del trabajo de grado.
