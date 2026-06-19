/**
 * Sidebar — navegación lateral clara con iconos SVG inline.
 *
 * Cada ítem se filtra por rol; la ruta activa se marca con fondo azul SK
 * tenue + barra lateral azul + texto navy.
 */
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.jsx';

const Icon = {
  Operator: (
    <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.6]">
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <path d="M7 6V4h10v2M9 19v2M15 19v2M7 11h10M7 15h6" strokeLinecap="round" />
    </svg>
  ),
  Twin: (
    <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.6]">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  ),
  Dashboard: (
    <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.6]">
      <path d="M3 13a9 9 0 1118 0M12 13l4-4" strokeLinecap="round" />
      <circle cx="12" cy="13" r="1.5" fill="currentColor" />
    </svg>
  ),
  Chat: (
    <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.6]">
      <path d="M21 12a8 8 0 11-3.2-6.4L21 4l-1 4.2A8 8 0 0121 12z" strokeLinejoin="round" />
      <path d="M8 11h8M8 14h5" strokeLinecap="round" />
    </svg>
  ),
  Etl: (
    <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.6]">
      <path d="M12 3v12M7 10l5 5 5-5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" />
    </svg>
  ),
  Admin: (
    <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.6]">
      <path d="M12 2l8 4v6c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-4z" strokeLinejoin="round" />
      <path d="M9 12l2.2 2.2L15.5 10" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
};

const ITEMS = [
  { to: '/operator',   label: 'Mi máquina',  hint: 'Operator HUD',     roles: ['operario'],                       icon: Icon.Operator },
  { to: '/supervisor', label: 'Digital Twin',hint: 'Live plant view',   roles: ['supervisor', 'admin'],            icon: Icon.Twin },
  { to: '/dashboard',  label: 'KPIs / OEE',  hint: 'Analytics',         roles: ['operario', 'supervisor', 'admin'], icon: Icon.Dashboard },
  { to: '/etl',        label: 'ETL · SAP',   hint: 'CSV ingest',        roles: ['supervisor', 'admin'],            icon: Icon.Etl },
  { to: '/chat',       label: 'Asistente IA',hint: 'Claude SQL agent',  roles: ['operario', 'supervisor', 'admin'], icon: Icon.Chat },
  { to: '/admin',      label: 'Administración',hint: 'Users · System',   roles: ['admin'],                          icon: Icon.Admin },
];

export default function Sidebar() {
  const { user } = useAuth();
  if (!user) return null;
  const items = ITEMS.filter((it) => it.roles.includes(user.role));

  return (
    <aside className="hidden md:flex flex-col w-60 shrink-0 bg-white border-r border-bg-line">
      <div className="px-4 pt-4 pb-3">
        <p className="label-eyebrow">Navegación</p>
      </div>

      <nav className="px-3 space-y-1">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-md px-3 py-2 transition-colors ${
                isActive
                  ? 'bg-sky-50 text-ink-high ring-1 ring-inset ring-accent/30'
                  : 'text-ink-mid hover:text-ink-high hover:bg-bg-base'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-accent" aria-hidden />
                )}
                <span className={isActive ? 'text-accent' : 'text-ink-low group-hover:text-ink-mid'}>
                  {item.icon}
                </span>
                <span className="leading-tight">
                  <span className="block text-sm font-medium tracking-wide">{item.label}</span>
                  <span className="mono block text-[10px] uppercase tracking-widest2 text-ink-low">
                    {item.hint}
                  </span>
                </span>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <footer className="mt-auto px-4 py-3 border-t border-bg-softline">
        <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">
          v0.1 · build dev
        </p>
      </footer>
    </aside>
  );
}
