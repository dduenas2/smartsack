/**
 * vite.config.js — Configuración de Vite + Vitest para SmartSack (frontend).
 *
 * - Usa el plugin oficial de React para JSX y HMR.
 * - Server escuchando en 0.0.0.0:5173 dentro del contenedor.
 * - watch.usePolling=true para que el hot-reload funcione bajo Docker en
 *   sistemas de archivos donde fsnotify no detecta cambios (Windows/WSL).
 * - Vitest con jsdom para probar componentes (Login, OperatorView, MachineTile).
 */
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    css: false,
    include: ['src/**/*.test.{js,jsx}'],
    exclude: ['node_modules', 'dist'],
  },
});
