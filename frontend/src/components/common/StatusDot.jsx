/**
 * StatusDot — punto pulsante con halo, codificado por estado.
 *
 * Animación `beacon` (escala + opacidad) encima del punto base para que se
 * note bien sobre fondos claros sin necesitar glow muy fuerte.
 */
const STYLES = {
  running:     { dot: 'bg-state-running',     halo: 'bg-state-running/30' },
  stopped:     { dot: 'bg-state-stopped',     halo: 'bg-state-stopped/30' },
  maintenance: { dot: 'bg-state-maintenance', halo: 'bg-state-maintenance/30' },
  idle:        { dot: 'bg-state-idle',        halo: 'bg-state-idle/25' },
  online:      { dot: 'bg-state-running',     halo: 'bg-state-running/30' },
  connecting:  { dot: 'bg-state-maintenance', halo: 'bg-state-maintenance/30' },
  offline:     { dot: 'bg-state-stopped',     halo: 'bg-state-stopped/30' },
  accent:      { dot: 'bg-accent',            halo: 'bg-accent/30' },
};

const SIZES = {
  sm: { dot: 'h-2 w-2',     halo: 'h-3 w-3' },
  md: { dot: 'h-2.5 w-2.5', halo: 'h-4 w-4' },
  lg: { dot: 'h-3 w-3',     halo: 'h-5 w-5' },
};

export default function StatusDot({ tone = 'idle', size = 'md', pulse = true }) {
  const { dot, halo } = STYLES[tone] || STYLES.idle;
  const sz = SIZES[size] || SIZES.md;

  return (
    <span className="relative inline-flex" aria-hidden>
      {pulse && (
        <span
          className={`absolute inline-flex rounded-full ${halo} ${sz.halo} animate-beacon`}
          style={{ left: '-3px', top: '-3px' }}
        />
      )}
      <span className={`relative inline-block rounded-full ${dot} ${sz.dot}`} />
    </span>
  );
}
