/**
 * supervisor.spec.js — Digital Twin del supervisor (vista de planta en vivo).
 */
import { test, expect } from '@playwright/test';
import { login, USERS } from './helpers.js';

test.describe('Vista supervisor (Digital Twin)', () => {
  // El Digital Twin es un dashboard ancho (mapa de planta + ticker lateral).
  // Usamos un viewport de monitor para que la grilla no exprima los tiles.
  test.use({ viewport: { width: 1600, height: 900 } });

  test.beforeEach(async ({ page }) => {
    await login(page, USERS.supervisor);
  });

  test('muestra la cabecera del Digital Twin', async ({ page }) => {
    await expect(page.getByText('Digital Twin · Bags Division')).toBeVisible();
    await expect(page.getByRole('heading', { name: /Planta de sacos/ })).toBeVisible();
  });

  test('carga el snapshot REST con las máquinas sembradas', async ({ page }) => {
    // El catálogo sembrado incluye TUB-01; debe aparecer en el mapa de planta.
    await expect(page.getByText('TUB-01', { exact: true }).first()).toBeVisible();
  });
});
