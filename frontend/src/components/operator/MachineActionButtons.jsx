/**
 * MachineActionButtons — eventos auxiliares que cambian el estado de la
 * máquina sin avanzar la operación.
 *
 * Estos eventos se registran en la bitácora (production_events) y disparan
 * la animación correspondiente en el Digital Twin del supervisor:
 *
 *   running → pause/stop  → stopped     · animación amber/rose
 *   stopped → resume      → running     · animación emerald
 *   running → maintenance → maintenance · animación amber
 *   running → format_change/incident: NO cambia estado pero se anima.
 *
 * IMPORTANTE: estas acciones NO modifican `operation.status`. Para avanzar
 * la operación se usa POST /operations/{id}/start|report|complete desde
 * `OperationQueue` y `CurrentOperationCard`.
 */
import { useState } from 'react';
import { createEvent } from '../../api/events.js';
import Button from '../common/Button.jsx';
import Card from '../common/Card.jsx';

const ICON = {
  pause: (
    <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current">
      <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
    </svg>
  ),
  resume: (
    <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current">
      <path d="M5 5h2v14H5zM10 5l11 7-11 7z" />
    </svg>
  ),
  format: (
    <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-[1.6]">
      <path d="M4 7h12M4 12h16M4 17h8" strokeLinecap="round" />
      <path d="M18 4l3 3-3 3M20 14l-3 3 3 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  incident: (
    <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-[1.6]">
      <path d="M12 3l10 18H2L12 3z" strokeLinejoin="round" />
      <path d="M12 10v5M12 18h.01" strokeLinecap="round" />
    </svg>
  ),
  stop: (
    <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current">
      <rect x="6" y="6" width="12" height="12" rx="1" />
    </svg>
  ),
  maintenance: (
    <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current stroke-[1.6]">
      <path
        d="M14.7 6.3a4 4 0 0 0-5.4 5.4l-6 6 2 2 6-6a4 4 0 0 0 5.4-5.4l-2.5 2.5-1.5-1.5 2.5-2.5z"
        strokeLinejoin="round"
      />
    </svg>
  ),
};

// Acciones según el estado actual de la máquina. Reflejan el mapping
// _EVENT_TO_MACHINE_STATUS del backend.
const ALLOWED_BY_STATUS = {
  idle:        [],  // sin operación tomada no hay acciones que registrar
  running:     ['pause', 'format_change', 'incident', 'stop', 'maintenance'],
  stopped:     ['resume', 'incident'],
  maintenance: ['resume'],
};

const ACTIONS = [
  { type: 'pause',         label: 'Pausar',              variant: 'warning', icon: ICON.pause },
  { type: 'resume',        label: 'Reanudar',            variant: 'success', icon: ICON.resume },
  { type: 'format_change', label: 'Cambio de formato',   variant: 'warning', icon: ICON.format,
    promptText: 'Describe brevemente el cambio de formato:' },
  { type: 'incident',      label: 'Reportar incidencia', variant: 'danger',  icon: ICON.incident,
    promptText: '¿Qué incidencia ocurrió?', requireDescription: true },
  { type: 'stop',          label: 'Detener',             variant: 'danger',  icon: ICON.stop,
    promptText: 'Motivo de la parada:' },
  { type: 'maintenance',   label: 'Mantenimiento',       variant: 'warning', icon: ICON.maintenance,
    promptText: 'Tipo de mantenimiento (preventivo, correctivo, etc.):' },
];

export default function MachineActionButtons({
  machineId,
  machineStatus,
  currentOperation,
  onRegistered,
}) {
  const [busy, setBusy] = useState(null);
  const [feedback, setFeedback] = useState(null);

  const allowed = new Set(ALLOWED_BY_STATUS[machineStatus] || []);

  async function handleClick(action) {
    if (!machineId) return;
    let description = null;
    if (action.promptText) {
      description = window.prompt(action.promptText) ?? null;
      if (action.requireDescription && !description?.trim()) return;
    }
    setBusy(action.type);
    setFeedback(null);
    try {
      const payload = {
        machine_id: machineId,
        event_type: action.type,
        description: description || action.label,
      };
      // Si hay operación en curso, vincular el evento para trazabilidad.
      if (currentOperation?.id) {
        payload.operation_id = currentOperation.id;
        payload.order_id = currentOperation.order_id;
      }
      const created = await createEvent(payload);
      setFeedback({
        kind: 'success',
        text: `${action.label} registrado · #${created.id}`,
      });
      onRegistered?.(created);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setFeedback({ kind: 'error', text: detail || 'No se pudo registrar el evento.' });
    } finally {
      setBusy(null);
    }
  }

  const stateHint =
    machineStatus === 'running'
      ? 'Pulsa para pausar, reportar incidencia o cambio de formato'
    : machineStatus === 'stopped'
      ? 'Reanuda cuando esté listo o reporta una incidencia'
    : machineStatus === 'maintenance'
      ? 'Reanuda cuando termine el mantenimiento'
    : machineStatus === 'idle'
      ? 'Toma una operación de la cola para habilitar acciones'
    : 'Registro en bitácora · broadcast en vivo a supervisores';

  return (
    <Card title="Acciones de máquina" hint={stateHint}>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5">
        {ACTIONS.map((action) => {
          const isAllowed = allowed.has(action.type);
          return (
            <Button
              key={action.type}
              variant={action.variant}
              icon={action.icon}
              onClick={() => handleClick(action)}
              disabled={busy !== null || !isAllowed}
              className={`justify-start ${!isAllowed ? 'opacity-40' : ''}`}
              title={
                !isAllowed
                  ? `No disponible en estado "${machineStatus || 'desconocido'}"`
                  : undefined
              }
            >
              {busy === action.type ? '...' : action.label}
            </Button>
          );
        })}
      </div>

      {feedback && (
        <div
          className={`mt-4 flex items-start gap-2 rounded-md px-3 py-2 text-sm ring-1 ring-inset animate-fade-in-up ${
            feedback.kind === 'success'
              ? 'text-state-running bg-state-running/10 ring-state-running/30'
              : 'text-state-stopped bg-state-stopped/10 ring-state-stopped/30'
          }`}
        >
          <span className="mono text-xs uppercase tracking-widest2">
            {feedback.kind === 'success' ? 'OK' : 'ERR'}
          </span>
          <span>{feedback.text}</span>
        </div>
      )}
    </Card>
  );
}
