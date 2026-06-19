/**
 * ModelInsights — feature importance del modelo de retraso + metadata.
 *
 * Se conecta a /api/predictions/feature-importance y /model-info.
 * Si el modelo no está disponible, muestra un placeholder amistoso con la
 * instrucción para entrenar.
 *
 * El admin/supervisor puede disparar `predict-active` para refrescar todas
 * las predicciones (y por tanto el AlertsPanel).
 */
import { useEffect, useState } from 'react';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { getFeatureImportance, getModelInfo, predictActive } from '../../api/predictions.js';

const FEATURE_PRETTY = {
  quantity_ordered: 'Cantidad pedida',
  planned_duration_hours: 'Duración planeada (h)',
  hour_of_day: 'Hora de inicio',
  day_of_week: 'Día de la semana',
  is_weekend: 'Es fin de semana',
  machine_concurrent_load: 'Carga concurrente máquina',
  machine_delay_rate_30d: 'Tasa retraso máquina (30d)',
  product_delay_rate_30d: 'Tasa retraso producto (30d)',
};

function pretty(name) {
  if (FEATURE_PRETTY[name]) return FEATURE_PRETTY[name];
  if (name.startsWith('product_type__')) return `Producto: ${name.split('__')[1]}`;
  if (name.startsWith('machine_code__')) return `Máquina: ${name.split('__')[1]}`;
  if (name.startsWith('shift__')) return `Turno: ${name.split('__')[1]}`;
  if (name.startsWith('priority__')) return `Prioridad: ${name.split('__')[1]}`;
  return name;
}

export default function ModelInsights() {
  const { user } = useAuth();
  const canRefresh = user && (user.role === 'admin' || user.role === 'supervisor');

  const [info, setInfo] = useState(null);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState(null);

  function load() {
    setLoading(true);
    Promise.all([getModelInfo(), getFeatureImportance({ topK: 8 }).catch(() => ({ items: [] }))])
      .then(([m, f]) => {
        setInfo(m);
        setItems(f.items || []);
        setError(null);
      })
      .catch((err) =>
        setError(err?.response?.data?.detail || 'Error cargando insights del modelo')
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  async function handleRefresh() {
    setRefreshing(true);
    setRefreshMsg(null);
    try {
      const res = await predictActive();
      setRefreshMsg(`Predicciones refrescadas: ${res.count} órdenes`);
    } catch (err) {
      setRefreshMsg(err?.response?.data?.detail || 'Error al refrescar');
    } finally {
      setRefreshing(false);
    }
  }

  if (loading && !info) {
    return (
      <Card accent="brand" title="Modelo predictivo">
        <div className="flex justify-center py-6">
          <Spinner size="sm" />
        </div>
      </Card>
    );
  }

  if (info && info.available === false) {
    return (
      <Card
        accent="amber"
        title="Modelo predictivo"
        hint="Sin modelo entrenado todavía"
      >
        <p className="text-sm text-ink-mid leading-relaxed">
          El motor de ML aún no tiene un modelo serializado. Entrena ejecutando
          en el contenedor backend:
        </p>
        <pre className="mt-2 mono text-[11px] bg-bg-base rounded-md p-2 overflow-x-auto">
          docker compose exec backend python -m ml.train
        </pre>
      </Card>
    );
  }

  const maxImp = items.length ? items[0].importance : 1;
  const winner = info?.winner === 'xgboost' ? 'XGBoost' : info?.winner === 'random_forest' ? 'Random Forest' : info?.winner || '—';
  const xgbF1 = info?.models?.xgboost?.test_metrics?.f1;
  const rfF1 = info?.models?.random_forest?.test_metrics?.f1;
  const auc = info?.models?.[info?.winner]?.test_metrics?.auc_roc;

  return (
    <Card
      accent="brand"
      title="Modelo predictivo"
      hint={info?.version}
      action={
        canRefresh && (
          <button
            type="button"
            onClick={handleRefresh}
            disabled={refreshing}
            className="mono text-[11px] uppercase tracking-widest2 px-2 py-1 rounded-md bg-ink-high text-white hover:bg-brand-deep disabled:opacity-40 transition-colors"
          >
            {refreshing ? 'refrescando...' : '↻ predecir activas'}
          </button>
        )
      }
    >
      {error && (
        <p className="text-state-stopped text-sm mb-3">{error}</p>
      )}
      {refreshMsg && (
        <p className="mono text-[11px] text-ink-mid mb-3">{refreshMsg}</p>
      )}

      <div className="grid grid-cols-3 gap-3 mb-4">
        <Stat label="Algoritmo" value={winner} />
        <Stat
          label="F1 (test)"
          value={(info?.models?.[info?.winner]?.test_metrics?.f1 ?? 0).toFixed(3)}
          tone={info?.models?.[info?.winner]?.test_metrics?.f1 >= 0.4 ? 'running' : 'maintenance'}
        />
        <Stat
          label="AUC-ROC"
          value={(auc ?? 0).toFixed(3)}
          tone={auc >= 0.7 ? 'running' : auc >= 0.55 ? 'maintenance' : 'stopped'}
        />
      </div>

      <p className="label-eyebrow mb-2">Top 8 features que más pesan</p>
      <ul className="space-y-1.5">
        {items.map((it) => {
          const w = (it.importance / Math.max(maxImp, 1e-6)) * 100;
          return (
            <li key={it.feature} className="flex items-center gap-2">
              <span className="text-[11px] text-ink-mid flex-1 truncate">
                {pretty(it.feature)}
              </span>
              <div className="h-1.5 w-24 rounded-full bg-bg-softline overflow-hidden">
                <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(2, w)}%` }} />
              </div>
              <span className="mono text-[10px] tabular-nums text-ink-low w-10 text-right">
                {(it.importance * 100).toFixed(1)}
              </span>
            </li>
          );
        })}
      </ul>

      {xgbF1 != null && rfF1 != null && (
        <p className="mono text-[10px] text-ink-low mt-3 leading-relaxed">
          Comparativa F1: XGBoost {xgbF1.toFixed(3)} · Random Forest {rfF1.toFixed(3)}
        </p>
      )}
    </Card>
  );
}

function Stat({ label, value, tone }) {
  const color =
    tone === 'running' ? 'text-state-running'
    : tone === 'stopped' ? 'text-state-stopped'
    : tone === 'maintenance' ? 'text-state-maintenance'
    : 'text-ink-high';
  return (
    <div className="rounded-md bg-bg-base p-2">
      <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">{label}</p>
      <p className={`mono text-base tabular-nums font-medium mt-0.5 ${color}`}>{value}</p>
    </div>
  );
}
