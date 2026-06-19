/**
 * CurrentOperationCard — operación activa con dial + form de reporte.
 *
 * Muestra:
 *   - Dial circular: avance de salida vs. entrada de la operación.
 *   - Stats compactos: recibido, producido, pendiente, prioridad, scrap.
 *   - Form de reporte: unidades producidas + scrap_kg + scrap_reason.
 *   - Botón "Cerrar operación" cuando ya tienes salida ≥ 1.
 *
 * Reglas:
 *   - EMP no acepta scrap (input deshabilitado).
 *   - scrap_reason solo es obligatorio si scrap_kg > 0.
 *   - El backend valida que quantity != 0 y que el acumulado no quede negativo.
 */
import { useState } from 'react';
import { reportProduction } from '../../api/operations.js';
import Badge from '../common/Badge.jsx';
import Button from '../common/Button.jsx';
import Card from '../common/Card.jsx';

function fmt(n) {
  return new Intl.NumberFormat('es-CO').format(n ?? 0);
}

const SCRAP_REASONS = [
  { value: 'quality_defect', label: 'Defecto de calidad' },
  { value: 'setup_loss',     label: 'Pérdida en setup / cambio de formato' },
  { value: 'material_break', label: 'Rotura de material' },
  { value: 'other',          label: 'Otra causa' },
];

const SEQUENCE_LABEL = {
  1: 'Impresión',
  2: 'Tubulado',
  3: 'Fondado',
  4: 'Empacado',
};

function ProgressDial({ pct, over = false }) {
  const r = 60;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  const gradId = over ? 'dialGradientOver' : 'dialGradient';

  return (
    <div className="relative h-40 w-40 grid place-items-center">
      <svg viewBox="0 0 140 140" className="absolute inset-0 -rotate-90">
        <circle cx="70" cy="70" r={r} stroke="#e2e8f0" strokeWidth="8" fill="none" />
        <circle
          cx="70" cy="70" r={r}
          stroke={`url(#${gradId})`} strokeWidth="8" fill="none"
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 600ms ease-out' }}
        />
        <defs>
          <linearGradient id="dialGradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#00205B" />
            <stop offset="100%" stopColor="#08B2FF" />
          </linearGradient>
          <linearGradient id="dialGradientOver" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#047857" />
            <stop offset="100%" stopColor="#10b981" />
          </linearGradient>
        </defs>
      </svg>
      <div className="text-center">
        <div className={`mono text-4xl font-medium tabular-nums ${over ? 'text-state-running' : 'text-ink-high'}`}>
          {pct}<span className="text-ink-low text-xl">%</span>
        </div>
        <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low mt-1">
          {over ? 'sobre meta' : 'avance'}
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value, unit, tone }) {
  const valueColor =
    tone === 'emerald' ? 'text-state-running' :
    tone === 'amber'   ? 'text-state-maintenance' :
    tone === 'sky'     ? 'text-accent' :
    tone === 'rose'    ? 'text-state-stopped' :
    'text-ink-high';
  return (
    <div className="rounded-md bg-bg-base ring-1 ring-bg-softline px-3 py-2">
      <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">{label}</p>
      <div className="mt-0.5 flex items-baseline gap-1">
        <span className={`mono text-lg font-medium tabular-nums ${valueColor}`}>{value}</span>
        {unit && <span className="text-[11px] text-ink-low">{unit}</span>}
      </div>
    </div>
  );
}

export default function CurrentOperationCard({
  operation,
  machineType,
  onProduced,
  onComplete,
  busy,
}) {
  if (!operation) {
    return (
      <Card title="Operación en curso" accent="brand">
        <div className="py-8 text-center text-ink-mid text-sm">
          <p>No hay operación activa en esta máquina.</p>
          <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low mt-2">
            Toma una operación de la cola para comenzar
          </p>
        </div>
      </Card>
    );
  }

  const order = operation.order;
  const machine = operation.machine;
  const totalIn = operation.quantity_in || 0;
  const done = operation.quantity_out || 0;
  const rawPct = totalIn > 0 ? (done / totalIn) * 100 : 0;
  const pct = Math.min(100, Math.round(rawPct));
  const isOver = done > totalIn && totalIn > 0;
  const isEmp = machineType === 'empacadora';

  return (
    <Card
      title="Operación en curso"
      accent="brand"
      action={
        <span className="inline-flex items-center gap-2">
          <span className="mono text-[10px] uppercase tracking-widest2 px-1.5 py-0.5 rounded bg-brand-primary/10 text-brand-primary">
            op{operation.sequence} · {SEQUENCE_LABEL[operation.sequence] || ''}
          </span>
          <Badge tone={operation.status}>{operation.status}</Badge>
        </span>
      }
    >
      <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-6 items-center">
        <ProgressDial pct={pct} over={isOver} />

        <div className="space-y-4 min-w-0">
          <div>
            <p className="label-eyebrow">Orden · {machine?.code}</p>
            <h3 className="mono text-2xl text-ink-high font-medium tracking-wide">
              {order?.order_number}
            </h3>
            <p className="text-sm text-ink-mid mt-1">{order?.product_type}</p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Stat label="Recibido" value={fmt(totalIn)} unit="ud" />
            <Stat label="Producido" value={fmt(done)} unit="ud" tone="emerald" />
            <Stat
              label={isOver ? 'Sobre meta' : 'Pendiente'}
              value={fmt(Math.abs(totalIn - done))}
              unit="ud"
              tone={isOver ? 'sky' : 'amber'}
            />
            <Stat
              label="Desperdicio"
              value={(operation.scrap_kg || 0).toFixed(1)}
              unit="kg"
              tone={operation.scrap_kg > 0 ? 'rose' : undefined}
            />
          </div>
        </div>
      </div>

      <ProductionReportForm
        operationId={operation.id}
        isEmp={isEmp}
        onProduced={onProduced}
      />

      <div className="mt-5 pt-5 border-t border-bg-line/60 flex items-center justify-between gap-3">
        <p className="text-xs text-ink-mid">
          {isEmp
            ? 'Cuando termines esta operación, el producto pasa a inventario para despacho.'
            : `Al cerrar, la operación siguiente quedará lista para el operario de ${
                { 1: 'TUB', 2: 'FON', 3: 'EMP' }[operation.sequence] || 'la siguiente máquina'
              }.`}
        </p>
        <Button
          variant="success"
          onClick={onComplete}
          disabled={busy || done <= 0}
          title={done <= 0 ? 'Reporta al menos un valor de producción antes de cerrar' : 'Cerrar operación'}
        >
          {busy ? '...' : 'Cerrar operación →'}
        </Button>
      </div>
    </Card>
  );
}

