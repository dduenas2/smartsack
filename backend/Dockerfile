# =============================================================================
# Dockerfile — Imagen del backend SmartSack (FastAPI + Python 3.11)
# -----------------------------------------------------------------------------
# Imagen ligera (slim) con todas las dependencias del stack: API, BD, ML, IA.
# =============================================================================

FROM python:3.11-slim

# Variables de entorno de Python para mejorar la experiencia en contenedores.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias del sistema necesarias para compilar paquetes Python
# (psycopg2, xgboost, scikit-learn, etc.) y para usar libgomp en runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar primero requirements para aprovechar la caché de Docker.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el código de la aplicación.
COPY . .

# Healthcheck que consulta el endpoint /health expuesto por main.py
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

EXPOSE 8000

# Arranque con Uvicorn en modo recarga para desarrollo.
# En producción quitar --reload y usar más workers (gunicorn + uvicorn workers).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
