/**
 * chat.spec.js — Asistente conversacional.
 *
 * El stack de prueba corre sin ANTHROPIC_API_KEY, así que el chatbot responde
 * en modo fallback (router por keywords). La pregunta sugerida sobre sacos mapea
 * a la tool get_production_stats, cuyo chip "producción" aparece bajo la
 * respuesta del asistente — lo usamos para confirmar el round-trip completo.
 */
import { test, expect } from '@playwright/test';
import { login, USERS } from './helpers.js';

test.describe('Asistente (chatbot)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page, USERS.admin);
    await page.goto('/chat');
    await expect(page.getByRole('heading', { name: /Asistente/ })).toBeVisible();
  });

  test('indica el modo activo del asistente', async ({ page }) => {
    // Sin API key el backend reporta llm_available=false.
    await expect(page.getByText('modo fallback (sin API key)')).toBeVisible();
  });

  test('responde a una pregunta y ejecuta una tool', async ({ page }) => {
    const pregunta = '¿Cuántos sacos se produjeron ayer?';
    await page.getByRole('button', { name: pregunta }).click();

    // La pregunta aparece como burbuja del usuario.
    await expect(page.getByText(pregunta)).toBeVisible();

    // El asistente responde y muestra el chip de la tool ejecutada.
    await expect(page.getByText('producción', { exact: true })).toBeVisible({ timeout: 15_000 });
  });
});
