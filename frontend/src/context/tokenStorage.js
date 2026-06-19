/**
 * tokenStorage — único lugar que toca el JWT del navegador.
 *
 * Decisión: usamos `sessionStorage` para que cada pestaña tenga su propia
 * sesión. Si dos pestañas tienen logins distintos (típico en demos
 * supervisor + operario en paralelo), recargar una NO arrastra el token
 * de la otra. `localStorage` haría justo lo contrario.
 *
 * Migración silenciosa: si encontramos un token antiguo en `localStorage`
 * lo movemos a `sessionStorage` la primera vez para no forzar al usuario
 * a relogearse al actualizar el frontend.
 */

const KEY = 'smartsack_token';

function migrateLegacyOnce() {
  try {
    const legacy = window.localStorage.getItem(KEY);
    if (legacy && !window.sessionStorage.getItem(KEY)) {
      window.sessionStorage.setItem(KEY, legacy);
    }
    if (legacy) window.localStorage.removeItem(KEY);
  } catch {
    /* sessionStorage o localStorage podrían estar deshabilitados (modo
       privado en algunos navegadores). En ese caso simplemente seguimos. */
  }
}

migrateLegacyOnce();

export const tokenStorage = {
  get() {
    try {
      return window.sessionStorage.getItem(KEY);
    } catch {
      return null;
    }
  },
  set(token) {
    try {
      window.sessionStorage.setItem(KEY, token);
    } catch {
      /* ignore */
    }
  },
  clear() {
    try {
      window.sessionStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  },
  key: KEY,
};
