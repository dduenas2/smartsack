/**
 * Tests del componente OperationQueue (cola del operario).
 *
 * Cubren:
 * - Mensaje vacío cuando no hay operaciones.
 * - Renderiza una operación READY como interactiva (clic dispara onStart).
 * - Una operación IN_PROGRESS no es clickable (en curso).
 * - El conteo correcto en el hint del Card.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import OperationQueue from './OperationQueue.jsx';

const opReady = {
  id: 1,
  status: 'ready',
  sequence: 2,
  quantity_in: 5000,
  order: { order_number: 'OP-2026-001234', product_type: 'Saco cemento 50kg', priority: 'high' },
};

const opRunning = {
  id: 2,
  status: 'in_progress',
  sequence: 3,
  quantity_in: 4900,
  quantity_out: 1200,
  order: { order_number: 'OP-2026-001000', product_type: 'Saco cal 25kg', priority: 'normal' },
};

describe('OperationQueue', () => {
  it('muestra estado vacío cuando no hay operaciones', () => {
    render(<OperationQueue operations={[]} onStart={vi.fn()} busyId={null} />);
    expect(
      screen.getByText(/No hay operaciones para esta máquina/i),
    ).toBeInTheDocument();
  });

  it('renderiza una operación READY como interactiva y dispara onStart al clic', () => {
    const onStart = vi.fn();
    render(<OperationQueue operations={[opReady]} onStart={onStart} busyId={null} />);
    expect(screen.getByText('OP-2026-001234')).toBeInTheDocument();
    expect(screen.getByText(/iniciar/i)).toBeInTheDocument();

    // El item es clickable: hacemos clic en su contenedor (el li).
    fireEvent.click(screen.getByText('OP-2026-001234').closest('li'));
    expect(onStart).toHaveBeenCalledWith(opReady);
  });

  it('una operación IN_PROGRESS no se puede iniciar de nuevo', () => {
    const onStart = vi.fn();
    render(<OperationQueue operations={[opRunning]} onStart={onStart} busyId={null} />);
    // "en curso" aparece tanto en el hint del Card como en el label de la fila.
    expect(screen.getAllByText(/en curso/i).length).toBeGreaterThanOrEqual(1);
    fireEvent.click(screen.getByText('OP-2026-001000').closest('li'));
    expect(onStart).not.toHaveBeenCalled();
  });

  it('muestra el hint correcto cuando hay 1 en curso y 2 esperando', () => {
    const ops = [
      opRunning,
      opReady,
      { ...opReady, id: 3, order: { ...opReady.order, order_number: 'OP-2026-001235' } },
    ];
    render(<OperationQueue operations={ops} onStart={vi.fn()} busyId={null} />);
    expect(screen.getByText(/1 en curso · 2 en espera/i)).toBeInTheDocument();
  });

  it('si busyId coincide muestra puntos suspensivos en lugar de "iniciar"', () => {
    render(<OperationQueue operations={[opReady]} onStart={vi.fn()} busyId={1} />);
    expect(screen.getByText('...')).toBeInTheDocument();
  });
});
