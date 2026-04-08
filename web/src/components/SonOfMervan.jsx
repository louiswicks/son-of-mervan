// src/components/SonOfMervan.jsx
import React, { useState, useMemo, useEffect, useRef } from "react";
import {
  PlusCircle, Calculator, Trash2, TrendingUp,
  DollarSign, PieChart, LayoutTemplate, X, Flame
} from "lucide-react";
import toast from "react-hot-toast";
import {
  ResponsiveContainer, LineChart, Line, CartesianGrid,
  XAxis, YAxis, Tooltip, BarChart, Bar
} from "recharts";
import { useCalculateBudget } from "../hooks/useBudget";
import { useTheme } from "../hooks/useTheme";
import { useCategories } from "../hooks/useCategories";
import { useStreaks } from "../hooks/useInsights";
import { getMonthlyTracker } from "../api/expenses";

const FALLBACK_CATEGORIES = [
  "Housing","Transportation","Food","Utilities","Insurance",
  "Healthcare","Entertainment","Other"
];

const BUDGET_TEMPLATES = [
  {
    id: "50-30-20",
    name: "50/30/20 Rule",
    description: "50% needs · 30% wants · 20% savings — a classic balanced approach.",
    savings_pct: 20,
    expenses: [
      { name: "Rent / Mortgage", category: "Housing",        pct: 25 },
      { name: "Groceries",       category: "Food",           pct: 10 },
      { name: "Transport",       category: "Transportation",  pct: 8  },
      { name: "Utilities",       category: "Utilities",      pct: 4  },
      { name: "Insurance",       category: "Insurance",      pct: 3  },
      { name: "Entertainment",   category: "Entertainment",  pct: 15 },
      { name: "Healthcare",      category: "Healthcare",     pct: 5  },
      { name: "Other",           category: "Other",          pct: 10 },
    ],
  },
  {
    id: "zero-based",
    name: "Zero-Based",
    description: "Every pound is allocated — income minus expenses equals zero.",
    savings_pct: 15,
    expenses: [
      { name: "Rent / Mortgage", category: "Housing",        pct: 30 },
      { name: "Groceries",       category: "Food",           pct: 12 },
      { name: "Transport",       category: "Transportation",  pct: 10 },
      { name: "Utilities",       category: "Utilities",      pct: 6  },
      { name: "Insurance",       category: "Insurance",      pct: 5  },
      { name: "Healthcare",      category: "Healthcare",     pct: 7  },
      { name: "Entertainment",   category: "Entertainment",  pct: 10 },
      { name: "Savings",         category: "Other",          pct: 15 },
      { name: "Other",           category: "Other",          pct: 5  },
    ],
  },
  {
    id: "minimalist",
    name: "Minimalist",
    description: "Essentials only — maximise savings by cutting discretionary spend.",
    savings_pct: 30,
    expenses: [
      { name: "Rent / Mortgage", category: "Housing",        pct: 35 },
      { name: "Groceries",       category: "Food",           pct: 15 },
      { name: "Transport",       category: "Transportation",  pct: 10 },
      { name: "Utilities",       category: "Utilities",      pct: 5  },
      { name: "Other",           category: "Other",          pct: 5  },
    ],
  },
  {
    id: "student",
    name: "Student Budget",
    description: "For those on tight budgets — essentials first with a little fun.",
    savings_pct: 10,
    expenses: [
      { name: "Rent",            category: "Housing",        pct: 40 },
      { name: "Groceries",       category: "Food",           pct: 20 },
      { name: "Transport",       category: "Transportation",  pct: 10 },
      { name: "Entertainment",   category: "Entertainment",  pct: 8  },
      { name: "Healthcare",      category: "Healthcare",     pct: 5  },
      { name: "Other",           category: "Other",          pct: 7  },
    ],
  },
];

