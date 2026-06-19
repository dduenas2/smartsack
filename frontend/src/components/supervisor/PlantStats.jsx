/**
 * PlantStats — KPIs en cabecera del Digital Twin (tema claro).
 */
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import Card from '../common/Card.jsx';
import StatusDot from '../common/StatusDot.jsx';

const COLORS = {
  running: '#16a34a',
  stopped: '#dc2626',
  maintenance: '#ea580c',
  idle: '#64748b',
};

const LABEL = {
  running: 'En operación',
  stopped: 'Detenidas',
  maintenance: 'Mantenimiento',
  idle: 'Disponibles',
};

export default function PlantStats({ machines }) {
  const counts = { running: 0, stopped: 0, maintenance: 0, idle: 0 };
  machines.forEach((m) => {
    if (counts[m.status] !== undefined) counts[m.status] += 1;
  });
  const total = machines.length;
  // "En curso ahora" = unidades buenas que han salido de las operaciones
  // activas, vs. unidades que entraron a esas operaciones. Es el avance
  // instantáneo del trabajo vivo en planta.
  const productionInProgress = machines.reduce(
    (acc, m) => acc + (m.current_operation?.quantity_out || 0),
    0
  );
  const productionTarget = machines.reduce(
    (acc, m) => acc + (m.current_operation?.quantity_in || 0),
    0
  );
  const utilization = total ? Math.round((counts.running / total) * 100) : 0;

  const data = Object.entries(counts).map(([status, value]) => ({
    status,
    label: LABEL[status],
    value,
  }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
      <Kpi
        label="Estaciones activas"
        value={counts.running}
        suffix={`/ ${total}`}
        tone="running"
        sub={`${utilization}% utilización`}
      />
      <Kpi
        label="Detenidas"
        value={counts.stopped}
        tone="stopped"
        sub={counts.stopped === 0 ? 'Sin paradas' : 'Atención requerida'}
      />
      <Kpi
        label="Mantenimiento"
        value={counts.maintenance}
        tone="maintenance"
        sub={counts.maintenance === 0 ? 'Sin tareas' : 'En curso'}
      />
      <Kpi
        label="En curso ahora"
        value={productionInProgress.toLocaleString('es-CO')}
        suffix={
          productionTarget
            ? `/ ${productionTarget.toLocaleString('es-CO')}`
            : ''
        }
        tone="accent"
        sub="unidades en operaciones activas"
      />

      <Card title="Distribución por estado" className="lg:col-span-1">
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
              <XAxis
                dataKey="label"
                stroke="#94a3b8"
                tick={{ fontSize: 10, fill: '#475569', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={{ stroke: '#dbe4ee' }}
              />
              <YAxis
                allowDecimals={false}
                stroke="#94a3b8"
                tick={{ fontSize: 10, fill: '#94a3b8' }}
                tickLine={false}
                axisLine={false}
                width={30}
              />
              <Tooltip
                cursor={{ fill: 'rgba(8,178,255,0.08)' }}
                contentStyle={{
                  background: '#ffffff',
                  border: '1px solid #dbe4ee',
                  borderRadius: 8,
                  color: '#00205B',
                  fontSize: 12,
                  boxShadow: '0 4px 12px rgba(0,32,91,0.08)',
                }}
                labelStyle={{ color: '#475569' }}
              />
              <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                {data.map((d) => (
                  <Cell key={d.status} fill={COLORS[d.status]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}

function Kpi({ label, value, suffix, sub, tone }) {
  const valueColor =
    tone === 'running'     ? 'text-state-running' :
    tone === 'stopped'     ? 'text-state-stopped' :
    tone === 'maintenance' ? 'text-state-maintenance' :
    tone === 'accent'      ? 'text-accent' :
    'text-ink-high';

  return (
    <div className="panel relative overflow-hidden p-4">
      <div className="flex items-center gap-2 mb-2">
        <StatusDot tone={tone === 'accent' ? 'online' : tone} size="sm" />
        <p className="label-eyebrow">{label}</p>
      </div>
      <div className="flex items-baseline gap-2">
        <span className={`mono text-3xl font-medium tabular-nums ${valueColor}`}>{value}</span>
        {suffix && (
          <span className="mono text-sm text-ink-mid tabular-nums">{suffix}</span>
        )}
      </div>
      {sub && <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low mt-1">{sub}</p>}
    </div>
  );
}
