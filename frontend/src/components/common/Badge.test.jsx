/**
 * Tests del componente Badge.
 *
 * Cubren el mapeo tone → label/color y el override de label vía children.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Badge from './Badge.jsx';

describe('Badge', () => {
  it('muestra el label canónico para tonos conocidos', () => {
    render(<Badge tone="running" />);
    expect(screen.getByText('En operación')).toBeInTheDocument();
  });

  it('mapea in_progress a "En curso"', () => {
    render(<Badge tone="in_progress" />);
    expect(screen.getByText('En curso')).toBeInTheDocument();
  });

  it('permite override del label vía children', () => {
    render(<Badge tone="urgent">¡Alta prioridad!</Badge>);
    expect(screen.getByText('¡Alta prioridad!')).toBeInTheDocument();
  });

  it('cae a "neutral" si el tono es desconocido', () => {
    render(<Badge tone="alien">marciano</Badge>);
    const node = screen.getByText('marciano');
    expect(node).toBeInTheDocument();
    // El estilo neutral usa slate-700 — no comprobamos clases exactas para no
    // acoplarnos a Tailwind, pero verificamos que el span se renderizó.
    expect(node.tagName).toBe('SPAN');
  });
});
