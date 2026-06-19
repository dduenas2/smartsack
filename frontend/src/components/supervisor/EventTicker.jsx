/**
 * EventTicker — feed en streaming con dedup por id y orden cronológico.
 *
 * Recibe la lista ya deduplicada y ordenada desde la página supervisor.
 * Pinta cada evento con timestamp mono, código de máquina, tipo coloreado
 * y descripción.
 */
import Card from '../common/Card.jsx';
import StatusDot from '../common/StatusDot.jsx';

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

export default function EventTicker({ events, wsStatus }) {
  const connTone =
    wsStatus === 'open' ? 'online' :
    wsStatus === 'connecting' ? 'connecting' :
    'offline';
  const connLabel =
    wsStatus === 'open' ? 'En vivo' :
    wsStatus === 'connecting' ? 'Conectando' :
    wsStatus === 'closed' ? 'Reconectando' : 'Sin conexión';

  return (
    <Card
      title="Stream en vivo"
      hint={`${events.length} evento(s) en buffer`}
      accent="brand"
      action={
        <span className="inline-flex items-center gap-1.5 mono text-[10px] uppercase tracking-widest2 text-ink-mid">
          <StatusDot tone={connTone} size="sm" />
          {connLabel}
        </span>
      }
    >
      {events.length === 0 ? (
        <p className="mono text-xs text-ink-low py-6 text-center uppercase tracking-widest2">
          Esperando eventos del piso...
        </p>
      ) : (
        <ul className="space-y-1.5 max-h-[440px] overflow-y-auto pr-1">
          {events.map((e) => (
            <li
              key={e.id}
              className="mono text-xs flex items-start gap-2.5 px-2 py-1.5 rounded bg-bg-base ring-1 ring-bg-softline animate-fade-in-up"
            >
              <span className="text-ink-low shrink-0 tabular-nums">
                {new Date(e.timestamp).toLocaleTimeString('es-CO', { hour12: false })}
              </span>
              <span className="text-accent shrink-0 tracking-widest2">
                {e.machineCode}
              </span>
              <span
                className={`shrink-0 uppercase tracking-widest2 text-[10px] ${TYPE_COLOR[e.eventType] || 'text-ink-mid'}`}
              >
                {e.eventType}
              </span>
              <span className="text-ink-mid truncate">
                {e.description || '—'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
