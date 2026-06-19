/**
 * Navbar — top bar navy (color de marca Smurfit Kappa) sobre tema claro.
 *
 * Identidad a la izquierda + reloj y datos del usuario a la derecha.
 */
import { useAuth } from '../../context/AuthContext.jsx';
import LiveClock from '../common/LiveClock.jsx';
import StatusDot from '../common/StatusDot.jsx';

const ROLE_LABELS = {
  operario: 'Operator',
  supervisor: 'Supervisor',
  admin: 'Admin',
};

export default function Navbar() {
  const { user, signOut } = useAuth();

  return (
    <header className="sticky top-0 z-30 navy-header text-ink-inverse">
      <div className="px-5 py-2.5 flex items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="relative h-9 w-9 rounded-md bg-accent grid place-items-center shadow-md">
            <span className="font-semibold text-white tracking-wider">SS</span>
          </div>
          <div className="leading-tight">
            <h1 className="text-[15px] font-medium text-white tracking-wide">
              SmartSack <span className="text-accent">·</span>{' '}
              <span className="text-white/70 font-light">Bags Division</span>
            </h1>
            <div className="mono text-[10px] tracking-widest2 uppercase text-white/50 flex items-center gap-1.5">
              <StatusDot tone="online" size="sm" />
              Sistema operativo
            </div>
          </div>
        </div>

        {/* Right cluster */}
        <div className="flex items-center gap-5">
          <ClockInverse />

          {user && (
            <>
              <div className="hidden sm:flex flex-col items-end leading-tight">
                <span className="text-sm text-white font-medium">
                  {user.full_name?.split('—')[0]?.trim() || user.username}
                </span>
                <span className="mono text-[10px] uppercase tracking-widest2 text-accent">
                  {ROLE_LABELS[user.role] || user.role}
                </span>
              </div>

              <button
                type="button"
                onClick={signOut}
                className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-xs uppercase tracking-widest2 text-white/80 ring-1 ring-inset ring-white/15 hover:text-white hover:ring-white/40 hover:bg-white/5 transition-colors"
              >
                <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 fill-none stroke-current stroke-2">
                  <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Salir
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

// LiveClock vive en componente común con colores claros; en navy lo
// renderizamos con tono blanco custom.
function ClockInverse() {
  return (
    <div className="hidden sm:block">
      <div className="text-white">
        <LiveClock />
      </div>
    </div>
  );
}
