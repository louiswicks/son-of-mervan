import React, { useState, useEffect } from "react";

const API_BASE_URL = "https://son-of-mervan-production.up.railway.app";

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

function StatusBanner({ type, message }) {
  if (!message) return null;
  const styles =
    type === "success"
      ? "bg-green-50 border-green-200 text-green-800"
      : "bg-red-50 border-red-200 text-red-800";
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm mb-4 ${styles}`}>
      {message}
    </div>
  );
}

export default function AccountSettings({ token, onLogout }) {
  const [profile, setProfile] = useState({ email: "", username: "" });
  const [usernameInput, setUsernameInput] = useState("");
  const [profileStatus, setProfileStatus] = useState({ type: "", message: "" });
  const [profileSaving, setProfileSaving] = useState(false);

  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [pwStatus, setPwStatus] = useState({ type: "", message: "" });
  const [pwSaving, setPwSaving] = useState(false);

  const [deleteConfirmText, setDeleteConfirmText] = useState("");
  const [deleteStatus, setDeleteStatus] = useState({ type: "", message: "" });
  const [deleteInFlight, setDeleteInFlight] = useState(false);

  const authHeaders = { Authorization: `Bearer ${token}` };

  // Load profile on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/users/me`, {
          headers: authHeaders,
        });
        if (res.ok) {
          const data = await res.json();
          setProfile(data);
          setUsernameInput(data.username || "");
        }
      } catch {
        // silently fail — non-critical
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleProfileSave(e) {
    e.preventDefault();
    setProfileSaving(true);
    setProfileStatus({ type: "", message: "" });
    try {
      const res = await fetch(`${API_BASE_URL}/users/me`, {
        method: "PUT",
        headers: { ...authHeaders, "Content-Type": "application/json" },
        body: JSON.stringify({ username: usernameInput || null }),
      });
      const data = await res.json();
      if (res.ok) {
        setProfile(data);
        setProfileStatus({ type: "success", message: "Profile updated." });
      } else {
        setProfileStatus({ type: "error", message: data.detail || "Update failed." });
      }
    } catch {
      setProfileStatus({ type: "error", message: "Network error. Please try again." });
    } finally {
      setProfileSaving(false);
    }
  }

  async function handleChangePassword(e) {
    e.preventDefault();
    if (newPw !== confirmPw) {
      setPwStatus({ type: "error", message: "New passwords do not match." });
      return;
    }
    setPwSaving(true);
    setPwStatus({ type: "", message: "" });
    try {
      const res = await fetch(`${API_BASE_URL}/users/me/password`, {
        method: "PUT",
        headers: { ...authHeaders, "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
      });
      const data = await res.json();
      if (res.ok) {
        setPwStatus({ type: "success", message: "Password changed successfully." });
        setCurrentPw("");
        setNewPw("");
        setConfirmPw("");
      } else {
        const msg =
          data.detail ||
          (Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join(" ") : "Update failed.");
        setPwStatus({ type: "error", message: msg });
      }
    } catch {
      setPwStatus({ type: "error", message: "Network error. Please try again." });
    } finally {
      setPwSaving(false);
    }
  }

  async function handleDeleteAccount() {
    if (deleteConfirmText !== "DELETE") return;
    setDeleteInFlight(true);
    setDeleteStatus({ type: "", message: "" });
    try {
      const res = await fetch(`${API_BASE_URL}/users/me`, {
        method: "DELETE",
        headers: authHeaders,
        credentials: "include",
      });
      const data = await res.json();
      if (res.ok) {
        setDeleteStatus({ type: "success", message: data.message });
        // Give user a moment to read the message, then log out
        setTimeout(() => {
          if (onLogout) onLogout();
        }, 2500);
      } else {
        setDeleteStatus({ type: "error", message: data.detail || "Deletion failed." });
        setDeleteInFlight(false);
      }
    } catch {
      setDeleteStatus({ type: "error", message: "Network error. Please try again." });
      setDeleteInFlight(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Account Settings</h1>

      {/* Profile */}
      <Section title="Profile">
        <form onSubmit={handleProfileSave} className="space-y-4">
          <StatusBanner {...profileStatus} />
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={profile.email}
              disabled
              className="w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-500 cursor-not-allowed"
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
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <button
            type="submit"
            disabled={profileSaving}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {profileSaving ? "Saving…" : "Save Profile"}
          </button>
        </form>
      </Section>

      {/* Security */}
      <Section title="Security">
        <form onSubmit={handleChangePassword} className="space-y-4">
          <StatusBanner {...pwStatus} />
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
            disabled={pwSaving}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {pwSaving ? "Updating…" : "Change Password"}
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
          <StatusBanner {...deleteStatus} />
          {!deleteStatus.message && (
            <>
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
                disabled={deleteConfirmText !== "DELETE" || deleteInFlight}
                className="bg-red-600 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg text-sm font-medium"
              >
                {deleteInFlight ? "Deleting…" : "Delete My Account"}
              </button>
            </>
          )}
        </div>
      </Section>
    </div>
  );
}
