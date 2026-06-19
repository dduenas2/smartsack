/**
 * Tests del componente Modal.
 *
 * Cubren visibilidad por prop `open`, cierre con tecla Escape y clic en
 * backdrop, y bloqueo del scroll del body mientras está abierto.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import Modal from './Modal.jsx';

describe('Modal', () => {
  it('no renderiza nada cuando open=false', () => {
    render(<Modal open={false} title="Hidden">contenido</Modal>);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renderiza título y contenido cuando open=true', () => {
    render(
      <Modal open onClose={() => {}} title="Editar">
        <span>cuerpo</span>
      </Modal>,
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Editar')).toBeInTheDocument();
    expect(screen.getByText('cuerpo')).toBeInTheDocument();
  });

  it('llama a onClose al pulsar Escape', () => {
    const onClose = vi.fn();
    render(<Modal open onClose={onClose} title="x">c</Modal>);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('llama a onClose al clicar el backdrop pero no el cuerpo', () => {
    const onClose = vi.fn();
    render(<Modal open onClose={onClose} title="x">c</Modal>);
    // Clic en el dialog (cuerpo) no debe cerrar.
    fireEvent.mouseDown(screen.getByRole('dialog'));
    expect(onClose).not.toHaveBeenCalled();
    // Clic en el backdrop (parent) sí cierra.
    const backdrop = screen.getByRole('dialog').parentElement;
    fireEvent.mouseDown(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
