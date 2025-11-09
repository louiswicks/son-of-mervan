// src/components/SignUpPage.jsx
import React, { useState } from "react";

const API_BASE_URL =
  import.meta?.env?.VITE_API_URL || "https://son-of-mervan-production.up.railway.app";

export default function SignUpPage({ goToLogin }) {
  const [form, setForm] = useState({ email: "", password: "", confirm: "" });
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [success, setSuccess] = useState("");
  const [devLink, setDevLink] = useState("");

  const onChange = (e) => {
    setErr("");
    setSuccess("");
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const validate = () => {
    if (!form.email || !form.password || !form.confirm) return "Please fill all fields.";
    if (form.password !== form.confirm) return "Passwords do not match.";
    if (form.password.length < 8) return "Password must be at least 8 characters.";
    const hasUpper = /[A-Z]/.test(form.password);
    const hasLower = /[a-z]/.test(form.password);
    const hasDigit = /\d/.test(form.password);
    const hasSpecial = /[^\w\s]/.test(form.password);
    if (!(hasUpper && hasLower && hasDigit && hasSpecial)) {
      return "Password must include upper, lower, number and special character.";
    }
    return "";
  };

  const submit = async (e) => {
    e.preventDefault();
    const v = validate();
    if (v) {
      setErr(v);
      return;
    }

    setLoading(true);
    setErr("");
    setSuccess("");
    setDevLink("");

    try {
      const res = await fetch(`${API_BASE_URL}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: form.email, password: form.password }),
      });
      const j = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(j.detail || "Sign up failed.");

      setSuccess("Account created. Please check your email to verify.");
      if (j.dev_verify_url) setDevLink(j.dev_verify_url);
    } catch (e) {
      setErr(e.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center p-4 sm:p-6">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-6 sm:p-8">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900 text-center mb-5 sm:mb-6">
          Create your account
        </h1>

        {err && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 text-red-700 px-4 py-3 text-[13px] sm:text-sm">
            {err}
          </div>
        )}
        {success && (
          <div className="mb-4 rounded-lg border border-green-200 bg-green-50 text-green-700 px-4 py-3 text-[13px] sm:text-sm">
            {success}
          </div>
        )}
        {devLink && (
          <div className="mb-4 text-xs text-gray-600 break-words">
            Dev mode: click to verify now →{" "}
            <a className="text-blue-600 underline break-all" href={devLink}>
              {devLink}
            </a>
          </div>
        )}

        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              name="email"
              type="email"
              value={form.email}
              onChange={onChange}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-[16px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <span className="text-xs text-gray-500">8+ chars, upper, lower, number, special</span>
            </div>
            <input
              name="password"
              type="password"
              value={form.password}
              onChange={onChange}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-[16px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="••••••••"
              autoComplete="new-password"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
            <input
              name="confirm"
              type="password"
              value={form.confirm}
              onChange={onChange}
              className="w-full px-4 py-3 border-2 border-gray-200 rounded-xl text-[16px] focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              placeholder="••••••••"
              autoComplete="new-password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold py-3 sm:py-3.5 rounded-xl shadow-lg disabled:opacity-60"
          >
            {loading ? "Creating account…" : "Sign Up"}
          </button>
        </form>

        <div className="text-center mt-5 text-sm text-gray-600">
          Already have an account?{" "}
          <button className="text-blue-600 hover:text-blue-800 font-medium" onClick={goToLogin}>
            Log in
          </button>
        </div>
      </div>
    </div>
  );
}
