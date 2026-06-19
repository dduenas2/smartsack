/**
 * OperatorView — vista del operario centrada en operaciones (no órdenes).
 *
 * Cada máquina trabaja "operaciones" (etapas de la ruta IMP→TUB→FON→EMP).
 * Cuando una operación está READY, el operario hace clic para tomarla;
 * mientras está IN_PROGRESS reporta producción y scrap, y al terminar la
 * cierra (lo que promueve automáticamente la siguiente máquina de la línea).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import { getMachine } from '../api/machines.js';
import {
  listOperations,
  startOperation,
  completeOperation,
} from '../api/operations.js';
import useWebSocket from '../hooks/useWebSocket.js';
import MachineStatusCard from '../components/operator/MachineStatusCard.jsx';
import CurrentOperationCard from '../components/operator/CurrentOperationCard.jsx';
import MachineActionButtons from '../components/operator/MachineActionButtons.jsx';
import OperationQueue from '../components/operator/OperationQueue.jsx';
import RecentEventsLog from '../components/operator/RecentEventsLog.jsx';
import Spinner from '../components/common/Spinner.jsx';

const FLASH_MS = 2800;

export default function OperatorView() {
  const { user } = useAuth();
  const [machine, setMachine] = useState(null);
  const [operations, setOperations] = useState([]); // ready + in_progress
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyOpId, setBusyOpId] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  const [flashEvent, setFlashEvent] = useState(null);
  const flashTimerRef = useRef(null);

  const loadAll = useCallback(async () => {
    if (!user?.machine_id) return;
    try {
      const [m, ops] = await Promise.all([
        getMachine(user.machine_id),
        listOperations({
          machine_id: user.machine_id,
          status: ['ready', 'in_progress'],
          limit: 20,
        }),
      ]);
      setMachine(m);
      setOperations(ops);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Error al cargar los datos.');
    } finally {
      setLoading(false);
    }
  }, [user?.machine_id]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => () => {
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
  }, []);

  // Suscripción al WS de planta: refrescamos cuando otro operario completa
  // su operación y la siguiente queda READY en mi máquina, o cuando la
  // operación que estoy procesando recibe un cambio externo.
  const handleWsMessage = useCallback(
    (msg) => {
      if (!user?.machine_id) return;
      const affectsMyMachine = (op) => op?.machine_id === user.machine_id;
      if (msg.type === 'operation_promoted' && affectsMyMachine(msg.operation)) {
        loadAll();
        return;
      }
      if (msg.type === 'operation_update' && affectsMyMachine(msg.operation)) {
        loadAll();
        return;
      }
      if (msg.type === 'machine_update' && msg.machine?.id === user.machine_id) {
        loadAll();
      }
    },
    [user?.machine_id, loadAll]
  );

  useWebSocket('/plant', handleWsMessage, { enabled: !!user?.machine_id });

  function triggerFlash(eventType) {
    setFlashEvent(eventType);
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current);
    flashTimerRef.current = setTimeout(() => setFlashEvent(null), FLASH_MS);
  }

  async function handleStartOperation(op) {
    if (!op || busyOpId) return;
    setBusyOpId(op.id);
    try {
      await startOperation(op.id);
      triggerFlash('start');
      setRefreshKey((k) => k + 1);
      await loadAll();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo iniciar la operación.');
    } finally {
      setBusyOpId(null);
    }
  }

  async function handleProductionReported() {
    triggerFlash('production_update');
    setRefreshKey((k) => k + 1);
    await loadAll();
  }

  async function handleCompleteOperation(op) {
    if (!op) return;
    setBusyOpId(op.id);
    try {
      await completeOperation(op.id);
      triggerFlash('end');
      setRefreshKey((k) => k + 1);
      await loadAll();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo cerrar la operación.');
    } finally {
      setBusyOpId(null);
    }
  }

  if (!user?.machine_id) {
    return (
      <div className="panel p-6 text-state-maintenance text-sm">
        Tu usuario no está asignado a ninguna máquina. Pídele al administrador
        que te asigne una.
      </div>
    );
  }

  if (loading && !machine) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner size="lg" label="Cargando estación..." />
      </div>
    );
  }

  if (error) {
    return <div className="panel p-4 text-state-stopped text-sm">{error}</div>;
  }

  const currentOperation = operations.find((o) => o.status === 'in_progress') || null;

  return (
    <div className="space-y-6 animate-fade-in-up">
      <MachineStatusCard machine={machine} flashEvent={flashEvent} />

      <MachineActionButtons
        machineId={user.machine_id}
        machineStatus={machine?.status}
        currentOperation={currentOperation}
        onRegistered={(ev) => {
          triggerFlash(ev.event_type);
          setRefreshKey((k) => k + 1);
          loadAll();
        }}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <CurrentOperationCard
            operation={currentOperation}
            machineType={machine?.type}
            onProduced={handleProductionReported}
            onComplete={() => handleCompleteOperation(currentOperation)}
            busy={busyOpId === currentOperation?.id}
          />
        </div>
        <div>
          <OperationQueue
            operations={operations}
            onStart={handleStartOperation}
            busyId={busyOpId}
          />
        </div>
      </div>

      <RecentEventsLog machineId={user.machine_id} refreshKey={refreshKey} />
    </div>
  );
}
