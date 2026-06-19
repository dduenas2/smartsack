/**
 * Tests del componente MachineTile (tile del Digital Twin).
 *
 * Cubren los tres modos de visualización:
 * - Sin operación ni orden: estado "Sin operación activa".
 * - Solo orden cabecera (sin operación): muestra avance de la orden.
 * - Operación activa: muestra avance de op + avance acumulado de la orden.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MachineTile from './MachineTile.jsx';

const baseMachine = {
  id: 1,
  code: 'IMP-01',
  name: 'Impresora 1',
  type: 'IMPRESORA',
  status: 'idle',
  location: 'Línea A',
};

describe('MachineTile', () => {
  it('muestra "Sin operación activa" cuando no hay datos operativos', () => {
    render(<MachineTile machine={baseMachine} flashEvent={null} flashKey={0} />);
    expect(screen.getByText('IMP-01')).toBeInTheDocument();
    expect(screen.getByText(/Sin operación activa/i)).toBeInTheDocument();
  });

  it('muestra avance de operación cuando hay current_operation', () => {
    const machine = {
      ...baseMachine,
      status: 'running',
      current_operation: {
        sequence: 1,
        order_number: 'OP-2026-001234',
        quantity_in: 10000,
        quantity_out: 5000,
        scrap_kg: 0,
      },
      current_order: {
        quantity_ordered: 10000,
        quantity_produced: 0,
      },
    };
    render(<MachineTile machine={machine} flashEvent="start" flashKey={1} />);
    expect(screen.getByText(/op1/i)).toBeInTheDocument();
    expect(document.body.textContent).toContain('OP-2026-001234');
    expect(screen.getByText('50%')).toBeInTheDocument(); // 5000/10000
  });

  it('muestra avance de la orden cuando hay current_order pero no operación', () => {
    const machine = {
      ...baseMachine,
      status: 'running',
      current_order: {
        order_number: 'OP-2026-001000',
        quantity_ordered: 20000,
        quantity_produced: 5000,
      },
    };
    render(<MachineTile machine={machine} flashEvent={null} flashKey={2} />);
    expect(document.body.textContent).toContain('OP-2026-001000');
    expect(screen.getByText('25%')).toBeInTheDocument(); // 5000/20000
  });

  it('muestra el scrap cuando la operación tiene desperdicio > 0', () => {
    const machine = {
      ...baseMachine,
      status: 'running',
      current_operation: {
        sequence: 2,
        order_number: 'OP-2026-001500',
        quantity_in: 10000,
        quantity_out: 4000,
        scrap_kg: 3.5,
      },
      current_order: { quantity_ordered: 10000, quantity_produced: 0 },
    };
    render(<MachineTile machine={machine} flashEvent={null} flashKey={3} />);
    expect(document.body.textContent).toMatch(/3\.5 kg scrap/i);
  });
});
