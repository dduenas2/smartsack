/**
 * Button — variantes corporativas en tema claro.
 *
 *   primary  → azul SK sólido
 *   success  → verde sólido
 *   warning  → naranja sólido
 *   danger   → rojo sólido
 *   neutral  → blanco con borde
 *   ghost    → transparente con borde
 */
const VARIANTS = {
  primary:
    'bg-accent text-white hover:bg-accent-soft shadow-sm focus:ring-accent/40',
  success:
    'bg-state-running text-white hover:bg-green-700 shadow-sm focus:ring-green-500/40',
  warning:
    'bg-state-maintenance text-white hover:bg-orange-700 shadow-sm focus:ring-orange-500/40',
  danger:
    'bg-state-stopped text-white hover:bg-red-700 shadow-sm focus:ring-red-500/40',
  neutral:
    'bg-white text-ink-mid hover:bg-bg-base ring-1 ring-inset ring-bg-line shadow-sm',
  ghost:
    'bg-transparent text-ink-mid hover:bg-bg-base ring-1 ring-inset ring-bg-line',
};

export default function Button({
  variant = 'primary',
  type = 'button',
  className = '',
  disabled = false,
  icon = null,
  children,
  ...props
}) {
  const cls = VARIANTS[variant] || VARIANTS.primary;
  return (
    <button
      type={type}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-md px-3.5 py-2 text-sm font-medium tracking-wide transition-all duration-150 focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${cls} ${className}`}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </button>
  );
}
