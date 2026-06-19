/**
 * OEEBreakdown — desglose A × P × Q del OEE de planta.
 *
 * Muestra las 3 barras del producto OEE (Disponibilidad, Rendimiento,
 * Calidad) con sus porcentajes. Una bandera explícita ayuda al usuario a
 * interpretar el indicador (clase mundial > 85%, aceptable 60–85%, etc.).
 */
import Card from '../common/Card.jsx';

function pct(v) {
  return `${(Number(v || 0) * 100).toFixed(1)}%`;
}

function classify(oee) {
  if (oee >= 0.85) return { label: 'Clase mundial', tone: 'text-state-running' };
  if (oee >= 0.6) return { label: 'Aceptable', tone: 'text-accent' };
  if (oee >= 0.4) return { label: 'Bajo', tone: 'text-state-maintenance' };
  return { label: 'Crítico', tone: 'text-state-stopped' };
}

function Bar({ label, value, color }) {
  const w = Math.max(2, Math.min(100, value * 100));
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="label-eyebrow">{label}</span>
        <span className="mono text-sm tabular-nums text-ink-high">{pct(value)}</span>
      </div>
      <div className="h-2 rounded-full bg-bg-softline overflow-hidden">
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{ width: `${w}%`, background: color }}
        />
      </div>
    </div>
  );
}

export default function OEEBreakdown({ overview }) {
  if (!overview) return null;
  const { availability, performance, quality, plant_oee } = overview;
  const cls = classify(plant_oee);

  return (
    <Card
      accent="brand"
      title="OEE — desglose A × P × Q"
      hint="Promedio simple sobre el día más reciente con registros"
      action={
        <span className={`mono text-xs uppercase tracking-widest2 ${cls.tone}`}>
          {cls.label}
        </span>
      }
    >
      <div className="space-y-4">
        <Bar label="Disponibilidad" value={availability} color="#16a34a" />
        <Bar label="Rendimiento" value={performance} color="#08B2FF" />
        <Bar label="Calidad" value={quality} color="#00205B" />

        <div className="flex items-baseline justify-between pt-3 border-t border-bg-softline">
          <span className="label-eyebrow">OEE consolidado</span>
          <span className="mono text-2xl font-medium text-ink-high tabular-nums">
            {pct(plant_oee)}
          </span>
        </div>
        <p className="mono text-[10px] text-ink-low leading-relaxed">
          OEE = Disponibilidad × Rendimiento × Calidad. La industria considera
          ≥ 85% como benchmark de clase mundial.
        </p>
      </div>
    </Card>
  );
}
