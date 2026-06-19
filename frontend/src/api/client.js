/**
 * api/client.js — Cliente Axios centralizado para hablar con el backend.
 *
 * Lee la URL base desde la variable de entorno VITE_API_BASE_URL (definida
 * en .env y expuesta por Vite). Centraliza interceptores para añadir el
 * token JWT de autenticación cuando se implemente en el siguiente paso.
 */
import axios from 'axios';
import { tokenStorage } from '../context/tokenStorage.js';

const baseURL = import.meta.env.VITE_API_BASE_URL || '/api';

const apiClient = axios.create({
  baseURL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.get();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      tokenStorage.clear();
    }
    return Promise.reject(error);
  }
);

export default apiClient;
