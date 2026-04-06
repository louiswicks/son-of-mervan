// src/components/AuthGuard.jsx
import React from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Moon, Sun, LayoutDashboard, Calendar, TrendingUp, Settings, Repeat } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../hooks/useTheme";

const NAV_TABS = [
  ["/budget", "Budget", LayoutDashboard],
  ["/expenses", "Tracker", Calendar],
  ["/annual", "Annual", TrendingUp],
  ["/recurring", "Recurring", Repeat],
  ["/settings", "Settings", Settings],
];

function Nav() {
  const navigate = useNavigate();
  const location = useLocation();
  const { handleLogout } = useAuth();
  const { theme, toggleTheme } = useTheme();

  const handleLogoutClick = async () => {
    await handleLogout();
    navigate("/login");
  };

  return (
    <>
      {/* Top header */}
      <header className="bg-white dark:bg-gray-900 shadow-sm border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between py-3">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">SYITB</h1>

            {/* Desktop nav */}
            <div className="hidden sm:flex sm:items-center sm:gap-2">
              {NAV_TABS.map(([path, label]) => (
                <button
                  key={path}
                  onClick={() => navigate(path)}
                  className={`px-3 py-1.5 rounded-lg font-medium text-sm transition-colors ${
                    location.pathname === path
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600"
                  }`}
                >
                  {label}
                </button>
              ))}
              <button
                onClick={toggleTheme}
                aria-label="Toggle theme"
                className="p-1.5 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700"
              >
                {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              </button>
              <button
                onClick={handleLogoutClick}
                className="bg-gray-600 hover:bg-gray-700 text-white px-3 py-1.5 rounded-lg font-medium text-sm"
              >
                Logout
              </button>
            </div>

            {/* Mobile: theme toggle + logout in header */}
            <div className="flex sm:hidden items-center gap-2">
              <button
                onClick={toggleTheme}
                aria-label="Toggle theme"
                className="min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200"
              >
                {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              </button>
              <button
                onClick={handleLogoutClick}
                className="min-h-[44px] px-4 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm text-gray-700 dark:text-gray-200"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Mobile: bottom tab bar */}
      <nav
        className="sm:hidden fixed bottom-0 left-0 right-0 z-50 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 safe-area-bottom"
        aria-label="Main navigation"
      >
        <div className="flex">
          {NAV_TABS.map(([path, label, Icon]) => {
            const active = location.pathname === path;
            return (
              <button
                key={path}
                onClick={() => navigate(path)}
                className={`flex-1 flex flex-col items-center justify-center py-2 min-h-[56px] text-xs font-medium transition-colors ${
                  active
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                }`}
                aria-label={label}
                aria-current={active ? "page" : undefined}
              >
                <Icon size={22} />
                <span className="mt-0.5">{label}</span>
              </button>
            );
          })}
        </div>
      </nav>
    </>
  );
}

export default function AuthGuard() {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-white" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return (
    <div className="min-h-dvh bg-gray-100 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      <Nav />
      {/* pb-24 on mobile to clear the fixed bottom tab bar */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 pb-24 sm:py-6">
        <Outlet />
      </main>
    </div>
  );
}
