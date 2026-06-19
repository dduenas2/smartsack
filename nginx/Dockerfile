# =============================================================================
# Dockerfile — Nginx reverse proxy de SmartSack
# -----------------------------------------------------------------------------
# Imagen mínima que sustituye la configuración por defecto de Nginx por la
# nuestra (rutas: / → frontend, /api → backend, /ws → WebSockets backend).
# =============================================================================
FROM nginx:1.27-alpine

# Reemplazar la configuración por defecto.
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
