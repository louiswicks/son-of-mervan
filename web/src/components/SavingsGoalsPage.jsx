// src/components/SavingsGoalsPage.jsx
import React, { useState } from "react";
import { Plus, Pencil, Trash2, X, Check, ChevronDown, ChevronUp, PiggyBank } from "lucide-react";
import PageWrapper from "./PageWrapper";
import Card from "./Card";
import EmptyState from "./EmptyState";
import { RadialBarChart, RadialBar, ResponsiveContainer } from "recharts";
import {
  useSavingsGoals,
  useCreateGoal,
  useUpdateGoal,
  useDeleteGoal,
  useContributions,
  useAddContribution,
  useDeleteContribution,
} from "../hooks/useSavings";
import ConfirmModal from "./ConfirmModal";
import { SkeletonTable } from "./Skeleton";

const EMPTY_GOAL_FORM = { name: "", target_amount: "", target_date: "" };
const EMPTY_CONTRIB_FORM = {
  amount: "",
  note: "",
  contributed_at: new Date().toISOString().slice(0, 10),
};

const STATUS_CONFIG = {
  achieved:    { label: "Achieved!",   bg: "bg-green-100 dark:bg-green-900/40", text: "text-green-700 dark:text-green-300" },
  ahead:       { label: "Ahead",       bg: "bg-blue-100 dark:bg-blue-900/40",   text: "text-blue-700 dark:text-blue-300" },
  on_track:    { label: "On track",    bg: "bg-teal-100 dark:bg-teal-900/40",   text: "text-teal-700 dark:text-teal-300" },
  behind:      { label: "Behind",      bg: "bg-red-100 dark:bg-red-900/40",     text: "text-red-700 dark:text-red-300" },
  no_deadline: { label: "No deadline", bg: "bg-gray-100 dark:bg-gray-700",      text: "text-gray-600 dark:text-gray-300" },
};

function toInputDate(dt) {
  if (!dt) return "";
  return new Date(dt).toISOString().slice(0, 10);
}

