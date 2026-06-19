/**
 * Admin — panel administrativo (solo rol 'admin').
 *
 * Cinco tabs (Users, Machines, Orders, System, Audit) que cada uno trae su
 * propio fetch + estado local. El panel comparte solo el header con tabs y
 * el usuario autenticado vía AuthContext.
 *
 * Decisión de UX: no usamos rutas anidadas para evitar que el browser
 * historique cada tab. La tab activa vive sólo en estado de React.
 */
import { useState } from 'react';
import { useAuth } from '../context/AuthContext.jsx';
import AdminAudit from '../components/admin/AdminAudit.jsx';
import AdminMachines from '../components/admin/AdminMachines.jsx';
import AdminOrders from '../components/admin/AdminOrders.jsx';
import AdminSystem from '../components/admin/AdminSystem.jsx';
import AdminUsers from '../components/admin/AdminUsers.jsx';

const TABS = [
  { id: 'users', label: 'Usuarios', component: AdminUsers },
  { id: 'machines', label: 'Máquinas', component: AdminMachines },
  { id: 'orders', label: 'Órdenes', component: AdminOrders },
  { id: 'system', label: 'Sistema', component: AdminSystem },
  { id: 'audit', label: 'Auditoría', component: AdminAudit },
];

export default function Admin() {
  const { user } = useAuth();
  const [active, setActive] = useState('users');
  const ActiveComponent = TABS.find((t) => t.id === active)?.component || AdminUsers;

  return (
    <div className="space-y-5 animate-fade-in-up">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="mono text-[10px] uppercase tracking-widest2 text-ink-low">
            Panel administrativo
          </p>
          <h1 className="text-xl font-medium text-ink-high">SmartSack — Admin</h1>
        </div>
        <p className="mono text-[11px] text-ink-mid">
          conectado como <span className="text-ink-high">{user?.username}</span>
        </p>
      </header>

      <nav className="flex flex-wrap gap-1 border-b border-bg-softline">
        {TABS.map((tab) => {
          const isActive = tab.id === active;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActive(tab.id)}
              className={`mono text-xs uppercase tracking-widest2 px-4 py-2.5 border-b-2 transition-colors ${
                isActive
                  ? 'border-accent text-ink-high'
                  : 'border-transparent text-ink-mid hover:text-ink-high'
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      <ActiveComponent currentUserId={user?.id} />
    </div>
  );
}
