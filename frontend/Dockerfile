# =============================================================================
# Dockerfile — Frontend SmartSack (React 18 + Vite)
# -----------------------------------------------------------------------------
# Imagen para el servidor de desarrollo de Vite con hot-reload.
# Para producción se sustituye por una build estática servida por Nginx.
# =============================================================================

FROM node:20-alpine

WORKDIR /app

# Copiar primero package.json para aprovechar la caché de Docker.
COPY package.json ./
RUN npm install

# Copiar el resto del código del frontend.
COPY . .

EXPOSE 5173

# Vite necesita --host 0.0.0.0 para ser accesible desde fuera del contenedor.
CMD ["npm", "run", "dev"]
