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
import ErrorBoundary from "./components/ErrorBoundary";

function withPageBoundary(element) {
  return <ErrorBoundary key={element.type?.name}>{element}</ErrorBoundary>;
}

export const router = createHashRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <SignUpPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  { path: "/verify-email", element: <VerifyEmailPage /> },
  { path: "/reset-password", element: <ResetPasswordPage /> },
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
      { path: "settings", element: withPageBoundary(<AccountSettings />) },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
