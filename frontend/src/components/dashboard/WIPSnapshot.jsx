/**
 * WIPSnapshot — Work In Progress en planta en este momento.
 *
 * Por cada máquina muestra: cuántas operaciones están en curso, cuántas
 * listas para tomar, y cuántas unidades hay vivas (in_progress: lo que
 * falta por producir; ready: lo que la máquina anterior ya entregó pero
 * aún no se ha tomado).
 *
 * Refresca cada 15s para no bombardear el backend; cuando llegue un
 * mensaje WS de operation_update también se podría invalidar (futuro).
 */
import { useEffect, useState } from 'react';
import { getWIP } from '../../api/dashboard.js';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';

function fmt(n) {
  return new Intl.NumberFormat('es-CO').format(n ?? 0);
}

export default function WIPSnapshot() {
  const [wip, setWip] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function fetchOnce() {
      try {
        const data = await getWIP();
        if (!cancelled) setWip(data);
      } catch {
        /* silencioso */
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchOnce();
    const id = setInterval(fetchOnce, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  if (loading) {
    return (
      <Card title="WIP en línea" hint="Trabajo en curso" accent="cyan">
        <div className="flex justify-center py-10"><Spinner /></div>
      </Card>
    );
  }
  if (!wip) return null;

  return (
    <Card
      title="WIP en línea"
      hint={`${fmt(wip.total_units_in_line)} unidades en tránsito`}
      accent="cyan"
    >
      <ul className="grid grid-cols-2 gap-2">
        {wip.machines.map((m) => {
          const total = m.units_in_progress + m.units_ready;
          const hasWork = m.operations_in_progress + m.operations_ready > 0;
          return (
            <li
              key={m.machine_id}
              className={`p-2.5 rounded-md ring-1 ring-inset ${
                hasWork
                  ? 'ring-accent/30 bg-accent/5'
                  : 'ring-bg-softline bg-bg-base'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="mono text-xs text-ink-high">{m.machine_code}</span>
                <span className="mono text-[10px] uppercase tracking-widest2 text-ink-low">
                  {m.machine_type}
                </span>
              </div>
              <div className="mt-1.5 flex items-baseline gap-1">
                <span className={`mono text-lg font-medium tabular-nums ${
                  hasWork ? 'text-accent' : 'text-ink-low'
                }`}>
                  {fmt(total)}
                </span>
                <span className="text-[10px] text-ink-low">ud</span>
              </div>
              <div className="mt-1 flex gap-2 mono text-[10px] uppercase tracking-widest2">
                {m.operations_in_progress > 0 && (
                  <span className="text-state-running">
                    {m.operations_in_progress}× en curso
                  </span>
                )}
                {m.operations_ready > 0 && (
                  <span className="text-accent">
                    {m.operations_ready}× listas
                  </span>
                )}
                {!hasWork && <span className="text-ink-low">— libre —</span>}
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