function fmt(n) {
  return Number(n).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// Radial progress ring using Recharts
function ProgressRing({ pct, status }) {
  const fill = status === "achieved" ? "#22c55e"
    : status === "ahead" ? "#3b82f6"
    : status === "on_track" ? "#14b8a6"
    : status === "behind" ? "#ef4444"
    : "#6b7280";

  const data = [{ value: Math.min(pct, 100), fill }];

  return (
    <div className="relative w-20 h-20 shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart
          cx="50%" cy="50%"
          innerRadius="70%" outerRadius="100%"
          startAngle={90} endAngle={90 - 360 * (Math.min(pct, 100) / 100)}
          data={data}
        >
          <RadialBar dataKey="value" background={{ fill: "#e5e7eb" }} cornerRadius={4} />
        </RadialBarChart>
      </ResponsiveContainer>
      <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-gray-700 dark:text-gray-200">
        {Math.round(pct)}%
      </span>
    </div>
  );
}

function GoalForm({ value, onChange, onSubmit, onCancel, submitLabel, isPending }) {
  return (
    <Card className="border-blue-300 dark:border-blue-600 mb-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Goal name</label>
          <input
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[44px]"
            placeholder="e.g. House deposit"
            value={value.name}
            onChange={(e) => onChange("name", e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Target amount (£)</label>
          <input
            type="number"
            min="0.01"
            step="0.01"
            inputMode="decimal"
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[44px]"
            placeholder="10000"
            value={value.target_amount}
            onChange={(e) => onChange("target_amount", e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Target date (optional)</label>
          <input
            type="date"
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[44px]"
            value={value.target_date}
            onChange={(e) => onChange("target_date", e.target.value)}
          />
        </div>
      </div>
      <div className="flex gap-2 mt-3 justify-end">
        <button
          onClick={onCancel}
          className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 min-h-[44px]"
        >
          <X size={14} /> Cancel
        </button>
        <button
          onClick={onSubmit}
          disabled={isPending || !value.name || !value.target_amount}
          className="flex items-center gap-1 px-4 py-2 rounded-lg text-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 min-h-[44px]"
        >
          <Check size={14} /> {submitLabel}
        </button>
      </div>
    </Card>
  );
}

function ContributionsPanel({ goal }) {
  const { data: contribs = [], isLoading } = useContributions(goal.id);
  const addMut = useAddContribution();
  const delMut = useDeleteContribution();
  const [form, setForm] = useState(EMPTY_CONTRIB_FORM);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const handleAdd = () => {
    if (!form.amount) return;
    addMut.mutate(
      { goalId: goal.id, data: { amount: parseFloat(form.amount), note: form.note || undefined, contributed_at: form.contributed_at || undefined } },
      { onSuccess: () => setForm(EMPTY_CONTRIB_FORM) }
    );
  };

  return (
    <div className="mt-3 border-t border-gray-200 dark:border-gray-700 pt-3">
      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">Contributions</p>

      {/* Add contribution form */}
      <div className="flex flex-wrap gap-2 mb-3">
        <input
          type="number"
          min="0.01"
          step="0.01"
          inputMode="decimal"
          placeholder="Amount (£)"
          className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 w-32 min-h-[40px]"
          value={form.amount}
          onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
        />
        <input
          placeholder="Note (optional)"
          className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 flex-1 min-w-[120px] min-h-[40px]"
          value={form.note}
          onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))}
        />
        <input
          type="date"
          className="border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[40px]"
          value={form.contributed_at}
          onChange={(e) => setForm((f) => ({ ...f, contributed_at: e.target.value }))}
        />
        <button
          onClick={handleAdd}
          disabled={addMut.isPending || !form.amount}
          className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 min-h-[40px]"
        >
          <Plus size={14} /> Add
        </button>
      </div>

      {/* Contribution list */}
      {isLoading ? (
        <p className="text-xs text-gray-400 dark:text-gray-500">Loading…</p>
      ) : contribs.length === 0 ? (
        <p className="text-xs text-gray-400 dark:text-gray-500 italic">No contributions yet.</p>
      ) : (
        <ul className="space-y-1">
          {contribs.map((c) => (
            <li key={c.id} className="flex items-center justify-between text-sm text-gray-700 dark:text-gray-300 py-1">
              <span>
                <span className="font-medium">£{fmt(c.amount)}</span>
                {c.note && <span className="ml-2 text-gray-400 dark:text-gray-500 text-xs">— {c.note}</span>}
                <span className="ml-2 text-gray-400 dark:text-gray-500 text-xs">{toInputDate(c.contributed_at)}</span>
              </span>
              <button
                onClick={() => setDeleteTarget(c.id)}
                className="text-red-400 hover:text-red-600 dark:text-red-500 dark:hover:text-red-400 p-1 min-w-[32px] min-h-[32px] flex items-center justify-center"
                aria-label="Delete contribution"
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {deleteTarget !== null && (
        <ConfirmModal
          message="Remove this contribution?"
          onConfirm={() => {
            delMut.mutate({ goalId: goal.id, contribId: deleteTarget });
            setDeleteTarget(null);
          }}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

function GoalCard({ goal, onEdit, onDelete }) {
  const [expanded, setExpanded] = useState(false);
  const pct = goal.target_amount > 0 ? (goal.current_amount / goal.target_amount) * 100 : 0;
  const cfg = STATUS_CONFIG[goal.status] ?? STATUS_CONFIG.no_deadline;

  return (
    <Card className="!p-4">
      <div className="flex gap-4 items-start">
        <ProgressRing pct={pct} status={goal.status} />

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 truncate">{goal.name}</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                £{fmt(goal.current_amount)} <span className="text-gray-400 dark:text-gray-500">of £{fmt(goal.target_amount)}</span>
              </p>
              {goal.target_date && (
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                  Target: {toInputDate(goal.target_date)}
                  {goal.required_monthly != null && (
                    <span className="ml-2">· Need £{fmt(goal.required_monthly)}/mo</span>
                  )}
                </p>
              )}
            </div>

            <div className="flex items-center gap-1 flex-wrap">
              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.text}`}>
                {cfg.label}
              </span>
              <button
                onClick={() => onEdit(goal)}
                className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 min-w-[36px] min-h-[36px] flex items-center justify-center"
                aria-label="Edit goal"
              >
                <Pencil size={15} />
              </button>
              <button
                onClick={() => onDelete(goal.id)}
                className="p-2 rounded-lg text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 min-w-[36px] min-h-[36px] flex items-center justify-center"
                aria-label="Delete goal"
              >
                <Trash2 size={15} />
              </button>
              <button
                onClick={() => setExpanded((v) => !v)}
                className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 min-w-[36px] min-h-[36px] flex items-center justify-center"
                aria-label={expanded ? "Collapse contributions" : "Expand contributions"}
              >
                {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
              </button>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mt-2 h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(pct, 100)}%`,
                backgroundColor: goal.status === "achieved" ? "#22c55e"
                  : goal.status === "ahead" ? "#3b82f6"
                  : goal.status === "on_track" ? "#14b8a6"
                  : goal.status === "behind" ? "#ef4444"
                  : "#6b7280",
              }}
            />
          </div>
        </div>
      </div>

      {expanded && <ContributionsPanel goal={goal} />}
    </Card>
  );
}

export default function SavingsGoalsPage() {
  const { data: goals = [], isLoading } = useSavingsGoals();
  const createMut = useCreateGoal();
  const updateMut = useUpdateGoal();
  const deleteMut = useDeleteGoal();

  const [showCreate, setShowCreate] = useState(false);
  const [editTarget, setEditTarget] = useState(null);   // goal object being edited
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [createForm, setCreateForm] = useState(EMPTY_GOAL_FORM);
  const [editForm, setEditForm] = useState(EMPTY_GOAL_FORM);

  const handleCreateChange = (k, v) => setCreateForm((f) => ({ ...f, [k]: v }));
  const handleEditChange = (k, v) => setEditForm((f) => ({ ...f, [k]: v }));

  const handleCreate = () => {
    createMut.mutate(
      {
        name: createForm.name,
        target_amount: parseFloat(createForm.target_amount),
        target_date: createForm.target_date || undefined,
      },
      {
        onSuccess: () => {
          setCreateForm(EMPTY_GOAL_FORM);
          setShowCreate(false);
        },
      }
    );
  };

  const handleEditOpen = (goal) => {
    setEditTarget(goal);
    setEditForm({
      name: goal.name,
      target_amount: String(goal.target_amount),
      target_date: toInputDate(goal.target_date),
    });
  };

  const handleEditSave = () => {
    updateMut.mutate(
      {
        id: editTarget.id,
        data: {
          name: editForm.name,
          target_amount: parseFloat(editForm.target_amount),
          target_date: editForm.target_date || null,
        },
      },
      { onSuccess: () => setEditTarget(null) }
    );
  };

  return (
    <PageWrapper>
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <PiggyBank size={22} className="text-blue-600 dark:text-blue-400" />
            Savings Goals
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Track progress toward your financial targets.
          </p>
        </div>
        {!showCreate && (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 min-h-[44px]"
          >
            <Plus size={16} /> Add goal
          </button>
        )}
      </div>

      {/* Create form */}
      {showCreate && (
        <GoalForm
          value={createForm}
          onChange={handleCreateChange}
          onSubmit={handleCreate}
          onCancel={() => { setShowCreate(false); setCreateForm(EMPTY_GOAL_FORM); }}
          submitLabel="Create goal"
          isPending={createMut.isPending}
        />
      )}

      {/* Edit form */}
      {editTarget && (
        <GoalForm
          value={editForm}
          onChange={handleEditChange}
          onSubmit={handleEditSave}
          onCancel={() => setEditTarget(null)}
          submitLabel="Save changes"
          isPending={updateMut.isPending}
        />
      )}

      {/* Goal list */}
      {isLoading ? (
        <SkeletonTable rows={3} />
      ) : goals.length === 0 && !showCreate ? (
        <EmptyState
          icon={<PiggyBank size={48} />}
          title="No savings goals yet"
          description="Start tracking your savings progress by creating your first goal."
          action={
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 min-h-[44px]"
            >
              <Plus size={16} /> Add your first goal
            </button>
          }
        />
      ) : goals.length > 0 ? (
        <div className="space-y-3">
          {goals.map((g) => (
            <GoalCard
              key={g.id}
              goal={g}
              onEdit={handleEditOpen}
              onDelete={setDeleteTarget}
            />
          ))}
        </div>
      ) : null}

      {/* Delete confirmation */}
      {deleteTarget !== null && (
        <ConfirmModal
          message="Delete this savings goal and all its contributions? This cannot be undone."
          onConfirm={() => {
            deleteMut.mutate(deleteTarget);
            setDeleteTarget(null);
          }}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </PageWrapper>
  );
}
