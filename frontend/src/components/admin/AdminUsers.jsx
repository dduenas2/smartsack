/**
 * AdminUsers — tab de gestión de usuarios.
 *
 * Lista paginada con filtros (rol, estado, búsqueda), botón "Nuevo usuario"
 * con modal de creación, edición inline (rol, máquina), reset de contraseña
 * y desactivación con confirmación.
 *
 * El backend valida machine_id ↔ rol y reglas anti-lockout; aquí mostramos el
 * mensaje de error que devuelva la API sin re-implementar la lógica.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { listMachines } from '../../api/machines.js';
import {
  assignMachine,
  createUser,
  deactivateUser,
  listUsers,
  resetUserPassword,
  updateUser,
} from '../../api/users.js';
import Badge from '../common/Badge.jsx';
import Button from '../common/Button.jsx';
import Card from '../common/Card.jsx';
import Modal from '../common/Modal.jsx';
import Spinner from '../common/Spinner.jsx';
import Field from './Field.jsx';

const ROLE_LABEL = { admin: 'Admin', supervisor: 'Supervisor', operario: 'Operario' };

export default function AdminUsers({ currentUserId }) {
  const [users, setUsers] = useState([]);
  const [total, setTotal] = useState(0);
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [filterRole, setFilterRole] = useState('');
  const [filterActive, setFilterActive] = useState('');
  const [search, setSearch] = useState('');

  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState(null); // user object
  const [resetting, setResetting] = useState(null); // user object

  const machinesById = useMemo(() => {
    const out = {};
    for (const m of machines) out[m.id] = m;
    return out;
  }, [machines]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { limit: 100 };
      if (filterRole) params.role = filterRole;
      if (filterActive !== '') params.is_active = filterActive === 'true';
      if (search.trim()) params.search = search.trim();
      const [u, m] = await Promise.all([listUsers(params), listMachines()]);
      setUsers(u.items);
      setTotal(u.total);
      setMachines(m);
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudieron cargar los usuarios.');
    } finally {
      setLoading(false);
    }
  }, [filterRole, filterActive, search]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleDeactivate(user) {
    if (!window.confirm(`¿Desactivar a ${user.username}?`)) return;
    try {
      await deactivateUser(user.id);
      await refresh();
    } catch (err) {
      window.alert(err?.response?.data?.detail || 'No se pudo desactivar el usuario.');
    }
  }

  async function handleReactivate(user) {
    try {
      await updateUser(user.id, { is_active: true });
      await refresh();
    } catch (err) {
      window.alert(err?.response?.data?.detail || 'No se pudo reactivar el usuario.');
    }
  }

  return (
    <Card
      title="Usuarios"
      hint={`${total} usuario${total === 1 ? '' : 's'} en el sistema`}
      action={
        <Button variant="primary" onClick={() => setCreateOpen(true)}>
          + Nuevo usuario
        </Button>
      }
      accent="brand"
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        <Field
          id="search"
          label="Buscar"
          placeholder="username o nombre"
          value={search}
          onChange={setSearch}
        />
        <Field
          id="filter-role"
          label="Rol"
          type="select"
          value={filterRole}
          onChange={setFilterRole}
        >
          <option value="">Todos</option>
          <option value="admin">Admin</option>
          <option value="supervisor">Supervisor</option>
          <option value="operario">Operario</option>
        </Field>
        <Field
          id="filter-active"
          label="Estado"
          type="select"
          value={filterActive}
          onChange={setFilterActive}
        >
          <option value="">Todos</option>
          <option value="true">Activos</option>
          <option value="false">Inactivos</option>
        </Field>
      </div>

      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner size="lg" label="Cargando usuarios..." />
        </div>
      ) : error ? (
        <p className="text-sm text-state-stopped">{error}</p>
      ) : users.length === 0 ? (
        <p className="text-sm text-ink-mid py-6 text-center">
          No hay usuarios que coincidan con los filtros.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-ink-low text-[11px] uppercase tracking-widest2 border-b border-bg-softline">
                <th className="py-2 px-3">Usuario</th>
                <th className="py-2 px-3">Nombre</th>
                <th className="py-2 px-3">Rol</th>
                <th className="py-2 px-3">Máquina</th>
                <th className="py-2 px-3">Estado</th>
                <th className="py-2 px-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.id}
                  className="border-b border-bg-softline last:border-b-0 hover:bg-bg-base/40"
                >
                  <td className="py-2.5 px-3 mono text-ink-high">{u.username}</td>
                  <td className="py-2.5 px-3 text-ink-mid">{u.full_name || '—'}</td>
                  <td className="py-2.5 px-3">
                    <Badge tone={u.role === 'admin' ? 'urgent' : u.role === 'supervisor' ? 'accent' : 'neutral'}>
                      {ROLE_LABEL[u.role] || u.role}
                    </Badge>
                  </td>
                  <td className="py-2.5 px-3 mono text-ink-mid">
                    {u.machine_id ? machinesById[u.machine_id]?.code || `#${u.machine_id}` : '—'}
                  </td>
                  <td className="py-2.5 px-3">
                    <Badge tone={u.is_active ? 'running' : 'stopped'}>
                      {u.is_active ? 'Activo' : 'Inactivo'}
                    </Badge>
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="flex items-center justify-end gap-1.5">
                      <Button
                        variant="neutral"
                        className="!py-1 !px-2 !text-xs"
                        onClick={() => setEditing(u)}
                      >
                        Editar
                      </Button>
                      <Button
                        variant="neutral"
                        className="!py-1 !px-2 !text-xs"
                        onClick={() => setResetting(u)}
                      >
                        Reset pwd
                      </Button>
                      {u.is_active ? (
                        <Button
                          variant="danger"
                          className="!py-1 !px-2 !text-xs"
                          disabled={u.id === currentUserId}
                          onClick={() => handleDeactivate(u)}
                        >
                          Desactivar
                        </Button>
                      ) : (
                        <Button
                          variant="success"
                          className="!py-1 !px-2 !text-xs"
                          onClick={() => handleReactivate(u)}
                        >
                          Reactivar
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {createOpen && (
        <CreateUserModal
          machines={machines}
          onClose={() => setCreateOpen(false)}
          onCreated={async () => {
            setCreateOpen(false);
            await refresh();
          }}
        />
      )}
      {editing && (
        <EditUserModal
          user={editing}
          machines={machines}
          currentUserId={currentUserId}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await refresh();
          }}
        />
      )}
      {resetting && (
        <ResetPasswordModal
          user={resetting}
          onClose={() => setResetting(null)}
          onDone={() => setResetting(null)}
        />
      )}
    </Card>
  );
}

// =============================================================================
// Modal: crear usuario
// =============================================================================
function CreateUserModal({ machines, onClose, onCreated }) {
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState('operario');
  const [machineId, setMachineId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createUser({
        username: username.trim(),
        password,
        full_name: fullName.trim() || null,
        role,
        machine_id: role === 'operario' && machineId ? Number(machineId) : null,
      });
      await onCreated();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo crear el usuario.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Nuevo usuario"
      hint="Crea operarios, supervisores o administradores"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field
          id="cu-username"
          label="Username"
          required
          minLength={3}
          maxLength={64}
          value={username}
          onChange={setUsername}
          placeholder="op_imp-01_4"
        />
        <Field
          id="cu-fullname"
          label="Nombre completo (opcional)"
          maxLength={128}
          value={fullName}
          onChange={setFullName}
        />
        <Field
          id="cu-password"
          label="Contraseña"
          type="password"
          required
          minLength={8}
          value={password}
          onChange={setPassword}
        />
        <Field id="cu-role" label="Rol" type="select" value={role} onChange={setRole}>
          <option value="operario">Operario</option>
          <option value="supervisor">Supervisor</option>
          <option value="admin">Admin</option>
        </Field>
        {role === 'operario' && (
          <Field
            id="cu-machine"
            label="Máquina asignada"
            type="select"
            value={machineId}
            onChange={setMachineId}
          >
            <option value="">— Sin asignar —</option>
            {machines.map((m) => (
              <option key={m.id} value={m.id}>
                {m.code} · {m.name}
              </option>
            ))}
          </Field>
        )}
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

// =============================================================================
// Modal: editar usuario (rol, nombre, máquina)
// =============================================================================
function EditUserModal({ user, machines, currentUserId, onClose, onSaved }) {
  const [fullName, setFullName] = useState(user.full_name || '');
  const [role, setRole] = useState(user.role);
  const [machineId, setMachineId] = useState(user.machine_id || '');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const isSelf = user.id === currentUserId;

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      // PATCH datos generales (no incluyo machine_id si no aplica para evitar conflictos).
      const patch = { full_name: fullName.trim() || null };
      if (!isSelf) patch.role = role;
      await updateUser(user.id, patch);

      // Asignación de máquina sólo si es operario.
      if (!isSelf && role === 'operario') {
        await assignMachine(user.id, machineId ? Number(machineId) : null);
      }
      await onSaved();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo guardar el cambio.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Editar — ${user.username}`}
      hint={isSelf ? 'No puedes cambiar tu propio rol.' : null}
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field
          id="eu-fullname"
          label="Nombre completo"
          maxLength={128}
          value={fullName}
          onChange={setFullName}
        />
        <Field
          id="eu-role"
          label="Rol"
          type="select"
          value={role}
          onChange={setRole}
          disabled={isSelf}
        >
          <option value="operario">Operario</option>
          <option value="supervisor">Supervisor</option>
          <option value="admin">Admin</option>
        </Field>
        {role === 'operario' && (
          <Field
            id="eu-machine"
            label="Máquina asignada"
            type="select"
            value={machineId}
            onChange={setMachineId}
            disabled={isSelf}
          >
            <option value="">— Sin asignar —</option>
            {machines.map((m) => (
              <option key={m.id} value={m.id}>
                {m.code} · {m.name}
              </option>
            ))}
          </Field>
        )}
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

// =============================================================================
// Modal: reset password
// =============================================================================
function ResetPasswordModal({ user, onClose, onDone }) {
  const [pwd, setPwd] = useState('');
  const [pwd2, setPwd2] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (pwd !== pwd2) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await resetUserPassword(user.id, pwd);
      onDone();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo cambiar la contraseña.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open onClose={onClose} title={`Reset — ${user.username}`} size="sm">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Field
          id="rp-1"
          label="Nueva contraseña"
          type="password"
          minLength={8}
          required
          value={pwd}
          onChange={setPwd}
        />
        <Field
          id="rp-2"
          label="Repetir contraseña"
          type="password"
          minLength={8}
          required
          value={pwd2}
          onChange={setPwd2}
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
          <Button type="submit" variant="warning" disabled={submitting}>
            {submitting ? 'Cambiando...' : 'Cambiar contraseña'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
