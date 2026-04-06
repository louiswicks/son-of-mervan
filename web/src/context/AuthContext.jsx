// src/context/AuthContext.jsx
import React, { createContext, useContext, useState, useEffect } from "react";
import { setAccessToken, setOnUnauthorized } from "../api/client";
import { refreshSession, logout as apiLogout } from "../api/auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setOnUnauthorized(() => {
      setToken(null);
      setIsAuthenticated(false);
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    (async () => {
      try {
        const data = await refreshSession();
        setAccessToken(data.access_token);
        setToken(data.access_token);
        setIsAuthenticated(true);
      } catch {
        // No valid session — stay on login page
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleLogin = (newToken) => {
    setAccessToken(newToken);
    setToken(newToken);
    setIsAuthenticated(true);
  };

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch {
      // Proceed with local logout even if request fails
    }
    setAccessToken(null);
    setToken(null);
    setIsAuthenticated(false);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, token, loading, handleLogin, handleLogout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
