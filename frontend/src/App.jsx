/**
 * App.jsx — Componente raíz de la SPA SmartSack.
 *
 * Define el árbol de rutas:
 *   /login                   → pública
 *   /operator                → solo rol 'operario'
 *   /supervisor              → solo 'supervisor' o 'admin'
 *   /dashboard, /chat        → cualquier usuario autenticado
 *   /                        → redirige por rol
 *
 * Las rutas autenticadas viven dentro de <Layout /> para compartir Navbar y
 * Sidebar. La validación inicial del JWT se hace en <AuthProvider />.
 */
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, defaultRouteFor, useAuth } from './context/AuthContext.jsx';
import Layout from './components/layout/Layout.jsx';
import ProtectedRoute from './components/layout/ProtectedRoute.jsx';
import Login from './pages/Login.jsx';
import OperatorView from './pages/OperatorView.jsx';
import OrderTraceView from './pages/OrderTraceView.jsx';
import SupervisorView from './pages/SupervisorView.jsx';
import Dashboard from './pages/Dashboard.jsx';
import ETL from './pages/ETL.jsx';
import Chat from './pages/Chat.jsx';
import Admin from './pages/Admin.jsx';
import Spinner from './components/common/Spinner.jsx';

function HomeRedirect() {
  const { user, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return <Navigate to={defaultRouteFor(user.role)} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Pública */}
          <Route path="/login" element={<Login />} />

          {/* Autenticadas, dentro del Layout */}
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route
              path="/operator"
              element={
                <ProtectedRoute allowedRoles={['operario']}>
                  <OperatorView />
                </ProtectedRoute>
              }
            />
            <Route
              path="/supervisor"
              element={
                <ProtectedRoute allowedRoles={['supervisor', 'admin']}>
                  <SupervisorView />
                </ProtectedRoute>
              }
            />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route
              path="/etl"
              element={
                <ProtectedRoute allowedRoles={['supervisor', 'admin']}>
                  <ETL />
                </ProtectedRoute>
              }
            />
            <Route path="/chat" element={<Chat />} />
            <Route path="/orders/:orderId" element={<OrderTraceView />} />
            <Route
              path="/admin"
              element={
                <ProtectedRoute allowedRoles={['admin']}>
                  <Admin />
                </ProtectedRoute>
              }
            />
          </Route>

          <Route path="/" element={<HomeRedirect />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
