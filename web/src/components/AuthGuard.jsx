// src/components/AuthGuard.jsx
import React, { useState, useRef, useEffect, useCallback } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Moon, Sun, LayoutDashboard, Calendar, TrendingUp, Settings,
  Repeat, PiggyBank, Bell, X, Trash2, BellOff, Lightbulb, Sliders,
  LineChart, CalendarDays, Receipt, Users, Tag, Upload, Waves,
  TrendingDown, BarChart3, ChevronLeft, ChevronRight, MoreHorizontal,
  LogOut, Menu,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../hooks/useTheme";
import { useProfile } from "../hooks/useProfile";
import {
  useNotifications,
  useMarkRead,
  useMarkAllRead,
  useDeleteNotification,
} from "../hooks/useAlerts";

// Primary nav — shown in sidebar primary section and mobile bottom tabs
const PRIMARY_NAV = [
  ["/budget", "Budget", LayoutDashboard],
  ["/expenses", "Tracker", Calendar],
  ["/annual", "Annual", TrendingUp],
  ["/insights", "Insights", Lightbulb],
];

// Secondary nav — shown in sidebar collapsible section and mobile "More" sheet
const SECONDARY_NAV = [
  ["/recurring", "Recurring", Repeat],
  ["/savings", "Savings", PiggyBank],
  ["/alerts", "Alerts", Bell],
  ["/scenarios", "What-If", Sliders],
  ["/investments", "Portfolio", LineChart],
  ["/calendar", "Calendar", CalendarDays],
  ["/tax", "Tax", Receipt],
  ["/household", "Household", Users],
  ["/categories", "Categories", Tag],
  ["/import", "Import", Upload],
  ["/forecast", "Forecast", Waves],
  ["/debts", "Debt Payoff", TrendingDown],
  ["/net-worth", "Net Worth", BarChart3],
];

// -------------------- Notification Panel --------------------

