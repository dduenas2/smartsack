/**
 * AuthContext — estado global de autenticación.
 *
 * El JWT se guarda en `sessionStorage` (NO en `localStorage`) para que cada
 * pestaña tenga su propia sesión: así puedes tener una pestaña como
 * supervisor y otra como operario sin que una pise la sesión de la otra.
 * Trade-off: cerrar la pestaña requiere volver a iniciar sesión, lo cual
 * es aceptable para el caso de uso (operadores en estaciones de planta).
 *
 * Uso:
 *   const { user, signIn, signOut, isLoading } = useAuth();
 *   import { tokenStorage } from '...';   // para api/client + WebSocket
 */
import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import * as authApi from '../api/auth.js';
import { tokenStorage } from './tokenStorage.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Al montar: si hay token guardado en esta pestaña, recupera el usuario.
  useEffect(() => {
    const token = tokenStorage.get();
    if (!token) {
      setIsLoading(false);
      return;
    }
    authApi
      .fetchCurrentUser()
      .then((data) => setUser(data))
      .catch(() => {
        tokenStorage.clear();
      })
      .finally(() => setIsLoading(false));
  }, []);

  const signIn = useCallback(async (username, password) => {
    const tokenResponse = await authApi.login(username, password);
    tokenStorage.set(tokenResponse.access_token);
    const me = await authApi.fetchCurrentUser();
    setUser(me);
    return me;
  }, []);

  const signOut = useCallback(() => {
    tokenStorage.clear();
    setUser(null);
  }, []);

  const value = { user, isLoading, signIn, signOut };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth debe usarse dentro de <AuthProvider>');
  }
  return ctx;
}

/**
 * Helper: devuelve la ruta por defecto según el rol del usuario.
 *
 * - operario   → /operator (HUD de su máquina)
 * - supervisor → /supervisor (Digital Twin)
 * - admin      → /admin (panel administrativo)
 */
export function defaultRouteFor(role) {
  if (role === 'operario') return '/operator';
  if (role === 'admin') return '/admin';
  return '/supervisor';
}

// Compat: re-exporta la clave para módulos que aún la importaban (useWebSocket).
export const TOKEN_STORAGE_KEY = 'smartsack_token';
