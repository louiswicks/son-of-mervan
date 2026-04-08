// src/router.jsx
import React from "react";
import { createHashRouter, Navigate } from "react-router-dom";
import AuthGuard from "./components/AuthGuard";
import LoginPage from "./components/LoginPage";
import SignUpPage from "./components/SignUpPage";
import ForgotPasswordPage from "./components/ForgotPasswordPage";
import VerifyEmailPage from "./components/VerifyEmailPage";
import ResetPasswordPage from "./components/ResetPasswordPage";
import SonOfMervan from "./components/SonOfMervan";
import MonthlyTracker from "./components/MonthlyTracker";
import AnnualOverview from "./components/AnnualOverview";
import AccountSettings from "./components/AccountSettings";
import RecurringExpensesPage from "./components/RecurringExpensesPage";
import SavingsGoalsPage from "./components/SavingsGoalsPage";
import BudgetAlertsPage from "./components/BudgetAlertsPage";
import InsightsPage from "./components/InsightsPage";
import ScenarioPlannerPage from "./components/ScenarioPlannerPage";
import InvestmentsPage from "./components/InvestmentsPage";
import CalendarPage from "./components/CalendarPage";
import TaxExportPage from "./components/TaxExportPage";
import HouseholdPage from "./components/HouseholdPage";
import CategoriesPage from "./components/CategoriesPage";
import ImportPage from "./components/ImportPage";
import ForecastPage from "./components/ForecastPage";
import ErrorBoundary from "./components/ErrorBoundary";
import OnboardingWizard from "./components/OnboardingWizard";

function withPageBoundary(element) {
  return <ErrorBoundary key={element.type?.name}>{element}</ErrorBoundary>;
}

export const router = createHashRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <SignUpPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/verify-email", element: <VerifyEmailPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
  { path: "/onboarding", element: <OnboardingWizard /> },
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
      { path: "settings", element: withPageBoundary(<AccountSettings />) },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
