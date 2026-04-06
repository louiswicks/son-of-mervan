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
      { path: "budget", element: <SonOfMervan /> },
      { path: "expenses", element: <MonthlyTracker /> },
      { path: "annual", element: <AnnualOverview /> },
      { path: "settings", element: <AccountSettings /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
