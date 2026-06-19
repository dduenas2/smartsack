/**
 * OrderTraceView — vista detalle de una orden con sus 4 operaciones.
 *
 * Acceso: /orders/:orderId
 * Muestra:
 *   - Cabecera de la orden (número, producto, prioridad, status, totales)
 *   - Timeline horizontal de las 4 operaciones IMP→TUB→FON→EMP con su
 *     estado, kg in/out, scrap, operador, turno, tiempos.
 *   - Auditable y exportable: pensado para QC y trazabilidad regulatoria.
 */
import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { listOrderOperations } from '../api/operations.js';
import Card from '../components/common/Card.jsx';
import Badge from '../components/common/Badge.jsx';
import Spinner from '../components/common/Spinner.jsx';

function fmt(n) {
  return new Intl.NumberFormat('es-CO').format(n ?? 0);
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('es-CO', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  });
}

const SEQUENCE_LABEL = {
  1: 'Impresión',
  2: 'Tubulado',
  3: 'Fondado',
  4: 'Empacado',
};

const SCRAP_REASON_LABEL = {
  quality_defect: 'Defecto calidad',
  setup_loss: 'Pérdida en setup',
  material_break: 'Rotura material',
  other: 'Otra causa',
};

export default function OrderTraceView() {
  const { orderId } = useParams();
  const [ops, setOps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    listOrderOperations(orderId)
      .then(setOps)
      .catch((err) =>
        setError(err?.response?.data?.detail || 'Error al cargar la orden')
      )
      .finally(() => setLoading(false));
  }, [orderId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size="lg" label="Cargando trazabilidad..." />
      </div>
    );
  }
  if (error) {
    return <div className="panel p-4 text-state-stopped text-sm">{error}</div>;
  }
  if (ops.length === 0) {
    return (
      <div className="panel p-4 text-ink-mid text-sm">
        Esta orden no tiene operaciones registradas.
      </div>
    );
  }

  const order = ops[0]?.order;
  const totalScrap = ops.reduce((s, op) => s + (op.scrap_kg || 0), 0);
  const finalOut = ops[ops.length - 1]?.quantity_out || 0;

  return (
    <div className="space-y-6 animate-fade-in-up">
      <header className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <p className="label-eyebrow">Trazabilidad de orden</p>
          <h1 className="text-3xl font-light text-ink-high tracking-wide mt-1">
            <span className="mono">{order?.order_number}</span>
          </h1>
          <p className="text-sm text-ink-mid mt-1">
            {order?.product_type} · {fmt(order?.quantity_ordered)} sacos pedidos
          </p>
        </div>
        <Link
          to="/supervisor"
          className="text-xs text-accent hover:underline mono uppercase tracking-widest2"
        >
          ← Volver al Digital Twin
        </Link>
      </header>

      <Card title="Resumen" accent="brand">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Pedido</p>
            <p className="mono text-xl text-ink-high tabular-nums">{fmt(order?.quantity_ordered)}</p>
            <p className="text-[11px] text-ink-low">sacos</p>
          </div>
          <div>
            <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Producido (EMP)</p>
            <p className="mono text-xl text-state-running tabular-nums">{fmt(finalOut)}</p>
            <p className="text-[11px] text-ink-low">sacos a inventario</p>
          </div>
          <div>
            <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Desperdicio total</p>
            <p className="mono text-xl text-state-stopped tabular-nums">
              {totalScrap.toFixed(1)}
            </p>
            <p className="text-[11px] text-ink-low">kg</p>
          </div>
          <div>
            <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Prioridad</p>
            <Badge tone={order?.priority}>{order?.priority}</Badge>
          </div>
        </div>
      </Card>

      <Card title="Ruta de fabricación" hint="IMP → TUB → FON → EMP" accent="cyan">
        <ol className="space-y-3">
          {ops.map((op, idx) => {
            const isLast = idx === ops.length - 1;
            return (
              <li key={op.id} className="relative">
                {!isLast && (
                  <span
                    className="absolute left-4 top-10 bottom-[-12px] w-px bg-bg-line"
                    aria-hidden
                  />
                )}
                <div className="flex items-start gap-3">
                  <div
                    className={`shrink-0 mono text-[11px] font-medium w-8 h-8 rounded-full grid place-items-center ring-1 ${
                      op.status === 'completed'
                        ? 'bg-state-running/10 text-state-running ring-state-running/30'
                        : op.status === 'in_progress'
                          ? 'bg-accent/10 text-accent ring-accent/30 animate-pulse'
                          : op.status === 'ready'
                            ? 'bg-sky-100 text-sky-700 ring-sky-300'
                            : 'bg-bg-base text-ink-low ring-bg-softline'
                    }`}
                  >
                    {op.sequence}
                  </div>
                  <div className="flex-1 panel p-3">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <div>
                        <p className="mono text-sm text-ink-high">
                          {SEQUENCE_LABEL[op.sequence]} · {op.machine?.code}
                        </p>
                        <p className="text-xs text-ink-mid mt-0.5">
                          {op.machine?.name}
                        </p>
                      </div>
                      <Badge tone={op.status}>{op.status}</Badge>
                    </div>
                    <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div>
                        <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">In</p>
                        <p className="mono text-sm tabular-nums text-ink-high">{fmt(op.quantity_in)}</p>
                      </div>
                      <div>
                        <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Out</p>
                        <p className="mono text-sm tabular-nums text-state-running">{fmt(op.quantity_out)}</p>
                      </div>
                      <div>
                        <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Scrap</p>
                        <p className={`mono text-sm tabular-nums ${
                          op.scrap_kg > 0 ? 'text-state-stopped' : 'text-ink-low'
                        }`}>
                          {(op.scrap_kg || 0).toFixed(1)} kg
                        </p>
                        {op.scrap_reason && (
                          <p className="text-[10px] text-ink-low">
                            {SCRAP_REASON_LABEL[op.scrap_reason]}
                          </p>
                        )}
                      </div>
                      <div>
                        <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Yield</p>
                        <p className="mono text-sm tabular-nums text-ink-high">
                          {op.quantity_in > 0
                            ? `${((op.quantity_out / op.quantity_in) * 100).toFixed(1)}%`
                            : '—'}
                        </p>
                      </div>
                    </div>
                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-ink-mid">
                      <p>
                        <span className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Inicio: </span>
                        {fmtDate(op.actual_start)}
                      </p>
                      <p>
                        <span className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Fin: </span>
                        {fmtDate(op.actual_end)}
                      </p>
                      <p>
                        <span className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Operador: </span>
                        {op.operator_id ? `#${op.operator_id}` : '—'}
                      </p>
                      <p>
                        <span className="mono text-[10px] uppercase tracking-widest2 text-ink-low">Turno: </span>
                        {op.shift || '—'}
                      </p>
                    </div>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </Card>
    </div>
  );
}
