// src/store/authStore.js
// Zustand store for authentication state.
// Access token is held in-memory only — never written to localStorage.
import { create } from 'zustand';

export const useAuthStore = create((set) => ({
  isAuthenticated: false,
  token: null,
  loading: true,

  // 2FA challenge state — set when login returns requires_2fa: true.
  // The challenge token is a short-lived JWT the user must exchange for a full session.
  totpChallengeToken: null,

  // Called after a successful login or initial session restore.
  handleLogin: (token) => set({ token, isAuthenticated: true, totpChallengeToken: null }),

  // Called inside the Axios interceptor after a silent token refresh —
  // only updates the token without changing isAuthenticated.
  setToken: (token) => set({ token }),

  // Called on logout or when a refresh attempt fails.
  clearAuth: () => set({ token: null, isAuthenticated: false, totpChallengeToken: null }),

  setLoading: (loading) => set({ loading }),

  // Called when login responds with requires_2fa: true
  setTOTPChallenge: (challengeToken) => set({ totpChallengeToken: challengeToken }),
}));
