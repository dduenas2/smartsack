/**
 * Field — input con label y error consistente con la línea visual del Login.
 *
 * Soporta `type="text" | "password" | "number" | "select"`. Cuando es select
 * el contenido se pasa como `children` (las opciones). Para otros tipos se
 * usa un <input>.
 */
export default function Field({
  id,
  label,
  type = 'text',
  value,
  onChange,
  placeholder,
  required = false,
  error = null,
  children,
  className = '',
  ...rest
}) {
  const isSelect = type === 'select';
  return (
    <div className={className}>
      <label
        htmlFor={id}
        className="mono block text-[10px] uppercase tracking-widest2 text-ink-low mb-1.5"
      >
        {label}
        {required && <span className="text-state-stopped"> *</span>}
      </label>
      {isSelect ? (
        <select
          id={id}
          value={value ?? ''}
          onChange={(e) => onChange?.(e.target.value)}
          required={required}
          className="block w-full rounded-md bg-white border border-bg-line px-3 py-2 text-sm text-ink-high focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 transition-colors"
          {...rest}
        >
          {children}
        </select>
      ) : (
        <input
          id={id}
          type={type}
          value={value ?? ''}
          onChange={(e) =>
            onChange?.(type === 'number' ? e.target.valueAsNumber : e.target.value)
          }
          placeholder={placeholder}
          required={required}
          className="block w-full rounded-md bg-white border border-bg-line px-3 py-2 text-sm text-ink-high placeholder-ink-mute focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 transition-colors"
          {...rest}
        />
      )}
      {error && <p className="mt-1 text-xs text-state-stopped">{error}</p>}
    </div>
  );
}
