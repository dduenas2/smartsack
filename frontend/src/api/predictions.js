/**
 * api/predictions.js — Wrapper de los endpoints REST del motor de ML.
 */
import apiClient from './client.js';

export async function getModelInfo() {
  const { data } = await apiClient.get('/predictions/model-info');
  return data;
}

export async function getFeatureImportance({ topK = 10 } = {}) {
  const { data } = await apiClient.get('/predictions/feature-importance', {
    params: { top_k: topK },
  });
  return data;
}

export async function predictActive() {
  const { data } = await apiClient.post('/predictions/predict-active');
  return data;
}

export async function predictOne(orderId) {
  const { data } = await apiClient.post(`/predictions/predict/${orderId}`);
  return data;
}

export async function reloadModel() {
  const { data } = await apiClient.post('/predictions/reload');
  return data;
}
