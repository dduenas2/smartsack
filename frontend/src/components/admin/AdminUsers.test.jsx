/**
 * Tests del componente AdminUsers.
 *
 * Mockeamos los módulos de API para no necesitar backend. Validamos:
 * - Carga inicial pinta usuarios y total.
 * - Filtros disparan refetch con los params correctos.
 * - El admin no puede desactivarse a sí mismo (botón disabled).
 * - Modal "Nuevo usuario" envía el payload correcto al confirmar.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

vi.mock('../../api/users.js', () => ({
  listUsers: vi.fn(),
  createUser: vi.fn(),
  updateUser: vi.fn(),
  deactivateUser: vi.fn(),
  resetUserPassword: vi.fn(),
  assignMachine: vi.fn(),
}));
vi.mock('../../api/machines.js', () => ({
  listMachines: vi.fn(),
}));

import AdminUsers from './AdminUsers.jsx';
import * as usersApi from '../../api/users.js';
import * as machinesApi from '../../api/machines.js';

const mockUsers = {
  total: 2,
  limit: 100,
  offset: 0,
  items: [
    {
      id: 1,
      username: 'admin',
      full_name: 'Administrador',
      role: 'admin',
      machine_id: null,
      is_active: true,
    },
    {
      id: 2,
      username: 'op_imp-01_1',
      full_name: 'Carlos Pérez',
      role: 'operario',
      machine_id: 1,
      is_active: true,
    },
  ],
};

const mockMachines = [
  { id: 1, code: 'IMP-01', name: 'Impresora 1', type: 'IMPRESORA' },
];

describe('AdminUsers', () => {
  beforeEach(() => {
    usersApi.listUsers.mockResolvedValue(mockUsers);
    machinesApi.listMachines.mockResolvedValue(mockMachines);
    usersApi.createUser.mockResolvedValue({ id: 99 });
    usersApi.deactivateUser.mockResolvedValue();
  });

  it('lista usuarios y muestra total', async () => {
    render(<AdminUsers currentUserId={1} />);
    await waitFor(() => {
      expect(screen.getByText('admin')).toBeInTheDocument();
    });
    expect(screen.getByText(/2 usuarios/i)).toBeInTheDocument();
    expect(screen.getByText('op_imp-01_1')).toBeInTheDocument();
    // El operario muestra el código de su máquina.
    expect(screen.getByText('IMP-01')).toBeInTheDocument();
  });

  it('botón "Desactivar" del propio usuario está deshabilitado', async () => {
    render(<AdminUsers currentUserId={1} />);
    await waitFor(() => screen.getByText('admin'));
    const adminRow = screen.getByText('admin').closest('tr');
    const deactivate = adminRow.querySelector('button.bg-state-stopped');
    expect(deactivate).toBeDisabled();
  });

  it('cambia el filtro de rol y refetcha', async () => {
    render(<AdminUsers currentUserId={1} />);
    await waitFor(() => screen.getByText('admin'));
    usersApi.listUsers.mockClear();

    fireEvent.change(screen.getByLabelText(/^Rol/i), { target: { value: 'operario' } });
    await waitFor(() => {
      expect(usersApi.listUsers).toHaveBeenCalledWith(
        expect.objectContaining({ role: 'operario' }),
      );
    });
  });

  it('crear usuario envía el payload al backend', async () => {
    render(<AdminUsers currentUserId={1} />);
    await waitFor(() => screen.getByText('admin'));

    fireEvent.click(screen.getByRole('button', { name: /nuevo usuario/i }));

    fireEvent.change(screen.getByLabelText(/^Username/i), {
      target: { value: 'sup_test' },
    });
    fireEvent.change(screen.getByLabelText(/^Contraseña/i), {
      target: { value: 'smartsack123' },
    });
    // Cambiar rol a supervisor (sin máquina).
    fireEvent.change(screen.getAllByLabelText(/^Rol/i)[1], {
      target: { value: 'supervisor' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^crear$/i }));

    await waitFor(() => {
      expect(usersApi.createUser).toHaveBeenCalledWith({
        username: 'sup_test',
        password: 'smartsack123',
        full_name: null,
        role: 'supervisor',
        machine_id: null,
      });
    });
  });
});
