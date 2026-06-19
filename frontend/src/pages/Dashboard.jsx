/**
 * Dashboard — KPIs, OEE y alertas predictivas.
 *
 * Orquesta los 6 widgets contra /api/dashboard/*. La cabecera (overview) se
 * carga aquí y se reparte entre KpiOverview y OEEBreakdown para evitar dos
 * fetchs idénticos. El resto de widgets cargan sus datos por su cuenta — son
 * más pesados y se benefician del caché HTTP del navegador.
 */
import { useEffect, useState } from 'react';
import { getOverview } from '../api/dashboard.js';
import KpiOverview from '../components/dashboard/KpiOverview.jsx';
import OEEBreakdown from '../components/dashboard/OEEBreakdown.jsx';
import OEETrendChart from '../components/dashboard/OEETrendChart.jsx';
import ProductionByShiftChart from '../components/dashboard/ProductionByShiftChart.jsx';
import OrderFulfillmentChart from '../components/dashboard/OrderFulfillmentChart.jsx';
import MachineRanking from '../components/dashboard/MachineRanking.jsx';
import AlertsPanel from '../components/dashboard/AlertsPanel.jsx';
import ModelInsights from '../components/dashboard/ModelInsights.jsx';
import ScrapPareto from '../components/dashboard/ScrapPareto.jsx';
import WIPSnapshot from '../components/dashboard/WIPSnapshot.jsx';
import Spinner from '../components/common/Spinner.jsx';

export default function Dashboard() {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getOverview()
      .then((res) => !cancelled && setOverview(res))
      .catch((err) =>
        !cancelled &&
        setError(err?.response?.data?.detail || 'Error al cargar el dashboard')
      )
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6 animate-fade-in-up">
      <header>
        <p className="label-eyebrow">Analytics</p>
        <h1 className="text-3xl font-light text-ink-high tracking-wide mt-1">
          Dashboard <span className="text-accent">·</span>{' '}
          <span className="text-ink-mid">KPIs &amp; OEE</span>
        </h1>
      </header>

      {loading && !overview ? (
        <div className="flex items-center justify-center py-24">
          <Spinner size="lg" label="Cargando KPIs..." />
        </div>
      ) : error ? (
        <div className="panel p-4 text-state-stopped text-sm">{error}</div>
      ) : (
        <>
          <KpiOverview data={overview} />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <OEETrendChart />
            </div>
            <div>
              <OEEBreakdown overview={overview} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ProductionByShiftChart />
            <OrderFulfillmentChart />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ScrapPareto days={30} />
            <WIPSnapshot />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2">
              <MachineRanking />
            </div>
            <div className="space-y-4">
              <AlertsPanel />
              <ModelInsights />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