function ProductionReportForm({ operationId, isEmp, onProduced }) {
  const [quantity, setQuantity] = useState('');
  const [scrapKg, setScrapKg] = useState('');
  const [reason, setReason] = useState('quality_defect');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    const q = parseInt(quantity, 10);
    const s = scrapKg ? parseFloat(scrapKg) : 0;
    if (!Number.isFinite(q) || q === 0) {
      setFeedback({ kind: 'error', text: 'Ingresa una cantidad distinta de cero.' });
      return;
    }
    if (s < 0) {
      setFeedback({ kind: 'error', text: 'El desperdicio no puede ser negativo.' });
      return;
    }
    if (s > 0 && !reason) {
      setFeedback({ kind: 'error', text: 'Selecciona la razón del desperdicio.' });
      return;
    }
    setBusy(true);
    setFeedback(null);
    try {
      await reportProduction(operationId, {
        quantity: q,
        scrap_kg: s,
        scrap_reason: s > 0 ? reason : null,
      });
      setFeedback({
        kind: 'success',
        text: `Reportado: ${q.toLocaleString('es-CO')} ud${
          s > 0 ? ` · ${s.toFixed(1)} kg scrap` : ''
        }.`,
      });
      setQuantity('');
      setScrapKg('');
      onProduced?.();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setFeedback({ kind: 'error', text: detail || 'No se pudo registrar el reporte.' });
    } finally {
      setBusy(false);
    }
  }

  const showReason = !isEmp && parseFloat(scrapKg) > 0;

  return (
    <div className="mt-5 pt-5 border-t border-bg-line/60">
      <p className="label-eyebrow mb-2">Reportar producción</p>
      <form onSubmit={handleSubmit} className="space-y-2.5">
        <div className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-2.5">
          <div className="relative">
            <input
              type="number" inputMode="numeric" step="1"
              value={quantity} onChange={(e) => setQuantity(e.target.value)}
              disabled={busy}
              placeholder="Unidades producidas"
              className="w-full rounded-md ring-1 ring-bg-softline bg-bg-base px-3 py-2 mono text-sm tabular-nums text-ink-high placeholder:text-ink-low focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-50"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 mono text-[10px] uppercase tracking-widest2 text-ink-low pointer-events-none">
              ud
            </span>
          </div>
          <div className="relative">
            <input
              type="number" inputMode="decimal" step="0.1" min="0"
              value={scrapKg} onChange={(e) => setScrapKg(e.target.value)}
              disabled={busy || isEmp}
              placeholder={isEmp ? 'No aplica' : 'Desperdicio'}
              className="w-full rounded-md ring-1 ring-bg-softline bg-bg-base px-3 py-2 mono text-sm tabular-nums text-ink-high placeholder:text-ink-low focus:outline-none focus:ring-2 focus:ring-accent disabled:opacity-40 disabled:cursor-not-allowed"
            />
            <span className="absolute right-3 top-1/2 -translate-y-1/2 mono text-[10px] uppercase tracking-widest2 text-ink-low pointer-events-none">
              kg
            </span>
          </div>
          <Button type="submit" variant="success" disabled={busy || !quantity}>
            {busy ? '...' : 'Registrar'}
          </Button>
        </div>
        {showReason && (
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={busy}
            className="w-full rounded-md ring-1 ring-bg-softline bg-bg-base px-3 py-2 text-sm text-ink-high focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {SCRAP_REASONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
        )}
      </form>
      <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low mt-2">
        {isEmp
          ? 'Empacadora: solo registra unidades buenas que van a inventario.'
          : 'Incremento desde el último reporte · negativo para correcciones'}
      </p>
      {feedback && (
        <div
          className={`mt-3 flex items-start gap-2 rounded-md px-3 py-2 text-sm ring-1 ring-inset animate-fade-in-up ${
            feedback.kind === 'success'
              ? 'text-state-running bg-state-running/10 ring-state-running/30'
              : 'text-state-stopped bg-state-stopped/10 ring-state-stopped/30'
          }`}
        >
          <span className="mono text-xs uppercase tracking-widest2">
            {feedback.kind === 'success' ? 'OK' : 'ERR'}
          </span>
          <span>{feedback.text}</span>
        </div>
      )}
    </div>
  );
}
