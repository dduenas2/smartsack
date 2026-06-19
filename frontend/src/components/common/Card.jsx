/**
 * Card — superficie blanca con borde fino, sombra suave y header opcional.
 *
 * El prop `accent` aplica una línea vertical de marca al borde izquierdo:
 *   brand   → azul Smurfit Kappa  (info)
 *   emerald → verde               (running / OK)
 *   rose    → rojo                (alerta)
 *   amber   → naranja             (warning)
 *   slate   → gris                (neutral / idle)
 */
const ACCENT_LINES = {
  brand: 'before:bg-accent',
  emerald: 'before:bg-state-running',
  rose: 'before:bg-state-stopped',
  amber: 'before:bg-state-maintenance',
  slate: 'before:bg-state-idle',
  // Aliases retrocompatibles.
  cyan: 'before:bg-accent',
  sky: 'before:bg-accent',
};

export default function Card({
  children,
  className = '',
  title,
  hint,
  action,
  accent,
}) {
  const accentClass = accent
    ? `relative pl-5 before:content-[''] before:absolute before:left-0 before:top-3 before:bottom-3 before:w-0.5 before:rounded-full ${ACCENT_LINES[accent] || ACCENT_LINES.brand}`
    : '';

  return (
    <section className={`panel shadow-soft ${accentClass} ${className}`}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-3 px-4 pt-3 pb-2 border-b border-bg-softline">
          <div>
            {title && <h2 className="label-eyebrow">{title}</h2>}
            {hint && <p className="mt-0.5 text-xs text-ink-low">{hint}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}
