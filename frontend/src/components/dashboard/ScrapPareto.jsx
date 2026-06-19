/**
 * ScrapPareto — desperdicio acumulado por máquina (kg) tipo Pareto.
 *
 * Muestra las 8 máquinas ordenadas DESC por scrap. La empacadora
 * siempre aparece con 0 (no genera desperdicio por diseño). El total
 * y el yield combinado se muestran arriba como resumen.
 */
import { useEffect, useState } from 'react';
import { getScrapByMachine, getYieldByOperation } from '../../api/dashboard.js';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';

function fmt(n) {
  return new Intl.NumberFormat('es-CO', { maximumFractionDigits: 1 }).format(n ?? 0);
}

const TYPE_COLOR = {
  impresora:  '#0EA5E9',  // sky
  tubuladora: '#F97316',  // orange
  fondadora:  '#A855F7',  // purple
  empacadora: '#10B981',  // emerald
};

export default function ScrapPareto({ days = 30 }) {
  const [data, setData] = useState(null);
  const [yieldData, setYieldData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([getScrapByMachine({ days }), getYieldByOperation({ days })])
      .then(([scrap, yld]) => {
        if (cancelled) return;
        setData(scrap);
        setYieldData(yld);
      })
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [days]);

  if (loading) {
    return (
      <Card title="Desperdicio por máquina" hint={`últimos ${days} días`} accent="rose">
        <div className="flex justify-center py-10"><Spinner /></div>
      </Card>
    );
  }
  if (!data) return null;

  const totals = data.totals_by_machine || [];
  const maxScrap = Math.max(...totals.map((t) => t.scrap_kg), 1);
  const totalKg = totals.reduce((sum, t) => sum + t.scrap_kg, 0);
  const yieldsByMachine = Object.fromEntries(
    (yieldData?.items || []).map((y) => [y.machine_code, y.yield_ratio])
  );

  return (
    <Card
      title="Desperdicio por máquina"
      hint={`últimos ${days} días · ${fmt(totalKg)} kg en total`}
      accent="rose"
    >
      <ul className="space-y-2">
        {totals.map((t) => {
          const pct = (t.scrap_kg / maxScrap) * 100;
          const color = TYPE_COLOR[t.machine_type] || '#94A3B8';
          const yieldR = yieldsByMachine[t.machine_code];
          return (
            <li key={t.machine_id} className="flex items-center gap-3">
              <span className="mono text-xs w-16 shrink-0 text-ink-high">
                {t.machine_code}
              </span>
              <div className="flex-1 relative h-7 bg-bg-base rounded ring-1 ring-bg-softline overflow-hidden">
                <div
                  className="absolute inset-y-0 left-0 transition-all"
                  style={{
                    width: `${pct}%`,
                    background: `linear-gradient(90deg, ${color}30, ${color})`,
                  }}
                />
                <div className="absolute inset-0 flex items-center justify-end px-2">
                  <span className="mono text-xs tabular-nums text-ink-high font-medium">
                    {fmt(t.scrap_kg)} kg
                  </span>
                </div>
              </div>
              <span
                className={`mono text-[10px] uppercase tracking-widest2 w-14 text-right shrink-0 ${
                  yieldR !== null && yieldR !== undefined
                    ? yieldR < 0.95
                      ? 'text-state-stopped'
                      : yieldR < 0.97
                        ? 'text-state-maintenance'
                        : 'text-state-running'
                    : 'text-ink-low'
                }`}
              >
                {yieldR !== null && yieldR !== undefined
                  ? `${(yieldR * 100).toFixed(1)}%`
                  : '—'}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low mt-3">
        Barra: kg de desperdicio · derecha: yield (out/in) — verde &gt; 97% · rojo &lt; 95%
      </p>
    </Card>
  );
}
