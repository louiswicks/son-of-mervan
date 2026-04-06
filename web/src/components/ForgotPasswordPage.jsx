// src/components/ForgotPasswordPage.jsx
import React, { useState } from "react";
import { requestPasswordReset } from "../api/auth";

export default function ForgotPasswordPage({ goToLogin }) {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);
  const [isError, setIsError] = useState(false);
  const [devLink, setDevLink] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setIsError(false);
    setMessage(null);
    setDevLink(null);

    try {
      const data = await requestPasswordReset(email);
      setMessage(data.message || "If that email is registered, a reset link has been sent.");
      if (data.dev_verify_url) setDevLink(data.dev_verify_url);
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
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mb-2">Forgot password?</h1>
        <p className="text-gray-600 mb-6 text-sm">
          Enter your email address and we'll send you a link to reset your password.
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
            {devLink && (
              <div className="mt-2">
                <span className="font-semibold">[DEV] </span>
                <a href={devLink} className="underline break-all">{devLink}</a>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email address</label>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-[16px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition"
              placeholder="you@example.com"
              required
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold py-3 sm:py-3.5 rounded-xl shadow-lg transition disabled:opacity-60"
          >
            {submitting ? "Sending…" : "Send reset link"}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-gray-600">
          <button onClick={goToLogin} className="font-semibold text-blue-600 hover:text-blue-800">
            Back to login
          </button>
        </div>
      </div>
    </div>
  );
}
