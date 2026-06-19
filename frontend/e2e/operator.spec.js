/**
 * operator.spec.js — Vista del operario (HUD de su máquina asignada).
 *
 * op_tub-01_1 está asignado a la máquina TUB-01 (Tubuladora línea A).
 */
import { test, expect } from '@playwright/test';
import { login, USERS } from './helpers.js';

test.describe('Vista operario', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, USERS.operario);
  });

  test('muestra la estación asignada del operario', async ({ page }) => {
    // Banner de la máquina: eyebrow fijo + código de la estación.
    await expect(page.getByText('Estación asignada')).toBeVisible();
    await expect(page.getByText('TUB-01', { exact: true })).toBeVisible();
  });

  test('muestra la cola de operaciones de la máquina', async ({ page }) => {
    await expect(page.getByText('Cola de operaciones')).toBeVisible();
  });
});
