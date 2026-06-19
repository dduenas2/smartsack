/**
 * Tests del módulo tokenStorage.
 *
 * Verifica la persistencia en sessionStorage (no localStorage) y la
 * migración silenciosa de tokens viejos.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

async function loadFresh() {
  vi.resetModules();
  const mod = await import('./tokenStorage.js');
  return mod.tokenStorage;
}

describe('tokenStorage', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  it('persiste el token en sessionStorage al hacer set', async () => {
    const tokenStorage = await loadFresh();
    tokenStorage.set('abc.def.ghi');
    expect(sessionStorage.getItem('smartsack_token')).toBe('abc.def.ghi');
    expect(localStorage.getItem('smartsack_token')).toBeNull();
  });

  it('devuelve null cuando no hay token', async () => {
    const tokenStorage = await loadFresh();
    expect(tokenStorage.get()).toBeNull();
  });

  it('clear borra el token guardado', async () => {
    const tokenStorage = await loadFresh();
    tokenStorage.set('xxx');
    tokenStorage.clear();
    expect(tokenStorage.get()).toBeNull();
  });

  it('migra tokens legacy desde localStorage en el primer uso', async () => {
    localStorage.setItem('smartsack_token', 'legacy-token');
    const tokenStorage = await loadFresh();
    expect(tokenStorage.get()).toBe('legacy-token');
    expect(localStorage.getItem('smartsack_token')).toBeNull();
  });
});
