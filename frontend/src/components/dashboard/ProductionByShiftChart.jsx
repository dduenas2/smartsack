/**
 * ProductionByShiftChart — barras apiladas por turno con producción diaria.
 */
import { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend as RechartsLegend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';
import { getProductionByShift } from '../../api/dashboard.js';

const COLORS = {
  turno_1: '#08B2FF',
  turno_2: '#00205B',
  turno_3: '#64748b',
};

const LABELS = {
  turno_1: 'Turno 1 · 06–14',
  turno_2: 'Turno 2 · 14–22',
  turno_3: 'Turno 3 · 22–06',
};

function fmtDate(d) {
  const date = new Date(d);
  return date.toLocaleDateString('es-CO', { month: 'short', day: '2-digit' });
}
function fmtNum(n) {
  return Number(n || 0).toLocaleString('es-CO');
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const total = payload.reduce((acc, p) => acc + (p.value || 0), 0);
  return (
    <div
      className="rounded-md border border-bg-line bg-white px-3 py-2 shadow-soft text-xs"
      style={{ minWidth: 200 }}
    >
      <p className="mono uppercase tracking-widest2 text-ink-low mb-1">
        {fmtDate(label)}
      </p>
      {payload.map((p) => (
        <div
          key={p.dataKey}
          className="flex items-center justify-between gap-3 mono tabular-nums"
        >
          <span style={{ color: p.color }}>{LABELS[p.dataKey]}</span>
          <span className="text-ink-high">{fmtNum(p.value)}</span>
        </div>
      ))}
      <div className="flex items-center justify-between gap-3 mono tabular-nums pt-1 mt-1 border-t border-bg-softline">
        <span className="label-eyebrow">Total</span>
        <span className="text-ink-high">{fmtNum(total)}</span>
      </div>
    </div>
  );
}

export default function ProductionByShiftChart() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getProductionByShift({ days: 7 })
      .then((res) => !cancelled && setData(res.points))
      .catch((err) =>
        !cancelled && setError(err?.response?.data?.detail || 'Error al cargar')
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card
      accent="brand"
      title="Producción por turno"
      hint="Sacos producidos en los últimos 7 días, apilados por turno"
    >
      <div className="h-72 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70">
            <Spinner size="sm" />
          </div>
        )}
        {error && (
          <p className="text-state-stopped text-sm py-12 text-center">{error}</p>
        )}
        {!error && (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: -4 }}>
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
                stroke="#94a3b8"
                tick={{ fontSize: 10, fill: '#94a3b8', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={false}
                width={56}
                tickFormatter={(v) => fmtNum(v)}
              />
              <Tooltip cursor={{ fill: 'rgba(8,178,255,0.08)' }} content={<CustomTooltip />} />
              <RechartsLegend
                wrapperStyle={{ fontSize: 10, fontFamily: 'JetBrains Mono' }}
                formatter={(v) => LABELS[v] || v}
              />
              <Bar dataKey="turno_1" stackId="prod" fill={COLORS.turno_1} radius={[0, 0, 0, 0]} />
              <Bar dataKey="turno_2" stackId="prod" fill={COLORS.turno_2} radius={[0, 0, 0, 0]} />
              <Bar dataKey="turno_3" stackId="prod" fill={COLORS.turno_3} radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </Card>
  );
}
