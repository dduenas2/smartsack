/**
 * PlantMap — grilla de MachineTile que conforma el "mapa" de la planta.
 *
 * Recibe `flashes`: Map<machineId, {eventType, key}> para que cada tile
 * pueda lanzar la animación correcta sólo cuando le toca.
 */
import MachineTile from './MachineTile.jsx';

export default function PlantMap({ machines, flashes }) {
  if (!machines || machines.length === 0) {
    return (
      <p className="text-ink-mid text-sm py-12 text-center">
        No hay máquinas registradas todavía.
      </p>
    );
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {machines.map((m) => {
        const f = flashes?.get(m.id);
        return (
          <MachineTile
            key={m.id}
            machine={m}
            flashEvent={f?.eventType}
            flashKey={f ? `${m.id}-${f.key}` : undefined}
          />
        );
      })}
    </div>
  );
}
