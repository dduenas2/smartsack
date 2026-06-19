/**
 * ProtectedRoute — wrapper de ruta que exige autenticación y, opcionalmente,
 * un rol concreto.
 *
 * - Si el usuario no está autenticado → redirige a /login.
 * - Si está autenticado pero su rol no está permitido → redirige a la ruta
 *   por defecto de su rol (evita pantalla de "acceso denegado" gratuita).
 * - Mientras se valida el token tras un refresh, muestra un Spinner.
 */
import { Navigate, useLocation } from 'react-router-dom';
import { defaultRouteFor, useAuth } from '../../context/AuthContext.jsx';
import Spinner from '../common/Spinner.jsx';

export default function ProtectedRoute({ allowedRoles, children }) {
  const { user, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" label="Verificando sesión..." />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={defaultRouteFor(user.role)} replace />;
  }

  return children;
}
