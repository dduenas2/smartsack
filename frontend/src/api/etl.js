/**
 * api/etl.js — Wrapper de los endpoints REST del módulo ETL.
 */
import apiClient from './client.js';

export async function uploadCsv({ kind, file, onProgress }) {
  const form = new FormData();
  form.append('kind', kind);
  form.append('file', file);
  const { data } = await apiClient.post('/etl/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress,
    timeout: 60000, // CSVs grandes pueden tomar varios segundos.
  });
  return data;
}

export async function listLoads({ kind, limit = 20, offset = 0 } = {}) {
  const { data } = await apiClient.get('/etl/status', {
    params: { ...(kind ? { kind } : {}), limit, offset },
  });
  return data;
}

export async function getLoad(id) {
  const { data } = await apiClient.get(`/etl/status/${id}`);
  return data;
}

/** Devuelve la URL absoluta de la plantilla, lista para `<a download>`. */
export function sampleCsvUrl(kind) {
  // Cliente axios usa baseURL '/api' por defecto; aquí queremos ruta directa
  // para que el browser maneje la descarga como link nativo.
  const base = apiClient.defaults.baseURL || '/api';
  return `${base}/etl/sample-csv/${kind}`;
}
