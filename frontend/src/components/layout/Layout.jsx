/**
 * Layout — esqueleto principal de las páginas autenticadas.
 *
 * Estructura: Navbar arriba + Sidebar a la izquierda + contenido a la derecha.
 * El contenido va sobre un fondo con grid sutil para reforzar el aspecto
 * "operations console".
 */
import { Outlet } from 'react-router-dom';
import Navbar from './Navbar.jsx';
import Sidebar from './Sidebar.jsx';

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col bg-bg-base text-ink-high">
      <Navbar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto bg-grid">
          <div className="p-6 max-w-[1600px] mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
