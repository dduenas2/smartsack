/**
 * Badge — etiqueta de estado en tonos suaves sobre fondo claro.
 */
const TONES = {
  running:     'text-green-700  bg-green-50    ring-green-600/30',
  stopped:     'text-red-700    bg-red-50      ring-red-600/30',
  maintenance: 'text-orange-700 bg-orange-50   ring-orange-600/30',
  idle:        'text-slate-700  bg-slate-100   ring-slate-400/40',
  pending:     'text-slate-700  bg-slate-100   ring-slate-300',
  ready:       'text-sky-700    bg-sky-50      ring-sky-600/30',
  in_progress: 'text-sky-700    bg-sky-50      ring-sky-600/30',
  completed:   'text-green-700  bg-green-50    ring-green-600/30',
  delayed:     'text-red-700    bg-red-50      ring-red-600/30',
  urgent:      'text-red-700    bg-red-50      ring-red-600/30',
  high:        'text-orange-700 bg-orange-50   ring-orange-600/30',
  normal:      'text-slate-700  bg-slate-100   ring-slate-300',
  low:         'text-slate-600  bg-slate-50    ring-slate-200',
  accent:      'text-accent-soft bg-sky-50     ring-accent/40',
  neutral:     'text-slate-700  bg-slate-100   ring-slate-300',
};

const LABELS = {
  running: 'En operación',
  stopped: 'Detenida',
  maintenance: 'Mantenimiento',
  idle: 'Disponible',
  pending: 'Pendiente',
  ready: 'Lista',
  in_progress: 'En curso',
  completed: 'Completada',
  delayed: 'Retrasada',
  urgent: 'Urgente',
  high: 'Alta',
  normal: 'Normal',
  low: 'Baja',
};

export default function Badge({ tone = 'neutral', children, mono = false }) {
  const cls = TONES[tone] || TONES.neutral;
  const label = children ?? LABELS[tone] ?? tone;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10.5px] tracking-widest2 uppercase font-medium ring-1 ring-inset ${cls} ${mono ? 'mono' : ''}`}
    >
      {label}
    </span>
  );
}
