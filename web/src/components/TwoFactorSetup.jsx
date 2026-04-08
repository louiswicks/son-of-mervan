// src/components/TwoFactorSetup.jsx
// Settings panel component for enabling and disabling TOTP 2FA.
import React, { useState } from "react";
import toast from "react-hot-toast";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTOTPStatus, setupTOTP, confirmTOTP, disableTOTP } from "../api/totp";

export default function TwoFactorSetup() {
  const queryClient = useQueryClient();

  const { data: status, isLoading } = useQuery({
    queryKey: ["totp-status"],
    queryFn: getTOTPStatus,
  });

  const enabled = status?.enabled ?? false;

  // Setup flow state
  const [setupData, setSetupData] = useState(null); // { provisioning_uri, qr_code_b64 }
  const [confirmCode, setConfirmCode] = useState("");
  const [setupError, setSetupError] = useState(null);

  // Disable flow state
  const [showDisable, setShowDisable] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");
  const [disableError, setDisableError] = useState(null);

  const setupMutation = useMutation({
    mutationFn: setupTOTP,
    onSuccess: (data) => {
      setSetupData(data);
      setSetupError(null);
    },
    onError: (err) => {
      setSetupError(err.response?.data?.detail || "Failed to start 2FA setup.");
    },
  });

  const confirmMutation = useMutation({
    mutationFn: (code) => confirmTOTP(code),
    onSuccess: () => {
      toast.success("Two-factor authentication enabled!");
      setSetupData(null);
      setConfirmCode("");
      queryClient.invalidateQueries({ queryKey: ["totp-status"] });
    },
    onError: (err) => {
      setSetupError(err.response?.data?.detail || "Invalid code. Please try again.");
    },
  });

  const disableMutation = useMutation({
    mutationFn: ({ password, code }) => disableTOTP(password, code),
    onSuccess: () => {
      toast.success("Two-factor authentication disabled.");
      setShowDisable(false);
      setDisablePassword("");
      setDisableCode("");
      setDisableError(null);
      queryClient.invalidateQueries({ queryKey: ["totp-status"] });
    },
    onError: (err) => {
      setDisableError(err.response?.data?.detail || "Failed to disable 2FA. Check your password and code.");
    },
  });

  if (isLoading) return <p className="text-sm text-gray-500">Loading 2FA status…</p>;

  // ── Already enabled — show disable panel ──────────────────────────────────
  if (enabled) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            ✓ Enabled
          </span>
          <span className="text-sm text-gray-600">Your account is protected with an authenticator app.</span>
        </div>

        {!showDisable ? (
          <button
            onClick={() => setShowDisable(true)}
            className="text-sm text-red-600 hover:text-red-800 font-medium"
          >
            Disable 2FA
          </button>
        ) : (
          <div className="border border-red-200 rounded-xl p-4 bg-red-50 space-y-3">
            <p className="text-sm font-medium text-red-700">
              Confirm your identity to disable 2FA
            </p>
            {disableError && (
              <p className="text-xs text-red-600">{disableError}</p>
            )}
            <input
              type="password"
              placeholder="Current password"
              autoComplete="current-password"
              value={disablePassword}
              onChange={(e) => setDisablePassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-red-400 focus:border-red-400"
            />
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              placeholder="Authenticator code"
              autoComplete="one-time-code"
              value={disableCode}
              onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, ""))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm tracking-widest text-center focus:ring-2 focus:ring-red-400 focus:border-red-400"
            />
            <div className="flex gap-2">
              <button
                onClick={() => disableMutation.mutate({ password: disablePassword, code: disableCode })}
                disabled={disableMutation.isPending || !disablePassword || disableCode.length < 6}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition disabled:opacity-60"
              >
                {disableMutation.isPending ? "Disabling…" : "Disable 2FA"}
              </button>
              <button
                onClick={() => { setShowDisable(false); setDisableError(null); setDisablePassword(""); setDisableCode(""); }}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Not enabled — show setup flow ─────────────────────────────────────────
  if (!setupData) {
    return (
      <div className="space-y-3">
        <p className="text-sm text-gray-600">
          Add an extra layer of security. You'll be asked for a code from your authenticator app each time you log in.
        </p>
        <button
          onClick={() => setupMutation.mutate()}
          disabled={setupMutation.isPending}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg transition disabled:opacity-60"
        >
          {setupMutation.isPending ? "Generating…" : "Set up 2FA"}
        </button>
        {setupError && <p className="text-xs text-red-600">{setupError}</p>}
      </div>
    );
  }

  // ── QR code + confirmation step ───────────────────────────────────────────
  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-700 font-medium">
        1. Scan this QR code with your authenticator app (Google Authenticator, Authy, 1Password, etc.):
      </p>

      <div className="flex justify-center">
        <img
          src={`data:image/png;base64,${setupData.qr_code_b64}`}
          alt="TOTP QR code"
          className="w-48 h-48 border border-gray-200 rounded-xl"
        />
      </div>

      <details className="text-xs text-gray-500">
        <summary className="cursor-pointer hover:text-gray-700">Can't scan? Enter manually</summary>
        <code className="block mt-1 break-all font-mono bg-gray-100 rounded p-2">
          {setupData.provisioning_uri}
        </code>
      </details>

      <p className="text-sm text-gray-700 font-medium">
        2. Enter the 6-digit code from your app to confirm setup:
      </p>

      {setupError && <p className="text-xs text-red-600">{setupError}</p>}

      <div className="flex gap-2">
        <input
          type="text"
          inputMode="numeric"
          maxLength={6}
          placeholder="000000"
          autoComplete="one-time-code"
          value={confirmCode}
          onChange={(e) => setConfirmCode(e.target.value.replace(/\D/g, ""))}
          className="flex-1 px-3 py-2 border-2 border-gray-200 rounded-lg text-sm tracking-widest text-center focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <button
          onClick={() => confirmMutation.mutate(confirmCode)}
          disabled={confirmMutation.isPending || confirmCode.length < 6}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg transition disabled:opacity-60"
        >
          {confirmMutation.isPending ? "Verifying…" : "Enable 2FA"}
        </button>
      </div>

      <button
        onClick={() => { setSetupData(null); setConfirmCode(""); setSetupError(null); }}
        className="text-xs text-gray-500 hover:text-gray-700"
      >
        Cancel setup
      </button>
    </div>
  );
}
