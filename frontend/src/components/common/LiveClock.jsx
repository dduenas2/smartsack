/**
 * LiveClock — reloj en vivo (ticking cada segundo).
 *
 * Hereda colores del contenedor padre (`text-current`) para que pueda
 * usarse tanto en el navbar navy (texto blanco) como en superficies claras.
 */
import { useEffect, useState } from 'react';

function format(d) {
  const time = d.toLocaleTimeString('es-CO', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
  const date = d.toLocaleDateString('es-CO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
  return { time, date };
}

export default function LiveClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const { time, date } = format(now);

  return (
    <div className="flex flex-col items-end leading-tight">
      <span className="mono text-sm font-medium tabular-nums tracking-wide">
        {time}
      </span>
      <span className="mono text-[10px] uppercase tracking-widest2 opacity-60">
        {date}
      </span>
    </div>
  );
}
