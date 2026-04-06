// src/store/authStore.js
// Zustand store for authentication state.
// Access token is held in-memory only — never written to localStorage.
import { create } from 'zustand';

export const useAuthStore = create((set) => ({
  isAuthenticated: false,
  token: null,
  loading: true,

  // Called after a successful login or initial session restore.
  handleLogin: (token) => set({ token, isAuthenticated: true }),

  // Called inside the Axios interceptor after a silent token refresh —
  // only updates the token without changing isAuthenticated.
  setToken: (token) => set({ token }),

  // Called on logout or when a refresh attempt fails.
  clearAuth: () => set({ token: null, isAuthenticated: false }),

  setLoading: (loading) => set({ loading }),
}));
