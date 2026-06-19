/**
 * api/events.js — Wrapper de los endpoints REST de eventos de producción.
 */
import apiClient from './client.js';

export async function createEvent(payload) {
  const { data } = await apiClient.post('/events', payload);
  return data;
}

export async function listEvents(params = {}) {
  const { data } = await apiClient.get('/events', { params });
  return data;
}
