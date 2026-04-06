import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { useAuth } from "../context/AuthContext";
import { useProfile, useUpdateProfile, useChangePassword, useDeleteAccount } from "../hooks/useProfile";
import { useCurrencies } from "../hooks/useCurrency";

function Section({ title, children }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mb-6">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      </div>
      <div className="px-6 py-5">{children}</div>
    </div>
  );
}

export default function AccountSettings() {
  const navigate = useNavigate();
  const { handleLogout } = useAuth();

  const { data: profile, isLoading: profileLoading } = useProfile();
  const updateProfileMutation = useUpdateProfile();
  const changePasswordMutation = useChangePassword();
  const deleteAccountMutation = useDeleteAccount();

  const { data: currencies = [] } = useCurrencies();

  const [usernameInput, setUsernameInput] = useState("");
  const [baseCurrencyInput, setBaseCurrencyInput] = useState("GBP");
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [deleteConfirmText, setDeleteConfirmText] = useState("");

  // Sync inputs when profile loads
  useEffect(() => {
    if (profile?.username !== undefined) {
      setUsernameInput(profile.username || "");
    }
    if (profile?.base_currency) {
      setBaseCurrencyInput(profile.base_currency);
    }
  }, [profile]);

  async function handleProfileSave(e) {
    e.preventDefault();
    updateProfileMutation.mutate({ username: usernameInput || null, base_currency: baseCurrencyInput });
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    if (newPw !== confirmPw) {
      toast.error("New passwords do not match.");
      return;
    }
    changePasswordMutation.mutate(
      { currentPw, newPw },
      {
        onSuccess: () => {
          setCurrentPw("");
          setNewPw("");
          setConfirmPw("");
        },
      },
    );
  }

  async function handleDeleteAccount() {
    if (deleteConfirmText !== "DELETE") return;
    deleteAccountMutation.mutate(undefined, {
      onSuccess: async (data) => {
        toast.success(data?.message || "Account scheduled for deletion.");
        setTimeout(async () => {
          await handleLogout();
          navigate("/login");
        }, 2500);
      },
    });
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Account Settings</h1>

      {/* Profile */}
      <Section title="Profile">
        <form onSubmit={handleProfileSave} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={profileLoading ? "" : (profile?.email || "")}
              disabled
              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed"
              placeholder={profileLoading ? "Loading…" : ""}
            />
            <p className="text-xs text-gray-400 mt-1">Email cannot be changed.</p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input
              type="text"
              value={usernameInput}
              onChange={(e) => setUsernameInput(e.target.value)}
              placeholder="Optional display name"
              maxLength={64}
              disabled={profileLoading}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-60"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Base Currency</label>
            <select
              value={baseCurrencyInput}
              onChange={(e) => setBaseCurrencyInput(e.target.value)}
              disabled={profileLoading || currencies.length === 0}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-60"
            >
              {currencies.length === 0 ? (
                <option value={baseCurrencyInput}>{baseCurrencyInput}</option>
              ) : (
                currencies.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.symbol} {c.code} — {c.name}
                  </option>
                ))
              )}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              All totals and new expenses will use this currency by default.
            </p>
          </div>
          <button
            type="submit"
            disabled={updateProfileMutation.isPending || profileLoading}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {updateProfileMutation.isPending ? "Saving…" : "Save Profile"}
          </button>
        </form>
      </Section>

      {/* Security */}
      <Section title="Security">
        <form onSubmit={handleChangePassword} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Current Password</label>
            <input
              type="password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              required
              autoComplete="current-password"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
            <input
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
              autoComplete="new-password"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">
              Min 8 chars — must include uppercase, lowercase, digit, and special character.
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
            <input
              type="password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              required
              autoComplete="new-password"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={changePasswordMutation.isPending}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {changePasswordMutation.isPending ? "Updating…" : "Change Password"}
          </button>
        </form>
      </Section>

      {/* Danger Zone */}
      <Section title="Danger Zone">
        <div className="space-y-4">
          <p className="text-sm text-gray-600">
            Deleting your account will schedule all your data for permanent removal after{" "}
            <strong>30 days</strong>. This action cannot be undone. You will be logged out immediately.
          </p>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Type <span className="font-mono font-bold">DELETE</span> to confirm
            </label>
            <input
              type="text"
              value={deleteConfirmText}
              onChange={(e) => setDeleteConfirmText(e.target.value)}
              placeholder="DELETE"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-red-500 focus:border-red-500"
            />
          </div>
          <button
            onClick={handleDeleteAccount}
            disabled={deleteConfirmText !== "DELETE" || deleteAccountMutation.isPending}
            className="bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {deleteAccountMutation.isPending ? "Deleting…" : "Delete My Account"}
          </button>
        </div>
      </Section>
    </div>
  );
}
