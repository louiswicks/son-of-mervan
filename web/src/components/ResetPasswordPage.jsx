// src/components/ResetPasswordPage.jsx
import React, { useState } from "react";
import { confirmPasswordReset } from "../api/auth";

function getTokenFromHash() {
  // Hash looks like: #/reset-password?token=abc123
  const hash = window.location.hash || "";
  const qIndex = hash.indexOf("?");
  if (qIndex === -1) return null;
  const params = new URLSearchParams(hash.slice(qIndex + 1));
  return params.get("token");
}

export default function ResetPasswordPage({ goToLogin }) {
  const token = getTokenFromHash();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);
  const [isError, setIsError] = useState(false);
  const [success, setSuccess] = useState(false);

  if (!token) {
    return (
      <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center px-4 sm:px-6">
        <div className="w-full max-w-md bg-white/95 backdrop-blur rounded-2xl shadow-xl p-6 sm:p-8 text-center">
          <h1 className="text-xl font-bold text-gray-900 mb-3">Invalid link</h1>
          <p className="text-gray-600 mb-6 text-sm">
            This password reset link is missing or malformed. Please request a new one.
          </p>
          <button
            onClick={goToLogin}
            className="font-semibold text-blue-600 hover:text-blue-800 text-sm"
          >
            Back to login
          </button>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setIsError(true);
      setMessage("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    setIsError(false);
    setMessage(null);

    try {
      const data = await confirmPasswordReset(token, newPassword);
      setSuccess(true);
      setMessage(data.message || "Password updated successfully.");
    } catch (err) {
      setIsError(true);
      setMessage(
        err.response?.data?.detail || err.message || "Something went wrong. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center px-4 sm:px-6">
      <div className="w-full max-w-md bg-white/95 backdrop-blur rounded-2xl shadow-xl p-6 sm:p-8">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mb-2">Set new password</h1>
        <p className="text-gray-600 mb-6 text-sm">
          Choose a strong password for your account.
        </p>

        {message && (
          <div
            className={`mb-4 rounded-lg px-4 py-3 text-[13px] sm:text-sm leading-relaxed ${
              isError
                ? "bg-red-50 text-red-700 border border-red-200"
                : "bg-green-50 text-green-700 border border-green-200"
            }`}
          >
            {message}
          </div>
        )}

        {success ? (
          <div className="text-center">
            <button
              onClick={goToLogin}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold py-3 rounded-xl shadow-lg transition"
            >
              Go to login
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">New password</label>
              <input
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-[16px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition"
                placeholder="••••••••"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm password</label>
              <input
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-[16px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition"
                placeholder="••••••••"
                required
              />
            </div>

            <p className="text-xs text-gray-500">
              Must be 8+ characters with uppercase, lowercase, digit, and special character.
            </p>

            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold py-3 sm:py-3.5 rounded-xl shadow-lg transition disabled:opacity-60"
            >
              {submitting ? "Updating…" : "Update password"}
            </button>
          </form>
        )}

        {!success && (
          <div className="mt-6 text-center text-sm text-gray-600">
            <button onClick={goToLogin} className="font-semibold text-blue-600 hover:text-blue-800">
              Back to login
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
