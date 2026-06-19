/**
 * OrderFulfillmentChart — gráfico de área apilada con cumplimiento de órdenes
 * (completadas, en curso, pendientes, retrasadas) por día.
 */
import { useEffect, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';
import { getOrderFulfillment } from '../../api/dashboard.js';

const COLORS = {
  completed: '#16a34a',
  in_progress: '#08B2FF',
  pending: '#94a3b8',
  delayed: '#dc2626',
};
const LABELS = {
  completed: 'Completadas',
  in_progress: 'En curso',
  pending: 'Pendientes',
  delayed: 'Retrasadas',
};

function fmtDate(d) {
  const date = new Date(d);
  return date.toLocaleDateString('es-CO', { month: 'short', day: '2-digit' });
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-bg-line bg-white px-3 py-2 shadow-soft text-xs">
      <p className="mono uppercase tracking-widest2 text-ink-low mb-1">
        {fmtDate(label)}
      </p>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-3 mono tabular-nums">
          <span style={{ color: p.color }}>{LABELS[p.dataKey]}</span>
          <span className="text-ink-high">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

export default function OrderFulfillmentChart() {
  const [data, setData] = useState([]);
  const [totals, setTotals] = useState({ completed: 0, delayed: 0, pending: 0, in_progress: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getOrderFulfillment({ days: 30 })
      .then((res) => {
        if (cancelled) return;
        setData(res.points);
        setTotals({
          completed: res.total_completed,
          delayed: res.total_delayed,
          pending: res.total_pending,
          in_progress: res.total_in_progress,
        });
      })
      .catch((err) =>
        !cancelled && setError(err?.response?.data?.detail || 'Error al cargar')
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const totalAll =
    totals.completed + totals.delayed + totals.pending + totals.in_progress;
  const onTimeRate = totalAll
    ? Math.round((totals.completed / totalAll) * 100)
    : 0;

  return (
    <Card
      accent="brand"
      title="Cumplimiento de órdenes (30d)"
      hint={`${onTimeRate}% completadas · ${totals.delayed} retrasadas`}
    >
      <div className="h-64 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70">
            <Spinner size="sm" />
          </div>
        )}
        {error && <p className="text-state-stopped text-sm py-12 text-center">{error}</p>}
        {!error && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: -10 }}>
              <defs>
                {Object.entries(COLORS).map(([k, c]) => (
                  <linearGradient key={k} id={`grad-${k}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={c} stopOpacity={0.45} />
                    <stop offset="95%" stopColor={c} stopOpacity={0.05} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid stroke="#eef2f8" vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDate}
                stroke="#94a3b8"
                tick={{ fontSize: 10, fill: '#475569', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={{ stroke: '#dbe4ee' }}
              />
              <YAxis
                allowDecimals={false}
                stroke="#94a3b8"
                tick={{ fontSize: 10, fill: '#94a3b8', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={false}
                width={32}
              />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="completed"
                stackId="1"
                stroke={COLORS.completed}
                strokeWidth={1.5}
                fill="url(#grad-completed)"
              />
              <Area
                type="monotone"
                dataKey="in_progress"
                stackId="1"
                stroke={COLORS.in_progress}
                strokeWidth={1.5}
                fill="url(#grad-in_progress)"
              />
              <Area
                type="monotone"
                dataKey="pending"
                stackId="1"
                stroke={COLORS.pending}
                strokeWidth={1.5}
                fill="url(#grad-pending)"
              />
              <Area
                type="monotone"
                dataKey="delayed"
                stackId="1"
                stroke={COLORS.delayed}
                strokeWidth={1.5}
                fill="url(#grad-delayed)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}
