/**
 * AdminOrders — tab de gestión manual de órdenes.
 *
 * Para cargas masivas se usa /etl. Esta vista cubre el caso "el supervisor
 * necesita meter una orden a mano fuera del CSV", o el admin quiere borrar
 * una orden creada por error.
 *
 * Las órdenes ingestadas vía POST automáticamente reciben las 4 operaciones
 * IMP→TUB→FON→EMP en la línea correspondiente cuando el ETL las inserta;
 * para órdenes creadas a mano se mantiene el modelo cabecera (las
 * operaciones se generarían cuando el operario las inicie).
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { listMachines } from '../../api/machines.js';
import {
  createOrder,
  deleteOrder,
  listOrders,
} from '../../api/orders.js';
import Badge from '../common/Badge.jsx';
import Button from '../common/Button.jsx';
import Card from '../common/Card.jsx';
import Modal from '../common/Modal.jsx';
import Spinner from '../common/Spinner.jsx';
import Field from './Field.jsx';

const PRIORITIES = ['low', 'normal', 'high', 'urgent'];

function fmt(n) {
  return new Intl.NumberFormat('es-CO').format(n ?? 0);
}

function isoFromLocal(local) {
  // <input type="datetime-local"> entrega "YYYY-MM-DDTHH:MM" sin tz.
  // Lo enviamos al backend con la zona local del navegador.
  if (!local) return null;
  return new Date(local).toISOString();
}

function localInputFromDate(d) {
  // Genera el formato "YYYY-MM-DDTHH:MM" en hora LOCAL para precargar el
  // input. `Date.toISOString()` devuelve UTC y descalibra el datepicker.
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

export default function AdminOrders() {
  const [orders, setOrders] = useState([]);
  const [total, setTotal] = useState(0);
  const [machines, setMachines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [createOpen, setCreateOpen] = useState(false);

  const machinesById = useMemo(() => {
    const out = {};
    for (const m of machines) out[m.id] = m;
    return out;
  }, [machines]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // sort=created_at_desc → la orden recién creada aparece arriba.
      const [o, m] = await Promise.all([
        listOrders({ limit: 50, sort: 'created_at_desc' }),
        listMachines(),
      ]);
      setOrders(o.items);
      setTotal(o.total);
      setMachines(m);
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudieron cargar las órdenes.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleDelete(order) {
    if (
      !window.confirm(
        `¿Eliminar la orden ${order.order_number}? Las operaciones y eventos asociados se eliminarán en cascada.`,
      )
    )
      return;
    try {
      await deleteOrder(order.id);
      await refresh();
    } catch (err) {
      window.alert(err?.response?.data?.detail || 'No se pudo eliminar la orden.');
    }
  }

  return (
    <Card
      title="Órdenes de producción"
      hint={`${total} en BD · creación manual fuera del flujo ETL`}
      action={
        <Button variant="primary" onClick={() => setCreateOpen(true)}>
          + Nueva orden
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
      ) : orders.length === 0 ? (
        <p className="text-sm text-ink-mid py-6 text-center">No hay órdenes.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-ink-low text-[11px] uppercase tracking-widest2 border-b border-bg-softline">
                <th className="py-2 px-3">Orden</th>
                <th className="py-2 px-3">Producto</th>
                <th className="py-2 px-3">Cantidad</th>
                <th className="py-2 px-3">Máquina</th>
                <th className="py-2 px-3">Estado</th>
                <th className="py-2 px-3">Prioridad</th>
                <th className="py-2 px-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr
                  key={o.id}
                  className="border-b border-bg-softline last:border-b-0 hover:bg-bg-base/40"
                >
                  <td className="py-2.5 px-3 mono text-ink-high">{o.order_number}</td>
                  <td className="py-2.5 px-3 text-ink-mid">{o.product_type}</td>
                  <td className="py-2.5 px-3 mono tabular-nums">
                    {fmt(o.quantity_produced)} / {fmt(o.quantity_ordered)}
                  </td>
                  <td className="py-2.5 px-3 mono text-ink-mid">
                    {o.machine_id ? machinesById[o.machine_id]?.code || `#${o.machine_id}` : '—'}
                  </td>
                  <td className="py-2.5 px-3">
                    <Badge tone={o.status} />
                  </td>
                  <td className="py-2.5 px-3">
                    <Badge tone={o.priority}>{o.priority}</Badge>
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="flex justify-end">
                      <Button
                        variant="danger"
                        className="!py-1 !px-2 !text-xs"
                        onClick={() => handleDelete(o)}
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
        <CreateOrderModal
          machines={machines}
          onClose={() => setCreateOpen(false)}
          onCreated={async () => {
            setCreateOpen(false);
            await refresh();
          }}
        />
      )}
    </Card>
  );
}

function CreateOrderModal({ machines, onClose, onCreated }) {
  // Defaults: arrancar dentro de 1h y cerrar 8h después (turno típico).
  const startDefault = new Date(Date.now() + 60 * 60 * 1000);
  const endDefault = new Date(startDefault.getTime() + 8 * 60 * 60 * 1000);
  const [orderNumber, setOrderNumber] = useState('');
  const [productType, setProductType] = useState('Saco cemento 50kg');
  const [productDescription, setProductDescription] = useState('');
  const [quantity, setQuantity] = useState(10000);
  const [machineId, setMachineId] = useState('');
  const [priority, setPriority] = useState('normal');
  const [plannedStart, setPlannedStart] = useState(localInputFromDate(startDefault));
  const [plannedEnd, setPlannedEnd] = useState(localInputFromDate(endDefault));
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await createOrder({
        order_number: orderNumber.trim(),
        product_type: productType.trim(),
        product_description: productDescription.trim() || null,
        quantity_ordered: Number(quantity),
        machine_id: machineId ? Number(machineId) : null,
        priority,
        planned_start: isoFromLocal(plannedStart),
        planned_end: isoFromLocal(plannedEnd),
      });
      await onCreated();
    } catch (err) {
      setError(err?.response?.data?.detail || 'No se pudo crear la orden.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal open onClose={onClose} title="Nueva orden de producción" size="lg">
      <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field
          id="co-num"
          label="Número de orden"
          required
          maxLength={32}
          value={orderNumber}
          onChange={setOrderNumber}
          placeholder="OP-2026-100001"
        />
        <Field
          id="co-prod"
          label="Producto"
          required
          maxLength={64}
          value={productType}
          onChange={setProductType}
        />
        <Field
          id="co-desc"
          label="Descripción"
          maxLength={255}
          value={productDescription}
          onChange={setProductDescription}
          className="md:col-span-2"
        />
        <Field
          id="co-qty"
          label="Cantidad"
          type="number"
          required
          min={1}
          value={quantity}
          onChange={setQuantity}
        />
        <Field
          id="co-mach"
          label="Máquina inicial"
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
        <Field
          id="co-pri"
          label="Prioridad"
          type="select"
          value={priority}
          onChange={setPriority}
        >
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </Field>
        <Field
          id="co-ps"
          label="Inicio planeado"
          type="datetime-local"
          required
          value={plannedStart}
          onChange={setPlannedStart}
        />
        <Field
          id="co-pe"
          label="Fin planeado"
          type="datetime-local"
          required
          value={plannedEnd}
          onChange={setPlannedEnd}
        />
        {error && (
          <div className="md:col-span-2 rounded-md bg-red-50 ring-1 ring-state-stopped/30 px-3 py-2 text-sm text-state-stopped">
            {error}
          </div>
        )}
        <div className="md:col-span-2 flex justify-end gap-2 pt-2">
          <Button type="button" variant="neutral" onClick={onClose} disabled={submitting}>
            Cancelar
          </Button>
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? 'Creando...' : 'Crear orden'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
