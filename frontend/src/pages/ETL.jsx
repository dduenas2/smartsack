/**
 * ETL — página de carga de archivos del ERP.
 *
 * Visible solo para roles supervisor/admin (filtrado en App + Sidebar).
 * Combina el dropzone de carga arriba y el historial paginado debajo.
 */
import { useState } from 'react';
import UploadDropzone from '../components/etl/UploadDropzone.jsx';
import LoadHistory from '../components/etl/LoadHistory.jsx';

export default function ETL() {
  const [refreshKey, setRefreshKey] = useState(0);

  return (
    <div className="space-y-6 animate-fade-in-up">
      <header>
        <p className="label-eyebrow">Integración ERP</p>
        <h1 className="text-3xl font-light text-ink-high tracking-wide mt-1">
          ETL <span className="text-accent">·</span>{' '}
          <span className="text-ink-mid">Carga desde SAP</span>
        </h1>
        <p className="mt-2 text-sm text-ink-mid max-w-2xl">
          Sube los archivos exportados del ERP (órdenes, confirmaciones, materiales,
          despachos). El sistema valida cada fila, descarta duplicados y registra
          el resultado completo en el historial.
        </p>
      </header>

      <UploadDropzone onUploaded={() => setRefreshKey((k) => k + 1)} />
      <LoadHistory refreshKey={refreshKey} />
    </div>
  );
}
