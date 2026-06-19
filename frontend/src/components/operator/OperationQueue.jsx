/**
 * OperationQueue — operaciones que el operario puede tomar en su máquina.
 *
 * Lista en orden cronológico las operaciones de la máquina con status
 * READY (esperando que alguien las tome) o IN_PROGRESS (la que estoy
 * trabajando ahora mismo). Hacer clic en una READY dispara el handler
 * `onStart` del padre, que llama a POST /operations/{id}/start.
 */
import Badge from '../common/Badge.jsx';
import Card from '../common/Card.jsx';

function fmt(n) {
  return new Intl.NumberFormat('es-CO').format(n ?? 0);
}

const SEQUENCE_LABEL = {
  1: 'Imp',
  2: 'Tub',
  3: 'Fon',
  4: 'Emp',
};

export default function OperationQueue({ operations, onStart, busyId }) {
  const ready = operations.filter((o) => o.status === 'ready');
  const running = operations.filter((o) => o.status === 'in_progress');

  const hint = running.length
    ? `1 en curso · ${ready.length} en espera`
    : ready.length
      ? `↓ ${ready.length} operación${ready.length === 1 ? '' : 'es'} esperando`
      : 'Sin operaciones pendientes';

  return (
    <Card title="Cola de operaciones" hint={hint} accent="sky">
      {operations.length === 0 ? (
        <p className="text-sm text-ink-mid py-2">
          No hay operaciones para esta máquina aún. Cuando la operación previa
          de la línea se complete, aparecerá aquí lista para iniciar.
        </p>
      ) : (
        <ul className="space-y-2">
          {operations.map((op) => {
            const isReady = op.status === 'ready';
            const isRunning = op.status === 'in_progress';
            const order = op.order;
            const interactive = isReady && !!onStart;
            return (
              <li
                key={op.id}
                onClick={() => interactive && busyId !== op.id && onStart(op)}
                className={`py-2.5 px-3 rounded-md ring-1 ring-inset transition-all ${
                  isRunning
                    ? 'bg-state-running/5 ring-state-running/40'
                    : interactive
                      ? 'cursor-pointer ring-bg-softline bg-bg-base hover:bg-accent/10 hover:ring-accent hover:shadow-sm'
                      : 'ring-bg-softline bg-bg-base opacity-70'
                }`}
                title={
                  interactive
                    ? `Iniciar op${op.sequence} de ${order?.order_number}`
                    : isRunning
                      ? 'Esta operación ya está en curso'
                      : 'Operación pendiente — espera la promoción de la previa'
                }
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="mono text-[10px] uppercase tracking-widest2 px-1.5 py-0.5 rounded bg-brand-primary/10 text-brand-primary">
                        op{op.sequence} · {SEQUENCE_LABEL[op.sequence]}
                      </span>
                      <span className="mono text-sm text-ink-high truncate">
                        {order?.order_number || '—'}
                      </span>
                    </div>
                    <p className="text-xs text-ink-mid mt-1 truncate">
                      {order?.product_type}
                    </p>
                    <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low mt-0.5">
                      Recibido: {fmt(op.quantity_in)} unidades
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1.5 shrink-0">
                    {order?.priority && (
                      <Badge tone={order.priority}>{order.priority}</Badge>
                    )}
                    {isRunning ? (
                      <span className="mono text-[10px] uppercase tracking-widest2 text-state-running font-medium">
                        en curso
                      </span>
                    ) : interactive ? (
                      <span className="mono text-[10px] uppercase tracking-widest2 text-accent font-medium">
                        {busyId === op.id ? '...' : 'iniciar →'}
                      </span>
                    ) : null}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
