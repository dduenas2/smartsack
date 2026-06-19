/**
 * Tests del componente Field.
 *
 * Cubren render como input de texto y como select con opciones, y la
 * propagación correcta del valor vía onChange (incluyendo conversión a
 * número cuando type='number').
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Field from './Field.jsx';

describe('Field', () => {
  it('renderiza input con label visible', () => {
    render(
      <Field id="x" label="Mi campo" value="hola" onChange={() => {}} />,
    );
    expect(screen.getByLabelText(/mi campo/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/mi campo/i)).toHaveValue('hola');
  });

  it('marca required con asterisco', () => {
    render(<Field id="x" label="Obligatorio" required value="" onChange={() => {}} />);
    expect(screen.getByText('*')).toBeInTheDocument();
  });

  it('propaga valor numérico cuando type=number', () => {
    const onChange = vi.fn();
    render(
      <Field id="x" label="N" type="number" value={1} onChange={onChange} />,
    );
    fireEvent.change(screen.getByLabelText(/n/i), { target: { value: '42' } });
    expect(onChange).toHaveBeenCalledWith(42);
  });

  it('renderiza como select cuando type=select', () => {
    render(
      <Field id="x" label="Rol" type="select" value="b" onChange={() => {}}>
        <option value="a">A</option>
        <option value="b">B</option>
      </Field>,
    );
    const select = screen.getByLabelText(/rol/i);
    expect(select.tagName).toBe('SELECT');
    expect(select).toHaveValue('b');
  });

  it('muestra error cuando se proporciona', () => {
    render(
      <Field
        id="x"
        label="Y"
        value=""
        onChange={() => {}}
        error="Algo falló"
      />,
    );
    expect(screen.getByText('Algo falló')).toBeInTheDocument();
  });
});
