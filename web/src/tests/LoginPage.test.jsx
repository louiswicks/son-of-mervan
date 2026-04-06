import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mocks must be declared before imports of the modules under test
const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

const mockLogin = jest.fn();
jest.mock('../api/auth', () => ({
  login: (...args) => mockLogin(...args),
}));

const mockHandleLogin = jest.fn();
jest.mock('../context/AuthContext', () => ({
  useAuth: () => ({ handleLogin: mockHandleLogin }),
}));

import LoginPage from '../components/LoginPage';

function renderLoginPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe('LoginPage', () => {
  test('renders email/username input, password input, and submit button', () => {
    renderLoginPage();
    expect(screen.getByPlaceholderText(/you@example\.com or yourname/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/••••••••/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /log in/i })).toBeInTheDocument();
  });

  test('shows "Forgot password?" link and "Create an account" link', () => {
    renderLoginPage();
    expect(screen.getByRole('button', { name: /forgot password/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create an account/i })).toBeInTheDocument();
  });

  test('successful login calls login API, handleLogin with token, and navigates to /budget', async () => {
    mockLogin.mockResolvedValue({ access_token: 'test-token-abc' });
    renderLoginPage();

    fireEvent.change(screen.getByPlaceholderText(/you@example\.com or yourname/i), {
      target: { value: 'user@test.com' },
    });
    fireEvent.change(screen.getByPlaceholderText(/••••••••/), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('user@test.com', 'password123');
      expect(mockHandleLogin).toHaveBeenCalledWith('test-token-abc');
      expect(mockNavigate).toHaveBeenCalledWith('/budget');
    });
  });

  test('failed login shows error message from API response', async () => {
    const apiError = new Error('Invalid credentials');
    apiError.response = { data: { detail: 'Incorrect password.' } };
    mockLogin.mockRejectedValue(apiError);

    renderLoginPage();

    fireEvent.change(screen.getByPlaceholderText(/you@example\.com or yourname/i), {
      target: { value: 'user@test.com' },
    });
    fireEvent.change(screen.getByPlaceholderText(/••••••••/), {
      target: { value: 'wrongpass' },
    });
    fireEvent.click(screen.getByRole('button', { name: /log in/i }));

    await waitFor(() => {
      expect(screen.getByText('Incorrect password.')).toBeInTheDocument();
    });
  });

  test('submit button shows "Logging in…" and is disabled while submitting', async () => {
    // Use a promise we control so we can inspect mid-flight state
    let resolveLogin;
    mockLogin.mockImplementation(
      () => new Promise((resolve) => { resolveLogin = resolve; }),
    );

    renderLoginPage();

    fireEvent.change(screen.getByPlaceholderText(/you@example\.com or yourname/i), {
      target: { value: 'user@test.com' },
    });
    fireEvent.change(screen.getByPlaceholderText(/••••••••/), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /log in/i }));

    // While the login promise is pending, the button text should change and be disabled
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /logging in/i })).toBeDisabled();
    });

    // Resolve the login to clean up
    resolveLogin({ access_token: 'tok' });
  });
});
