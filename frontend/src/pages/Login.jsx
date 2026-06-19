/**
 * Login — página de acceso (tema claro Smurfit Kappa).
 *
 * Fondo claro con grid navy sutil + radial-glow azul. Tarjeta blanca
 * centrada con la marca arriba en navy. Si el usuario ya está autenticado,
 * redirige a la home de su rol.
 */
import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { defaultRouteFor, useAuth } from '../context/AuthContext.jsx';
import Button from '../components/common/Button.jsx';
import Spinner from '../components/common/Spinner.jsx';
import StatusDot from '../components/common/StatusDot.jsx';

export default function Login() {
  const { user, isLoading, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }
  if (user) return <Navigate to={defaultRouteFor(user.role)} replace />;

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const me = await signIn(username, password);
      const target = location.state?.from || defaultRouteFor(me.role);
      navigate(target, { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || 'No se pudo iniciar sesión. Verifica tus credenciales.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen relative grid place-items-center p-6 overflow-hidden bg-grid">
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(800px 400px at 50% 0%, rgba(8,178,255,0.08), transparent 60%), radial-gradient(700px 350px at 50% 100%, rgba(0,32,91,0.05), transparent 60%)',
        }}
        aria-hidden
      />

      <section className="panel relative w-full max-w-md p-7 animate-fade-in-up">
        <header className="text-center mb-7">
          <div className="mx-auto h-14 w-14 rounded-md bg-brand-primary grid place-items-center shadow-md">
            <span className="font-semibold text-white text-lg tracking-wider">SS</span>
          </div>
          <h1 className="mt-4 text-xl font-medium text-ink-high tracking-wide">
            SmartSack <span className="text-accent">·</span>{' '}
            <span className="text-ink-mid font-light">Bags Division</span>
          </h1>
          <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low mt-1">
            Authentication required
          </p>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field
            id="username"
            label="Usuario"
            placeholder="admin / supervisor1 / op_tub-01_1"
            value={username}
            onChange={setUsername}
            autoFocus
          />
          <Field
            id="password"
            label="Contraseña"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={setPassword}
          />

          {error && (
            <div className="flex items-start gap-2 rounded-md bg-red-50 ring-1 ring-state-stopped/30 px-3 py-2 text-sm text-state-stopped">
              <StatusDot tone="offline" size="sm" pulse={false} />
              <span>{error}</span>
            </div>
          )}

          <Button
            type="submit"
            variant="primary"
            disabled={submitting}
            className="w-full justify-center py-2.5 text-sm tracking-widest2 uppercase"
          >
            {submitting ? 'Verificando...' : 'Iniciar sesión'}
          </Button>
        </form>

        <footer className="mt-6 flex items-center justify-between text-[11px] text-ink-low">
          <span className="mono uppercase tracking-widest2">v0.1 · build dev</span>
          <span>
            Demo: <span className="mono text-ink-mid">admin / smartsack123</span>
          </span>
        </footer>
      </section>
    </main>
  );
}

function Field({ id, label, type = 'text', value, onChange, placeholder, autoFocus }) {
  return (
    <div>
      <label
        htmlFor={id}
        className="mono block text-[10px] uppercase tracking-widest2 text-ink-low mb-1.5"
      >
        {label}
      </label>
      <input
        id={id}
        type={type}
        autoFocus={autoFocus}
        required
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="block w-full rounded-md bg-white border border-bg-line px-3 py-2.5 text-sm text-ink-high placeholder-ink-mute focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 transition-colors"
      />
    </div>
  );
}
