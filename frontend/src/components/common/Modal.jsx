/**
 * Modal — diálogo modal centrado con backdrop y trampa de foco básica.
 *
 * No depende de portales ni de librerías externas. Mantiene la UX consistente
 * con el resto de la SPA (panel blanco, sombra, esquinas redondeadas).
 *
 * Uso:
 *   <Modal open={isOpen} onClose={() => setOpen(false)} title="Editar usuario">
 *     <form>...</form>
 *   </Modal>
 */
import { useEffect } from 'react';

export default function Modal({
  open,
  onClose,
  title,
  hint,
  children,
  size = 'md',
  footer,
}) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  if (!open) return null;

  const widthClass =
    size === 'sm'
      ? 'max-w-sm'
      : size === 'lg'
        ? 'max-w-2xl'
        : size === 'xl'
          ? 'max-w-4xl'
          : 'max-w-md';

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center p-4 bg-ink-high/30 backdrop-blur-sm animate-fade-in"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose?.();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        className={`panel w-full ${widthClass} animate-fade-in-up`}
      >
        <header className="flex items-start justify-between gap-3 px-5 pt-4 pb-3 border-b border-bg-softline">
          <div>
            <h2 id="modal-title" className="text-base font-medium text-ink-high">
              {title}
            </h2>
            {hint && <p className="mt-0.5 text-xs text-ink-low">{hint}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
            className="text-ink-low hover:text-ink-high transition-colors"
          >
            ✕
          </button>
        </header>
        <div className="p-5">{children}</div>
        {footer && (
          <footer className="px-5 py-3 border-t border-bg-softline flex justify-end gap-2">
            {footer}
          </footer>
        )}
      </div>
    </div>
  );
}
