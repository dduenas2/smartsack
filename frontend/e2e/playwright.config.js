/**
 * playwright.config.js — Configuración E2E de SmartSack.
 *
 * Las pruebas corren en el host contra el stack ya levantado por Docker Compose
 * (`docker compose up -d`), accediendo a través de Nginx en http://localhost.
 * No usamos `webServer` porque el stack es externo a Playwright; debe estar
 * arriba antes de correr (`docker compose ps` → todo healthy).
 */
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  // Solo specs en la raíz de e2e/: evita que Playwright recorra node_modules.
  testMatch: '*.spec.js',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost',
    headless: true,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
