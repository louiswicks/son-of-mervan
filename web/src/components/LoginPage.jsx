// src/components/LoginPage.jsx
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login, resendVerification } from "../api/auth";
import { useAuth } from "../context/AuthContext";
import { useAuthStore } from "../store/authStore";

export default function LoginPage() {
  const navigate = useNavigate();
  const { handleLogin } = useAuth();
  const setTOTPChallenge = useAuthStore((s) => s.setTOTPChallenge);
  const goToSignup = () => navigate("/register");
  const goToForgotPassword = () => navigate("/forgot-password");
  const [identifier, setIdentifier] = useState(""); // email or username
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState(null);
  const [isError, setIsError] = useState(false);
  const [showResend, setShowResend] = useState(false);
  const [resendSubmitting, setResendSubmitting] = useState(false);
  const [resendMessage, setResendMessage] = useState(null);

  const doLogin = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setIsError(false);
    setMessage(null);

    try {
      const data = await login(identifier, password);

      // 2FA gate — server returned a challenge token instead of an access token
      if (data?.requires_2fa && data?.totp_challenge_token) {
        setTOTPChallenge(data.totp_challenge_token);
        navigate("/2fa");
        return;
      }

      if (!data?.access_token) throw new Error("No access token returned");
      handleLogin(data.access_token);
      navigate("/budget");
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || "Login failed";
      setIsError(true);
      setMessage(detail);
      // Show resend button when the server says email is unverified
      if (err.response?.status === 403 && detail.toLowerCase().includes("verify")) {
        setShowResend(true);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const doResend = async () => {
    setResendSubmitting(true);
    setResendMessage(null);
    try {
      await resendVerification(identifier);
      setResendMessage("Verification email sent — check your inbox.");
      setShowResend(false);
    } catch (err) {
      setResendMessage(err.response?.data?.detail || "Failed to resend. Please try again.");
    } finally {
      setResendSubmitting(false);
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
            {showResend && (
              <div className="mt-2">
                <button
                  type="button"
                  onClick={doResend}
                  disabled={resendSubmitting}
                  className="text-xs font-semibold underline text-red-700 hover:text-red-900 disabled:opacity-50"
                  aria-label="Resend verification email"
                >
                  {resendSubmitting ? "Sending…" : "Resend verification email"}
                </button>
              </div>
            )}
          </div>
        )}

        {resendMessage && (
          <div className="mb-4 rounded-lg px-4 py-3 text-[13px] sm:text-sm leading-relaxed bg-green-50 text-green-700 border border-green-200">
            {resendMessage}
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

        <div className="mt-4 text-center">
          <button onClick={goToForgotPassword} className="text-sm text-gray-500 hover:text-blue-600">
            Forgot password?
          </button>
        </div>

        <div className="mt-4 text-center text-sm text-gray-600">
          New here?{" "}
          <button onClick={goToSignup} className="font-semibold text-blue-600 hover:text-blue-800">
            Create an account
          </button>
        </div>

        <div className="mt-2 text-center">
          <button
            type="button"
            onClick={() => setShowResend((prev) => !prev)}
            className="text-xs text-gray-400 hover:text-gray-600"
            aria-label="Resend verification email link"
          >
            Didn't receive your verification email?
          </button>
          {showResend && !message && (
            <div className="mt-2 flex flex-col items-center gap-2">
              <p className="text-xs text-gray-500">Enter your email and we'll send a new link.</p>
              <button
                type="button"
                onClick={doResend}
                disabled={resendSubmitting || !identifier}
                className="text-xs font-semibold text-blue-600 hover:text-blue-800 underline disabled:opacity-50"
              >
                {resendSubmitting ? "Sending…" : "Send verification email"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
