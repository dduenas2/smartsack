/**
 * OEETrendChart — línea temporal de OEE (planta o por máquina) en N días.
 *
 * Permite alternar el rango (7 / 30 / 90 días) y ver A, P, Q superpuestos
 * además del OEE consolidado. Tooltip personalizado en estética del tema
 * claro de Smurfit Kappa.
 */
import { useEffect, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';
import { getOEETrend } from '../../api/dashboard.js';

const RANGES = [
  { label: '7d', value: 7 },
  { label: '30d', value: 30 },
  { label: '90d', value: 90 },
];

const COLORS = {
  oee: '#00205B',
  availability: '#16a34a',
  performance: '#08B2FF',
  quality: '#ea580c',
};

function fmtDate(d) {
  const date = new Date(d);
  return date.toLocaleDateString('es-CO', { month: 'short', day: '2-digit' });
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div
      className="rounded-md border border-bg-line bg-white px-3 py-2 shadow-soft text-xs"
      style={{ minWidth: 160 }}
    >
      <p className="mono uppercase tracking-widest2 text-ink-low mb-1">
        {fmtDate(label)}
      </p>
      {payload.map((p) => (
        <div
          key={p.dataKey}
          className="flex items-center justify-between gap-3 mono tabular-nums"
        >
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="text-ink-high">
            {(p.value * 100).toFixed(1)}%
          </span>
        </div>
      ))}
    </div>
  );
}

export default function OEETrendChart() {
  const [days, setDays] = useState(30);
  const [points, setPoints] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getOEETrend({ days })
      .then((res) => {
        if (!cancelled) setPoints(res.points);
      })
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.detail || 'Error al cargar');
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [days]);

  return (
    <Card
      accent="brand"
      title="Tendencia de OEE"
      hint="Disponibilidad, Rendimiento, Calidad y OEE diarios"
      action={
        <div className="flex gap-1">
          {RANGES.map((r) => (
            <button
              key={r.value}
              type="button"
              onClick={() => setDays(r.value)}
              className={`mono text-[11px] uppercase tracking-widest2 px-2 py-1 rounded-md border transition-colors ${
                days === r.value
                  ? 'bg-ink-high text-white border-ink-high'
                  : 'bg-white text-ink-mid border-bg-line hover:border-accent hover:text-accent'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      }
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
            <LineChart
              data={points}
              margin={{ top: 12, right: 16, bottom: 4, left: -10 }}
            >
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
                domain={[0, 1]}
                tickFormatter={(v) => `${Math.round(v * 100)}%`}
                stroke="#94a3b8"
                tick={{ fontSize: 10, fill: '#94a3b8', fontFamily: 'JetBrains Mono' }}
                tickLine={false}
                axisLine={false}
                width={42}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="availability"
                name="Disponibilidad"
                stroke={COLORS.availability}
                strokeWidth={1.5}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="performance"
                name="Rendimiento"
                stroke={COLORS.performance}
                strokeWidth={1.5}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="quality"
                name="Calidad"
                stroke={COLORS.quality}
                strokeWidth={1.5}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="oee"
                name="OEE"
                stroke={COLORS.oee}
                strokeWidth={2.4}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="flex flex-wrap gap-4 pt-3 border-t border-bg-softline mt-2">
        <Legend color={COLORS.oee} label="OEE" emphasis />
        <Legend color={COLORS.availability} label="Disponibilidad" />
        <Legend color={COLORS.performance} label="Rendimiento" />
        <Legend color={COLORS.quality} label="Calidad" />
      </div>
    </Card>
  );
}

function Legend({ color, label, emphasis }) {
  return (
    <span className="flex items-center gap-2 mono text-[10px] uppercase tracking-widest2 text-ink-low">
      <span
        className={`inline-block ${emphasis ? 'w-4 h-1' : 'w-3 h-0.5'} rounded-full`}
        style={{ background: color }}
      />
      {label}
    </span>
  );
}
