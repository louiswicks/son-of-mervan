import React, { useState } from "react";
import { Bell, BellOff, Plus, Trash2, Edit2, Check, X } from "lucide-react";
import PageWrapper from "./PageWrapper";
import Card from "./Card";
import {
  useBudgetAlerts,
  useCreateAlert,
  useUpdateAlert,
  useDeleteAlert,
} from "../hooks/useAlerts";
import { useCategories } from "../hooks/useCategories";

const FALLBACK_CATEGORIES = [
  "Housing",
  "Transportation",
  "Food",
  "Utilities",
  "Insurance",
  "Healthcare",
  "Entertainment",
  "Other",
];

const THRESHOLD_PRESETS = [50, 75, 80, 90, 100];

function AlertForm({ onSubmit, onCancel, initial = {}, categories = FALLBACK_CATEGORIES }) {
  const [category, setCategory] = useState(initial.category || categories[0]);
  const [threshold, setThreshold] = useState(initial.threshold_pct ?? 80);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({ category, threshold_pct: Number(threshold) });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Category
        </label>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white min-h-[44px]"
        >
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Alert threshold
        </label>
        <div className="flex gap-2 flex-wrap mb-2">
          {THRESHOLD_PRESETS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setThreshold(p)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors min-h-[36px] ${
                threshold === p
                  ? "bg-blue-600 text-white"
                  : "bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-300 dark:hover:bg-gray-600"
              }`}
            >
              {p}%
            </button>
          ))}
        </div>
        <input
          type="number"
          min={1}
          max={100}
          value={threshold}
          onChange={(e) => setThreshold(e.target.value)}
          className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-white min-h-[44px]"
        />
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          You'll be notified when actual spending reaches this % of planned.
        </p>
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          className="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium min-h-[44px]"
        >
          {initial.id ? "Save changes" : "Create alert"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 bg-gray-200 hover:bg-gray-300 dark:bg-gray-700 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 px-4 py-2 rounded-lg text-sm font-medium min-h-[44px]"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

function AlertCard({ alert, onEdit, onDelete, onToggle }) {
  return (
    <Card className="!p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
              alert.active
                ? "bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400"
                : "bg-gray-100 dark:bg-gray-700 text-gray-400"
            }`}
          >
            {alert.active ? <Bell size={18} /> : <BellOff size={18} />}
          </div>
          <div className="min-w-0">
            <p className="font-semibold text-gray-900 dark:text-white truncate">
              {alert.category}
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Alert at{" "}
              <span className="font-medium text-blue-600 dark:text-blue-400">
                {alert.threshold_pct}%
              </span>{" "}
              of planned
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => onToggle(alert)}
            title={alert.active ? "Disable alert" : "Enable alert"}
            className={`min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg text-sm transition-colors ${
              alert.active
                ? "text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/30"
                : "text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700"
            }`}
          >
            {alert.active ? <Check size={16} /> : <X size={16} />}
          </button>
          <button
            onClick={() => onEdit(alert)}
            className="min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <Edit2 size={16} />
          </button>
          <button
            onClick={() => onDelete(alert.id)}
            className="min-w-[36px] min-h-[36px] flex items-center justify-center rounded-lg text-red-500 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>
    </Card>
  );
}

export default function BudgetAlertsPage() {
  const { data: alerts = [], isLoading } = useBudgetAlerts();
  const createMutation = useCreateAlert();
  const updateMutation = useUpdateAlert();
  const deleteMutation = useDeleteAlert();

  const { data: categoriesData } = useCategories();
  const categories = categoriesData?.map((c) => c.name) ?? FALLBACK_CATEGORIES;

  const [showForm, setShowForm] = useState(false);
  const [editingAlert, setEditingAlert] = useState(null);

  const handleCreate = async (payload) => {
    await createMutation.mutateAsync(payload);
    setShowForm(false);
  };

  const handleUpdate = async (payload) => {
    await updateMutation.mutateAsync({ id: editingAlert.id, payload });
    setEditingAlert(null);
  };

  const handleToggle = (alert) => {
    updateMutation.mutate({ id: alert.id, payload: { active: !alert.active } });
  };

  const handleDelete = (id) => {
    deleteMutation.mutate(id);
  };

  return (
    <PageWrapper className="max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Budget Alerts</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Get notified when spending reaches your threshold
          </p>
        </div>
        {!showForm && !editingAlert && (
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium min-h-[44px]"
          >
            <Plus size={16} />
            New alert
          </button>
        )}
      </div>

      {/* Create form */}
      {showForm && (
        <Card>
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">New alert</h3>
          <AlertForm
            onSubmit={handleCreate}
            onCancel={() => setShowForm(false)}
            categories={categories}
          />
        </Card>
      )}

      {/* Edit form */}
      {editingAlert && (
        <Card className="border-blue-300 dark:border-blue-600">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-4">
            Edit alert — {editingAlert.category}
          </h3>
          <AlertForm
            initial={editingAlert}
            onSubmit={handleUpdate}
            onCancel={() => setEditingAlert(null)}
            categories={categories}
          />
        </Card>
      )}

      {/* Alert list */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-20 rounded-xl bg-gray-200 dark:bg-gray-700 animate-pulse"
            />
          ))}
        </div>
      ) : alerts.length === 0 && !showForm ? (
        <Card className="text-center py-16">
          <Bell size={40} className="mx-auto mb-4 text-gray-300 dark:text-gray-600" />
          <p className="text-gray-500 dark:text-gray-400 font-medium">No alerts configured</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1 mb-6">
            Set a threshold and we'll notify you before you overspend.
          </p>
          <button
            onClick={() => setShowForm(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium"
          >
            Create your first alert
          </button>
        </Card>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onEdit={setEditingAlert}
              onDelete={handleDelete}
              onToggle={handleToggle}
            />
          ))}
        </div>
      )}

      {/* Info card */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl p-4">
        <p className="text-sm text-blue-800 dark:text-blue-200 font-medium mb-1">How alerts work</p>
        <p className="text-sm text-blue-700 dark:text-blue-300">
          Each night at 00:10 UTC, your spending is compared to your planned budget.
          If any category crosses your threshold, you'll receive an in-app notification
          and an email. One alert per category per calendar month.
        </p>
      </div>
    </PageWrapper>
  );
}
