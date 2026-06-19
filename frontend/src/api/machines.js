/**
 * api/machines.js — Wrapper de los endpoints REST de máquinas.
 */
import apiClient from './client.js';

export async function listMachines(params = {}) {
  const { data } = await apiClient.get('/machines', { params });
  return data;
}

export async function getMachine(id) {
  const { data } = await apiClient.get(`/machines/${id}`);
  return data;
}

export async function createMachine(payload) {
  const { data } = await apiClient.post('/machines', payload);
  return data;
}

export async function updateMachine(id, payload) {
  const { data } = await apiClient.patch(`/machines/${id}`, payload);
  return data;
}

export async function deleteMachine(id) {
  await apiClient.delete(`/machines/${id}`);
}
