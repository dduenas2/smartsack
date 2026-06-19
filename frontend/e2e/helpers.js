/**
 * helpers.js — utilidades compartidas por los specs E2E.
 *
 * No coincide con el patrón `*.spec.js`, así que Playwright no lo trata como
 * archivo de pruebas. Centraliza los usuarios sembrados (ver `scripts.seed`) y
 * el flujo de login para no repetirlo en cada spec.
 */
import { expect } from '@playwright/test';

export const PASSWORD = 'smartsack123';

export const USERS = {
  admin: { username: 'admin', role: 'admin', home: '/admin' },
  supervisor: { username: 'supervisor1', role: 'supervisor', home: '/supervisor' },
  operario: { username: 'op_tub-01_1', role: 'operario', home: '/operator' },
};

/**
 * Inicia sesión vía la UI de /login y espera la redirección a la home del rol.
 * Devuelve cuando ya estamos fuera de /login (sesión establecida).
 */
export async function login(page, user) {
  await page.goto('/login');
  await page.locator('#username').fill(user.username);
  await page.locator('#password').fill(PASSWORD);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page).toHaveURL(new RegExp(`${user.home}$`));
}
