/**
 * api/dashboard.js — Wrapper de los endpoints REST del dashboard.
 *
 * Cada función devuelve directamente el body JSON del backend, listo para
 * pasarse a un widget. Ver `app/schemas/dashboard.py` en el backend para los
 * contratos completos.
 */
import apiClient from './client.js';

export async function getOverview() {
  const { data } = await apiClient.get('/dashboard/overview');
  return data;
}

export async function getOEETrend({ days = 30, machineId } = {}) {
  const { data } = await apiClient.get('/dashboard/oee-trend', {
    params: { days, ...(machineId ? { machine_id: machineId } : {}) },
  });
  return data;
}

export async function getProductionByShift({ days = 7 } = {}) {
  const { data } = await apiClient.get('/dashboard/production-by-shift', {
    params: { days },
  });
  return data;
}

export async function getOrderFulfillment({ days = 30 } = {}) {
  const { data } = await apiClient.get('/dashboard/order-fulfillment', {
    params: { days },
  });
  return data;
}

export async function getMachineRanking({ days = 30 } = {}) {
  const { data } = await apiClient.get('/dashboard/machine-ranking', {
    params: { days },
  });
  return data;
}

export async function getAlerts({ threshold = 0.6, limit = 20 } = {}) {
  const { data } = await apiClient.get('/dashboard/alerts', {
    params: { threshold, limit },
  });
  return data;
}

export async function getScrapByMachine({ days = 30 } = {}) {
  const { data } = await apiClient.get('/dashboard/scrap-by-machine', {
    params: { days },
  });
  return data;
}

export async function getYieldByOperation({ days = 30 } = {}) {
  const { data } = await apiClient.get('/dashboard/yield-by-operation', {
    params: { days },
  });
  return data;
}

export async function getWIP() {
  const { data } = await apiClient.get('/dashboard/wip');
  return data;
}
