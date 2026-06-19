/**
 * SupervisorView — Digital Twin (tema claro Smurfit Kappa).
 *
 * Cambios clave respecto a versiones previas:
 *   - `flashes`: Map<machineId, {eventType, key}> que viaja a cada tile
 *     para que dispare la animación flash-{state} adecuada.
 *   - `tickerEvents`: dedup por id + orden cronológico (timestamp DESC),
 *     lo que elimina los duplicados que aparecían en dev por React
 *     StrictMode (ya además mitigados con el `alive` flag de useWebSocket).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { listMachines } from '../api/machines.js';
import useWebSocket from '../hooks/useWebSocket.js';
import PlantMap from '../components/supervisor/PlantMap.jsx';
import PlantStats from '../components/supervisor/PlantStats.jsx';
import EventTicker from '../components/supervisor/EventTicker.jsx';
import StatusDot from '../components/common/StatusDot.jsx';
import Spinner from '../components/common/Spinner.jsx';

const FLASH_MS = 2800;     // duración del resaltado en cada tile
const TICKER_MAX = 50;     // eventos máximos en buffer

export default function SupervisorView() {
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Map<machineId, { eventType, key }>. `key` se usa como React key del
  // tile para forzar re-mount y reiniciar la animación cuando llega un
  // segundo evento durante el cooldown.
  const [flashes, setFlashes] = useState(() => new Map());
  const flashTimers = useRef(new Map());

  const [tickerEvents, setTickerEvents] = useState([]);

  // Snapshot inicial vía REST.
  useEffect(() => {
    listMachines()
      .then(setMachines)
      .catch((err) => setError(err?.response?.data?.detail || 'Error cargando las máquinas'))
      .finally(() => setLoading(false));
  }, []);

  // Limpieza de timers al desmontar.
  useEffect(() => {
    const timers = flashTimers.current;
    return () => {
      timers.forEach((id) => clearTimeout(id));
      timers.clear();
    };
  }, []);

  const triggerFlash = useCallback((machineId, eventType) => {
    setFlashes((prev) => {
      const next = new Map(prev);
      next.set(machineId, { eventType, key: Date.now() });
      return next;
    });

    const existing = flashTimers.current.get(machineId);
    if (existing) clearTimeout(existing);
    const timer = setTimeout(() => {
      setFlashes((prev) => {
        const next = new Map(prev);
        next.delete(machineId);
        return next;
      });
      flashTimers.current.delete(machineId);
    }, FLASH_MS);
    flashTimers.current.set(machineId, timer);
  }, []);

  const handleMessage = useCallback(
    (message) => {
      if (message.type === 'snapshot') {
        setMachines(message.machines);
        return;
      }
      if (message.type === 'machine_update') {
        const updated = message.machine;
        // El backend envía el payload completo (status + current_order embebida);
        // hacemos merge superficial para preservar campos que el WS no manda.
        setMachines((prev) =>
          prev.map((m) => (m.id === updated.id ? { ...m, ...updated } : m))
        );
        triggerFlash(updated.id, message.event?.event_type || null);

        if (message.event) {
          const entry = {
            id: message.event.id,
            machineCode: updated.code,
            eventType: message.event.event_type,
            description: message.event.description,
            timestamp: message.event.timestamp,
          };
          setTickerEvents((prev) => {
            // 1) Dedup por id (cinturón frente a cualquier doble entrega).
            if (prev.some((e) => e.id === entry.id)) return prev;
            // 2) Inserta y ordena por timestamp DESC (más reciente arriba).
            const merged = [entry, ...prev].sort(
              (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
            );
            return merged.slice(0, TICKER_MAX);
          });
        }
      }
    },
    [triggerFlash]
  );

  const { status: wsStatus } = useWebSocket('/plant', handleMessage);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size="lg" label="Cargando Digital Twin..." />
      </div>
    );
  }

  if (error) {
    return <div className="panel p-4 text-state-stopped text-sm">{error}</div>;
  }

  const connTone =
    wsStatus === 'open' ? 'online' :
    wsStatus === 'connecting' ? 'connecting' :
    'offline';
  const connLabel =
    wsStatus === 'open' ? 'Conectado en vivo' :
    wsStatus === 'connecting' ? 'Conectando...' :
    wsStatus === 'closed' ? 'Reconectando...' : 'Desconectado';

  return (
    <div className="space-y-6 animate-fade-in-up">
      <header className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <p className="label-eyebrow">Digital Twin · Bags Division</p>
          <h1 className="text-3xl font-light text-ink-high tracking-wide mt-1">
            Planta de sacos <span className="text-accent">·</span>{' '}
            <span className="text-ink-mid">tiempo real</span>
          </h1>
          <p className="text-sm text-ink-mid mt-1">
            Estado operativo en vivo de todas las estaciones de la línea.
          </p>
        </div>
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md panel">
          <StatusDot tone={connTone} size="md" />
          <span className="mono text-xs uppercase tracking-widest2 text-ink-mid">
            {connLabel}
          </span>
        </div>
      </header>

      <PlantStats machines={machines} />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_360px] gap-6">
        <PlantMap machines={machines} flashes={flashes} />
        <EventTicker events={tickerEvents} wsStatus={wsStatus} />
      </div>
    </div>
  );
}
