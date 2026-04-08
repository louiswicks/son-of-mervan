// src/components/TwoFactorPage.jsx
// Shown after a successful password login when the account has 2FA enabled.
// The user must enter their authenticator-app code to complete the login.
import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { verifyTOTPLogin } from "../api/totp";
import { useAuth } from "../context/AuthContext";

export default function TwoFactorPage() {
  const navigate = useNavigate();
  const { handleLogin } = useAuth();
  const totpChallengeToken = useAuthStore((s) => s.totpChallengeToken);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  // Redirect to login if there's no pending challenge
  useEffect(() => {
    if (!totpChallengeToken) {
      navigate("/login", { replace: true });
    } else {
      inputRef.current?.focus();
    }
  }, [totpChallengeToken, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (code.trim().length < 6) return;

    setSubmitting(true);
    setError(null);
    try {
      const data = await verifyTOTPLogin(totpChallengeToken, code.trim());
      if (!data?.access_token) throw new Error("No access token returned");
      handleLogin(data.access_token);
      navigate("/budget", { replace: true });
    } catch (err) {
      setError(err.response?.data?.detail || "Invalid or expired code. Please try again.");
      setCode("");
      inputRef.current?.focus();
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    clearAuth();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center px-4 sm:px-6">
      <div className="w-full max-w-md bg-white/95 backdrop-blur rounded-2xl shadow-xl p-6 sm:p-8">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl" role="img" aria-label="lock">🔒</span>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Two-Factor Authentication</h1>
        </div>
        <p className="text-gray-600 mb-6 text-sm">
          Open your authenticator app and enter the 6-digit code for <strong>SYITB</strong>.
        </p>

        {error && (
          <div className="mb-4 rounded-lg px-4 py-3 text-[13px] sm:text-sm bg-red-50 text-red-700 border border-red-200">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="totp-code" className="block text-sm font-medium text-gray-700 mb-1">
              Authenticator code
            </label>
            <input
              id="totp-code"
              ref={inputRef}
              type="text"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-[16px] tracking-[0.4em] text-center focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition"
              placeholder="000000"
              required
            />
          </div>

          <button
            type="submit"
            disabled={submitting || code.length < 6}
            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold py-3 rounded-xl shadow-lg transition disabled:opacity-60"
          >
            {submitting ? "Verifying…" : "Verify code"}
          </button>
        </form>

        <div className="mt-4 text-center">
          <button
            onClick={handleCancel}
            className="text-sm text-gray-500 hover:text-blue-600"
          >
            Back to login
          </button>
        </div>
      </div>
    </div>
  );
}
