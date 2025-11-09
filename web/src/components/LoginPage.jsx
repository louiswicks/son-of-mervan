// src/components/LoginPage.jsx
import React, { useState } from "react";

const API_BASE_URL =
  import.meta?.env?.VITE_API_URL || "https://son-of-mervan-production.up.railway.app";

export default function LoginPage({ onLogin, goToSignup }) {
  const [identifier, setIdentifier] = useState(""); // email or username
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);
  const [isError, setIsError] = useState(false);

  const doLogin = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setIsError(false);
    setMessage(null);

    try {
      const res = await fetch(`${API_BASE_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password }),
      });

      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || "Login failed");
      if (!body?.access_token) throw new Error("No access token returned");

      onLogin?.(body.access_token);
    } catch (err) {
      setIsError(true);
      setMessage(err.message || "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center px-4 sm:px-6">
      <div className="w-full max-w-md bg-white/95 backdrop-blur rounded-2xl shadow-xl p-6 sm:p-8">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 mb-2 sm:mb-3">Welcome back</h1>
        <p className="text-gray-600 mb-6">Use your credentials to access SYITB.</p>

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

        <form onSubmit={doLogin} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email or username</label>
            <input
              type="text"
              autoComplete="username"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-[16px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition"
              placeholder="you@example.com or yourname"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-[16px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition"
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold py-3 sm:py-3.5 rounded-xl shadow-lg transition disabled:opacity-60"
          >
            {submitting ? "Logging in…" : "Log in"}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-gray-600">
          New here?{" "}
          <button onClick={goToSignup} className="font-semibold text-blue-600 hover:text-blue-800">
            Create an account
          </button>
        </div>
      </div>
    </div>
  );
}
