/**
 * Setup global de Vitest:
 * - Extiende `expect` con matchers de @testing-library/jest-dom.
 * - Limpia el DOM entre tests para evitar fugas entre archivos.
 * - Mockea sessionStorage si jsdom lo expone como noop (Vitest 2.x lo provee).
 */
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
  // Aislamos sesiones entre tests — el storage para JWT vive aquí.
  sessionStorage.clear();
  localStorage.clear();
});