function NotificationPanel({ onClose }) {
  const { data, isLoading } = useNotifications();
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();
  const deleteNotif = useDeleteNotification();
  const navigate = useNavigate();
  const panelRef = useRef(null);

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

  return (
    <>
      <div className="fixed inset-0 bg-black/20 dark:bg-black/40 z-40" aria-hidden="true" />
      <div
        ref={panelRef}
        className="fixed top-0 right-0 bottom-0 z-50 w-full max-w-sm bg-white dark:bg-gray-900 shadow-2xl flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-labelledby="notifications-panel-title"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <h2 id="notifications-panel-title" className="font-semibold text-gray-900 dark:text-white">
              Notifications
            </h2>
            {unreadCount > 0 && (
              <span
                className="bg-red-500 text-white text-xs font-bold rounded-full px-1.5 py-0.5 min-w-[20px] text-center"
                aria-label={`${unreadCount} unread`}
              >
                {unreadCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {unreadCount > 0 && (
              <button
                onClick={() => markAllRead.mutate()}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline px-2 py-1"
              >
                Mark all read
              </button>
            )}
            <button
              onClick={onClose}
              aria-label="Close notifications"
              className="min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <X size={18} />
            </button>
          </div>
        </div>

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
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">Budget alerts will appear here</p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-100 dark:divide-gray-800">
              {notifications.map((n) => (
                <li
                  key={n.id}
                  onClick={() => n.read_at === null && markRead.mutate(n.id)}
                  className={`flex gap-3 p-4 cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-800 ${
                    n.read_at === null ? "bg-blue-50/60 dark:bg-blue-900/10" : ""
                  }`}
                >
                  <div className="flex-shrink-0 mt-0.5">
                    <div className={`w-2 h-2 rounded-full mt-1.5 ${n.read_at === null ? "bg-blue-500" : "bg-transparent"}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium truncate ${n.read_at === null ? "text-gray-900 dark:text-white" : "text-gray-600 dark:text-gray-300"}`}>
                      {n.title}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">{n.message}</p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      {new Date(n.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteNotif.mutate(n.id); }}
                    className="flex-shrink-0 min-w-[32px] min-h-[32px] flex items-center justify-center rounded-lg text-gray-400 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors self-start"
                    aria-label="Delete notification"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="border-t border-gray-200 dark:border-gray-700 p-4">
          <button
            onClick={() => { navigate("/alerts"); onClose(); }}
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

function BellButton({ onClick, collapsed }) {
  const { data } = useNotifications();
  const unreadCount = data?.unread_count ?? 0;

  return (
    <button
      onClick={onClick}
      aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : "Notifications"}
      title={collapsed ? (unreadCount > 0 ? `Notifications, ${unreadCount} unread` : "Notifications") : undefined}
      className="relative flex items-center justify-center rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 min-w-[36px] min-h-[36px]"
    >
      <Bell size={18} aria-hidden="true" />
      {unreadCount > 0 && (
        <span
          className="absolute -top-0.5 -right-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center leading-none"
          aria-hidden="true"
        >
          {unreadCount > 9 ? "9+" : unreadCount}
        </span>
      )}
    </button>
  );
}

// -------------------- Sidebar Nav Item --------------------

function SidebarNavItem({ path, label, Icon, collapsed }) {
  const location = useLocation();
  const navigate = useNavigate();
  const active = location.pathname === path;

  return (
    <button
      onClick={() => navigate(path)}
      aria-current={active ? "page" : undefined}
      aria-label={label}
      title={collapsed ? label : undefined}
      className={`flex items-center gap-3 w-full rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
        collapsed ? "justify-center" : ""
      } ${
        active
          ? "bg-blue-600 text-white"
          : "text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
      }`}
    >
      <Icon size={20} aria-hidden="true" className="flex-shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </button>
  );
}

// -------------------- Desktop Sidebar --------------------

function Sidebar({ collapsed, onToggle, onNotifClick }) {
  const navigate = useNavigate();
  const { handleLogout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [secondaryOpen, setSecondaryOpen] = useState(true);
  const location = useLocation();

  const isSecondaryActive = SECONDARY_NAV.some(([p]) => location.pathname === p) ||
    location.pathname === "/settings";

  // Auto-expand secondary section when a secondary route is active
  useEffect(() => {
    if (isSecondaryActive) setSecondaryOpen(true);
  }, [isSecondaryActive]);

  const handleLogoutClick = async () => {
    await handleLogout();
    navigate("/login");
  };

  return (
    <aside
      className={`hidden sm:flex flex-col fixed inset-y-0 left-0 z-30 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-700 transition-all duration-200 ease-in-out ${
        collapsed ? "w-16" : "w-60"
      }`}
      aria-label="Main navigation"
    >
      {/* Brand + collapse toggle */}
      <div className={`flex items-center border-b border-gray-200 dark:border-gray-700 h-14 px-3 ${collapsed ? "justify-center" : "justify-between"}`}>
        {!collapsed && (
          <span className="text-lg font-bold text-gray-900 dark:text-white tracking-tight">SYITB</span>
        )}
        <button
          onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex items-center justify-center w-8 h-8 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Scrollable nav area */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-3 px-2 space-y-0.5">
        {/* Primary nav */}
        {PRIMARY_NAV.map(([path, label, Icon]) => (
          <SidebarNavItem key={path} path={path} label={label} Icon={Icon} collapsed={collapsed} />
        ))}

        {/* Divider + secondary section */}
        <div className="my-2 border-t border-gray-200 dark:border-gray-700" />

        {!collapsed ? (
          <>
            <button
              onClick={() => setSecondaryOpen((o) => !o)}
              className="flex items-center justify-between w-full px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              aria-expanded={secondaryOpen}
            >
              <span>More</span>
              <ChevronRight
                size={12}
                className={`transition-transform duration-200 ${secondaryOpen ? "rotate-90" : ""}`}
              />
            </button>
            {secondaryOpen &&
              SECONDARY_NAV.map(([path, label, Icon]) => (
                <SidebarNavItem key={path} path={path} label={label} Icon={Icon} collapsed={false} />
              ))}
          </>
        ) : (
          SECONDARY_NAV.map(([path, label, Icon]) => (
            <SidebarNavItem key={path} path={path} label={label} Icon={Icon} collapsed={true} />
          ))
        )}

        {/* Settings */}
        <div className="my-2 border-t border-gray-200 dark:border-gray-700" />
        <SidebarNavItem path="/settings" label="Settings" Icon={Settings} collapsed={collapsed} />
      </nav>

      {/* Footer actions */}
      <div className={`border-t border-gray-200 dark:border-gray-700 p-2 flex ${collapsed ? "flex-col items-center gap-1" : "items-center gap-1"}`}>
        <BellButton onClick={onNotifClick} collapsed={collapsed} />
        <button
          onClick={toggleTheme}
          aria-label="Toggle theme"
          title={collapsed ? "Toggle theme" : undefined}
          className="flex items-center justify-center w-9 h-9 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        >
          {theme === "dark" ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
        </button>
        {!collapsed && <div className="flex-1" />}
        <button
          onClick={handleLogoutClick}
          aria-label="Logout"
          title={collapsed ? "Logout" : undefined}
          className={`flex items-center gap-2 rounded-lg px-2 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-400 transition-colors ${collapsed ? "justify-center w-9 h-9" : ""}`}
        >
          <LogOut size={18} aria-hidden="true" />
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </aside>
  );
}

// -------------------- Mobile More Sheet --------------------

function MobileMoreSheet({ onClose }) {
  const navigate = useNavigate();
  const { handleLogout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const sheetRef = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (sheetRef.current && !sheetRef.current.contains(e.target)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  const handleNav = (path) => {
    navigate(path);
    onClose();
  };

  const handleLogoutClick = async () => {
    await handleLogout();
    navigate("/login");
    onClose();
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" aria-hidden="true" />
      <div
        ref={sheetRef}
        className="fixed bottom-0 left-0 right-0 z-50 bg-white dark:bg-gray-900 rounded-t-2xl shadow-2xl max-h-[80vh] flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-label="More navigation options"
      >
        {/* Handle */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full bg-gray-300 dark:bg-gray-600" />
        </div>
        <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-700">
          <span className="font-semibold text-gray-900 dark:text-white">More</span>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
          >
            <X size={18} />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 p-4">
          <div className="grid grid-cols-2 gap-2">
            {SECONDARY_NAV.map(([path, label, Icon]) => {
              const active = location.pathname === path;
              return (
                <button
                  key={path}
                  onClick={() => handleNav(path)}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-medium transition-colors text-left ${
                    active
                      ? "bg-blue-600 text-white"
                      : "bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
                  }`}
                >
                  <Icon size={18} aria-hidden="true" />
                  <span>{label}</span>
                </button>
              );
            })}

            {/* Settings */}
            <button
              onClick={() => handleNav("/settings")}
              aria-current={location.pathname === "/settings" ? "page" : undefined}
              className={`flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-medium transition-colors text-left ${
                location.pathname === "/settings"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-50 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
              }`}
            >
              <Settings size={18} aria-hidden="true" />
              <span>Settings</span>
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex items-center gap-3">
          <button
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            {theme === "dark" ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
            <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>
          </button>
          <button
            onClick={handleLogoutClick}
            aria-label="Logout"
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"
          >
            <LogOut size={16} aria-hidden="true" />
            <span>Logout</span>
          </button>
        </div>
      </div>
    </>
  );
}

// -------------------- Mobile Bottom Tab Bar --------------------

function MobileTabBar({ onNotifClick }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { data } = useNotifications();
  const unreadCount = data?.unread_count ?? 0;
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <>
      <nav
        className="sm:hidden fixed bottom-0 left-0 right-0 z-50 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-700 safe-area-bottom"
        aria-label="Main navigation"
      >
        <div className="flex">
          {PRIMARY_NAV.map(([path, label, Icon]) => {
            const active = location.pathname === path;
            return (
              <button
                key={path}
                onClick={() => navigate(path)}
                aria-label={label}
                aria-current={active ? "page" : undefined}
                className={`flex-1 flex flex-col items-center justify-center py-2 min-h-[56px] text-xs font-medium transition-colors ${
                  active
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                }`}
              >
                <Icon size={22} aria-hidden="true" />
                <span className="mt-0.5">{label}</span>
              </button>
            );
          })}

          {/* More tab */}
          <button
            onClick={() => setMoreOpen(true)}
            aria-label="More"
            className="flex-1 flex flex-col items-center justify-center py-2 min-h-[56px] text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 transition-colors relative"
          >
            <MoreHorizontal size={22} aria-hidden="true" />
            <span className="mt-0.5">More</span>
            {unreadCount > 0 && (
              <span
                className="absolute top-1.5 right-4 bg-red-500 text-white text-[9px] font-bold rounded-full w-3.5 h-3.5 flex items-center justify-center"
                aria-hidden="true"
              >
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </button>
        </div>
      </nav>

      {moreOpen && <MobileMoreSheet onClose={() => setMoreOpen(false)} />}
    </>
  );
}

// -------------------- Main AuthGuard --------------------

export default function AuthGuard() {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();
  const [notifOpen, setNotifOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    try {
      return localStorage.getItem("sidebarCollapsed") === "true";
    } catch {
      return false;
    }
  });

  const { data: profile, isLoading: profileLoading } = useProfile({
    enabled: isAuthenticated && !loading,
  });

  const handleToggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      try { localStorage.setItem("sidebarCollapsed", String(next)); } catch {}
      return next;
    });
  }, []);

  if (loading || (isAuthenticated && profileLoading && !profile)) {
    return (
      <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-white" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (profile && profile.has_completed_onboarding === false) {
    return <Navigate to="/onboarding" replace />;
  }

  return (
    <div className="min-h-dvh bg-gray-100 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      {/* Desktop sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={handleToggleSidebar}
        onNotifClick={() => setNotifOpen(true)}
      />

      {/* Main content — offset by sidebar width on desktop */}
      <main
        className={`transition-all duration-200 ease-in-out px-4 sm:px-6 pt-4 pb-24 sm:pb-6 ${
          sidebarCollapsed ? "sm:ml-16" : "sm:ml-60"
        }`}
      >
        <Outlet />
      </main>

      {/* Mobile bottom tab bar */}
      <MobileTabBar onNotifClick={() => setNotifOpen(true)} />

      {/* Notification slide-over */}
      {notifOpen && <NotificationPanel onClose={() => setNotifOpen(false)} />}
    </div>
  );
}
