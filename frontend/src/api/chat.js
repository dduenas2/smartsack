/**
 * api/chat.js — wrapper del chat conversacional.
 */
import apiClient from './client.js';

export async function sendMessage({ message, history = [] }) {
  const { data } = await apiClient.post(
    '/chat/message',
    { message, history },
    { timeout: 60000 } // El LLM puede tardar más que el timeout estándar.
  );
  return data;
}

export async function getStatus() {
  const { data } = await apiClient.get('/chat/status');
  return data;
}
