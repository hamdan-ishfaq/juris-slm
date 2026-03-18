import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { render, screen } from '@testing-library/react';

import Login from '../pages/Login';

const mockNavigate = vi.fn();
const mockLogin = vi.fn();
const mockRegister = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('../lib/api', () => ({
  authAPI: {
    login: (...args) => mockLogin(...args),
    register: (...args) => mockRegister(...args),
  },
}));

vi.mock('react-hot-toast', () => ({
  default: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

describe('Login page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('blocks submit when required fields are empty', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    const emailInput = screen.getByLabelText('Email');
    const passwordInput = screen.getByLabelText('Password');
    await user.clear(emailInput);
    await user.clear(passwordInput);

    await user.click(screen.getByRole('button', { name: 'Sign In' }));

    expect(mockLogin).not.toHaveBeenCalled();
    expect(emailInput).toBeInvalid();
    expect(passwordInput).toBeInvalid();
  });

  it('shows 401 error message on invalid credentials', async () => {
    const user = userEvent.setup();
    mockLogin.mockRejectedValueOnce({ response: { status: 401 } });

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    await user.click(screen.getByRole('button', { name: 'Sign In' }));

    expect(await screen.findByText('Invalid email or password')).toBeInTheDocument();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});