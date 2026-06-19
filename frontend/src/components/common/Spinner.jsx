/**
 * Spinner — anillo azul SK para estados de carga.
 */
export default function Spinner({ size = 'md', label }) {
  const sizes = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-10 w-10' };
  return (
    <div className="inline-flex items-center gap-2 text-ink-mid">
      <span
        className={`${sizes[size]} animate-spin rounded-full border-2 border-bg-line border-t-accent`}
        aria-hidden="true"
      />
      {label && <span className="text-sm tracking-wide">{label}</span>}
    </div>
  );
}
