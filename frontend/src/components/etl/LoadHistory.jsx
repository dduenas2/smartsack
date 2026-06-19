/**
 * LoadHistory — tabla del historial de cargas ETL.
 *
 * Filtro por tipo, paginado simple "ver más", y panel expandible con el
 * error_log de cada carga. La página le pasa `refreshKey` para forzar
 * refetch tras un upload exitoso.
 */
import { useEffect, useState } from 'react';
import Card from '../common/Card.jsx';
import Spinner from '../common/Spinner.jsx';
import { listLoads } from '../../api/etl.js';

const KIND_LABEL = {
  production_orders: 'Órdenes',
  confirmations: 'Confirmaciones',
  materials: 'Materiales',
  shipments: 'Despachos',
};

const STATUS_PILL = {
  success: 'bg-state-running/10 text-state-running',
  partial: 'bg-state-maintenance/10 text-state-maintenance',
  failed:  'bg-state-stopped/10 text-state-stopped',
  pending: 'bg-bg-softline text-ink-mid',
};

function fmtDateTime(iso) {
  const d = new Date(iso);
  return d.toLocaleString('es-CO', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function LoadHistory({ refreshKey }) {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listLoads({ kind: filter || undefined, limit: 30 })
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
        setTotal(res.total);
      })
      .catch((err) =>
        !cancelled && setError(err?.response?.data?.detail || 'Error al cargar')
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [filter, refreshKey]);

  return (
    <Card
      accent="brand"
      title="Historial de cargas"
      hint={`${total} cargas registradas`}
      action={
        <select
          className="mono text-[11px] uppercase tracking-widest2 px-2 py-1 rounded-md border border-bg-line bg-white text-ink-mid focus:border-accent focus:outline-none"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="">Todos los tipos</option>
          <option value="production_orders">Órdenes</option>
          <option value="confirmations">Confirmaciones</option>
          <option value="materials">Materiales</option>
          <option value="shipments">Despachos</option>
        </select>
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
          Aún no hay cargas registradas.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left mono text-[10px] uppercase tracking-widest2 text-ink-low border-b border-bg-softline">
                <th className="py-2 pr-3 font-medium">Fecha</th>
                <th className="py-2 pr-3 font-medium">Archivo</th>
                <th className="py-2 pr-3 font-medium">Tipo</th>
                <th className="py-2 pr-3 font-medium">Estado</th>
                <th className="py-2 pr-3 font-medium text-right">Filas</th>
                <th className="py-2 pr-3 font-medium text-right">Ins</th>
                <th className="py-2 pr-3 font-medium text-right">Upd</th>
                <th className="py-2 pr-3 font-medium text-right">Fail</th>
                <th className="py-2 pr-3 font-medium text-right">Dur</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <Row
                  key={it.id}
                  item={it}
                  expanded={expandedId === it.id}
                  setExpandedId={setExpandedId}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function Row({ item, expanded, setExpandedId }) {
  const hasErrors =
    item.error_log &&
    ((item.error_log.global || []).length + (item.error_log.rows || []).length) > 0;
  return (
    <>
      <tr
        className={`border-b border-bg-softline transition-colors ${
          hasErrors ? 'cursor-pointer hover:bg-bg-base' : ''
        }`}
        onClick={() => hasErrors && setExpandedId(expanded ? null : item.id)}
      >
        <td className="py-2 pr-3 mono text-[11px] text-ink-low tabular-nums whitespace-nowrap">
          {fmtDateTime(item.uploaded_at)}
        </td>
        <td className="py-2 pr-3 mono text-ink-high text-xs truncate max-w-[200px]">
          {item.filename}
        </td>
        <td className="py-2 pr-3 text-ink-mid text-xs">
          {KIND_LABEL[item.kind] || item.kind}
        </td>
        <td className="py-2 pr-3">
          <span
            className={`mono text-[10px] uppercase tracking-widest2 px-1.5 py-0.5 rounded ${
              STATUS_PILL[item.status]
            }`}
          >
            {item.status}
          </span>
        </td>
        <td className="py-2 pr-3 text-right mono tabular-nums text-ink-mid">{item.rows_total}</td>
        <td className="py-2 pr-3 text-right mono tabular-nums text-state-running">
          {item.rows_inserted}
        </td>
        <td className="py-2 pr-3 text-right mono tabular-nums text-accent">{item.rows_updated}</td>
        <td className="py-2 pr-3 text-right mono tabular-nums">
          {item.rows_failed > 0 ? (
            <span className="text-state-stopped">{item.rows_failed}</span>
          ) : (
            <span className="text-ink-low">0</span>
          )}
        </td>
        <td className="py-2 pr-3 text-right mono text-[10px] tabular-nums text-ink-low">
          {item.duration_ms} ms
        </td>
      </tr>
      {expanded && hasErrors && (
        <tr>
          <td colSpan={9} className="py-2 px-3 bg-bg-base">
            {(item.error_log.global || []).length > 0 && (
              <div className="mb-2">
                <p className="label-eyebrow mb-1">Errores globales</p>
                <ul className="list-disc pl-5 text-xs text-state-stopped">
                  {item.error_log.global.map((g, i) => (
                    <li key={i}>{g}</li>
                  ))}
                </ul>
              </div>
            )}
            {(item.error_log.rows || []).length > 0 && (
              <div>
                <p className="label-eyebrow mb-1">
                  Errores por fila ({item.error_log.rows.length})
                </p>
                <ul className="space-y-0.5 max-h-48 overflow-y-auto pr-1">
                  {item.error_log.rows.slice(0, 30).map((r, i) => (
                    <li key={i} className="mono text-[11px] tabular-nums text-ink-mid">
                      <span className="text-ink-low">fila {r.row}</span>
                      {r.order_number && (
                        <>
                          {' · '}
                          <span className="text-ink-high">{r.order_number}</span>
                        </>
                      )}
                      {' — '}
                      <span className="text-state-stopped">{r.error}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  );
}
