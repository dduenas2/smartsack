/**
 * api/orders.js — Wrapper de los endpoints REST de órdenes de producción.
 */
import apiClient from './client.js';

export async function listOrders(params = {}) {
  const { data } = await apiClient.get('/orders', { params });
  return data; // PaginatedResponse: { total, limit, offset, items }
}

export async function getOrder(id) {
  const { data } = await apiClient.get(`/orders/${id}`);
  return data;
}

export async function createOrder(payload) {
  const { data } = await apiClient.post('/orders', payload);
  return data;
}

export async function updateOrder(id, patch) {
  const { data } = await apiClient.patch(`/orders/${id}`, patch);
  return data;
}

export async function deleteOrder(id) {
  await apiClient.delete(`/orders/${id}`);
}
