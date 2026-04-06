// src/components/SonOfMervan.jsx
import React, { useState, useMemo } from "react";
import {
  PlusCircle, Calculator, Trash2, TrendingUp,
  DollarSign, PieChart
} from "lucide-react";
import {
  ResponsiveContainer, LineChart, Line, CartesianGrid,
  XAxis, YAxis, Tooltip, BarChart, Bar
} from "recharts";
import { useCalculateBudget } from "../hooks/useBudget";
import { useTheme } from "../hooks/useTheme";

const CATEGORIES = [
  "Housing","Transportation","Food","Utilities","Insurance",
  "Healthcare","Entertainment","Other"
];

export default function SonOfMervan() {
  const [salary, setSalary] = useState("");
  const [expenses, setExpenses] = useState([
    { name: "", amount: "", category: "Housing" },
  ]);
  const [results, setResults] = useState(null);

  const calculateMutation = useCalculateBudget();

  const addExpense = () =>
    setExpenses((xs) => [...xs, { name: "", amount: "", category: "Housing" }]);

  const removeExpense = (i) =>
    setExpenses((xs) => (xs.length > 1 ? xs.filter((_, j) => j !== i) : xs));

  const updateExpense = (i, field, value) =>
    setExpenses((xs) => xs.map((x, j) => (j === i ? { ...x, [field]: value } : x)));

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
    <div className="min-h-dvh bg-gradient-to-br from-slate-50 to-blue-50 dark:from-gray-900 dark:to-gray-900 p-3 sm:p-4">
      <div className="mx-auto w-full max-w-6xl space-y-4 sm:space-y-6">
        {/* Header */}
        <header className="text-center py-3 sm:py-6">
          <h1 className="text-2xl sm:text-4xl font-bold text-gray-800 dark:text-gray-100">Son Of Mervan</h1>
          <p className="text-gray-600 dark:text-gray-400 text-sm sm:text-base">There are two sides to every dollar</p>
        </header>

        {/* Inputs Card */}
        <section className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-700 p-4 sm:p-6 md:p-8">
          <div className="flex items-center mb-4 sm:mb-6">
            <DollarSign className="text-blue-500 mr-2 sm:mr-3" size={22} />
            <h2 className="text-xl sm:text-2xl font-semibold text-gray-800 dark:text-gray-100">
              Financial Information
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
            {/* Salary */}
            <div className="space-y-2 sm:space-y-3">
              <label className="block text-sm font-semibold text-gray-700">
                Monthly Salary (£)
              </label>
              <input
                inputMode="decimal"
                pattern="[0-9]*[.]?[0-9]*"
                value={salary}
                onChange={(e) =>
                  setSalary(e.target.value.replace(/[^\d.]/g, ""))
                }
                className="w-full px-3 py-3 sm:py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition"
                placeholder="e.g. 2500"
              />
            </div>

            {/* Expenses */}
            <div className="space-y-2 sm:space-y-3">
              <div className="flex items-center justify-between">
                <label className="block text-sm font-semibold text-gray-700">
                  Monthly Expenses
                </label>
                <button
                  type="button"
                  onClick={addExpense}
                  className="inline-flex items-center text-blue-600 hover:text-blue-800 font-semibold px-3 py-2 rounded-lg hover:bg-blue-50 transition"
                >
                  <PlusCircle size={18} className="mr-2" />
                  Add
                </button>
              </div>

              <div className="max-h-72 sm:max-h-64 overflow-y-auto space-y-2.5">
                {expenses.map((exp, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-1 sm:grid-cols-12 gap-2 bg-gray-50 dark:bg-gray-700 px-3 py-3 rounded-xl items-center"
                  >
                    <input
                      className="sm:col-span-5 px-3 py-2.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 min-h-[44px]"
                      placeholder="Expense name"
                      value={exp.name}
                      onChange={(e) => updateExpense(i, "name", e.target.value)}
                    />
                    <input
                      inputMode="decimal"
                      pattern="[0-9]*[.]?[0-9]*"
                      className="sm:col-span-2 px-3 py-2.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 min-h-[44px]"
                      placeholder="£"
                      value={exp.amount}
                      onChange={(e) =>
                        updateExpense(i, "amount", e.target.value.replace(/[^\d.]/g, ""))
                      }
                    />
                    <select
                      className="sm:col-span-3 px-3 py-2.5 border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 min-h-[44px]"
                      value={exp.category}
                      onChange={(e) => updateExpense(i, "category", e.target.value)}
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                    <div className="sm:col-span-2 flex justify-end">
                      {expenses.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeExpense(i)}
                          className="text-red-600 hover:text-red-800 p-2 hover:bg-red-50 rounded-lg"
                          aria-label="Remove expense row"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Calculate button */}
          <div className="mt-5 sm:mt-8">
            <div className="md:hidden sticky bottom-20 sm:bottom-3 z-20">
              <button
                onClick={doCalculate}
                disabled={loading}
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white font-bold py-3 rounded-xl shadow-lg active:scale-[.99] transition disabled:opacity-60"
              >
                {loading ? "Calculating…" : (
                  <span className="inline-flex items-center justify-center">
                    <Calculator className="mr-2" size={18} />
                    Calculate Budget
                  </span>
                )}
              </button>
            </div>

            <div className="hidden md:flex justify-center">
              <button
                onClick={doCalculate}
                disabled={loading}
                className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-bold py-3 px-8 rounded-xl shadow-lg transition disabled:opacity-60"
              >
                {loading ? "Calculating…" : (
                  <span className="inline-flex items-center">
                    <Calculator className="mr-2" size={18} />
                    Calculate Budget
                  </span>
                )}
              </button>
            </div>
          </div>
        </section>

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
