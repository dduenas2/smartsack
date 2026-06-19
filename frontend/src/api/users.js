/**
 * api/users.js — Wrapper de los endpoints CRUD de usuarios (panel admin).
 *
 * Todas las llamadas requieren rol admin: el cliente axios añade el JWT
 * automáticamente vía interceptor; el backend devuelve 403 si el rol no es
 * suficiente y 401 si el token es inválido (el interceptor de respuesta
 * limpia la sesión en ese caso).
 */
import apiClient from './client.js';

export async function listUsers(params = {}) {
  const { data } = await apiClient.get('/users', { params });
  return data;
}

export async function getUser(id) {
  const { data } = await apiClient.get(`/users/${id}`);
  return data;
}

export async function createUser(payload) {
  const { data } = await apiClient.post('/users', payload);
  return data;
}

export async function updateUser(id, patch) {
  const { data } = await apiClient.patch(`/users/${id}`, patch);
  return data;
}

export async function deactivateUser(id) {
  await apiClient.delete(`/users/${id}`);
}

export async function resetUserPassword(id, newPassword) {
  const { data } = await apiClient.post(`/users/${id}/reset-password`, {
    new_password: newPassword,
  });
  return data;
}

export async function assignMachine(id, machineId) {
  const { data } = await apiClient.post(`/users/${id}/assign-machine`, {
    machine_id: machineId,
  });
  return data;
}
