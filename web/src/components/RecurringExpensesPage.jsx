// src/components/RecurringExpensesPage.jsx
import React, { useState } from "react";
import { Plus, Pencil, Trash2, RefreshCw, X, Check } from "lucide-react";
import {
  useRecurring,
  useCreateRecurring,
  useUpdateRecurring,
  useDeleteRecurring,
  useTriggerGenerate,
} from "../hooks/useRecurring";
import ConfirmModal from "./ConfirmModal";
import { SkeletonTable } from "./Skeleton";

const CATEGORIES = [
  "Housing", "Transportation", "Food", "Utilities",
  "Insurance", "Healthcare", "Entertainment", "Other",
];

const FREQUENCIES = ["daily", "weekly", "monthly", "yearly"];

const FREQ_LABELS = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  yearly: "Yearly",
};

const EMPTY_FORM = {
  name: "",
  category: "Housing",
  planned_amount: "",
  frequency: "monthly",
  start_date: new Date().toISOString().slice(0, 10),
  end_date: "",
};

function toISOInput(dt) {
  if (!dt) return "";
  return new Date(dt).toISOString().slice(0, 10);
}

function FormRow({ value, onChange, onSubmit, onCancel, submitLabel, isPending }) {
  return (
    <div className="bg-white dark:bg-gray-800 border border-blue-300 dark:border-blue-600 rounded-xl p-4 mb-4 shadow-sm">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Name</label>
          <input
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[44px]"
            placeholder="e.g. Rent"
            value={value.name}
            onChange={(e) => onChange("name", e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Category</label>
          <select
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[44px]"
            value={value.category}
            onChange={(e) => onChange("category", e.target.value)}
          >
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Amount (£)</label>
          <input
            type="number"
            min="0"
            step="0.01"
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[44px]"
            placeholder="0.00"
            value={value.planned_amount}
            onChange={(e) => onChange("planned_amount", e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Frequency</label>
          <select
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[44px]"
            value={value.frequency}
            onChange={(e) => onChange("frequency", e.target.value)}
          >
            {FREQUENCIES.map((f) => (
              <option key={f} value={f}>{FREQ_LABELS[f]}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Start date</label>
          <input
            type="date"
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[44px]"
            value={value.start_date}
            onChange={(e) => onChange("start_date", e.target.value)}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">End date <span className="text-gray-400">(optional)</span></label>
          <input
            type="date"
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 min-h-[44px]"
            value={value.end_date}
            onChange={(e) => onChange("end_date", e.target.value)}
          />
        </div>
      </div>
      <div className="flex gap-2 mt-4 justify-end">
        <button
          onClick={onCancel}
          className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 min-h-[44px]"
        >
          <X size={16} /> Cancel
        </button>
        <button
          onClick={onSubmit}
          disabled={isPending}
          className="flex items-center gap-1 px-4 py-2 rounded-lg text-sm bg-blue-600 hover:bg-blue-700 text-white font-medium min-h-[44px] disabled:opacity-50"
        >
          <Check size={16} /> {isPending ? "Saving…" : submitLabel}
        </button>
      </div>
    </div>
  );
}

export default function RecurringExpensesPage() {
  const { data: items = [], isLoading } = useRecurring();
  const createMutation = useCreateRecurring();
  const updateMutation = useUpdateRecurring();
  const deleteMutation = useDeleteRecurring();
  const generateMutation = useTriggerGenerate();

  const [showAdd, setShowAdd] = useState(false);
  const [addForm, setAddForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [deleteTarget, setDeleteTarget] = useState(null);

  const handleAdd = async () => {
    if (!addForm.name || !addForm.planned_amount) return;
    await createMutation.mutateAsync({
      ...addForm,
      planned_amount: parseFloat(addForm.planned_amount),
      start_date: new Date(addForm.start_date).toISOString(),
      end_date: addForm.end_date ? new Date(addForm.end_date).toISOString() : null,
    });
    setShowAdd(false);
    setAddForm(EMPTY_FORM);
  };

  const startEdit = (item) => {
    setEditingId(item.id);
    setEditForm({
      name: item.name,
      category: item.category,
      planned_amount: String(item.planned_amount),
      frequency: item.frequency,
      start_date: toISOInput(item.start_date),
      end_date: toISOInput(item.end_date),
    });
  };

  const handleUpdate = async () => {
    await updateMutation.mutateAsync({
      id: editingId,
      data: {
        ...editForm,
        planned_amount: parseFloat(editForm.planned_amount),
        start_date: new Date(editForm.start_date).toISOString(),
        end_date: editForm.end_date ? new Date(editForm.end_date).toISOString() : null,
      },
    });
    setEditingId(null);
  };

  const handleDelete = async () => {
    await deleteMutation.mutateAsync(deleteTarget);
    setDeleteTarget(null);
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Recurring Expenses</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Planned rows are auto-generated daily into your monthly budget.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="flex items-center gap-1 px-3 py-2 rounded-lg text-sm border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 min-h-[44px] disabled:opacity-50"
            title="Generate planned rows for this month now"
          >
            <RefreshCw size={16} className={generateMutation.isPending ? "animate-spin" : ""} />
            <span className="hidden sm:inline">Generate now</span>
          </button>
          <button
            onClick={() => { setShowAdd(true); setEditingId(null); }}
            className="flex items-center gap-1 px-4 py-2 rounded-lg text-sm bg-blue-600 hover:bg-blue-700 text-white font-medium min-h-[44px]"
          >
            <Plus size={16} /> Add recurring
          </button>
        </div>
      </div>

      {/* Add form */}
      {showAdd && (
        <FormRow
          value={addForm}
          onChange={(field, val) => setAddForm((f) => ({ ...f, [field]: val }))}
          onSubmit={handleAdd}
          onCancel={() => setShowAdd(false)}
          submitLabel="Create"
          isPending={createMutation.isPending}
        />
      )}

      {/* List */}
      {isLoading ? (
        <SkeletonTable rows={4} />
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-gray-400 dark:text-gray-500">
          <RefreshCw size={40} className="mx-auto mb-3 opacity-30" />
          <p className="font-medium">No recurring expenses yet</p>
          <p className="text-sm mt-1">Add one above — it'll appear in each month's planned budget automatically.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) =>
            editingId === item.id ? (
              <FormRow
                key={item.id}
                value={editForm}
                onChange={(field, val) => setEditForm((f) => ({ ...f, [field]: val }))}
                onSubmit={handleUpdate}
                onCancel={() => setEditingId(null)}
                submitLabel="Save"
                isPending={updateMutation.isPending}
              />
            ) : (
              <div
                key={item.id}
                className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 flex items-center gap-4 shadow-sm"
              >
                {/* Frequency badge */}
                <span className="hidden sm:inline-flex shrink-0 text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 uppercase tracking-wide">
                  {item.frequency}
                </span>

                {/* Main info */}
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 dark:text-gray-100 truncate">{item.name}</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {item.category}
                    {item.end_date && (
                      <> · ends {toISOInput(item.end_date)}</>
                    )}
                    {item.last_generated_at && (
                      <> · last generated {toISOInput(item.last_generated_at)}</>
                    )}
                  </p>
                </div>

                {/* Amount */}
                <p className="shrink-0 text-base font-semibold text-gray-900 dark:text-gray-100">
                  £{item.planned_amount.toFixed(2)}
                  <span className="text-xs font-normal text-gray-500 dark:text-gray-400 ml-1 sm:hidden">
                    /{item.frequency}
                  </span>
                </p>

                {/* Actions */}
                <div className="flex gap-1 shrink-0">
                  <button
                    onClick={() => startEdit(item)}
                    className="p-2 rounded-lg text-gray-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/30 min-w-[44px] min-h-[44px] flex items-center justify-center"
                    aria-label="Edit"
                  >
                    <Pencil size={16} />
                  </button>
                  <button
                    onClick={() => setDeleteTarget(item.id)}
                    className="p-2 rounded-lg text-gray-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 min-w-[44px] min-h-[44px] flex items-center justify-center"
                    aria-label="Delete"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            )
          )}
        </div>
      )}

      {deleteTarget !== null && (
        <ConfirmModal
          message="Delete this recurring expense? Future months won't include it, but existing planned rows are kept."
          onConfirm={handleDelete}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}
