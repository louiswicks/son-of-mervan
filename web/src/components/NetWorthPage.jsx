// src/components/NetWorthPage.jsx
import React, { useState, useMemo } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { PlusCircle, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import toast from "react-hot-toast";
import { useNetWorthSnapshots, useCreateSnapshot, useDeleteSnapshot } from "../hooks/useNetWorth";
import { useTheme } from "../hooks/useTheme";

const today = () => new Date().toISOString().slice(0, 10);

function fmt(n) {
  return `£${Number(n).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

// ---------- KPI Card ----------

function KpiCard({ label, value, positive }) {
  const colour =
    positive === undefined
      ? "text-[var(--color-text)]"
      : positive
      ? "text-green-500"
      : "text-red-500";
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 flex flex-col gap-1">
      <span className="text-xs text-[var(--color-muted)] uppercase tracking-wide">{label}</span>
      <span className={`text-2xl font-bold ${colour}`}>{fmt(value)}</span>
    </div>
  );
}

// ---------- Item row inside the add form ----------

function ItemRow({ item, onChange, onRemove }) {
  return (
    <div className="flex gap-2 items-center">
      <input
        className="flex-1 input-base"
        placeholder="Name"
        value={item.name}
        onChange={(e) => onChange({ ...item, name: e.target.value })}
      />
      <input
        className="w-36 input-base"
        type="number"
        placeholder="Value"
        min="0"
        step="0.01"
        value={item.value}
        onChange={(e) => onChange({ ...item, value: e.target.value })}
      />
      <button
        type="button"
        onClick={onRemove}
        className="text-red-400 hover:text-red-600 transition-colors"
        aria-label="Remove item"
      >
        <Trash2 size={16} />
      </button>
    </div>
  );
}

// ---------- Add Snapshot Form ----------

function AddSnapshotForm({ onClose }) {
  const createMut = useCreateSnapshot();
  const [date, setDate] = useState(today());
  const [assets, setAssets] = useState([{ name: "", value: "" }]);
  const [liabilities, setLiabilities] = useState([{ name: "", value: "" }]);

  const updateItem = (list, setList, idx, updated) => {
    const next = [...list];
    next[idx] = updated;
    setList(next);
  };
  const removeItem = (list, setList, idx) => setList(list.filter((_, i) => i !== idx));
  const addItem = (setList) => setList((prev) => [...prev, { name: "", value: "" }]);

  const handleSubmit = (e) => {
    e.preventDefault();
    const cleanAssets = assets
      .filter((a) => a.name.trim() && a.value !== "")
      .map((a) => ({ name: a.name.trim(), value: parseFloat(a.value) }));
    const cleanLiabilities = liabilities
      .filter((l) => l.name.trim() && l.value !== "")
      .map((l) => ({ name: l.name.trim(), value: parseFloat(l.value) }));

    if (!cleanAssets.length && !cleanLiabilities.length) {
      toast.error("Add at least one asset or liability.");
      return;
    }

    createMut.mutate(
      { snapshot_date: date, assets: cleanAssets, liabilities: cleanLiabilities },
      {
        onSuccess: () => {
          toast.success("Snapshot saved!");
          onClose();
        },
        onError: (err) => {
          toast.error(err?.response?.data?.detail ?? "Failed to save snapshot.");
        },
      }
    );
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 space-y-6"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[var(--color-text)]">Add Snapshot</h2>
        <button type="button" onClick={onClose} className="text-[var(--color-muted)] hover:text-[var(--color-text)]">
          ✕
        </button>
      </div>

      <div>
        <label className="block text-sm font-medium text-[var(--color-text)] mb-1">Date</label>
        <input
          type="date"
          className="input-base w-48"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          required
        />
      </div>

      {/* Assets */}
      <section>
        <h3 className="text-sm font-semibold text-[var(--color-text)] mb-2">Assets</h3>
        <div className="space-y-2">
          {assets.map((a, i) => (
            <ItemRow
              key={i}
              item={a}
              onChange={(v) => updateItem(assets, setAssets, i, v)}
              onRemove={() => removeItem(assets, setAssets, i)}
            />
          ))}
        </div>
        <button
          type="button"
          onClick={() => addItem(setAssets)}
          className="mt-2 text-sm text-blue-500 hover:underline flex items-center gap-1"
        >
          <PlusCircle size={14} /> Add asset
        </button>
      </section>

      {/* Liabilities */}
      <section>
        <h3 className="text-sm font-semibold text-[var(--color-text)] mb-2">Liabilities</h3>
        <div className="space-y-2">
          {liabilities.map((l, i) => (
            <ItemRow
              key={i}
              item={l}
              onChange={(v) => updateItem(liabilities, setLiabilities, i, v)}
              onRemove={() => removeItem(liabilities, setLiabilities, i)}
            />
          ))}
        </div>
        <button
          type="button"
          onClick={() => addItem(setLiabilities)}
          className="mt-2 text-sm text-blue-500 hover:underline flex items-center gap-1"
        >
          <PlusCircle size={14} /> Add liability
        </button>
      </section>

      <div className="flex gap-3 justify-end">
        <button type="button" onClick={onClose} className="btn-secondary">
          Cancel
        </button>
        <button type="submit" className="btn-primary" disabled={createMut.isPending}>
          {createMut.isPending ? "Saving…" : "Save Snapshot"}
        </button>
      </div>
    </form>
  );
}

// ---------- Snapshot row ----------

function SnapshotRow({ snap, onDelete }) {
  const [open, setOpen] = useState(false);
  const nw = snap.net_worth;
  const positive = nw >= 0;

  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 text-sm hover:bg-[var(--color-hover)] transition-colors"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="font-medium text-[var(--color-text)]">{snap.snapshot_date}</span>
        <div className="flex items-center gap-4">
          <span className={positive ? "text-green-500 font-semibold" : "text-red-500 font-semibold"}>
            {fmt(nw)}
          </span>
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-3 border-t border-[var(--color-border)]">
          <div className="grid grid-cols-2 gap-4 mt-3">
            <div>
              <p className="text-xs text-[var(--color-muted)] mb-1">Assets ({fmt(snap.total_assets)})</p>
              <ul className="space-y-1">
                {snap.assets.map((a, i) => (
                  <li key={i} className="flex justify-between text-sm text-[var(--color-text)]">
                    <span>{a.name}</span>
                    <span>{fmt(a.value)}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs text-[var(--color-muted)] mb-1">Liabilities ({fmt(snap.total_liabilities)})</p>
              <ul className="space-y-1">
                {snap.liabilities.map((l, i) => (
                  <li key={i} className="flex justify-between text-sm text-[var(--color-text)]">
                    <span>{l.name}</span>
                    <span>{fmt(l.value)}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <button
            onClick={() => onDelete(snap.id)}
            className="flex items-center gap-1 text-xs text-red-400 hover:text-red-600 transition-colors mt-2"
            aria-label={`Delete snapshot from ${snap.snapshot_date}`}
          >
            <Trash2 size={12} /> Delete
          </button>
        </div>
      )}
    </div>
  );
}

// ---------- Main Page ----------

export default function NetWorthPage() {
  const { theme } = useTheme();
  const { data: snapshots = [], isLoading } = useNetWorthSnapshots();
  const deleteMut = useDeleteSnapshot();
  const [showForm, setShowForm] = useState(false);

  const chartColors = useMemo(
    () => ({
      positive: theme === "dark" ? "#34d399" : "#10b981",
      negative: theme === "dark" ? "#f87171" : "#ef4444",
      grid: theme === "dark" ? "#334155" : "#e5e7eb",
      axis: theme === "dark" ? "#94a3b8" : "#6b7280",
      area: theme === "dark" ? "#60a5fa" : "#3b82f6",
    }),
    [theme]
  );

  const latest = snapshots.length > 0 ? snapshots[snapshots.length - 1] : null;

  const chartData = snapshots.map((s) => ({
    date: s.snapshot_date,
    "Net Worth": s.net_worth,
    Assets: s.total_assets,
    Liabilities: s.total_liabilities,
  }));

  const handleDelete = (id) => {
    deleteMut.mutate(id, {
      onSuccess: () => toast.success("Snapshot deleted."),
      onError: () => toast.error("Could not delete snapshot."),
    });
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text)]">Net Worth</h1>
          <p className="text-sm text-[var(--color-muted)] mt-1">
            Track assets and liabilities over time.
          </p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="btn-primary flex items-center gap-2"
          aria-label="Add snapshot"
        >
          <PlusCircle size={16} />
          Add Snapshot
        </button>
      </div>

      {/* Form */}
      {showForm && <AddSnapshotForm onClose={() => setShowForm(false)} />}

      {/* KPI cards */}
      {latest && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <KpiCard label="Net Worth" value={latest.net_worth} positive={latest.net_worth >= 0} />
          <KpiCard label="Total Assets" value={latest.total_assets} />
          <KpiCard label="Total Liabilities" value={latest.total_liabilities} />
        </div>
      )}

      {/* Area Chart */}
      {chartData.length > 1 && (
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="text-sm font-semibold text-[var(--color-text)] mb-4">Net Worth Trend</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="nwGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={chartColors.area} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={chartColors.area} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                <XAxis dataKey="date" tick={{ fill: chartColors.axis, fontSize: 11 }} />
                <YAxis
                  tickFormatter={(v) => `£${(v / 1000).toFixed(0)}k`}
                  tick={{ fill: chartColors.axis, fontSize: 11 }}
                />
                <Tooltip
                  formatter={(v) => fmt(v)}
                  contentStyle={{
                    backgroundColor: "var(--color-surface)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 8,
                    color: "var(--color-text)",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="Net Worth"
                  stroke={chartColors.area}
                  strokeWidth={2.5}
                  fill="url(#nwGradient)"
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Snapshot list */}
      {isLoading ? (
        <p className="text-sm text-[var(--color-muted)]">Loading…</p>
      ) : snapshots.length === 0 ? (
        <div className="text-center py-16 text-[var(--color-muted)]">
          <p className="text-base">No snapshots yet.</p>
          <p className="text-sm mt-1">Click "Add Snapshot" to record your net worth today.</p>
        </div>
      ) : (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-[var(--color-text)]">History</h2>
          {[...snapshots].reverse().map((snap) => (
            <SnapshotRow key={snap.id} snap={snap} onDelete={handleDelete} />
          ))}
        </div>
      )}
    </div>
  );
}
