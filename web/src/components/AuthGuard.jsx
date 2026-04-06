// src/components/AuthGuard.jsx
import React, { useState, useRef, useEffect } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Moon, Sun, LayoutDashboard, Calendar, TrendingUp, Settings,
  Repeat, PiggyBank, Bell, X, Trash2, BellOff,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../hooks/useTheme";
import {
  useNotifications,
  useMarkRead,
  useMarkAllRead,
  useDeleteNotification,
} from "../hooks/useAlerts";

const NAV_TABS = [
  ["/budget", "Budget", LayoutDashboard],
  ["/expenses", "Tracker", Calendar],
  ["/annual", "Annual", TrendingUp],
  ["/recurring", "Recurring", Repeat],
  ["/savings", "Savings", PiggyBank],
  ["/alerts", "Alerts", Bell],
  ["/settings", "Settings", Settings],
];

// -------------------- Notification Panel --------------------

function NotificationPanel({ onClose }) {
  const { data, isLoading } = useNotifications();
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();
  const deleteNotif = useDeleteNotification();
  const navigate = useNavigate();
  const panelRef = useRef(null);

  // Close on outside click
  useEffect(() => {
    function handleClick(e) {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  const notifications = data?.items ?? [];
  const unreadCount = data?.unread_count ?? 0;

  const handleMarkRead = (id) => {
    markRead.mutate(id);
  };

  const handleMarkAllRead = () => {
    markAllRead.mutate();
  };

  const handleDelete = (e, id) => {
    e.stopPropagation();
    deleteNotif.mutate(id);
  };

  const handleConfigureAlerts = () => {
    navigate("/alerts");
    onClose();
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/20 dark:bg-black/40 z-40"
        aria-hidden="true"
      />

      {/* Slide-over panel */}
      <div
        ref={panelRef}
        className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-sm bg-white dark:bg-gray-900 shadow-2xl flex flex-col"
        role="dialog"
        aria-label="Notifications"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold text-gray-900 dark:text-white">Notifications</h2>
            {unreadCount > 0 && (
              <span className="bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                {unreadCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline px-2 py-1"
              >
                Mark all read
              </button>
            )}
            <button
              onClick={onClose}
              className="min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Notification list */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 rounded-lg bg-gray-100 dark:bg-gray-800 animate-pulse" />
              ))}
            </div>
          ) : notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 px-6 text-center">
              <BellOff size={36} className="text-gray-300 dark:text-gray-600 mb-3" />
              <p className="text-gray-500 dark:text-gray-400 font-medium">No notifications</p>
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
                Budget alerts will appear here
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-gray-800">
              {notifications.map((n) => (
                <li
                  key={n.id}
                  onClick={() => n.read_at === null && handleMarkRead(n.id)}
                  className={`flex gap-3 p-4 cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-800 ${
                    n.read_at === null
                      ? "bg-blue-50/60 dark:bg-blue-900/10"
                      : ""
                  }`}
                >
                  <div className="flex-shrink-0 mt-0.5">
                    <div
                      className={`w-2 h-2 rounded-full mt-1.5 ${
                        n.read_at === null
                          ? "bg-blue-500"
                          : "bg-transparent"
                      }`}
                    />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p
                      className={`text-sm font-medium truncate ${
                        n.read_at === null
                          ? "text-gray-900 dark:text-white"
                          : "text-gray-600 dark:text-gray-300"
                      }`}
                    >
                      {n.title}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                      {n.message}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      {new Date(n.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, n.id)}
                    className="flex-shrink-0 min-w-[32px] min-h-[32px] flex items-center justify-center rounded-lg text-gray-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors self-start"
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 dark:border-gray-700 p-4">
          <button
            onClick={handleConfigureAlerts}
            className="w-full bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-200 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors"
          >
            Configure alert thresholds
          </button>
        </div>
      </div>
    </>
  );
}

// -------------------- Bell Button --------------------

function BellButton({ onClick }) {
  const { data } = useNotifications();
  const unreadCount = data?.unread_count ?? 0;

  return (
    <button
      onClick={onClick}
      aria-label="Notifications"
      className="relative p-1.5 rounded-lg text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 min-w-[36px] min-h-[36px] flex items-center justify-center"
    >
      <Bell size={18} />
      {unreadCount > 0 && (
        <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center leading-none">
          {unreadCount > 9 ? "9+" : unreadCount}
        </span>
      )}
    </button>
  );
}

// -------------------- Nav --------------------

function Nav() {
  const navigate = useNavigate();
  const location = useLocation();
  const { handleLogout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [notifOpen, setNotifOpen] = useState(false);

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
              <BellButton onClick={() => setNotifOpen(true)} />
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

            {/* Mobile: bell + theme toggle + logout in header */}
            <div className="flex sm:hidden items-center gap-2">
              <BellButton onClick={() => setNotifOpen(true)} />
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

      {/* Notification slide-over */}
      {notifOpen && <NotificationPanel onClose={() => setNotifOpen(false)} />}
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
