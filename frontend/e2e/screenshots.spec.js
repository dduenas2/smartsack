/**
 * screenshots.spec.js — Captura las pantallas del Manual de Usuario.
 *
 * NO es una prueba de regresión: usa el framework Playwright sólo para navegar
 * la app (ya levantada por Docker Compose en http://localhost) e ir guardando
 * capturas en docs/capturas/. Ejecutar con:
 *
 *   cd frontend/e2e && npx playwright test screenshots.spec.js
 */
import { test } from '@playwright/test';
import { login, USERS } from './helpers.js';

const OUT = '../../docs/capturas';

// Esto NO es una prueba de regresión: genera las capturas del manual. Se omite
// en CI para no inflar el conteo de E2E ni escribir artefactos en el pipeline.
test.beforeEach(() => {
  test.skip(!!process.env.CI, 'Generación manual de capturas; no se ejecuta en CI');
});

// Pantallas anchas (Digital Twin, dashboard) en viewport de monitor.
test.use({ viewport: { width: 1600, height: 900 } });

async function shot(page, name) {
  // Pequeño margen para que terminen animaciones de gráficas.
  await page.waitForTimeout(900);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}

test('captura · login', async ({ page }) => {
  await page.goto('/login');
  await page.locator('#username').waitFor();
  await shot(page, '01-login');
});

test('captura · vista operario', async ({ page }) => {
  await login(page, USERS.operario);
  await page.getByText('Estación asignada').waitFor();
  await shot(page, '02-operario');
});

test('captura · digital twin supervisor', async ({ page }) => {
  await login(page, USERS.supervisor);
  await page.getByText('Digital Twin · Bags Division').waitFor();
  await page.getByText('TUB-01', { exact: true }).first().waitFor();
  await shot(page, '03-supervisor-digital-twin');
});

test('captura · dashboard KPIs', async ({ page }) => {
  await login(page, USERS.supervisor);
  await page.goto('/dashboard');
  await page.getByRole('main').getByText('Analytics').waitFor();
  await shot(page, '04-dashboard');
});

test('captura · asistente conversacional', async ({ page }) => {
  await login(page, USERS.supervisor);
  await page.goto('/chat');
  await page.getByText('¿En qué te ayudo?').waitFor();
  await shot(page, '05-chat');
});

test('captura · carga ETL', async ({ page }) => {
  await login(page, USERS.supervisor);
  await page.goto('/etl');
  await page.getByText('Integración ERP').waitFor();
  await shot(page, '06-etl');
});

test('captura · administración', async ({ page }) => {
  await login(page, USERS.admin);
  await page.getByText('SmartSack — Admin').waitFor();
  await shot(page, '07-admin');
});
