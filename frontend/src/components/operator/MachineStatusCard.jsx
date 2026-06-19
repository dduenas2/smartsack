/**
 * MachineStatusCard — banner del operario (tema claro).
 *
 * Cuando el estado de la máquina cambia (detectado por `flashEvent`), la
 * tarjeta dispara una animación `flash-{state}` para que el operario sepa
 * de inmediato que su acción se aplicó.
 */
import Badge from '../common/Badge.jsx';
import StatusDot from '../common/StatusDot.jsx';

const FLASH_BY_EVENT = {
  start: 'animate-flash-emerald',
  resume: 'animate-flash-emerald',
  stop: 'animate-flash-rose',
  incident: 'animate-flash-rose',
  pause: 'animate-flash-amber',
  format_change: 'animate-flash-amber',
  end: 'animate-flash-slate',
  maintenance: 'animate-flash-amber',
};

export default function MachineStatusCard({ machine, flashEvent }) {
  if (!machine) {
    return (
      <div className="panel p-6 text-ink-mid text-sm">Cargando información...</div>
    );
  }
  const flashClass = flashEvent ? FLASH_BY_EVENT[flashEvent] || 'animate-flash-brand' : '';

  return (
    <section
      key={`${machine.id}-${machine.status}-${flashEvent || ''}`}
      className={`panel relative overflow-hidden p-6 ${flashClass}`}
    >
      <div className="absolute inset-0 bg-grid opacity-50 pointer-events-none" aria-hidden />

      <div className="relative flex flex-wrap items-center justify-between gap-6">
        <div className="flex items-center gap-5">
          <div className="px-4 py-2 rounded-md bg-brand-primary text-white">
            <span className="mono text-2xl font-medium tracking-widest2">
              {machine.code}
            </span>
          </div>
          <div className="leading-tight">
            <p className="label-eyebrow">Estación asignada</p>
            <h1 className="text-3xl font-light text-ink-high tracking-wide mt-1">
              {machine.name}
            </h1>
            <p className="text-sm text-ink-mid mt-1">
              <span className="capitalize">{machine.type}</span>
              {machine.location && (
                <>
                  <span className="mx-2 text-ink-mute">·</span>
                  {machine.location}
                </>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <StatusDot tone={machine.status} size="lg" />
          <Badge tone={machine.status} />
        </div>
      </div>
    </section>
  );
}
