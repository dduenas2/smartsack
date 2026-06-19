/**
 * api/auth.js — Llamadas a los endpoints de autenticación.
 *
 * El backend usa OAuth2PasswordRequestForm en /api/auth/login, por lo que
 * el body se envía como application/x-www-form-urlencoded (URLSearchParams),
 * no JSON.
 */
import apiClient from './client.js';

export async function login(username, password) {
  const body = new URLSearchParams();
  body.append('username', username);
  body.append('password', password);

  const { data } = await apiClient.post('/auth/login', body, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  });
  return data;
}

export async function fetchCurrentUser() {
  const { data } = await apiClient.get('/auth/me');
  return data;
}
