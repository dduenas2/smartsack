# Manual técnico — SmartSack

**Proyecto:** SmartSack · **Entregable:** E8 · **Audiencia:** personal técnico
(despliegue, operación y mantenimiento)

Guía de instalación, configuración, operación y resolución de problemas de la
plataforma SmartSack.

---

## 1. Descripción general

SmartSack es una plataforma web complementaria al ERP para plantas de
fabricación de sacos de papel. Integra tres capacidades sobre un mismo backend:

- **Digital Twin** en tiempo real (operarios y supervisores vía WebSockets).
- **Motor de predicción de retrasos** (ML) + dashboard de KPIs/OEE.
- **Asistente conversacional** que traduce preguntas en lenguaje natural a
  consultas sobre la base de datos mediante la API de Claude.

Todo se ejecuta con **Docker Compose**; no requiere instalación a nivel de host
más allá de Docker.

## 2. Arquitectura

Cinco servicios en la red `smartsack_net`:

| Servicio | Imagen / base | Rol |
|---|---|---|
| `postgres` | PostgreSQL 16 | Base de datos relacional |
| `redis` | Redis 7 | Caché de estado de máquinas |
| `backend` | FastAPI (Python) | API REST + WebSockets + ML + chatbot |
| `frontend` | React 18 + Vite | SPA (interfaz de usuario) |
| `nginx` | Nginx | **Punto de entrada único** (proxy) |

**Nginx** es la única puerta de entrada (puerto 80):

- `/api/` → backend (REST).
- `/ws/` → backend (WebSockets).
- `/docs`, `/redoc`, `/openapi.json` → backend (Swagger/OpenAPI).
- todo lo demás → frontend (SPA).

### Fuentes de datos

1. **ETL por lotes** (`POST /api/etl/upload`): CSVs exportados del ERP
   (órdenes, confirmaciones, materiales, despachos) validados con Pandas.
2. **Captura en tiempo real**: los operarios registran eventos (paradas,
   cambios de formato, incidencias, cierre de orden) que se propagan a los
   supervisores por WebSockets.

## 3. Requisitos previos

- **Docker** 24+ y **Docker Compose** v2.
- Puertos libres en el host: **80** (Nginx). En desarrollo también se exponen
  8000 (backend), 5173 (frontend), 5432 (postgres) y 6379 (redis).
- ~2 GB de RAM disponibles.

## 4. Instalación y despliegue

```bash
# 1. Clonar el repositorio
git clone https://github.com/dduenas2/smartsack.git
cd smartsack

# 2. Crear el archivo de entorno a partir de la plantilla
cp .env.example .env
#    Editar .env y definir: POSTGRES_PASSWORD, DATABASE_URL (misma contraseña),
#    JWT_SECRET_KEY (openssl rand -hex 32) y, opcionalmente, ANTHROPIC_API_KEY.

# 3. Levantar el stack
docker compose up -d --build

# 4. Migrar la base de datos
docker compose exec backend alembic upgrade head

# 5. Sembrar datos de demostración (8 máquinas, 6 meses de historia, 20 usuarios)
docker compose exec backend python -m scripts.seed --reset

# 6. (Opcional) Entrenar el modelo de predicción de retrasos
docker compose exec backend python -m ml.train
```

La aplicación queda disponible en **http://localhost**.

## 5. Variables de entorno

Definidas en `.env` (plantilla en `.env.example`). El backend las valida en
`app/config.py` (nunca se lee `os.environ` directamente).

| Variable | Descripción | Por defecto |
|---|---|---|
| `ENVIRONMENT` | Entorno de ejecución | `development` |
| `TZ` | Zona horaria | `America/Bogota` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Credenciales de PostgreSQL | `smartsack` / *(definir)* / `smartsack` |
| `DATABASE_URL` | Cadena de conexión (debe contener la misma contraseña) | — |
| `REDIS_URL` | Conexión a Redis | `redis://redis:6379/0` |
| `BACKEND_HOST` / `BACKEND_PORT` | Bind del backend | `0.0.0.0` / `8000` |
| `JWT_SECRET_KEY` | Clave de firma JWT (`openssl rand -hex 32`) | *(definir)* |
| `JWT_ALGORITHM` | Algoritmo JWT | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Vigencia del token | `480` |
| `CORS_ORIGINS` | Orígenes permitidos (coma) | `http://localhost,...` |
| `VITE_API_BASE_URL` / `VITE_WS_BASE_URL` | Rutas que usa el frontend | `/api` / `/ws` |
| `ANTHROPIC_API_KEY` | Clave de la API de Claude. **Vacía → chatbot en modo fallback** | *(vacía)* |
| `ANTHROPIC_MODEL` | Modelo de Claude | `claude-sonnet-4-6` |
| `LOG_LEVEL` | Nivel de log | `INFO` |

