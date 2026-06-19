/**
 * AdminSystem — tab de salud del sistema, settings runtime y modelo ML.
 *
 * Compone tres tarjetas:
 *  1) Health — estado de Postgres/Redis/Anthropic/ML model + WS conectados.
 *  2) Settings — toggles runtime (chatbot, predictions, mantenimiento).
 *  3) ML Model — versión cargada, métricas y botón "Recargar modelo".
 *
 * El refresh es manual (botón) para no forzar polling: en el panel admin no
 * necesitamos vista en tiempo real; el supervisor ya tiene el Digital Twin.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  getMlStatus,
  getSystemHealth,
  listSettings,
  reloadMlModel,
  updateSetting,
} from '../../api/admin.js';
import Badge from '../common/Badge.jsx';
import Button from '../common/Button.jsx';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';
import StatusDot from '../common/StatusDot.jsx';

const STATUS_TONE = { ok: 'running', degraded: 'maintenance', down: 'stopped' };

function fmtIso(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('es-CO', {
    dateStyle: 'short',
    timeStyle: 'short',
  });
}

export default function AdminSystem() {
  const [health, setHealth] = useState(null);
  const [settings, setSettings] = useState([]);
  const [mlStatus, setMlStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [reloading, setReloading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, s, ml] = await Promise.all([
        getSystemHealth(),
        listSettings(),
        getMlStatus(),
      ]);
      setHealth(h);
      setSettings(s);
      setMlStatus(ml);
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo cargar el panel del sistema.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleToggle(setting) {
    try {
      const updated = await updateSetting(setting.key, !setting.value);
      setSettings((current) =>
        current.map((s) => (s.key === setting.key ? updated : s)),
      );
    } catch (err) {
      window.alert(err?.response?.data?.detail || 'No se pudo cambiar el setting.');
    }
  }

  async function handleReload() {
    setReloading(true);
    try {
      await reloadMlModel();
      await refresh();
    } catch (err) {
      window.alert(err?.response?.data?.detail || 'No se pudo recargar el modelo.');
    } finally {
      setReloading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner size="lg" label="Consultando estado del sistema..." />
      </div>
    );
  }

  if (error) {
    return <p className="text-sm text-state-stopped">{error}</p>;
  }

  return (
    <div className="space-y-6">
      <Card
        title="Estado del sistema"
        hint={`Última verificación: ${fmtIso(health.checked_at)}`}
        action={
          <Button variant="neutral" onClick={refresh}>
            Refrescar
          </Button>
        }
        accent={
          health.overall === 'ok'
            ? 'emerald'
            : health.overall === 'degraded'
              ? 'amber'
              : 'rose'
        }
      >
        <div className="flex items-center gap-3 mb-4">
          <StatusDot tone={STATUS_TONE[health.overall]} size="md" />
          <span className="mono text-[11px] uppercase tracking-widest2 text-ink-mid">
            Overall:
          </span>
          <Badge tone={STATUS_TONE[health.overall]}>{health.overall}</Badge>
          <span className="ml-auto mono text-[11px] text-ink-low">
            WS conectados: {health.websocket_connections}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {health.checks.map((c) => (
            <div
              key={c.name}
              className="flex items-start gap-3 p-3 rounded-md ring-1 ring-bg-softline bg-bg-base/40"
            >
              <StatusDot tone={STATUS_TONE[c.status]} size="md" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <span className="mono text-sm text-ink-high">{c.name}</span>
                  <Badge tone={STATUS_TONE[c.status]}>{c.status}</Badge>
                </div>
                <p className="text-xs text-ink-mid mt-0.5 truncate">
                  {c.detail || '—'}
                </p>
                {c.latency_ms != null && (
                  <p className="mono text-[10px] text-ink-low mt-0.5">
                    {c.latency_ms.toFixed(2)} ms
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>

        <dl className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-4 text-xs">
          <div>
            <dt className="mono uppercase tracking-widest2 text-ink-low">
              Última carga ETL
            </dt>
            <dd className="text-ink-mid">{fmtIso(health.last_etl_load_at)}</dd>
          </div>
          <div>
            <dt className="mono uppercase tracking-widest2 text-ink-low">
              Última predicción ML
            </dt>
            <dd className="text-ink-mid">{fmtIso(health.last_ml_prediction_at)}</dd>
          </div>
        </dl>
      </Card>

      <Card title="Configuración runtime" hint="Toggles que NO requieren redeploy" accent="brand">
        <ul className="divide-y divide-bg-softline">
          {settings.map((s) => (
            <li key={s.key} className="flex items-center justify-between gap-4 py-3">
              <div className="min-w-0">
                <p className="mono text-sm text-ink-high">{s.key}</p>
                <p className="text-xs text-ink-mid mt-0.5">{s.description}</p>
                <p className="mono text-[10px] text-ink-low mt-0.5">
                  Última edición: {fmtIso(s.updated_at)}
                </p>
              </div>
              <Toggle value={!!s.value} onChange={() => handleToggle(s)} />
            </li>
          ))}
        </ul>
      </Card>

      <Card
        title="Modelo de Machine Learning"
        hint={
          mlStatus.model_loaded
            ? `Cargado: v${mlStatus.model_version || '?'}`
            : 'Modelo no cargado'
        }
        action={
          <Button variant="neutral" onClick={handleReload} disabled={reloading}>
            {reloading ? 'Recargando...' : 'Recargar modelo'}
          </Button>
        }
        accent={mlStatus.model_loaded ? 'emerald' : 'amber'}
      >
        <dl className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <Stat label="Versión" value={mlStatus.model_version || '—'} mono />
          <Stat
            label="Entrenado"
            value={fmtIso(mlStatus.trained_at)}
          />
          <Stat
            label="Features"
            value={mlStatus.feature_count ?? '—'}
            mono
          />
          <Stat
            label="Predicciones totales"
            value={mlStatus.predictions_count_total}
            mono
          />
        </dl>
        {mlStatus.metrics && (
          <details className="mt-4">
            <summary className="cursor-pointer mono text-[11px] uppercase tracking-widest2 text-ink-low">
              Métricas detalladas
            </summary>
            <pre className="mt-2 text-[11px] mono bg-bg-base p-3 rounded-md overflow-auto max-h-64 ring-1 ring-bg-softline">
              {JSON.stringify(mlStatus.metrics, null, 2)}
            </pre>
          </details>
        )}
      </Card>
    </div>
  );
}

function Stat({ label, value, mono = false }) {
  return (
    <div>
      <dt className="mono uppercase tracking-widest2 text-[10px] text-ink-low">
        {label}
      </dt>
      <dd className={`mt-0.5 text-ink-high ${mono ? 'mono' : ''}`}>{value}</dd>
    </div>
  );
}

function Toggle({ value, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={value}
      onClick={onChange}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-accent/40 ${
        value ? 'bg-state-running' : 'bg-bg-line'
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
          value ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}
