// src/components/HouseholdPage.jsx
import React, { useState } from "react";
import { Users, UserPlus, UserMinus, Home, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import toast from "react-hot-toast";
import {
  useMyHousehold,
  useCreateHousehold,
  useInviteMember,
  useRemoveMember,
  useDissolveHousehold,
  useHouseholdBudget,
} from "../hooks/useHousehold";
import { useProfile } from "../hooks/useProfile";
import ConfirmModal from "./ConfirmModal";
import { SkeletonCard } from "./Skeleton";
import PageWrapper from "./PageWrapper";
import Card from "./Card";

const CURRENT_MONTH = new Date().toISOString().slice(0, 7);

function fmt(n) {
  return Number(n || 0).toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function RoleBadge({ role }) {
  if (role === "owner") {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300">
        Owner
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
      Member
    </span>
  );
}

// ---------- No household — create or discover ----------

function NoHousehold({ onCreate }) {
  const [name, setName] = useState("");
  const { mutate, isPending } = useCreateHousehold();

  function handleCreate(e) {
    e.preventDefault();
    if (!name.trim()) return;
    mutate(name.trim(), {
      onSuccess: () => toast.success("Household created!"),
      onError: (err) => toast.error(err?.response?.data?.detail || "Failed to create household"),
    });
  }

  return (
    <div className="max-w-lg mx-auto mt-12 text-center">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-indigo-100 dark:bg-indigo-900/40 mb-4">
        <Home size={32} className="text-indigo-600 dark:text-indigo-400" />
      </div>
      <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
        No household yet
      </h2>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-8">
        Create a household to share your budget with a partner or housemates. Once created, you can
        invite members by email.
      </p>

      <form onSubmit={handleCreate} className="flex gap-2">
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Smith Family Budget"
          className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          type="submit"
          disabled={isPending || !name.trim()}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {isPending ? "Creating…" : "Create"}
        </button>
      </form>
    </div>
  );
}

// ---------- Invite panel ----------

function InvitePanel({ pendingInvites }) {
  const [email, setEmail] = useState("");
  const { mutate, isPending } = useInviteMember();

  function handleInvite(e) {
    e.preventDefault();
    if (!email.trim()) return;
    mutate(email.trim().toLowerCase(), {
      onSuccess: () => {
        toast.success(`Invite sent to ${email}`);
        setEmail("");
      },
      onError: (err) => toast.error(err?.response?.data?.detail || "Failed to send invite"),
    });
  }

  return (
    <Card>
      <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
        <UserPlus size={16} className="text-indigo-500" />
        Invite a member
      </h3>
      <form onSubmit={handleInvite} className="flex gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="member@example.com"
          className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          type="submit"
          disabled={isPending || !email.trim()}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
        >
          {isPending ? "Sending…" : "Invite"}
        </button>
      </form>

      {pendingInvites.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Pending invites:</p>
          <ul className="space-y-1">
            {pendingInvites.map((inv) => (
              <li key={inv} className="text-xs text-gray-600 dark:text-gray-300 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 inline-block" />
                {inv}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

// ---------- Budget view ----------

function BudgetView({ householdId }) {
  const [month, setMonth] = useState(CURRENT_MONTH);
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useHouseholdBudget(open ? month : null);

  return (
    <Card className="!p-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between p-5 text-left"
      >
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Combined budget view</h3>
        {open ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
      </button>

      {open && (
        <div className="px-5 pb-5">
          <div className="flex items-center gap-2 mb-4">
            <input
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-1.5 text-sm text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          {isLoading ? (
            <SkeletonCard />
          ) : data ? (
            <>
              {/* Combined totals */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                {[
                  ["Combined Income", data.combined_salary_planned, data.combined_salary_actual],
                  ["Combined Expenses", data.combined_expenses_planned, data.combined_expenses_actual],
                  ["Remaining", data.combined_remaining_planned, data.combined_remaining_actual],
                ].map(([label, planned, actual]) => (
                  <div key={label} className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{label}</p>
                    <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">£{fmt(actual)}</p>
                    <p className="text-xs text-gray-400">plan: £{fmt(planned)}</p>
                  </div>
                ))}
              </div>

              {/* Per-member breakdown */}
              <div className="space-y-3">
                {data.members.map((m) => (
                  <div key={m.user_id} className="border border-gray-200 dark:border-gray-600 rounded-lg p-3">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-7 h-7 rounded-full bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase">
                        {(m.username || m.email).slice(0, 1)}
                      </div>
                      <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                        {m.username || m.email}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <p className="text-gray-500 dark:text-gray-400">Income</p>
                        <p className="font-medium text-gray-900 dark:text-gray-100">£{fmt(m.salary_actual)}</p>
                      </div>
                      <div>
                        <p className="text-gray-500 dark:text-gray-400">Expenses</p>
                        <p className="font-medium text-gray-900 dark:text-gray-100">£{fmt(m.total_expenses_actual)}</p>
                      </div>
                      <div>
                        <p className="text-gray-500 dark:text-gray-400">Remaining</p>
                        <p className={`font-medium ${m.remaining_actual >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
                          £{fmt(m.remaining_actual)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">No data for this month.</p>
          )}
        </div>
      )}
    </Card>
  );
}

// ---------- Main page ----------

export default function HouseholdPage() {
  const { data: household, isLoading, error } = useMyHousehold();
  const { data: profile } = useProfile();
  const { mutate: removeMember } = useRemoveMember();
  const { mutate: dissolve } = useDissolveHousehold();
  const [dissolveOpen, setDissolveOpen] = useState(false);
  const [removeTarget, setRemoveTarget] = useState(null);

  const isOwner = household && profile && household.owner_id === profile.id;

  if (isLoading) {
    return (
      <PageWrapper className="max-w-2xl">
        <SkeletonCard />
        <SkeletonCard />
      </PageWrapper>
    );
  }

  if (error?.response?.status === 404 || !household) {
    return <NoHousehold />;
  }

  if (error) {
    return (
      <PageWrapper className="max-w-2xl">
        <p className="text-red-500">Failed to load household. Please refresh.</p>
      </PageWrapper>
    );
  }

  function handleRemoveMember(userId) {
    removeMember(userId, {
      onSuccess: () => toast.success("Member removed"),
      onError: (err) => toast.error(err?.response?.data?.detail || "Failed to remove member"),
    });
    setRemoveTarget(null);
  }

  function handleDissolve() {
    dissolve(undefined, {
      onSuccess: () => toast.success("Household dissolved"),
      onError: (err) => toast.error(err?.response?.data?.detail || "Failed to dissolve household"),
    });
    setDissolveOpen(false);
  }

  return (
    <PageWrapper className="max-w-2xl">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center">
          <Users size={20} className="text-indigo-600 dark:text-indigo-400" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">{household.name}</h1>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {household.members.length} member{household.members.length !== 1 ? "s" : ""}
          </p>
        </div>
      </div>

      {/* Members list */}
      <Card>
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Members</h3>
        <ul className="divide-y divide-gray-100 dark:divide-gray-700">
          {household.members.map((m) => (
            <li key={m.user_id} className="flex items-center justify-between py-2.5">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase">
                  {(m.username || m.email).slice(0, 1)}
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {m.username || m.email}
                  </p>
                  {m.username && (
                    <p className="text-xs text-gray-400">{m.email}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <RoleBadge role={m.role} />
                {isOwner && m.role !== "owner" && (
                  <button
                    onClick={() => setRemoveTarget(m)}
                    className="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                    title="Remove member"
                  >
                    <UserMinus size={14} />
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </Card>

      {/* Invite — owner only */}
      {isOwner && <InvitePanel pendingInvites={household.pending_invites} />}

      {/* Budget view */}
      <BudgetView />

      {/* Danger zone — owner only */}
      {isOwner && (
        <Card className="border-red-200 dark:border-red-900/40">
          <h3 className="font-semibold text-red-600 dark:text-red-400 mb-1 flex items-center gap-2">
            <Trash2 size={16} />
            Danger zone
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
            Dissolving the household permanently removes all members' access to the shared budget view.
            Individual budgets are not affected.
          </p>
          <button
            onClick={() => setDissolveOpen(true)}
            className="px-3 py-1.5 rounded-lg border border-red-300 text-red-600 text-sm font-medium hover:bg-red-50 dark:hover:bg-red-900/20"
          >
            Dissolve household
          </button>
        </Card>
      )}

      {/* Confirm dissolve */}
      {dissolveOpen && (
        <ConfirmModal
          title="Dissolve household?"
          message="This will remove all members from the household. Individual budgets are unaffected. This cannot be undone."
          confirmLabel="Dissolve"
          onConfirm={handleDissolve}
          onCancel={() => setDissolveOpen(false)}
        />
      )}

      {/* Confirm remove member */}
      {removeTarget && (
        <ConfirmModal
          title="Remove member?"
          message={`Remove ${removeTarget.username || removeTarget.email} from the household? They can be re-invited later.`}
          confirmLabel="Remove"
          onConfirm={() => handleRemoveMember(removeTarget.user_id)}
          onCancel={() => setRemoveTarget(null)}
        />
      )}
    </PageWrapper>
  );
}