export default function SonOfMervan() {
  const [salary, setSalary] = useState("");
  const [expenses, setExpenses] = useState([
    { name: "", amount: "", category: "Housing" },
  ]);
  const [results, setResults] = useState(null);
  const [showTemplateModal, setShowTemplateModal] = useState(false);
  const [loadingPrevMonth, setLoadingPrevMonth] = useState(false);

  const calculateMutation = useCalculateBudget();
  const { data: categoriesData } = useCategories();
  const { data: streakData } = useStreaks();
  const shownMilestoneRef = useRef(null);

  useEffect(() => {
    if (!streakData) return;
    const streak = streakData.current_streak;
    const milestones = [12, 6, 3];
    for (const m of milestones) {
      if (streak === m && shownMilestoneRef.current !== m) {
        shownMilestoneRef.current = m;
        toast.success(`🔥 ${m}-month streak! You're on a roll — ${m} months under budget!`, {
          duration: 6000,
          icon: "🏆",
        });
        break;
      }
    }
  }, [streakData]);
  const CATEGORIES = useMemo(
    () => categoriesData?.map((c) => c.name) ?? FALLBACK_CATEGORIES,
    [categoriesData]
  );

  const addExpense = () =>
    setExpenses((xs) => [...xs, { name: "", amount: "", category: "Housing" }]);

  const removeExpense = (i) =>
    setExpenses((xs) => (xs.length > 1 ? xs.filter((_, j) => j !== i) : xs));

  const updateExpense = (i, field, value) =>
    setExpenses((xs) => xs.map((x, j) => (j === i ? { ...x, [field]: value } : x)));

  const applyTemplate = (template) => {
    const salaryNum = parseFloat(salary) || 0;
    setExpenses(
      template.expenses.map((e) => ({
        name: e.name,
        category: e.category,
        amount: salaryNum > 0 ? String(Math.round((salaryNum * e.pct) / 100)) : "",
      }))
    );
    setShowTemplateModal(false);
  };

  const prevMonthLabel = (() => {
    const now = new Date();
    const y = now.getFullYear();
    const m = now.getMonth(); // 0-based, so current month index
    const prevM = m === 0 ? 12 : m;
    const prevY = m === 0 ? y - 1 : y;
    return {
      str: `${prevY}-${String(prevM).padStart(2, "0")}`,
      display: new Date(prevY, prevM - 1).toLocaleString("default", { month: "long", year: "numeric" }),
    };
  })();

  const loadPrevMonth = async () => {
    setLoadingPrevMonth(true);
    try {
      const data = await getMonthlyTracker(prevMonthLabel.str, { page_size: 100 });
      const items = data?.expenses?.items ?? [];
      if (!items.length && !data?.salary_planned) {
        toast(`No budget found for ${prevMonthLabel.display}`, { icon: "ℹ️" });
        return;
      }
      if (data.salary_planned) setSalary(String(data.salary_planned));
      if (items.length) {
        setExpenses(
          items.map((e) => ({
            name: e.name,
            category: e.category,
            amount: String(e.planned_amount),
          }))
        );
      }
      toast.success(`Loaded budget from ${prevMonthLabel.display}`);
    } catch {
      toast.error("Could not load previous month's budget");
    } finally {
      setLoadingPrevMonth(false);
    }
  };

  const doCalculate = async () => {
    const currentMonth = new Date().toISOString().slice(0, 7);
    const body = {
      month: currentMonth,
      monthly_salary: parseFloat(salary) || 0,
      expenses: expenses
        .filter((e) => e.name && e.amount !== "")
        .map((e) => ({
          name: e.name,
          amount: parseFloat(e.amount) || 0,
          category: e.category,
        })),
    };
    try {
      const data = await calculateMutation.mutateAsync({ payload: body, commit: false });
      setResults(data);
    } catch {
      // onError in the mutation hook handles the toast
    }
  };

  const savingsData = useMemo(() => {
    if (!results || results.remaining_budget <= 0) return [];
    const m = results.remaining_budget;
    return Array.from({ length: 25 }, (_, i) => ({
      month: i,
      savings: m * i,
    }));
  }, [results]);

  const categoryData = useMemo(() => {
    if (!results) return [];
    const entries = Object.entries(results.expenses_by_category || {});
    return entries.map(([category, amount]) => ({ category, amount }));
  }, [results]);

  const loading = calculateMutation.isPending;
  const { theme } = useTheme();
  const chartColors = useMemo(() => ({
    primary:       theme === "dark" ? "#60a5fa" : "#3b82f6",
    success:       theme === "dark" ? "#34d399" : "#10b981",
    grid:          theme === "dark" ? "#334155" : "#e5e7eb",
    axis:          theme === "dark" ? "#94a3b8" : "#6b7280",
    tooltipBg:     theme === "dark" ? "#1e293b" : "#ffffff",
    tooltipBorder: theme === "dark" ? "#334155" : "#e5e7eb",
    tooltipText:   theme === "dark" ? "#f1f5f9" : "#111827",
  }), [theme]);
  const tooltipStyle = {
    backgroundColor: chartColors.tooltipBg,
    border: `1px solid ${chartColors.tooltipBorder}`,
    color: chartColors.tooltipText,
  };

  return (
    <div className="min-h-dvh bg-gray-50 dark:bg-gray-900 p-3 sm:p-6">
      <div className="mx-auto w-full max-w-3xl space-y-4 sm:space-y-6">

        {/* Streak Badge */}
        {streakData && streakData.current_streak > 0 && (
          <div
            className="flex items-center gap-2 bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800 rounded-2xl px-4 py-3"
            data-testid="streak-badge"
          >
            <Flame className="text-orange-500 shrink-0" size={20} />
            <span className="font-semibold text-orange-700 dark:text-orange-400">
              {streakData.current_streak}-month streak
            </span>
            <span className="text-orange-600 dark:text-orange-500 text-sm">
              — {streakData.current_streak} consecutive month{streakData.current_streak !== 1 ? "s" : ""} under budget!
            </span>
            {streakData.longest_streak > streakData.current_streak && (
              <span className="ml-auto text-xs text-orange-500 dark:text-orange-400">
                Best: {streakData.longest_streak}
              </span>
            )}
          </div>
        )}

        {/* Inputs Card */}
        <section className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5 sm:p-7">
          <div className="flex items-center gap-2 mb-5">
            <DollarSign className="text-blue-500 shrink-0" size={20} />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              Son Of Mervan
            </h2>
          </div>

          {/* Salary */}
          <div className="mb-5">
            <label htmlFor="budget-salary" className="block text-sm font-medium text-gray-600 dark:text-gray-400 mb-1.5">
              Monthly take-home salary (£)
            </label>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500 font-medium select-none" aria-hidden="true">£</span>
              <input
                id="budget-salary"
                inputMode="decimal"
                pattern="[0-9]*[.]?[0-9]*"
                value={salary}
                onChange={(e) => setSalary(e.target.value.replace(/[^\d.]/g, ""))}
                className="w-full pl-7 pr-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition placeholder-gray-400"
                placeholder="0.00"
              />
            </div>
          </div>

          {/* Expenses */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Monthly expenses
              </label>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={loadPrevMonth}
                  disabled={loadingPrevMonth}
                  aria-label={`Load ${prevMonthLabel.display} budget`}
                  data-testid="load-prev-month-btn"
                  className="inline-flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 font-medium px-2.5 py-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition disabled:opacity-50"
                >
                  {loadingPrevMonth ? "Loading…" : `Load ${prevMonthLabel.display}`}
                </button>
                <button
                  type="button"
                  onClick={() => setShowTemplateModal(true)}
                  className="inline-flex items-center gap-1.5 text-sm text-purple-600 dark:text-purple-400 hover:text-purple-800 dark:hover:text-purple-300 font-medium px-2.5 py-1.5 rounded-lg hover:bg-purple-50 dark:hover:bg-purple-900/30 transition"
                >
                  <LayoutTemplate size={15} />
                  Use Template
                </button>
                <button
                  type="button"
                  onClick={addExpense}
                  className="inline-flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium px-2.5 py-1.5 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-900/30 transition"
                >
                  <PlusCircle size={15} />
                  Add row
                </button>
              </div>
            </div>

            {/* Column headers — desktop only */}
            <div className="hidden sm:grid grid-cols-12 gap-2 px-1 mb-1">
              <span className="col-span-5 text-xs text-gray-400 dark:text-gray-500 font-medium">Name</span>
              <span className="col-span-3 text-xs text-gray-400 dark:text-gray-500 font-medium">Amount</span>
              <span className="col-span-3 text-xs text-gray-400 dark:text-gray-500 font-medium">Category</span>
              <span className="col-span-1" aria-hidden="true" />
            </div>

            <div className="space-y-3 sm:space-y-2">
              {expenses.map((exp, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-gray-200 dark:border-gray-700 p-3 sm:border-0 sm:rounded-none sm:p-0 grid grid-cols-1 sm:grid-cols-12 gap-y-2 sm:gap-2 items-start sm:items-center"
                >
                  {/* Name */}
                  <div className="sm:col-span-5">
                    <label className="block sm:hidden text-xs text-gray-400 dark:text-gray-500 font-medium mb-1">Name</label>
                    <input
                      className="w-full px-3 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition placeholder-gray-400 dark:placeholder-gray-500 text-sm min-h-[44px] sm:min-h-0"
                      placeholder="e.g. Rent"
                      aria-label={`Expense ${i + 1} name`}
                      value={exp.name}
                      onChange={(e) => updateExpense(i, "name", e.target.value)}
                    />
                  </div>

                  {/* Amount */}
                  <div className="sm:col-span-3">
                    <label className="block sm:hidden text-xs text-gray-400 dark:text-gray-500 font-medium mb-1">Amount</label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500 text-sm select-none" aria-hidden="true">£</span>
                      <input
                        inputMode="decimal"
                        pattern="[0-9]*[.]?[0-9]*"
                        aria-label={`Expense ${i + 1} amount`}
                        className="w-full pl-7 pr-3 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition placeholder-gray-400 dark:placeholder-gray-500 text-sm min-h-[44px] sm:min-h-0"
                        placeholder="0.00"
                        value={exp.amount}
                        onChange={(e) => updateExpense(i, "amount", e.target.value.replace(/[^\d.]/g, ""))}
                      />
                    </div>
                  </div>

                  {/* Category */}
                  <div className="sm:col-span-3">
                    <label className="block sm:hidden text-xs text-gray-400 dark:text-gray-500 font-medium mb-1">Category</label>
                    <select
                      aria-label={`Expense ${i + 1} category`}
                      className="w-full px-3 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition text-sm min-h-[44px] sm:min-h-0"
                      value={exp.category}
                      onChange={(e) => updateExpense(i, "category", e.target.value)}
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </div>

                  {/* Delete */}
                  <div className="sm:col-span-1 flex sm:justify-center">
                    {expenses.length > 1 ? (
                      <button
                        type="button"
                        onClick={() => removeExpense(i)}
                        className="text-gray-400 hover:text-red-500 p-1.5 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition min-h-[44px] min-w-[44px] sm:min-h-0 sm:min-w-0 flex items-center justify-center"
                        aria-label="Remove row"
                      >
                        <Trash2 size={15} />
                      </button>
                    ) : <div className="hidden sm:block w-8" />}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Calculate button */}
          <div className="mt-6">
            <button
              onClick={doCalculate}
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold py-3 rounded-xl shadow-sm transition disabled:opacity-60 flex items-center justify-center gap-2"
            >
              <Calculator size={17} />
              {loading ? "Calculating…" : "Calculate Budget"}
            </button>
          </div>
        </section>

        {/* Template Modal */}
        {showTemplateModal && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
            role="dialog"
            aria-modal="true"
            aria-label="Budget template selector"
            onClick={(e) => { if (e.target === e.currentTarget) setShowTemplateModal(false); }}
          >
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-5 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-2">
                  <LayoutTemplate className="text-purple-500" size={20} />
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    Choose a Budget Template
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={() => setShowTemplateModal(false)}
                  aria-label="Close template selector"
                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="p-5 space-y-4">
                {BUDGET_TEMPLATES.map((template) => (
                  <div
                    key={template.id}
                    className="border border-gray-200 dark:border-gray-700 rounded-xl p-4 hover:border-purple-400 dark:hover:border-purple-500 transition"
                  >
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div>
                        <h3 className="font-semibold text-gray-900 dark:text-gray-100">
                          {template.name}
                        </h3>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                          {template.description}
                        </p>
                      </div>
                      <span className="shrink-0 text-xs font-medium bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 px-2 py-1 rounded-full">
                        {template.savings_pct}% savings
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {template.expenses.map((e) => (
                        <span
                          key={e.name}
                          className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 px-2 py-0.5 rounded-full"
                        >
                          {e.name} · {e.pct}%
                        </span>
                      ))}
                    </div>

                    <button
                      type="button"
                      onClick={() => applyTemplate(template)}
                      className="w-full bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium py-2 rounded-lg transition"
                    >
                      Use this template
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {results && (
          <section className="space-y-4 sm:space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white p-4 sm:p-6 rounded-2xl shadow-xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-blue-100 text-sm">Monthly Salary</span>
                  <DollarSign size={20} className="text-blue-200" />
                </div>
                <div className="text-2xl sm:text-3xl font-bold">
                  £{(results.monthly_salary || 0).toLocaleString()}
                </div>
              </div>

              <div className="bg-gradient-to-br from-red-500 to-red-600 text-white p-4 sm:p-6 rounded-2xl shadow-xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-red-100 text-sm">Total Expenses</span>
                  <PieChart size={20} className="text-red-200" />
                </div>
                <div className="text-2xl sm:text-3xl font-bold">
                  £{(results.total_expenses || 0).toLocaleString()}
                </div>
              </div>

              <div
                className={`text-white p-4 sm:p-6 rounded-2xl shadow-xl ${
                  results.remaining_budget >= 0
                    ? "bg-gradient-to-br from-green-500 to-green-600"
                    : "bg-gradient-to-br from-red-500 to-red-600"
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm">
                    {results.remaining_budget >= 0 ? "Monthly Savings" : "Budget Deficit"}
                  </span>
                  <TrendingUp size={20} />
                </div>
                <div className="text-2xl sm:text-3xl font-bold">
                  £{Math.abs(results.remaining_budget || 0).toLocaleString()}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
              {results.remaining_budget > 0 && (
                <div className="bg-white dark:bg-gray-800 p-4 sm:p-6 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-700">
                  <h3 className="text-lg sm:text-xl font-semibold text-gray-800 dark:text-gray-100 mb-3 sm:mb-4 flex items-center">
                    <TrendingUp className="mr-2 text-green-500" size={20} />
                    Savings Projection
                  </h3>
                  <div className="h-60 sm:h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={savingsData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                        <XAxis dataKey="month" tick={{ fill: chartColors.axis }} />
                        <YAxis tickFormatter={(v) => `£${v.toLocaleString()}`} tick={{ fill: chartColors.axis }} />
                        <Tooltip
                          formatter={(v) => [`£${Number(v).toLocaleString()}`, "Savings"]}
                          contentStyle={tooltipStyle}
                        />
                        <Line type="monotone" dataKey="savings" stroke={chartColors.success} strokeWidth={3} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              <div className="bg-white dark:bg-gray-800 p-4 sm:p-6 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-700">
                <h3 className="text-lg sm:text-xl font-semibold text-gray-800 dark:text-gray-100 mb-3 sm:mb-4 flex items-center">
                  <PieChart className="mr-2 text-blue-500" size={20} />
                  Expense Breakdown
                </h3>

                {categoryData.length > 0 && (
                  <div className="h-60 sm:h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={categoryData}>
                        <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                        <XAxis dataKey="category" interval={0} angle={-30} textAnchor="end" height={60} tick={{ fill: chartColors.axis }} />
                        <YAxis tickFormatter={(v) => `£${v.toLocaleString()}`} tick={{ fill: chartColors.axis }} />
                        <Tooltip
                          formatter={(v) => [`£${Number(v).toLocaleString()}`, "Amount"]}
                          contentStyle={tooltipStyle}
                        />
                        <Bar dataKey="amount" fill={chartColors.primary} radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {results?.expenses_by_category && (
                  <ul className="mt-3 sm:mt-4 space-y-2">
                    {Object.entries(results.expenses_by_category).map(([cat, amt]) => (
                      <li key={cat} className="flex justify-between bg-gray-50 dark:bg-gray-700 px-3 py-2 rounded-lg">
                        <span className="font-medium text-gray-700 dark:text-gray-200">{cat}</span>
                        <span className="font-semibold">£{Number(amt).toLocaleString()}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
