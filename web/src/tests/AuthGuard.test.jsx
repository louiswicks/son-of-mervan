import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: () => mockNavigate,
}));

const mockHandleLogout = jest.fn();
let mockAuthState = { isAuthenticated: false, loading: false };

jest.mock('../context/AuthContext', () => ({
  useAuth: () => ({ ...mockAuthState, handleLogout: mockHandleLogout }),
}));

jest.mock('../hooks/useTheme', () => ({
  useTheme: () => ({ theme: 'light', toggleTheme: jest.fn() }),
}));

import AuthGuard from '../components/AuthGuard';

function renderAuthGuard(initialPath = '/') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/login" element={<div>Login page</div>} />
          <Route element={<AuthGuard />}>
            <Route path="/" element={<div>Dashboard content</div>} />
            <Route path="/budget" element={<div>Budget page</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  mockAuthState = { isAuthenticated: false, loading: false };
});

describe('AuthGuard', () => {
  test('shows spinner when loading=true', () => {
    mockAuthState = { isAuthenticated: false, loading: true };
    renderAuthGuard();
    // The spinner div has class animate-spin
    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
  });

  test('redirects to /login when not authenticated', () => {
    mockAuthState = { isAuthenticated: false, loading: false };
    renderAuthGuard();
    // Should render the Login page sentinel text
    expect(screen.getByText('Login page')).toBeInTheDocument();
  });

  test('renders nav and outlet content when authenticated', () => {
    mockAuthState = { isAuthenticated: true, loading: false };
    renderAuthGuard('/');
    expect(screen.getByText('Dashboard content')).toBeInTheDocument();
    // SYITB branding in nav header
    expect(screen.getByText('SYITB')).toBeInTheDocument();
  });

  test('logout button calls handleLogout and navigates to /login', async () => {
    mockAuthState = { isAuthenticated: true, loading: false };
    mockHandleLogout.mockResolvedValue(undefined);
    renderAuthGuard('/');

    // There are two logout buttons (desktop + mobile) - click the first visible one
    const logoutButtons = screen.getAllByRole('button', { name: /logout/i });
    expect(logoutButtons.length).toBeGreaterThan(0);
    fireEvent.click(logoutButtons[0]);

    await waitFor(() => {
      expect(mockHandleLogout).toHaveBeenCalledTimes(1);
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });
  });

  test('active nav tab gets aria-current="page" in mobile bottom bar', () => {
    mockAuthState = { isAuthenticated: true, loading: false };
    renderAuthGuard('/budget');

    // Mobile bottom tab bar buttons have aria-label + aria-current="page" when active.
    // The desktop nav button has text "Budget" but no aria-label/aria-current.
    // The mobile tab bar button has aria-label="Budget" and aria-current="page".
    // There are two Budget buttons — find the one with aria-current
    const allBudgetButtons = screen.getAllByRole('button', { name: 'Budget' });
    const activeTab = allBudgetButtons.find(
      (btn) => btn.getAttribute('aria-current') === 'page',
    );
    expect(activeTab).toBeTruthy();
    expect(activeTab).toHaveAttribute('aria-current', 'page');
  });
});
