# SmartSack

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
└── nginx/                  # Reverse proxy
    ├── Dockerfile
    └── nginx.conf
```

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

# 4. Verificar que todo funciona
curl http://localhost/api/health
# → {"status":"ok","service":"SmartSack","timestamp":"..."}

# 5. Abrir la SPA en el navegador
# http://localhost
```

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
docker compose exec backend pytest                          # 134 tests del backend
docker compose exec frontend npm run test                   # 17 tests del frontend (Vitest)
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
docker compose exec backend python -m ml.evaluate      # Métricas detalladas + matriz de confusión
docker compose exec backend python -m ml.predict_all   # Genera predicciones para todas las órdenes activas
```

### Cargar datos por ETL

Los CSVs viven en `backend/samples/` y se pueden subir desde:

- **UI**: `http://localhost/etl` (rol admin/supervisor)
- **API**: `POST /api/etl/upload` (form-data: `file`, `kind`)
- **Plantillas**: `GET /api/etl/sample-csv/{kind}` para descargar la cabecera vacía.

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
| 9    | Chatbot con API de Claude + LangChain + function calling (8 tools)            | ✅ Listo  |
| 10   | Pruebas (134 backend + 17 frontend), documentación, despliegue                | ✅ Listo  |

---

## Autor

David — estudiante de Ingeniería de Software, Politécnico Grancolombiano.

## Licencia

Proyecto académico. Uso restringido a fines educativos del trabajo de grado.
