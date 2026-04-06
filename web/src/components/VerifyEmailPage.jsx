// src/components/VerifyEmailPage.jsx
import React, { useEffect, useState } from "react";
import { verifyEmail } from "../api/auth";

export default function VerifyEmailPage({ goToLogin }) {
  const [status, setStatus] = useState("verifying"); // verifying | ok | error
  const [msg, setMsg] = useState("");

  useEffect(() => {
    // Works for both /verify-email?token=... and #/verify-email?token=...
    const hash = window.location.hash || "";
    const tokenFromHash = new URLSearchParams(hash.split("?")[1] || "").get("token");
    const tokenFromQuery = new URLSearchParams(window.location.search).get("token");
    const token = tokenFromHash || tokenFromQuery;

    if (!token) {
      setStatus("error");
      setMsg("Missing verification token.");
      return;
    }

    (async () => {
      try {
        const data = await verifyEmail(token);
        setStatus("ok");
        setMsg(data.message || "Email verified. You can now log in.");
      } catch (e) {
        setStatus("error");
        setMsg(e.response?.data?.detail || e.message || "Verification failed.");
      }
    })();
  }, []);

  return (
    <div className="min-h-dvh bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-8 text-center">
        {status === "verifying" && (
          <h1 className="text-xl font-semibold text-gray-800">Verifying…</h1>
        )}

        {status === "ok" && (
          <>
            <h1 className="text-xl font-semibold text-green-700 mb-2">Email verified ✅</h1>
            <p className="text-gray-700 mb-6">{msg}</p>
            <button
              className="px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700"
              onClick={() => {
                window.location.hash = "";
                goToLogin?.();
              }}
            >
              Go to Login
            </button>
          </>
        )}

        {status === "error" && (
          <>
            <h1 className="text-xl font-semibold text-red-700 mb-2">Verification failed</h1>
            <p className="text-gray-700">{msg}</p>
          </>
        )}
      </div>
    </div>
  );
}
