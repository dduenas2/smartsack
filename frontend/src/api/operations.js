/**
 * api/operations.js — endpoints REST de operaciones (ruta IMP→TUB→FON→EMP).
 *
 * Una operación es la unidad de trabajo del operario; vive dentro de una
 * orden cabecera y representa una etapa específica de la línea.
 */
import apiClient from './client.js';

export async function listOperations(params = {}) {
  // FastAPI espera arrays como params repetidos: ?status=ready&status=in_progress
  // (no ?status[]=ready). Forzamos ese formato con paramsSerializer.
  const { data } = await apiClient.get('/operations', {
    params,
    paramsSerializer: {
      indexes: null, // arrays se serializan como param=a&param=b (sin brackets)
    },
  });
  return data;
}

export async function getOperation(id) {
  const { data } = await apiClient.get(`/operations/${id}`);
  return data;
}

export async function startOperation(id) {
  const { data } = await apiClient.post(`/operations/${id}/start`);
  return data;
}

export async function reportProduction(id, payload) {
  const { data } = await apiClient.post(`/operations/${id}/report`, payload);
  return data;
}

export async function completeOperation(id) {
  const { data } = await apiClient.post(`/operations/${id}/complete`);
  return data;
}

export async function listOrderOperations(orderId) {
  const { data } = await apiClient.get(`/orders/${orderId}/operations`);
  return data;
}