> **Seguridad:** `.env` no se versiona. En producción, usa contraseñas fuertes,
> un `JWT_SECRET_KEY` aleatorio y restringe `CORS_ORIGINS` al dominio real.

## 6. Operación

### URLs útiles

| Recurso | URL |
|---|---|
| Aplicación (SPA) | http://localhost |
| API REST | http://localhost/api |
| Documentación interactiva (Swagger) | http://localhost/docs |
| WebSocket | ws://localhost/ws/ |

### Comandos frecuentes

```bash
# Migraciones (Alembic)
docker compose exec backend alembic upgrade head
docker compose exec backend alembic revision --autogenerate -m "mensaje"

# Re-sembrar datos (reinicia secuencias de identidad → IDs estables)
docker compose exec backend python -m scripts.seed --reset

# Entrenar / generar figuras del modelo ML
docker compose exec backend python -m ml.train
docker compose exec backend python -m ml.figures

# Generar CSVs de ejemplo para el ETL
docker compose exec backend python -m scripts.generate_sample_csvs --count 60

# Ver logs
docker compose logs -f backend
```

## 7. Autenticación y roles

Autenticación por **JWT** (Bearer). Tres roles:

- `operario` — vista de su máquina y registro de eventos.
- `supervisor` — Digital Twin completo, dashboard, ETL.
- `admin` — todo lo anterior + administración de usuarios.

**Usuarios de demostración** (contraseña `smartsack123`):

| Usuario | Rol |
|---|---|
| `admin` | admin |
| `supervisor1` | supervisor |
| `op_imp-01_1` (y similares por máquina) | operario |

> Cambia estas credenciales antes de cualquier despliegue real.

## 8. Componentes técnicos

- **Backend** (`backend/app/`): arquitectura por capas
  `routers → services → models ← schemas`. `config.py` expone un único objeto
  `settings`. Todos los routers se montan bajo el prefijo `/api`.
- **WebSocket** (`app/websocket/manager.py`): los supervisores/admin reciben
  todo el tráfico de planta; cada operario sólo los mensajes de su máquina.
- **Chatbot** (`app/services/chat_service.py`): dos modos transparentes.
  *Modo LLM* (con `ANTHROPIC_API_KEY` válida): LangChain + function calling.
  *Modo fallback* (sin clave): enrutador heurístico por palabras clave. La
  conversación es sin estado (el frontend envía el historial completo).
- **ML** (`backend/ml/`): `features.py` es la única fuente de verdad de las
  features y la etiqueta. `train.py` escribe `models/delay_predictor.joblib` +
  manifest. La inferencia carga el modelo en memoria y expone `reload_model()`.
  Si no existe el `.joblib`, los endpoints de predicción piden entrenar primero.

## 9. Mantenimiento

```bash
# Backup de la base de datos
docker compose exec postgres pg_dump -U smartsack smartsack > backup_$(date +%F).sql

# Restaurar
cat backup.sql | docker compose exec -T postgres psql -U smartsack smartsack

# Reiniciar todo desde cero (DESTRUYE el volumen de datos)
docker compose down -v && docker compose up -d --build
```

## 10. Resolución de problemas

| Síntoma | Causa probable | Solución |
|---|---|---|
| El puerto 80 no levanta | Otro servicio usa el puerto | Liberar el 80 o remapear `nginx` en `docker-compose.yml` |
| Los endpoints de predicción dan error | El modelo no está entrenado | `docker compose exec backend python -m ml.train` |
| El chatbot responde genérico/por palabras clave | `ANTHROPIC_API_KEY` vacía o inválida | Definirla en `.env` y reiniciar `backend` |
| Las pruebas o la app fallan por datos faltantes | BD sin migrar/sembrar | `alembic upgrade head` + `scripts.seed --reset` |
| `Permission denied` al hacer checkout/reset en git | El contenedor escribió archivos como root en `backend/samples` o `backend/ml` | `docker compose exec -T backend chown -R 1000:1000 /app/samples /app/ml` |
| Cambios en `.env` no surten efecto | El contenedor cachea el entorno | `docker compose up -d --force-recreate backend` |

## 11. Pruebas

```bash
# Backend (requiere BD migrada + sembrada)
docker compose exec backend pytest

# Frontend (unitarias + lint)
docker compose exec frontend npm run test
docker compose exec frontend npm run lint

# E2E (Playwright, contra el stack)
(cd frontend/e2e && npm test)
```

El pipeline de CI (GitHub Actions) ejecuta estas mismas pruebas en cada push y
pull request.
