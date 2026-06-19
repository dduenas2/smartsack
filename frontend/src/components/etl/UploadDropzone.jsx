/**
 * UploadDropzone — drag & drop con selector de tipo y resumen del resultado.
 *
 * Tras subir el archivo se despliegan los contadores (insertadas, actualizadas,
 * saltadas, fallidas) y, si hay errores por fila, las primeras 10 con su
 * mensaje. Tras éxito, dispara `onUploaded` para que la lista se refresque.
 */
import { useRef, useState } from 'react';
import Card from '../common/Card.jsx';
import { uploadCsv, sampleCsvUrl } from '../../api/etl.js';

const KINDS = [
  { value: 'production_orders', label: 'Órdenes de producción' },
  { value: 'confirmations',     label: 'Confirmaciones' },
  { value: 'materials',         label: 'Movimientos de material' },
  { value: 'shipments',         label: 'Despachos' },
];

const STATUS_TONE = {
  success: 'border-state-running/40 bg-state-running/5 text-state-running',
  partial: 'border-state-maintenance/40 bg-state-maintenance/5 text-state-maintenance',
  failed:  'border-state-stopped/40 bg-state-stopped/5 text-state-stopped',
  pending: 'border-bg-line bg-bg-base text-ink-mid',
};

export default function UploadDropzone({ onUploaded }) {
  const [kind, setKind] = useState('production_orders');
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  function handleFiles(files) {
    const f = files?.[0];
    if (!f) return;
    if (!f.name.toLowerCase().endsWith('.csv')) {
      setError('Sólo se aceptan archivos .csv');
      return;
    }
    setFile(f);
    setError(null);
    setResult(null);
  }

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await uploadCsv({ kind, file });
      setResult(res);
      onUploaded?.(res);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Error subiendo el archivo');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      accent="brand"
      title="Cargar archivo desde SAP"
      hint="Drag & drop o selecciona el CSV exportado del ERP"
      action={
        <a
          href={sampleCsvUrl(kind)}
          download
          className="mono text-[11px] uppercase tracking-widest2 text-accent hover:text-accent-soft"
        >
          ↓ plantilla {kind}
        </a>
      }
    >
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="label-eyebrow">Tipo de archivo</span>
          <select
            className="rounded-md border border-bg-line bg-white px-3 py-2 text-sm text-ink-high focus:border-accent focus:outline-none"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setResult(null);
              setError(null);
            }}
          >
            {KINDS.map((k) => (
              <option key={k.value} value={k.value}>
                {k.label}
              </option>
            ))}
          </select>
        </label>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
          onClick={() => inputRef.current?.click()}
          className={`cursor-pointer rounded-md border-2 border-dashed p-6 text-center transition-colors ${
            dragOver
              ? 'border-accent bg-accent/5'
              : 'border-bg-line bg-bg-base hover:border-accent/60'
          }`}
        >
          <p className="text-ink-mid text-sm">
            {file ? (
              <>
                <span className="mono text-ink-high font-medium">{file.name}</span>{' '}
                <span className="text-ink-low">
                  · {(file.size / 1024).toFixed(1)} KB
                </span>
              </>
            ) : (
              <>
                Arrastra un .csv aquí, o{' '}
                <span className="text-accent underline">haz clic</span>{' '}
                para seleccionarlo
              </>
            )}
          </p>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>

        <div className="flex items-center justify-end gap-2">
          {file && (
            <button
              type="button"
              className="mono text-[11px] uppercase tracking-widest2 text-ink-low hover:text-ink-mid"
              onClick={() => {
                setFile(null);
                setResult(null);
                setError(null);
                if (inputRef.current) inputRef.current.value = '';
              }}
            >
              Limpiar
            </button>
          )}
          <button
            type="button"
            onClick={submit}
            disabled={!file || busy}
            className="px-4 py-2 rounded-md bg-ink-high text-white text-sm font-medium hover:bg-brand-deep disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {busy ? 'Procesando...' : 'Cargar al sistema'}
          </button>
        </div>

        {error && (
          <p className="rounded-md border border-state-stopped/40 bg-state-stopped/5 text-state-stopped text-sm px-3 py-2">
            {error}
          </p>
        )}

        {result && <UploadResult result={result} />}
      </div>
    </Card>
  );
}

function UploadResult({ result }) {
  return (
    <div className={`rounded-md border ${STATUS_TONE[result.status] || STATUS_TONE.pending} p-3`}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="mono text-xs uppercase tracking-widest2">
            Resultado · {result.status}
          </p>
          <p className="mono text-sm tabular-nums mt-1">
            {result.rows_total} filas · {result.rows_inserted} ins · {result.rows_updated} upd
            · {result.rows_skipped} skip · {result.rows_failed} fail · {result.duration_ms} ms
          </p>
        </div>
      </div>
      {result.error_log?.global?.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs">
          {result.error_log.global.map((g, i) => (
            <li key={i}>{g}</li>
          ))}
        </ul>
      )}
      {result.error_log?.rows?.length > 0 && (
        <details className="mt-2">
          <summary className="cursor-pointer mono text-xs uppercase tracking-widest2">
            Errores por fila ({result.error_log.rows.length})
          </summary>
          <ul className="mt-1 space-y-0.5 max-h-48 overflow-y-auto pr-1">
            {result.error_log.rows.slice(0, 25).map((r, i) => (
              <li key={i} className="mono text-[11px] tabular-nums text-ink-mid">
                <span className="text-ink-low">fila {r.row}</span>
                {r.order_number && <> · <span className="text-ink-high">{r.order_number}</span></>}
                {' — '}{r.error}
              </li>
            ))}
            {result.error_log.rows.length > 25 && (
              <li className="text-[11px] text-ink-low italic">
                …y {result.error_log.rows.length - 25} más
              </li>
            )}
          </ul>
        </details>
      )}
    </div>
  );
}
