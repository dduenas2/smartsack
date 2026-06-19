/**
 * useWebSocket — hook robusto frente a React StrictMode.
 *
 * Características:
 * - Adjunta el JWT vía query string.
 * - Reconexión con backoff exponencial (1s → 2s → 4s → 8s → máx 16s).
 * - **`alive` flag**: si el efecto se desmonta (típico en StrictMode dev,
 *   donde React monta/desmonta dos veces para detectar bugs), los mensajes
 *   que lleguen al WS difunto se descartan en lugar de inyectarse al
 *   handler actual. Esto elimina los eventos duplicados en el ticker.
 */
import { useEffect, useRef, useState } from 'react';
import { tokenStorage } from '../context/tokenStorage.js';

const WS_BASE_URL = import.meta.env.VITE_WS_BASE_URL || '/ws';

function buildWsUrl(path, token) {
  const origin = window.location.origin.replace(/^http/, 'ws');
  const base = WS_BASE_URL.startsWith('ws')
    ? WS_BASE_URL
    : `${origin}${WS_BASE_URL}`;
  const url = new URL(`${base}${path}`);
  if (token) url.searchParams.set('token', token);
  return url.toString();
}

export default function useWebSocket(path, onMessage, { enabled = true } = {}) {
  const [status, setStatus] = useState('idle');
  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    if (!enabled) return undefined;
    const token = tokenStorage.get();
    if (!token) return undefined;

    let alive = true;
    let ws = null;
    let timeoutId = null;
    let retries = 0;

    function connect() {
      if (!alive) return;
      setStatus('connecting');
      ws = new WebSocket(buildWsUrl(path, token));

      ws.onopen = () => {
        if (!alive) {
          // El efecto ya se desmontó (StrictMode); cerrar limpio.
          try { ws.close(); } catch { /* ignore */ }
          return;
        }
        retries = 0;
        setStatus('open');
      };

      ws.onmessage = (event) => {
        if (!alive) return;
        try {
          const data = JSON.parse(event.data);
          onMessageRef.current?.(data);
        } catch {
          /* mensaje no-JSON: ignorar */
        }
      };

      ws.onerror = () => {
        if (alive) setStatus('error');
      };

      ws.onclose = () => {
        if (!alive) return;
        setStatus('closed');
        const delay = Math.min(16000, 1000 * 2 ** retries);
        retries += 1;
        timeoutId = setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      alive = false;
      if (timeoutId) clearTimeout(timeoutId);
      if (ws && ws.readyState <= 1) {
        try { ws.close(); } catch { /* ignore */ }
      }
    };
  }, [path, enabled]);

  return { status };
}
