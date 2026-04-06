import React from 'react';
import { render, screen } from '@testing-library/react';

// Mock the entire api/client module (uses axios ESM which CRA Jest can't parse)
jest.mock('./api/client', () => ({
  default: {
    get: jest.fn().mockResolvedValue({ data: {} }),
    post: jest.fn().mockResolvedValue({ data: {} }),
    put: jest.fn().mockResolvedValue({ data: {} }),
    delete: jest.fn().mockResolvedValue({ data: {} }),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() },
    },
  },
}));

// Mock AuthContext so AuthProvider doesn't call refreshSession
jest.mock('./context/AuthContext', () => ({
  AuthProvider: ({ children }) => <>{children}</>,
  useAuth: () => ({
    isAuthenticated: false,
    loading: false,
    handleLogin: jest.fn(),
    handleLogout: jest.fn(),
  }),
}));

// Mock hooks/useTheme
jest.mock('./hooks/useTheme', () => ({
  useTheme: () => ({ theme: 'light', toggleTheme: jest.fn() }),
}));

// Mock react-hot-toast to avoid any ESM issues
jest.mock('react-hot-toast', () => ({
  default: {
    success: jest.fn(),
    error: jest.fn(),
  },
  Toaster: () => null,
}));

import App from './App.jsx';

test('renders the login page when not authenticated', async () => {
  render(<App />);
  // Login page has "Welcome back" heading
  const heading = await screen.findByText(/welcome back/i);
  expect(heading).toBeInTheDocument();
});
