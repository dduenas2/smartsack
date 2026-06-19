/**
 * AdminAudit — bitácora de acciones administrativas (read-only).
 *
 * Lista paginada de entradas de admin_audit_log con filtros por:
 *  - entity_type (user/machine/order/setting/ml_model)
 *  - action      (create/update/delete/reset_password/reload_model/...)
 *  - days_back   (últimos N días)
 *
 * Cada fila muestra actor, acción, entidad y un detalle expandible con el
 * before/after JSON. La columna `metadata` (extra) sólo aparece si tiene
 * datos.
 */
import { useCallback, useEffect, useState } from 'react';
import { listAuditLog } from '../../api/admin.js';
import Badge from '../common/Badge.jsx';
import Button from '../common/Button.jsx';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';
import Field from './Field.jsx';

const ACTION_TONE = {
  create: 'running',
  update: 'accent',
  delete: 'stopped',
  deactivate: 'stopped',
  reset_password: 'maintenance',
  reload_model: 'accent',
  update_setting: 'accent',
  assign_machine: 'accent',
};

function fmtIso(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('es-CO', {
    dateStyle: 'short',
    timeStyle: 'medium',
  });
}

const PAGE_SIZE = 25;

export default function AdminAudit() {
  const [entries, setEntries] = useState([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [entityType, setEntityType] = useState('');
  const [action, setAction] = useState('');
  const [daysBack, setDaysBack] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { limit: PAGE_SIZE, offset };
      if (entityType) params.entity_type = entityType;
      if (action) params.action = action;
      if (daysBack !== '') params.days_back = Number(daysBack);
      const data = await listAuditLog(params);
      setEntries(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo cargar la bitácora.');
    } finally {
      setLoading(false);
    }
  }, [offset, entityType, action, daysBack]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const lastPage = Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);
  const currentPage = Math.floor(offset / PAGE_SIZE);

  return (
    <Card
      title="Bitácora de auditoría"
      hint={`${total} entradas · append-only`}
      accent="brand"
    >
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-4">
        <Field
          id="aa-entity"
          label="Entidad"
          type="select"
          value={entityType}
          onChange={(v) => {
            setOffset(0);
            setEntityType(v);
          }}
        >
          <option value="">Todas</option>
          <option value="user">user</option>
          <option value="machine">machine</option>
          <option value="order">order</option>
          <option value="setting">setting</option>
          <option value="ml_model">ml_model</option>
        </Field>
        <Field
          id="aa-action"
          label="Acción"
          type="select"
          value={action}
          onChange={(v) => {
            setOffset(0);
            setAction(v);
          }}
        >
          <option value="">Todas</option>
          <option value="create">create</option>
          <option value="update">update</option>
          <option value="delete">delete</option>
          <option value="deactivate">deactivate</option>
          <option value="reset_password">reset_password</option>
          <option value="assign_machine">assign_machine</option>
          <option value="update_setting">update_setting</option>
          <option value="reload_model">reload_model</option>
        </Field>
        <Field
          id="aa-days"
          label="Últimos N días"
          type="number"
          min={0}
          max={365}
          value={daysBack}
          onChange={(v) => {
            setOffset(0);
            setDaysBack(v);
          }}
        />
        <div className="flex items-end">
          <Button variant="neutral" onClick={refresh} className="w-full">
            Refrescar
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-10">
          <Spinner size="lg" label="Cargando bitácora..." />
        </div>
      ) : error ? (
        <p className="text-sm text-state-stopped">{error}</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-ink-mid py-6 text-center">
          No hay entradas para los filtros seleccionados.
        </p>
      ) : (
        <ul className="divide-y divide-bg-softline">
          {entries.map((e) => (
            <AuditRow key={e.id} entry={e} />
          ))}
        </ul>
      )}

      <div className="flex items-center justify-between pt-4 mt-2 border-t border-bg-softline">
        <p className="mono text-[11px] text-ink-low">
          Página {currentPage + 1} de {lastPage + 1}
        </p>
        <div className="flex gap-2">
          <Button
            variant="neutral"
            disabled={currentPage === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            Anterior
          </Button>
          <Button
            variant="neutral"
            disabled={currentPage >= lastPage}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Siguiente
          </Button>
        </div>
      </div>
    </Card>
  );
}

function AuditRow({ entry }) {
  const [open, setOpen] = useState(false);
  const tone = ACTION_TONE[entry.action] || 'neutral';
  const hasDetails = entry.before || entry.after || entry.extra;
  return (
    <li className="py-3">
      <div className="flex items-center gap-3 flex-wrap">
        <Badge tone={tone}>{entry.action}</Badge>
        <span className="mono text-sm text-ink-high">
          {entry.entity_type}
          {entry.entity_id != null && (
            <span className="text-ink-low">#{entry.entity_id}</span>
          )}
        </span>
        <span className="text-xs text-ink-mid">por</span>
        <span className="mono text-xs text-ink-mid">
          {entry.actor_username || '(borrado)'}
        </span>
        <span className="ml-auto mono text-[11px] text-ink-low">
          {fmtIso(entry.created_at)}
        </span>
        {hasDetails && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="mono text-[11px] uppercase tracking-widest2 text-accent"
          >
            {open ? '▾ ocultar' : '▸ detalle'}
          </button>
        )}
      </div>
      {open && (
        <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
          {entry.before && (
            <pre className="mono bg-bg-base p-2 rounded-md ring-1 ring-bg-softline overflow-auto max-h-48">
              <span className="block text-ink-low mb-1 uppercase tracking-widest2 text-[10px]">
                before
              </span>
              {JSON.stringify(entry.before, null, 2)}
            </pre>
          )}
          {entry.after && (
            <pre className="mono bg-bg-base p-2 rounded-md ring-1 ring-bg-softline overflow-auto max-h-48">
              <span className="block text-ink-low mb-1 uppercase tracking-widest2 text-[10px]">
                after
              </span>
              {JSON.stringify(entry.after, null, 2)}
            </pre>
          )}
          {entry.extra && (
            <pre className="md:col-span-2 mono bg-bg-base p-2 rounded-md ring-1 ring-bg-softline overflow-auto max-h-48">
              <span className="block text-ink-low mb-1 uppercase tracking-widest2 text-[10px]">
                extra
              </span>
              {JSON.stringify(entry.extra, null, 2)}
            </pre>
          )}
        </div>
      )}
    </li>
  );
}
