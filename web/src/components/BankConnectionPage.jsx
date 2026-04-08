import React, { useState } from "react";
import {
  Landmark,
  RefreshCw,
  Unlink,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import {
  useConnections,
  useConnectBank,
  useSyncTransactions,
  useDisconnectBank,
  useReviewDraft,
  useConfirmAllDrafts,
  useDrafts,
} from "../hooks/useBanking";

// -------------------- Helpers --------------------

function fmtDate(str) {
  if (!str) return "—";
  return new Date(str).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtAmount(amount, currency = "GBP") {
  if (amount == null) return "—";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}

// -------------------- Confirm Modal --------------------

function ConfirmModal({ title, message, onConfirm, onCancel }) {
  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40" aria-hidden="true" />
      <div
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
      >
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl max-w-sm w-full p-6">
          <div className="flex items-start gap-3 mb-4">
            <AlertTriangle
              size={22}
              className="text-red-500 flex-shrink-0 mt-0.5"
              aria-hidden="true"
            />
            <div>
              <h2
                id="confirm-modal-title"
                className="font-semibold text-gray-900 dark:text-white"
              >
                {title}
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{message}</p>
            </div>
          </div>
          <div className="flex gap-3 justify-end">
            <button
              onClick={onCancel}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors min-h-[40px]"
            >
              Cancel
            </button>
            <button
              onClick={onConfirm}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors min-h-[40px]"
            >
              Disconnect
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

// -------------------- Category Picker (inline) --------------------

const CATEGORIES = [
  "Housing",
  "Transportation",
  "Food",
  "Utilities",
  "Insurance",
  "Healthcare",
  "Entertainment",
  "Other",
];

// -------------------- Draft Row --------------------

function DraftRow({ draft }) {
  const review = useReviewDraft();
  const [category, setCategory] = useState(draft.suggested_category || "Other");

  return (
    <tr className="border-t border-gray-100 dark:border-gray-800">
      <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100 max-w-[180px] truncate">
        {draft.description || "—"}
      </td>
      <td className="px-4 py-3 text-sm text-right font-mono text-gray-900 dark:text-gray-100 whitespace-nowrap">
        {fmtAmount(draft.amount, draft.currency)}
      </td>
      <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">
        {draft.transaction_date || "—"}
      </td>
      <td className="px-4 py-3">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="text-sm border border-gray-300 dark:border-gray-600 rounded-lg px-2 py-1.5 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[36px]"
          aria-label="Category"
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => review.mutate({ id: draft.id, action: "confirm", category })}
            disabled={review.isPending}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors min-h-[36px]"
            aria-label="Confirm transaction"
          >
            <CheckCircle size={14} aria-hidden="true" />
            Confirm
          </button>
          <button
            onClick={() => review.mutate({ id: draft.id, action: "reject" })}
            disabled={review.isPending}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-red-50 dark:hover:bg-red-900/20 hover:text-red-600 dark:hover:text-red-400 disabled:opacity-50 transition-colors min-h-[36px]"
            aria-label="Reject transaction"
          >
            <XCircle size={14} aria-hidden="true" />
            Reject
          </button>
        </div>
      </td>
    </tr>
  );
}

// -------------------- Drafts Panel --------------------

function DraftsPanel() {
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 25;
  const { data, isLoading } = useDrafts(page, PAGE_SIZE);
  const confirmAll = useConfirmAllDrafts();

  const drafts = data?.drafts ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  if (isLoading) {
    return (
      <div className="space-y-2 p-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 rounded-lg bg-gray-100 dark:bg-gray-800 animate-pulse" />
        ))}
      </div>
    );
  }

  if (drafts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <CheckCircle size={40} className="text-green-400 mb-3" aria-hidden="true" />
        <p className="text-gray-600 dark:text-gray-400 font-medium">No pending transactions</p>
        <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
          Sync your bank to pull in new transactions for review.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <p className="text-sm text-gray-600 dark:text-gray-400">
          {total} pending transaction{total !== 1 ? "s" : ""}
        </p>
        <button
          onClick={() => confirmAll.mutate()}
          disabled={confirmAll.isPending}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors min-h-[36px]"
        >
          <CheckCircle size={14} aria-hidden="true" />
          Confirm All
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[600px]" aria-label="Pending transactions">
          <thead>
            <tr className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              <th className="px-4 py-2">Description</th>
              <th className="px-4 py-2 text-right">Amount</th>
              <th className="px-4 py-2">Date</th>
              <th className="px-4 py-2">Category</th>
              <th className="px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {drafts.map((d) => (
              <DraftRow key={d.id} draft={d} />
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 py-3 border-t border-gray-100 dark:border-gray-800">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
            className="px-3 py-1.5 rounded-lg text-sm bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-40 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            Previous
          </button>
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Page {page} of {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="px-3 py-1.5 rounded-lg text-sm bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-40 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

// -------------------- Connected State --------------------

function ConnectedCard({ connection }) {
  const sync = useSyncTransactions();
  const disconnect = useDisconnectBank();
  const [disconnectConfirm, setDisconnectConfirm] = useState(false);
  const [draftsOpen, setDraftsOpen] = useState(true);

  return (
    <>
      {/* Sandbox banner */}
      {connection.is_sandbox && (
        <div
          className="flex items-center gap-2 px-4 py-2.5 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-700 rounded-xl text-yellow-800 dark:text-yellow-300 text-sm mb-4"
          role="status"
        >
          <AlertTriangle size={16} className="flex-shrink-0" aria-hidden="true" />
          <span>
            <strong>Sandbox mode</strong> — Using TrueLayer Sandbox. Mock data only, no real
            transactions.
          </span>
        </div>
      )}

      {/* Connection info card */}
      <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-sm mb-4">
        <div className="flex items-start justify-between p-5 gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center flex-shrink-0">
              <Landmark size={20} className="text-blue-600 dark:text-blue-400" aria-hidden="true" />
            </div>
            <div>
              <p className="font-semibold text-gray-900 dark:text-white">
                {connection.provider ?? "Connected Bank"}
              </p>
              {connection.account_id && (
                <p className="text-xs text-gray-500 dark:text-gray-400 font-mono mt-0.5">
                  {connection.account_id}
                </p>
              )}
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                Last synced:{" "}
                {connection.last_synced_at ? fmtDate(connection.last_synced_at) : "Never"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => sync.mutate(connection.id)}
              disabled={sync.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60 transition-colors min-h-[40px]"
            >
              <RefreshCw
                size={15}
                aria-hidden="true"
                className={sync.isPending ? "animate-spin" : ""}
              />
              {sync.isPending ? "Syncing…" : "Sync Now"}
            </button>
            <button
              onClick={() => setDisconnectConfirm(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors min-h-[40px]"
            >
              <Unlink size={15} aria-hidden="true" />
              Disconnect
            </button>
          </div>
        </div>
      </div>

      {/* Drafts panel */}
      <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-sm">
        <button
          onClick={() => setDraftsOpen((o) => !o)}
          className="flex items-center justify-between w-full px-5 py-4 text-left"
          aria-expanded={draftsOpen}
        >
          <span className="font-semibold text-gray-900 dark:text-white">Pending Transactions</span>
          {draftsOpen ? (
            <ChevronUp size={18} className="text-gray-400" aria-hidden="true" />
          ) : (
            <ChevronDown size={18} className="text-gray-400" aria-hidden="true" />
          )}
        </button>
        {draftsOpen && <DraftsPanel />}
      </div>

      {disconnectConfirm && (
        <ConfirmModal
          title="Disconnect bank account?"
          message="This will remove the bank connection and all pending draft transactions. Confirmed transactions will be preserved."
          onConfirm={() => {
            disconnect.mutate(connection.id);
            setDisconnectConfirm(false);
          }}
          onCancel={() => setDisconnectConfirm(false)}
        />
      )}
    </>
  );
}

// -------------------- Disconnected State --------------------

function DisconnectedCard({ onConnect, isConnecting }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-sm p-8 flex flex-col items-center text-center max-w-md mx-auto">
      <div className="w-16 h-16 rounded-2xl bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center mb-5">
        <Landmark size={32} className="text-blue-600 dark:text-blue-400" aria-hidden="true" />
      </div>
      <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
        Connect your bank
      </h2>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-6 leading-relaxed">
        Securely link your bank account to automatically import transactions for review. We
        connect via TrueLayer — read-only access, no payments.
      </p>

      <ul className="text-sm text-gray-600 dark:text-gray-400 space-y-2 text-left mb-8 w-full">
        {[
          "Read-only — we can never move your money",
          "Transactions need your approval before they're saved",
          "You can disconnect at any time",
          "Bank credentials are handled by TrueLayer, not us",
        ].map((item) => (
          <li key={item} className="flex items-center gap-2">
            <CheckCircle size={15} className="text-green-500 flex-shrink-0" aria-hidden="true" />
            <span>{item}</span>
          </li>
        ))}
      </ul>

      <button
        onClick={onConnect}
        disabled={isConnecting}
        className="flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60 transition-colors min-h-[48px] w-full justify-center"
      >
        <Landmark size={16} aria-hidden="true" />
        {isConnecting ? "Redirecting to bank…" : "Connect Bank"}
      </button>
    </div>
  );
}

// -------------------- Page --------------------

export default function BankConnectionPage() {
  const { data, isLoading } = useConnections();
  const connectMutation = useConnectBank();

  const connections = data?.connections ?? [];
  const activeConnection = connections[0] ?? null;

  return (
    <div className="max-w-3xl mx-auto py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Banking</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Connect a bank account to automatically import and categorise your transactions.
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          <div className="h-28 rounded-2xl bg-gray-100 dark:bg-gray-800 animate-pulse" />
          <div className="h-48 rounded-2xl bg-gray-100 dark:bg-gray-800 animate-pulse" />
        </div>
      ) : activeConnection ? (
        <ConnectedCard connection={activeConnection} />
      ) : (
        <DisconnectedCard
          onConnect={() => connectMutation.mutate()}
          isConnecting={connectMutation.isPending}
        />
      )}
    </div>
  );
}
