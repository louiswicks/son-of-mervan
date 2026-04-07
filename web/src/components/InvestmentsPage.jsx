import React, { useState } from "react";
import {
  TrendingUp, TrendingDown, Plus, Pencil, Trash2, RefreshCw, X, ChevronDown,
} from "lucide-react";
import {
  useInvestments,
  usePortfolioSummary,
  useCreateInvestment,
  useUpdateInvestment,
  useDeleteInvestment,
  useSyncPrices,
} from "../hooks/useInvestments";

const ASSET_TYPES = ["stock", "etf", "fund", "crypto", "other"];
const CURRENCIES = ["GBP", "USD", "EUR", "JPY", "AUD", "CAD", "CHF", "HKD", "SGD", "NOK"];

const EMPTY_FORM = {
  name: "",
  ticker: "",
  asset_type: "stock",
  units: "",
  purchase_price: "",
  currency: "GBP",
  notes: "",
};

function formatCurrency(value, currency = "GBP") {
  if (value == null) return "—";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPct(value) {
  if (value == null) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

// -------------------- Summary Cards --------------------

function SummaryCards({ summary }) {
  const hasValue = summary?.total_value != null;
  const gainPositive = (summary?.total_gain_loss ?? 0) >= 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
      <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Holdings</p>
        <p className="text-2xl font-bold text-gray-900 dark:text-white">
          {summary?.holdings_count ?? 0}
        </p>
      </div>
      <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Cost</p>
        <p className="text-2xl font-bold text-gray-900 dark:text-white">
          {formatCurrency(summary?.total_cost ?? 0)}
        </p>
      </div>
      <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Portfolio Value</p>
        <p className="text-2xl font-bold text-gray-900 dark:text-white">
          {hasValue ? formatCurrency(summary.total_value) : "—"}
        </p>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">Live prices</p>
      </div>
      <div className={`rounded-xl p-4 shadow-sm border ${
        hasValue
          ? gainPositive
            ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
            : "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
          : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700"
      }`}>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Unrealised Gain/Loss</p>
        {hasValue ? (
          <>
            <p className={`text-2xl font-bold ${gainPositive ? "text-green-700 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}>
              {formatCurrency(summary.total_gain_loss)}
            </p>
            <p className={`text-sm font-medium ${gainPositive ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
              {formatPct(summary.total_gain_loss_pct)}
            </p>
          </>
        ) : (
          <p className="text-2xl font-bold text-gray-400 dark:text-gray-500">—</p>
        )}
      </div>
    </div>
  );
}

// -------------------- Form Modal --------------------

function HoldingForm({ initial, onSave, onCancel, loading }) {
  const [form, setForm] = useState(initial || EMPTY_FORM);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const handleSubmit = (e) => {
    e.preventDefault();
    const payload = {
      name: form.name.trim(),
      ticker: form.ticker.trim() || null,
      asset_type: form.asset_type,
      units: parseFloat(form.units),
      purchase_price: parseFloat(form.purchase_price),
      currency: form.currency,
      notes: form.notes.trim() || null,
    };
    if (!payload.name || isNaN(payload.units) || isNaN(payload.purchase_price)) return;
    onSave(payload);
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="font-semibold text-gray-900 dark:text-white">
            {initial ? "Edit Holding" : "Add Holding"}
          </h2>
          <button onClick={onCancel} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
            <X size={18} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="px-5 py-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Name *</label>
            <input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              required
              placeholder="e.g. Vanguard S&P 500 ETF"
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Ticker</label>
              <input
                value={form.ticker}
                onChange={(e) => set("ticker", e.target.value)}
                placeholder="e.g. VUSA.L"
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Type</label>
              <select
                value={form.asset_type}
                onChange={(e) => set("asset_type", e.target.value)}
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {ASSET_TYPES.map((t) => (
                  <option key={t} value={t}>{t.toUpperCase()}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Units *</label>
              <input
                type="number"
                step="any"
                min="0.000001"
                value={form.units}
                onChange={(e) => set("units", e.target.value)}
                required
                placeholder="0.00"
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Purchase Price *</label>
              <input
                type="number"
                step="any"
                min="0"
                value={form.purchase_price}
                onChange={(e) => set("purchase_price", e.target.value)}
                required
                placeholder="0.00"
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Currency</label>
            <select
              value={form.currency}
              onChange={(e) => set("currency", e.target.value)}
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {CURRENCIES.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Notes</label>
            <input
              value={form.notes}
              onChange={(e) => set("notes", e.target.value)}
              placeholder="Optional notes"
              className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              {loading ? "Saving…" : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// -------------------- Holdings Table Row --------------------

function HoldingRow({ holding, onEdit, onDelete }) {
  const hasPrice = holding.current_price != null;
  const gainPositive = (holding.gain_loss ?? 0) >= 0;

  return (
    <tr className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
      <td className="py-3 px-4">
        <div className="font-medium text-gray-900 dark:text-white text-sm">{holding.name}</div>
        {holding.ticker && (
          <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">{holding.ticker}</div>
        )}
      </td>
      <td className="py-3 px-3 text-center">
        <span className="inline-block bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs rounded px-2 py-0.5 uppercase">
          {holding.asset_type}
        </span>
      </td>
      <td className="py-3 px-3 text-right text-sm text-gray-700 dark:text-gray-300 tabular-nums">
        {holding.units.toLocaleString("en-GB", { maximumFractionDigits: 6 })}
      </td>
      <td className="py-3 px-3 text-right text-sm text-gray-700 dark:text-gray-300 tabular-nums">
        {formatCurrency(holding.purchase_price, holding.currency)}
      </td>
      <td className="py-3 px-3 text-right text-sm text-gray-700 dark:text-gray-300 tabular-nums">
        {hasPrice ? formatCurrency(holding.current_price, holding.currency) : <span className="text-gray-400">—</span>}
      </td>
      <td className="py-3 px-3 text-right text-sm font-medium tabular-nums">
        {hasPrice
          ? <span className={gainPositive ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400"}>
              {formatCurrency(holding.current_value, holding.currency)}
            </span>
          : <span className="text-gray-400">—</span>
        }
      </td>
      <td className="py-3 px-3 text-right text-sm tabular-nums">
        {hasPrice ? (
          <span className={`flex items-center justify-end gap-1 ${gainPositive ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400"}`}>
            {gainPositive ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
            {formatPct(holding.gain_loss_pct)}
          </span>
        ) : (
          <span className="text-gray-400">—</span>
        )}
      </td>
      <td className="py-3 px-3">
        <div className="flex items-center justify-end gap-1">
          <button
            onClick={() => onEdit(holding)}
            className="p-1.5 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 rounded transition-colors"
            title="Edit"
          >
            <Pencil size={14} />
          </button>
          <button
            onClick={() => onDelete(holding.id)}
            className="p-1.5 text-gray-400 hover:text-red-500 dark:hover:text-red-400 rounded transition-colors"
            title="Remove"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </td>
    </tr>
  );
}

// -------------------- Main Page --------------------

export default function InvestmentsPage() {
  const { data: holdings = [], isLoading } = useInvestments();
  const { data: summary } = usePortfolioSummary();
  const createMut = useCreateInvestment();
  const updateMut = useUpdateInvestment();
  const deleteMut = useDeleteInvestment();
  const syncMut = useSyncPrices();

  const [showForm, setShowForm] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const handleSave = (payload) => {
    if (editTarget) {
      updateMut.mutate(
        { id: editTarget.id, ...payload },
        { onSuccess: () => { setEditTarget(null); setShowForm(false); } }
      );
    } else {
      createMut.mutate(payload, {
        onSuccess: () => setShowForm(false),
      });
    }
  };

  const handleEdit = (holding) => {
    setEditTarget(holding);
    setShowForm(true);
  };

  const handleDelete = (id) => {
    setDeleteConfirm(id);
  };

  const confirmDelete = () => {
    deleteMut.mutate(deleteConfirm, { onSuccess: () => setDeleteConfirm(null) });
  };

  const isSaving = createMut.isPending || updateMut.isPending;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Investments</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Track your portfolio — stocks, ETFs, funds, crypto
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => syncMut.mutate()}
            disabled={syncMut.isPending || holdings.length === 0}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors disabled:opacity-40"
            title="Sync prices via Yahoo Finance"
          >
            <RefreshCw size={14} className={syncMut.isPending ? "animate-spin" : ""} />
            Sync Prices
          </button>
          <button
            onClick={() => { setEditTarget(null); setShowForm(true); }}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={15} />
            Add Holding
          </button>
        </div>
      </div>

      {/* Summary */}
      <SummaryCards summary={summary} />

      {/* Holdings table */}
      {isLoading ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-8 text-center">
          <div className="animate-pulse text-gray-400 dark:text-gray-500">Loading portfolio…</div>
        </div>
      ) : holdings.length === 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-12 text-center">
          <TrendingUp size={40} className="mx-auto text-gray-300 dark:text-gray-600 mb-3" />
          <p className="text-gray-500 dark:text-gray-400 font-medium">No holdings yet</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1 mb-4">
            Add your first investment to start tracking your portfolio.
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Add Holding
          </button>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 dark:bg-gray-900/50 text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  <th className="py-3 px-4 text-left">Name</th>
                  <th className="py-3 px-3 text-center">Type</th>
                  <th className="py-3 px-3 text-right">Units</th>
                  <th className="py-3 px-3 text-right">Buy Price</th>
                  <th className="py-3 px-3 text-right">Cur. Price</th>
                  <th className="py-3 px-3 text-right">Value</th>
                  <th className="py-3 px-3 text-right">Gain/Loss</th>
                  <th className="py-3 px-3 text-right"></th>
                </tr>
              </thead>
              <tbody>
                {holdings.map((h) => (
                  <HoldingRow
                    key={h.id}
                    holding={h}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* Price sync notice */}
          <div className="px-4 py-2 bg-gray-50 dark:bg-gray-900/30 border-t border-gray-100 dark:border-gray-800">
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Prices synced daily at 16:30 UTC via Yahoo Finance. Add a ticker symbol to enable auto-sync.
            </p>
          </div>
        </div>
      )}

      {/* Add/Edit modal */}
      {showForm && (
        <HoldingForm
          initial={
            editTarget
              ? {
                  name: editTarget.name || "",
                  ticker: editTarget.ticker || "",
                  asset_type: editTarget.asset_type || "stock",
                  units: editTarget.units?.toString() || "",
                  purchase_price: editTarget.purchase_price?.toString() || "",
                  currency: editTarget.currency || "GBP",
                  notes: editTarget.notes || "",
                }
              : null
          }
          onSave={handleSave}
          onCancel={() => { setShowForm(false); setEditTarget(null); }}
          loading={isSaving}
        />
      )}

      {/* Delete confirm */}
      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-2xl w-full max-w-sm p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Remove holding?</h3>
            <p className="text-sm text-gray-500 dark:text-gray-400 mb-5">
              This will remove the holding and all its price history. This cannot be undone.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                disabled={deleteMut.isPending}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {deleteMut.isPending ? "Removing…" : "Remove"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
