// src/context/AuthContext.jsx
// AuthProvider runs the session-restore side effect on mount.
// All auth state lives in authStore (Zustand) — no React Context needed.
import { useEffect } from 'react';
import { useAuthStore } from '../store/authStore';
import { refreshSession, logout as apiLogout } from '../api/auth';

export function AuthProvider({ children }) {
  const { handleLogin, setLoading } = useAuthStore();

  useEffect(() => {
    (async () => {
      try {
        const data = await refreshSession();
        handleLogin(data.access_token);
      } catch {
        // No valid session — stay on login page
      } finally {
        setLoading(false);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return children;
}

/**
 * useAuth() provides the same API as before so existing consumers don't change.
 * handleLogout is defined here (not in the store) to avoid a circular import:
 *   authStore → api/auth → api/client → authStore
 */
export function useAuth() {
  const { isAuthenticated, token, loading, handleLogin, clearAuth } = useAuthStore();

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch {
      // Proceed with local logout even if the request fails
    }
    clearAuth();
  };

  return { isAuthenticated, token, loading, handleLogin, handleLogout };
}
