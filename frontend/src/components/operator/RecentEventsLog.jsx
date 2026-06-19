/**
 * RecentEventsLog — bitácora de los últimos eventos de la máquina.
 *
 * Estilo terminal: timestamp mono, tipo de evento como tag coloreado,
 * descripción a la derecha. Hace polling ligero cada 10s para mantenerse
 * vivo (más adelante, suscripción WS específica de la máquina).
 */
import { useEffect, useState } from 'react';
import { listEvents } from '../../api/events.js';
import Card from '../common/Card.jsx';

const TYPE_COLOR = {
  start: 'text-state-running',
  resume: 'text-state-running',
  end: 'text-ink-mid',
  pause: 'text-state-maintenance',
  format_change: 'text-state-maintenance',
  stop: 'text-state-stopped',
  incident: 'text-state-stopped',
  maintenance: 'text-state-idle',
  production_update: 'text-accent',
};

export default function RecentEventsLog({ machineId, refreshKey }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!machineId) return undefined;
    let cancelled = false;
    async function fetchOnce() {
      try {
        const data = await listEvents({ machine_id: machineId, limit: 10 });
        if (!cancelled) setEvents(data.items);
      } catch {
        /* silencioso — la pantalla principal ya alerta de errores de API */
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchOnce();
    const id = setInterval(fetchOnce, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [machineId, refreshKey]);

  return (
    <Card
      title="Bitácora reciente"
      hint="Últimos 10 eventos · refresca cada 10s"
      accent="cyan"
    >
      {loading && events.length === 0 ? (
        <p className="text-sm text-ink-mid">Cargando bitácora...</p>
      ) : events.length === 0 ? (
        <p className="text-sm text-ink-mid">Sin eventos registrados aún.</p>
      ) : (
        <ul className="space-y-1.5">
          {events.map((e) => (
            <li
              key={e.id}
              className="mono text-xs flex items-start gap-3 px-2 py-1.5 rounded hover:bg-bg-base"
            >
              <span className="text-ink-low shrink-0 tabular-nums">
                {new Date(e.timestamp).toLocaleTimeString('es-CO', { hour12: false })}
              </span>
              <span
                className={`shrink-0 uppercase tracking-widest2 text-[10px] ${TYPE_COLOR[e.event_type] || 'text-ink-mid'}`}
              >
                {e.event_type.padEnd(13, ' ')}
              </span>
              <span className="text-ink-mid truncate">
                {e.event_type === 'production_update' && e.quantity !== null
                  ? `${e.quantity > 0 ? '+' : ''}${e.quantity.toLocaleString('es-CO')} sacos${
                      e.description ? ` · ${e.description}` : ''
                    }`
                  : (e.description || '—')}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
