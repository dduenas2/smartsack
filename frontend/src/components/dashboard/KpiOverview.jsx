/**
 * KpiOverview — fila de tarjetas KPI en cabecera del Dashboard.
 *
 * Lee la respuesta de /api/dashboard/overview y la presenta como 4 grandes
 * tarjetas con números agregados. El delta de OEE vs ayer se muestra como
 * pill ▲/▼ con color de tendencia.
 */
import StatusDot from '../common/StatusDot.jsx';

function fmt(n) {
  return Number(n || 0).toLocaleString('es-CO');
}
function pct(v) {
  return `${(Number(v || 0) * 100).toFixed(1)}%`;
}

export default function KpiOverview({ data }) {
  if (!data) return null;
  const delta =
    data.plant_oee_yesterday != null
      ? data.plant_oee - data.plant_oee_yesterday
      : null;
  const deltaTone =
    delta == null ? 'idle' : delta >= 0 ? 'running' : 'stopped';
  const deltaArrow = delta == null ? '·' : delta >= 0 ? '▲' : '▼';

  const utilization = data.total_machines
    ? Math.round((data.active_machines / data.total_machines) * 100)
    : 0;

  const fulfilled =
    data.production_target_today > 0
      ? Math.round((data.production_today / data.production_target_today) * 100)
      : 0;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <Kpi
        tone="accent"
        eyebrow="OEE de planta"
        value={pct(data.plant_oee)}
        sub={
          delta != null
            ? `${deltaArrow} ${pct(Math.abs(delta))} vs ayer`
            : 'Sin dato comparativo'
        }
        subTone={deltaTone}
        date={data.reference_date}
      />
      <Kpi
        tone="running"
        eyebrow="Producción del día"
        value={fmt(data.production_today)}
        suffix={
          data.production_target_today
            ? `/ ${fmt(data.production_target_today)}`
            : ''
        }
        sub={`${fulfilled}% del objetivo`}
      />
      <Kpi
        tone="running"
        eyebrow="Estaciones activas"
        value={`${data.active_machines}`}
        suffix={`/ ${data.total_machines}`}
        sub={`${utilization}% utilización`}
      />
      <Kpi
        tone={data.orders_delayed > 0 ? 'stopped' : 'running'}
        eyebrow="Estado de órdenes"
        value={`${data.orders_in_progress}`}
        suffix="en curso"
        sub={`${data.orders_completed_today} completadas hoy · ${data.orders_delayed} retrasadas`}
        subTone={data.orders_delayed > 0 ? 'stopped' : 'idle'}
      />
    </div>
  );
}

function Kpi({ tone = 'accent', eyebrow, value, suffix, sub, subTone, date }) {
  const valueColor =
    tone === 'running' ? 'text-state-running'
    : tone === 'stopped' ? 'text-state-stopped'
    : tone === 'maintenance' ? 'text-state-maintenance'
    : 'text-accent';
  const subColor =
    subTone === 'running' ? 'text-state-running'
    : subTone === 'stopped' ? 'text-state-stopped'
    : 'text-ink-low';

  return (
    <div className="panel relative overflow-hidden p-4 shadow-soft">
      <div className="flex items-center gap-2 mb-2">
        <StatusDot tone={tone === 'accent' ? 'online' : tone} size="sm" />
        <p className="label-eyebrow">{eyebrow}</p>
      </div>
      <div className="flex items-baseline gap-2">
        <span className={`mono text-4xl font-medium tabular-nums ${valueColor}`}>
          {value}
        </span>
        {suffix && (
          <span className="mono text-sm text-ink-mid tabular-nums">{suffix}</span>
        )}
      </div>
      {sub && (
        <p className={`mono text-[10px] uppercase tracking-widest2 mt-2 ${subColor}`}>
          {sub}
        </p>
      )}
      {date && (
        <p className="mono text-[10px] text-ink-mute mt-1">ref · {date}</p>
      )}
    </div>
  );
}
