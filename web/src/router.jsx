// src/router.jsx
import React, { Suspense, lazy } from "react";
import { createHashRouter, Navigate } from "react-router-dom";
import AuthGuard from "./components/AuthGuard";
import AsyncBoundary from "./components/AsyncBoundary";
import ErrorBoundary from "./components/ErrorBoundary";

// Eagerly-loaded infrastructure (needed before any lazy chunk resolves)
// AuthGuard, AsyncBoundary, ErrorBoundary are intentionally NOT lazy.

// Public routes — lazy loaded
const LoginPage = lazy(() => import("./components/LoginPage"));
const SignUpPage = lazy(() => import("./components/SignUpPage"));
const ForgotPasswordPage = lazy(() => import("./components/ForgotPasswordPage"));
const VerifyEmailPage = lazy(() => import("./components/VerifyEmailPage"));
const ResetPasswordPage = lazy(() => import("./components/ResetPasswordPage"));
const OnboardingWizard = lazy(() => import("./components/OnboardingWizard"));

// Protected routes — lazy loaded
const SonOfMervan = lazy(() => import("./components/SonOfMervan"));
const MonthlyTracker = lazy(() => import("./components/MonthlyTracker"));
const AnnualOverview = lazy(() => import("./components/AnnualOverview"));
const AccountSettings = lazy(() => import("./components/AccountSettings"));
const RecurringExpensesPage = lazy(() => import("./components/RecurringExpensesPage"));
const SavingsGoalsPage = lazy(() => import("./components/SavingsGoalsPage"));
const BudgetAlertsPage = lazy(() => import("./components/BudgetAlertsPage"));
const InsightsPage = lazy(() => import("./components/InsightsPage"));
const ScenarioPlannerPage = lazy(() => import("./components/ScenarioPlannerPage"));
const InvestmentsPage = lazy(() => import("./components/InvestmentsPage"));
const CalendarPage = lazy(() => import("./components/CalendarPage"));
const TaxExportPage = lazy(() => import("./components/TaxExportPage"));
const HouseholdPage = lazy(() => import("./components/HouseholdPage"));
const CategoriesPage = lazy(() => import("./components/CategoriesPage"));
const ImportPage = lazy(() => import("./components/ImportPage"));
const ForecastPage = lazy(() => import("./components/ForecastPage"));
const DebtPayoffPage = lazy(() => import("./components/DebtPayoffPage"));
const NetWorthPage = lazy(() => import("./components/NetWorthPage"));

// Minimal spinner for public-route Suspense fallbacks (no auth context available)
function PageSpinner() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
      }}
      role="status"
      aria-label="Loading page"
    >
      <div
        style={{
          width: 40,
          height: 40,
          border: "4px solid #e5e7eb",
          borderTopColor: "#6366f1",
          borderRadius: "50%",
          animation: "spin 0.7s linear infinite",
        }}
      />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

// Protected routes: ErrorBoundary + Suspense (AsyncBoundary) per page
function withPageBoundary(element) {
  return (
    <AsyncBoundary key={element.type?.displayName || element.type?._payload?.value?.name}>
      {element}
    </AsyncBoundary>
  );
}

// Public lazy routes: simple Suspense spinner (no ErrorBoundary — keep public pages resilient)
function withPublicSuspense(element) {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageSpinner />}>{element}</Suspense>
    </ErrorBoundary>
  );
}

export const router = createHashRouter([
  { path: "/login", element: withPublicSuspense(<LoginPage />) },
  { path: "/register", element: withPublicSuspense(<SignUpPage />) },
  { path: "/forgot-password", element: withPublicSuspense(<ForgotPasswordPage />) },
  { path: "/verify-email", element: withPublicSuspense(<VerifyEmailPage />) },
  { path: "/reset-password", element: withPublicSuspense(<ResetPasswordPage />) },
  { path: "/onboarding", element: withPublicSuspense(<OnboardingWizard />) },
  {
    path: "/",
    element: <AuthGuard />,
    children: [
      { index: true, element: <Navigate to="/budget" replace /> },
      { path: "budget", element: withPageBoundary(<SonOfMervan />) },
      { path: "expenses", element: withPageBoundary(<MonthlyTracker />) },
      { path: "annual", element: withPageBoundary(<AnnualOverview />) },
      { path: "recurring", element: withPageBoundary(<RecurringExpensesPage />) },
      { path: "savings", element: withPageBoundary(<SavingsGoalsPage />) },
      { path: "alerts", element: withPageBoundary(<BudgetAlertsPage />) },
      { path: "insights", element: withPageBoundary(<InsightsPage />) },
      { path: "scenarios", element: withPageBoundary(<ScenarioPlannerPage />) },
      { path: "investments", element: withPageBoundary(<InvestmentsPage />) },
      { path: "calendar", element: withPageBoundary(<CalendarPage />) },
      { path: "tax", element: withPageBoundary(<TaxExportPage />) },
      { path: "household", element: withPageBoundary(<HouseholdPage />) },
      { path: "categories", element: withPageBoundary(<CategoriesPage />) },
      { path: "import", element: withPageBoundary(<ImportPage />) },
      { path: "forecast", element: withPageBoundary(<ForecastPage />) },
      { path: "debts", element: withPageBoundary(<DebtPayoffPage />) },
      { path: "net-worth", element: withPageBoundary(<NetWorthPage />) },
      { path: "settings", element: withPageBoundary(<AccountSettings />) },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
