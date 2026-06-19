/**
 * AdminMachines — tab de catálogo de máquinas.
 *
 * Permite al admin crear nuevas máquinas, editar nombre/ubicación/estado y
 * eliminar entradas obsoletas. El catálogo en producción suele ser estático
 * (8 máquinas), pero el panel queda listo para escalado o mantenimiento.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  createMachine,
  deleteMachine,
  listMachines,
  updateMachine,
} from '../../api/machines.js';
import Badge from '../common/Badge.jsx';
import Button from '../common/Button.jsx';
import Card from '../common/Card.jsx';
import Modal from '../common/Modal.jsx';
import Spinner from '../common/Spinner.jsx';
import Field from './Field.jsx';

// El enum del backend usa los valores en minúscula ("impresora"); enviar
// MAYÚSCULAS rebota con 422.
const MACHINE_TYPES = [
  ['tubuladora', 'Tubuladora'],
  ['impresora', 'Impresora'],
  ['fondadora', 'Fondadora'],
  ['empacadora', 'Empacadora'],
];

const MACHINE_STATUSES = ['running', 'stopped', 'maintenance', 'idle'];

export default function AdminMachines() {
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listMachines();
      setMachines(data);
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudieron cargar las máquinas.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleDelete(machine) {
    if (
      !window.confirm(
        `¿Eliminar la máquina ${machine.code}? Esta acción no se puede deshacer.`,
      )
    )
      return;
    try {
      await deleteMachine(machine.id);
      await refresh();
    } catch (err) {
      window.alert(err?.response?.data?.detail || 'No se pudo eliminar la máquina.');
    }
  }

  return (
    <Card
      title="Catálogo de máquinas"
      hint={`${machines.length} máquinas registradas`}
      action={
        <Button variant="primary" onClick={() => setCreateOpen(true)}>
          + Nueva máquina
        </Button>
      }
      accent="brand"
    >
      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner size="lg" label="Cargando..." />
        </div>
      ) : error ? (
        <p className="text-sm text-state-stopped">{error}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-ink-low text-[11px] uppercase tracking-widest2 border-b border-bg-softline">
                <th className="py-2 px-3">Código</th>
                <th className="py-2 px-3">Nombre</th>
                <th className="py-2 px-3">Tipo</th>
                <th className="py-2 px-3">Ubicación</th>
                <th className="py-2 px-3">Estado</th>
                <th className="py-2 px-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {machines.map((m) => (
                <tr
                  key={m.id}
                  className="border-b border-bg-softline last:border-b-0 hover:bg-bg-base/40"
                >
                  <td className="py-2.5 px-3 mono text-ink-high">{m.code}</td>
                  <td className="py-2.5 px-3 text-ink-mid">{m.name}</td>
                  <td className="py-2.5 px-3 text-ink-mid">{m.type}</td>
                  <td className="py-2.5 px-3 text-ink-mid">{m.location || '—'}</td>
                  <td className="py-2.5 px-3">
                    <Badge tone={m.status} />
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="flex justify-end gap-1.5">
                      <Button
                        variant="neutral"
                        className="!py-1 !px-2 !text-xs"
                        onClick={() => setEditing(m)}
                      >
                        Editar
                      </Button>
                      <Button
                        variant="danger"
                        className="!py-1 !px-2 !text-xs"
                        onClick={() => handleDelete(m)}
                      >
                        Eliminar
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {createOpen && (
        <CreateMachineModal
          onClose={() => setCreateOpen(false)}
          onCreated={async () => {
            setCreateOpen(false);
            await refresh();
          }}
        />
      )}
      {editing && (
        <EditMachineModal
          machine={editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await refresh();
          }}
        />
      )}
    </Card>
  );
}

function CreateMachineModal({ onClose, onCreated }) {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [type, setType] = useState('impresora');
  const [location, setLocation] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createMachine({
        code: code.trim(),
        name: name.trim(),
        type,
        location: location.trim() || null,
      });
      await onCreated();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo crear la máquina.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open onClose={onClose} title="Nueva máquina">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field
          id="cm-code"
          label="Código"
          required
          maxLength={32}
          value={code}
          onChange={setCode}
          placeholder="IMP-03"
        />
        <Field
          id="cm-name"
          label="Nombre"
          required
          maxLength={64}
          value={name}
          onChange={setName}
        />
        <Field id="cm-type" label="Tipo" type="select" value={type} onChange={setType}>
          {MACHINE_TYPES.map(([v, label]) => (
            <option key={v} value={v}>
              {label}
            </option>
          ))}
        </Field>
        <Field
          id="cm-loc"
          label="Ubicación (opcional)"
          maxLength={64}
          value={location}
          onChange={setLocation}
          placeholder="Línea A"
        />
        {error && (
          <div className="rounded-md bg-red-50 ring-1 ring-state-stopped/30 px-3 py-2 text-sm text-state-stopped">
            {error}
          </div>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="neutral" onClick={onClose} disabled={submitting}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Creando...' : 'Crear'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function EditMachineModal({ machine, onClose, onSaved }) {
  const [name, setName] = useState(machine.name);
  const [location, setLocation] = useState(machine.location || '');
  const [statusValue, setStatusValue] = useState(machine.status);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await updateMachine(machine.id, {
        name: name.trim(),
        location: location.trim() || null,
        status: statusValue,
      });
      await onSaved();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo actualizar.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={`Editar — ${machine.code}`}>
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field id="em-name" label="Nombre" required value={name} onChange={setName} />
        <Field
          id="em-loc"
          label="Ubicación"
          value={location}
          onChange={setLocation}
        />
        <Field
          id="em-status"
          label="Estado"
          type="select"
          value={statusValue}
          onChange={setStatusValue}
        >
          {MACHINE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Field>
        {error && (
          <div className="rounded-md bg-red-50 ring-1 ring-state-stopped/30 px-3 py-2 text-sm text-state-stopped">
            {error}
          </div>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="neutral" onClick={onClose} disabled={submitting}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Guardando...' : 'Guardar'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
