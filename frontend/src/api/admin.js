/**
 * api/admin.js — Endpoints del panel administrativo.
 *
 * Agrupa:
 *   - /admin/audit              Bitácora paginada de acciones admin.
 *   - /admin/system/health      Snapshot del estado de los componentes.
 *   - /admin/system/settings    Settings runtime (read + patch).
 *   - /admin/system/ml-status   Estado del modelo ML cargado.
 *   - /predictions/reload       Recarga del joblib (admin).
 */
import apiClient from './client.js';

// ---------- Audit ----------
export async function listAuditLog(params = {}) {
  const { data } = await apiClient.get('/admin/audit', { params });
  return data;
}

// ---------- System health / status ----------
export async function getSystemHealth() {
  const { data } = await apiClient.get('/admin/system/health');
  return data;
}

export async function getMlStatus() {
  const { data } = await apiClient.get('/admin/system/ml-status');
  return data;
}

export async function reloadMlModel() {
  const { data } = await apiClient.post('/predictions/reload');
  return data;
}

// ---------- System settings ----------
export async function listSettings() {
  const { data } = await apiClient.get('/admin/system/settings');
  return data;
}

export async function updateSetting(key, value) {
  const { data } = await apiClient.patch(`/admin/system/settings/${key}`, {
    value,
  });
  return data;
}
