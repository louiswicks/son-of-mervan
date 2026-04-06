// src/App.js
import React, { useState, useEffect } from "react";
import LoginPage from "./components/LoginPage";
import SignUpPage from "./components/SignUpPage";
import SonOfMervan from "./components/SonOfMervan";
import MonthlyTracker from "./components/MonthlyTracker";
import AnnualOverview from "./components/AnnualOverview";
import VerifyEmailPage from "./components/VerifyEmailPage";
import ForgotPasswordPage from "./components/ForgotPasswordPage";
import ResetPasswordPage from "./components/ResetPasswordPage";
import AccountSettings from "./components/AccountSettings";
import { setAccessToken, setOnUnauthorized } from "./api/client";
import { refreshSession, logout as apiLogout } from "./api/auth";
import "./App.css";

function App() {
  // --- hooks (must be top-level)
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("budget");
  const [authMode, setAuthMode] = useState("login");
  const [refreshKey, setRefreshKey] = useState(0);
  const [hash, setHash] = useState(window.location.hash || ""); // 👈 track hash

  useEffect(() => {
    const onHash = () => setHash(window.location.hash || "");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // Register an unauthorized callback so the 401 interceptor can log us out
  useEffect(() => {
    setOnUnauthorized(() => {
      setToken(null);
      setIsAuthenticated(false);
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // On startup: try to restore session from httpOnly refresh token cookie.
  // Access token is never stored in localStorage — memory only.
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
    // Access token stored in memory only — NOT localStorage
    setAccessToken(newToken);
    setToken(newToken);
    setIsAuthenticated(true);
    if (window.location.hash.startsWith("#/verify-email")) {
      window.location.hash = "";
    }
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

  const handleAnyDataSaved = () => setRefreshKey((k) => k + 1);

  // --- loading screen
  if (loading) {
    return (
      <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-white" />
      </div>
    );
  }

  // --- PUBLIC ROUTES
  if (!isAuthenticated) {
    if (hash.startsWith("#/verify-email")) {
      return (
        <VerifyEmailPage
          goToLogin={() => {
            window.location.hash = "";
            setAuthMode("login");
          }}
        />
      );
    }

    if (hash.startsWith("#/reset-password")) {
      return (
        <ResetPasswordPage
          goToLogin={() => {
            window.location.hash = "";
            setAuthMode("login");
          }}
        />
      );
    }

    if (authMode === "signup") {
      return <SignUpPage onLogin={handleLogin} goToLogin={() => setAuthMode("login")} />;
    }

    if (authMode === "forgot-password") {
      return (
        <ForgotPasswordPage goToLogin={() => setAuthMode("login")} />
      );
    }

    return (
      <LoginPage
        onLogin={handleLogin}
        goToSignup={() => setAuthMode("signup")}
        goToForgotPassword={() => setAuthMode("forgot-password")}
      />
    );
  }

  // --- AUTHENTICATED APP
  return (
    <div className="min-h-dvh bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center py-3 sm:py-0">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">SYITB</h1>

            {/* Desktop nav buttons */}
            <div className="hidden sm:flex sm:items-center sm:gap-2">
              {[
                ["budget", "Current Budget"],
                ["monthly", "Monthly Tracker"],
                ["annual", "Annual Overview"],
                ["settings", "Settings"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setActiveTab(key)}
                  className={`px-3 py-1.5 rounded-lg font-medium text-sm ${
                    activeTab === key
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-700 hover:bg-gray-300"
                  }`}
                >
                  {label}
                </button>
              ))}
              <button
                onClick={handleLogout}
                className="bg-gray-600 hover:bg-gray-700 text-white px-3 py-1.5 rounded-lg font-medium text-sm"
              >
                Logout
              </button>
            </div>

            {/* Mobile: compact select + logout */}
            <div className="flex sm:hidden items-center gap-2">
              <select
                value={activeTab}
                onChange={(e) => setActiveTab(e.target.value)}
                className="flex-1 rounded-lg border-2 border-gray-200 px-3 py-2 text-[16px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                aria-label="Choose section"
              >
                <option value="budget">Current Budget</option>
                <option value="monthly">Monthly Tracker</option>
                <option value="annual">Annual Overview</option>
                <option value="settings">Settings</option>
              </select>
              <button
                onClick={handleLogout}
                className="rounded-lg border border-gray-300 px-3 py-2 text-[16px] text-gray-700"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
        {activeTab === "budget" && <SonOfMervan token={token} onSaved={handleAnyDataSaved} />}
        {activeTab === "monthly" && <MonthlyTracker token={token} onSaved={handleAnyDataSaved} />}
        {activeTab === "annual" && <AnnualOverview token={token} refreshKey={refreshKey} />}
        {activeTab === "settings" && <AccountSettings token={token} onLogout={handleLogout} />}
      </main>
    </div>
  );
}

export default App;
