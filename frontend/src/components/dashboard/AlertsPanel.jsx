/**
 * AlertsPanel — listado de órdenes con probabilidad de retraso > umbral.
 *
 * Las filas de probabilidad alta (≥ 0.85) se marcan en rojo; las medias
 * (0.6–0.85) en ámbar. Permite cambiar el umbral en vivo con un slider.
 */
import { useEffect, useState } from 'react';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';
import { getAlerts } from '../../api/dashboard.js';

function fmtDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('es-CO', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function sevForProb(p) {
  if (p >= 0.85) return { tone: 'stopped', label: 'Crítica' };
  if (p >= 0.7) return { tone: 'maintenance', label: 'Alta' };
  return { tone: 'idle', label: 'Media' };
}

const TONE_BG = {
  stopped: 'border-state-stopped/40 bg-state-stopped/5',
  maintenance: 'border-state-maintenance/40 bg-state-maintenance/5',
  idle: 'border-bg-line bg-white',
};
const TONE_PILL = {
  stopped: 'bg-state-stopped text-white',
  maintenance: 'bg-state-maintenance text-white',
  idle: 'bg-state-idle text-white',
};

export default function AlertsPanel() {
  const [threshold, setThreshold] = useState(0.6);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getAlerts({ threshold, limit: 12 })
      .then((res) => !cancelled && setItems(res.items))
      .catch((err) =>
        !cancelled && setError(err?.response?.data?.detail || 'Error al cargar')
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [threshold]);

  return (
    <Card
      accent="rose"
      title="Alertas predictivas"
      hint="Órdenes activas con riesgo de retraso según el modelo ML"
      action={
        <div className="flex items-center gap-2">
          <span className="mono text-[10px] uppercase tracking-widest2 text-ink-low">
            umbral
          </span>
          <input
            type="range"
            min={0.3}
            max={0.95}
            step={0.05}
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            className="w-24 accent-state-stopped"
          />
          <span className="mono text-xs tabular-nums text-ink-high w-10 text-right">
            {Math.round(threshold * 100)}%
          </span>
        </div>
      }
    >
      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner size="sm" />
        </div>
      ) : error ? (
        <p className="text-state-stopped text-sm py-6 text-center">{error}</p>
      ) : items.length === 0 ? (
        <p className="text-ink-mid text-sm py-6 text-center">
          Sin alertas por encima del umbral. Producción nominal.
        </p>
      ) : (
        <ul className="space-y-2 max-h-96 overflow-y-auto pr-1">
          {items.map((a) => {
            const sev = sevForProb(a.delay_probability);
            return (
              <li
                key={a.order_id}
                className={`rounded-md border p-3 transition-colors ${TONE_BG[sev.tone]}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="mono text-sm text-ink-high font-medium">
                        {a.order_number}
                      </span>
                      <span
                        className={`mono text-[9px] uppercase tracking-widest2 px-1.5 py-0.5 rounded ${TONE_PILL[sev.tone]}`}
                      >
                        {sev.label}
                      </span>
                      <span className="mono text-[9px] uppercase tracking-widest2 text-ink-low">
                        {a.status}
                      </span>
                    </div>
                    <p className="text-xs text-ink-mid mt-1 truncate">
                      {a.product_type}
                      {a.machine_code && (
                        <>
                          <span className="text-ink-mute"> · </span>
                          <span className="mono">{a.machine_code}</span>
                        </>
                      )}
                    </p>
                    <p className="mono text-[10px] text-ink-low mt-1">
                      Plan: {fmtDateTime(a.planned_end)} · +{a.predicted_delay_hours.toFixed(1)}h
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="mono text-2xl tabular-nums text-ink-high font-medium leading-none">
                      {(a.delay_probability * 100).toFixed(0)}
                      <span className="text-sm text-ink-low">%</span>
                    </p>
                    <p className="mono text-[9px] uppercase tracking-widest2 text-ink-low mt-1">
                      prob. retraso
                    </p>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
