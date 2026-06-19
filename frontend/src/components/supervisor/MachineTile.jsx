/**
 * MachineTile — celda del Digital Twin (tema claro).
 *
 * Cuando llega un machine_update por WebSocket:
 *   - El prop `flashEvent` indica el `event_type` que disparó el cambio.
 *   - La tarjeta dispara la animación `flash-{state}` correspondiente:
 *       start/resume   → flash-emerald
 *       stop/incident  → flash-rose
 *       pause/format   → flash-amber
 *       end            → flash-slate
 *       (sin event)    → flash-brand
 *   - El borde lateral se mantiene del color del nuevo estado siempre.
 */
import Badge from '../common/Badge.jsx';
import StatusDot from '../common/StatusDot.jsx';

const STATUS_BAR = {
  running: 'bg-state-running',
  stopped: 'bg-state-stopped',
  maintenance: 'bg-state-maintenance',
  idle: 'bg-state-idle',
};

const FLASH_BY_EVENT = {
  start: 'animate-flash-emerald',
  resume: 'animate-flash-emerald',
  stop: 'animate-flash-rose',
  incident: 'animate-flash-rose',
  pause: 'animate-flash-amber',
  format_change: 'animate-flash-amber',
  end: 'animate-flash-slate',
  maintenance: 'animate-flash-amber',
};

function fmt(n) {
  return new Intl.NumberFormat('es-CO').format(n ?? 0);
}

export default function MachineTile({ machine, flashEvent, flashKey }) {
  const bar = STATUS_BAR[machine.status] || 'bg-bg-line';
  const flashClass = flashEvent
    ? FLASH_BY_EVENT[flashEvent] || 'animate-flash-brand'
    : '';
  // El % de la máquina refleja el avance de su operación actual
  // (quantity_out vs quantity_in). La orden cabecera solo se actualiza al
  // cerrar EMP, así que para el resto de máquinas no es indicativo.
  const op = machine.current_operation;
  const order = machine.current_order;
  const opPct =
    op && op.quantity_in > 0
      ? Math.min(100, Math.round((op.quantity_out / op.quantity_in) * 100))
      : 0;
  // Avance de la orden mostrado por esta máquina: cuántas unidades del
  // total pedido ha procesado esta máquina hasta ahora. Para IMP/TUB/FON
  // es op.quantity_out (lo que va saliendo); para EMP coincide con
  // order.quantity_produced (lo que ya llegó a inventario).
  const orderProgressUnits = op
    ? op.quantity_out
    : (order?.quantity_produced || 0);
  const orderPct =
    order && order.quantity_ordered > 0
      ? Math.min(100, Math.round((orderProgressUnits / order.quantity_ordered) * 100))
      : 0;

  return (
    <div
      // El `key` hace que React re-monte el nodo y la animación se replay
      // cada vez que llega un nuevo evento (mismo eventType o no).
      key={flashKey}
      className={`panel relative overflow-hidden transition-shadow ${flashClass}`}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${bar}`} aria-hidden />

      <div className="pl-5 pr-4 py-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">
              {machine.type}
              {machine.location && <> · {machine.location}</>}
            </p>
            <p className="mono text-xl text-ink-high tracking-widest2 mt-0.5">
              {machine.code}
            </p>
            <h3 className="text-sm text-ink-mid truncate mt-0.5">{machine.name}</h3>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <StatusDot tone={machine.status} size="md" />
            <Badge tone={machine.status} />
          </div>
        </div>

        {op ? (
          <div className="mt-4">
            {/* Línea 1: avance de la operación actual de ESTA máquina */}
            <div className="flex items-center justify-between text-[11px] text-ink-mid mono">
              <span className="truncate">
                <span className="text-accent">op{op.sequence}</span> · {op.order_number}
              </span>
              <span className="tabular-nums text-ink-high">{opPct}%</span>
            </div>
            <div className="mt-1.5 h-1 rounded-full bg-bg-line overflow-hidden">
              <div
                className="h-1 bg-accent transition-all duration-500"
                style={{ width: `${opPct}%` }}
              />
            </div>
            <p className="mono text-[10px] text-ink-low mt-1.5 tabular-nums">
              {fmt(op.quantity_out)} / {fmt(op.quantity_in)} ud
              {op.scrap_kg > 0 && (
                <span className="text-state-stopped"> · {op.scrap_kg.toFixed(1)} kg scrap</span>
              )}
            </p>
            {/* Línea 2: avance de la orden a través de esta máquina */}
            {order && (
              <p className="mono text-[10px] text-ink-low mt-1 tabular-nums">
                <span className="uppercase tracking-widest2">orden:</span>{' '}
                {fmt(orderProgressUnits)} / {fmt(order.quantity_ordered)} sacos · {orderPct}%
              </p>
            )}
          </div>
        ) : order ? (
          <div className="mt-4">
            <div className="flex items-center justify-between text-[11px] text-ink-mid mono">
              <span className="truncate">{order.order_number}</span>
              <span className="tabular-nums text-ink-high">{orderPct}%</span>
            </div>
            <div className="mt-1.5 h-1 rounded-full bg-bg-line overflow-hidden">
              <div
                className="h-1 bg-accent transition-all duration-500"
                style={{ width: `${orderPct}%` }}
              />
            </div>
            <p className="mono text-[10px] text-ink-low mt-1.5 tabular-nums">
              {fmt(order.quantity_produced)} / {fmt(order.quantity_ordered)} sacos
            </p>
          </div>
        ) : (
          <div className="mt-4">
            <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">
              Sin operación activa
            </p>
            <div className="mt-1.5 h-1 rounded-full bg-bg-softline" />
          </div>
        )}
      </div>
    </div>
  );
}
