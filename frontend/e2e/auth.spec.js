/**
 * auth.spec.js — Flujo de autenticación: login, redirección por rol y logout.
 */
import { test, expect } from '@playwright/test';
import { login, USERS, PASSWORD } from './helpers.js';

test.describe('Autenticación', () => {
  test('rechaza credenciales inválidas con un mensaje de error', async ({ page }) => {
    await page.goto('/login');
    await page.locator('#username').fill('admin');
    await page.locator('#password').fill('clave-incorrecta');
    await page.getByRole('button', { name: 'Iniciar sesión' }).click();

    await expect(page.getByText(/contraseña incorrectos|No se pudo iniciar sesión/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  test('login de admin redirige a /admin y muestra la sesión', async ({ page }) => {
    await login(page, USERS.admin);

    // La Navbar (banner) muestra el rol y el botón de salir cuando hay sesión.
    await expect(page.getByRole('banner').getByText('Admin', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Salir' })).toBeVisible();
  });

  test('redirige a la home correcta según el rol (operario → /operator)', async ({ page }) => {
    await login(page, USERS.operario);
    await expect(page).toHaveURL(/\/operator$/);
  });

  test('logout vuelve a /login', async ({ page }) => {
    await login(page, USERS.admin);
    await page.getByRole('button', { name: 'Salir' }).click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole('button', { name: 'Iniciar sesión' })).toBeVisible();
  });

  test('una ruta protegida sin sesión redirige a /login', async ({ page }) => {
    await page.goto('/supervisor');
    await expect(page).toHaveURL(/\/login$/);
  });

  // Sanity: el password sembrado es el esperado por el resto de specs.
  test('el usuario supervisor sembrado puede entrar', async ({ page }) => {
    expect(PASSWORD).toBe('smartsack123');
    await login(page, USERS.supervisor);
    await expect(page).toHaveURL(/\/supervisor$/);
  });
});
