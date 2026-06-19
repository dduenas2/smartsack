/**
 * MachineRanking — tabla de máquinas ordenadas por OEE promedio (30d).
 *
 * Cada fila muestra rank, código, tipo, OEE promedio + minibarra de cada
 * factor (A/P/Q). Los líderes y rezagados se resaltan con un borde de color
 * para localizar a primera vista oportunidades de mejora.
 */
import { useEffect, useState } from 'react';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';
import { getMachineRanking } from '../../api/dashboard.js';

function pct(v) {
  return v == null ? '—' : `${(v * 100).toFixed(1)}%`;
}

function tonePillForOee(oee) {
  if (oee == null) return 'bg-bg-softline text-ink-low';
  if (oee >= 0.85) return 'bg-state-running/10 text-state-running';
  if (oee >= 0.6) return 'bg-accent/10 text-accent';
  if (oee >= 0.4) return 'bg-state-maintenance/10 text-state-maintenance';
  return 'bg-state-stopped/10 text-state-stopped';
}

function MiniBar({ value, color }) {
  const w = value == null ? 0 : Math.max(2, Math.min(100, value * 100));
  return (
    <div className="h-1 w-16 rounded-full bg-bg-softline overflow-hidden">
      <div className="h-full rounded-full" style={{ width: `${w}%`, background: color }} />
    </div>
  );
}

export default function MachineRanking() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getMachineRanking({ days: 30 })
      .then((res) => !cancelled && setItems(res.items))
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
      title="Ranking de máquinas (OEE 30d)"
      hint="Identifica líderes y oportunidades de mejora"
    >
      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner size="sm" />
        </div>
      ) : error ? (
        <p className="text-state-stopped text-sm py-6 text-center">{error}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left mono text-[10px] uppercase tracking-widest2 text-ink-low border-b border-bg-softline">
                <th className="py-2 pr-4 font-medium">#</th>
                <th className="py-2 pr-4 font-medium">Máquina</th>
                <th className="py-2 pr-4 font-medium">Tipo</th>
                <th className="py-2 pr-4 font-medium text-right">OEE</th>
                <th className="py-2 pr-4 font-medium">Disp.</th>
                <th className="py-2 pr-4 font-medium">Rend.</th>
                <th className="py-2 pr-4 font-medium">Cal.</th>
                <th className="py-2 pr-4 font-medium text-right">Muestras</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m, idx) => (
                <tr
                  key={m.machine_id}
                  className="border-b border-bg-softline last:border-b-0 hover:bg-bg-softline/40 transition-colors"
                >
                  <td className="py-3 pr-4">
                    <span className="mono text-ink-mid tabular-nums">{idx + 1}</span>
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex flex-col">
                      <span className="mono text-ink-high font-medium">{m.code}</span>
                      <span className="text-ink-low text-xs">{m.name}</span>
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-ink-mid capitalize">{m.type}</td>
                  <td className="py-3 pr-4 text-right">
                    <span
                      className={`inline-block mono tabular-nums px-2 py-1 rounded-md text-xs font-medium ${tonePillForOee(
                        m.avg_oee
                      )}`}
                    >
                      {pct(m.avg_oee)}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <MiniBar value={m.avg_availability} color="#16a34a" />
                      <span className="mono text-[10px] text-ink-low tabular-nums">
                        {pct(m.avg_availability)}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <MiniBar value={m.avg_performance} color="#08B2FF" />
                      <span className="mono text-[10px] text-ink-low tabular-nums">
                        {pct(m.avg_performance)}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      <MiniBar value={m.avg_quality} color="#ea580c" />
                      <span className="mono text-[10px] text-ink-low tabular-nums">
                        {pct(m.avg_quality)}
                      </span>
                    </div>
                  </td>
                  <td className="py-3 pr-4 text-right mono text-ink-low tabular-nums">
                    {m.sample_count}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
