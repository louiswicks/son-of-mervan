// src/components/AuthGuard.jsx
import React from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../hooks/useTheme";

const NAV_TABS = [
  ["/budget", "Current Budget"],
  ["/expenses", "Monthly Tracker"],
  ["/annual", "Annual Overview"],
  ["/settings", "Settings"],
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
    <header className="bg-white dark:bg-gray-900 shadow-sm border-b border-gray-200 dark:border-gray-700">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center py-3 sm:py-0">
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white">SYITB</h1>

          {/* Desktop nav */}
          <div className="hidden sm:flex sm:items-center sm:gap-2">
            {NAV_TABS.map(([path, label]) => (
              <button
                key={path}
                onClick={() => navigate(path)}
                className={`px-3 py-1.5 rounded-lg font-medium text-sm ${
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

          {/* Mobile: compact select + theme toggle + logout */}
          <div className="flex sm:hidden items-center gap-2">
            <select
              value={location.pathname}
              onChange={(e) => navigate(e.target.value)}
              className="flex-1 rounded-lg border-2 border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white px-3 py-2 text-[16px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              aria-label="Choose section"
            >
              {NAV_TABS.map(([path, label]) => (
                <option key={path} value={path}>{label}</option>
              ))}
            </select>
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 px-3 py-2"
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <button
              onClick={handleLogoutClick}
              className="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-[16px] text-gray-700 dark:text-gray-200"
            >
              Logout
            </button>
          </div>
        </div>
      </div>
    </header>
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
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-6">
        <Outlet />
      </main>
    </div>
  );
}
