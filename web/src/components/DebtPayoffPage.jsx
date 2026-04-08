// src/components/DebtPayoffPage.jsx
import React, { useState } from "react";
import { Plus, Pencil, Trash2, X, TrendingDown } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  useDebts,
  usePayoffPlan,
  useCreateDebt,
  useUpdateDebt,
  useDeleteDebt,
} from "../hooks/useDebts";
import ConfirmModal from "./ConfirmModal";
import { SkeletonTable } from "./Skeleton";
import toast from "react-hot-toast";
import PageWrapper from "./PageWrapper";
import Card from "./Card";

const EMPTY_FORM = {
  name: "",
  balance: "",
  interest_rate: "",
  minimum_payment: "",
};

function fmt(n) {
  return Number(n).toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function pct(rate) {
  return (rate * 100).toFixed(1) + "%";
}

// Build chart data from payoff plan months
function buildChartData(plan, debts) {
  if (!plan || !plan.months.length) return [];
  // Sample every N months to keep chart readable (max ~60 data points)
  const total = plan.months.length;
  const step = Math.max(1, Math.floor(total / 60));
  const sampled = plan.months.filter((_, i) => i % step === 0 || i === total - 1);
  return sampled.map((m) => {
    const entry = { month: `M${m.month}` };
    m.debts.forEach((d) => {
      entry[d.name] = d.remaining_balance;
    });
    return entry;
  });
}

const COLORS = [
  "#ef4444", "#f97316", "#eab308", "#22c55e",
  "#14b8a6", "#3b82f6", "#8b5cf6", "#ec4899",
];

// ---------- Debt Form Modal ----------

function DebtModal({ initial, onClose, onSave, isLoading }) {
  const [form, setForm] = useState(
    initial
      ? {
          name: initial.name,
          balance: String(initial.balance),
          interest_rate: String((initial.interest_rate * 100).toFixed(2)),
          minimum_payment: String(initial.minimum_payment),
        }
      : EMPTY_FORM
  );

  function set(k, v) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!form.name.trim()) return toast.error("Name is required");
    const balance = parseFloat(form.balance);
    const interest_rate = parseFloat(form.interest_rate) / 100;
    const minimum_payment = parseFloat(form.minimum_payment);
    if (isNaN(balance) || balance <= 0) return toast.error("Balance must be positive");
    if (isNaN(interest_rate) || interest_rate < 0 || interest_rate > 2)
      return toast.error("Interest rate must be 0–200%");
    if (isNaN(minimum_payment) || minimum_payment <= 0)
      return toast.error("Minimum payment must be positive");
    onSave({ name: form.name.trim(), balance, interest_rate, minimum_payment });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
            {initial ? "Edit Debt" : "Add Debt"}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
            <X size={20} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Debt name
            </label>
            <input
              type="text"
              placeholder="e.g. Credit Card, Car Loan"
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Current balance (£)
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              placeholder="0.00"
              value={form.balance}
              onChange={(e) => set("balance", e.target.value)}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Annual interest rate (%)
            </label>
            <input
              type="number"
              step="0.1"
              min="0"
              max="200"
              placeholder="e.g. 18.9"
              value={form.interest_rate}
              onChange={(e) => set("interest_rate", e.target.value)}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Monthly minimum payment (£)
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              placeholder="0.00"
              value={form.minimum_payment}
              onChange={(e) => set("minimum_payment", e.target.value)}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:ring-2 focus:ring-red-500 outline-none"
            />
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium disabled:opacity-50"
            >
              {isLoading ? "Saving…" : initial ? "Save changes" : "Add debt"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------- Main Page ----------

export default function DebtPayoffPage() {
  const [strategy, setStrategy] = useState("avalanche");
  const [showModal, setShowModal] = useState(false);
  const [editDebt, setEditDebt] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const { data: debtsRes, isLoading: debtsLoading } = useDebts();
  const { data: planRes, isLoading: planLoading } = usePayoffPlan(strategy);

  const createDebt = useCreateDebt();
  const updateDebt = useUpdateDebt();
  const deleteDebt = useDeleteDebt();

  const debts = debtsRes?.data ?? [];
  const plan = planRes?.data ?? null;
  const chartData = buildChartData(plan, debts);
  const debtNames = debts.map((d) => d.name);

  function handleSave(payload) {
    if (editDebt) {
      updateDebt.mutate(
        { id: editDebt.id, ...payload },
        {
          onSuccess: () => { toast.success("Debt updated"); setEditDebt(null); },
          onError: () => toast.error("Failed to update debt"),
        }
      );
    } else {
      createDebt.mutate(payload, {
        onSuccess: () => { toast.success("Debt added"); setShowModal(false); },
        onError: () => toast.error("Failed to add debt"),
      });
    }
  }

  function handleDelete() {
    deleteDebt.mutate(deleteTarget.id, {
      onSuccess: () => { toast.success("Debt deleted"); setDeleteTarget(null); },
      onError: () => toast.error("Failed to delete debt"),
    });
  }

  const totalBalance = debts.reduce((s, d) => s + d.balance, 0);
  const totalMinimum = debts.reduce((s, d) => s + d.minimum_payment, 0);

  return (
    <PageWrapper className="max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <TrendingDown className="text-red-500" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Debt Payoff</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Model snowball and avalanche strategies to eliminate debt faster
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium"
        >
          <Plus size={16} />
          Add debt
        </button>
      </div>

      {/* Summary KPIs */}
      {debts.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <Card className="!p-4">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total owed</p>
            <p className="text-xl font-bold text-red-600 dark:text-red-400">£{fmt(totalBalance)}</p>
          </Card>
          <Card className="!p-4">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Monthly minimums</p>
            <p className="text-xl font-bold text-gray-900 dark:text-gray-100">£{fmt(totalMinimum)}</p>
          </Card>
          <Card className="!p-4">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Months to freedom</p>
            <p className="text-xl font-bold text-gray-900 dark:text-gray-100">
              {planLoading ? "…" : plan?.payoff_months ?? "—"}
            </p>
          </Card>
          <Card className="!p-4">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total interest ({strategy})</p>
            <p className="text-xl font-bold text-orange-600 dark:text-orange-400">
              {planLoading ? "…" : plan ? `£${fmt(plan.total_interest_paid)}` : "—"}
            </p>
          </Card>
        </div>
      )}

      {/* Debt list */}
      <Card className="overflow-hidden !p-0">
        <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100">Your debts</h2>
        </div>
        {debtsLoading ? (
          <div className="p-5"><SkeletonTable rows={3} /></div>
        ) : debts.length === 0 ? (
          <div className="px-5 py-12 text-center text-gray-400 dark:text-gray-500">
            <TrendingDown size={40} className="mx-auto mb-3 opacity-30" />
            <p className="font-medium">No debts added yet</p>
            <p className="text-sm mt-1">Add your first debt to start modelling your payoff plan.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700/50">
                <tr>
                  <th className="px-5 py-3 text-left font-medium text-gray-600 dark:text-gray-300">Name</th>
                  <th className="px-5 py-3 text-right font-medium text-gray-600 dark:text-gray-300">Balance</th>
                  <th className="px-5 py-3 text-right font-medium text-gray-600 dark:text-gray-300">APR</th>
                  <th className="px-5 py-3 text-right font-medium text-gray-600 dark:text-gray-300">Min. payment</th>
                  <th className="px-5 py-3 text-right font-medium text-gray-600 dark:text-gray-300">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {debts.map((d) => (
                  <tr key={d.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                    <td className="px-5 py-3 font-medium text-gray-900 dark:text-gray-100">{d.name}</td>
                    <td className="px-5 py-3 text-right text-red-600 dark:text-red-400 font-semibold">
                      £{fmt(d.balance)}
                    </td>
                    <td className="px-5 py-3 text-right text-gray-700 dark:text-gray-300">
                      {pct(d.interest_rate)}
                    </td>
                    <td className="px-5 py-3 text-right text-gray-700 dark:text-gray-300">
                      £{fmt(d.minimum_payment)}/mo
                    </td>
                    <td className="px-5 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => setEditDebt(d)}
                          className="p-1.5 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 rounded"
                        >
                          <Pencil size={15} />
                        </button>
                        <button
                          onClick={() => setDeleteTarget(d)}
                          className="p-1.5 text-gray-400 hover:text-red-600 dark:hover:text-red-400 rounded"
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Payoff plan chart */}
      {debts.length > 0 && (
        <Card className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h2 className="font-semibold text-gray-900 dark:text-gray-100">Payoff timeline</h2>
            <div className="flex rounded-lg overflow-hidden border border-gray-300 dark:border-gray-600 text-sm">
              {["avalanche", "snowball"].map((s) => (
                <button
                  key={s}
                  onClick={() => setStrategy(s)}
                  className={`px-4 py-1.5 capitalize ${
                    strategy === s
                      ? "bg-red-600 text-white"
                      : "bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div className="text-xs text-gray-500 dark:text-gray-400">
            {strategy === "avalanche"
              ? "Avalanche: pay highest interest rate first — minimises total interest paid."
              : "Snowball: pay smallest balance first — motivating quick wins."}
          </div>

          {planLoading ? (
            <div className="h-64 flex items-center justify-center text-gray-400">Loading plan…</div>
          ) : chartData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-gray-400">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height={320}>
              <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11 }}
                  interval={Math.max(0, Math.floor(chartData.length / 8) - 1)}
                  stroke="#9ca3af"
                />
                <YAxis
                  tickFormatter={(v) => `£${(v / 1000).toFixed(0)}k`}
                  tick={{ fontSize: 11 }}
                  stroke="#9ca3af"
                />
                <Tooltip
                  formatter={(v) => [`£${fmt(v)}`, undefined]}
                  contentStyle={{ fontSize: 12 }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {debtNames.map((name, i) => (
                  <Line
                    key={name}
                    type="monotone"
                    dataKey={name}
                    stroke={COLORS[i % COLORS.length]}
                    dot={false}
                    strokeWidth={2}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>
      )}

      {/* Modals */}
      {(showModal || editDebt) && (
        <DebtModal
          initial={editDebt}
          onClose={() => { setShowModal(false); setEditDebt(null); }}
          onSave={handleSave}
          isLoading={createDebt.isPending || updateDebt.isPending}
        />
      )}

      {deleteTarget && (
        <ConfirmModal
          title="Delete debt"
          message={`Remove "${deleteTarget.name}" from your debt list? This cannot be undone.`}
          confirmLabel="Delete"
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
          danger
        />
      )}
    </PageWrapper>
  );
}
