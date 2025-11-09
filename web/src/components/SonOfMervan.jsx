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

const API_BASE_URL = "https://son-of-mervan-production.up.railway.app";

const CATEGORIES = [
  "Housing","Transportation","Food","Utilities","Insurance",
  "Healthcare","Entertainment","Other"
];

export default function SonOfMervan({ token, onSaved }) {
  const [salary, setSalary] = useState("");
  const [expenses, setExpenses] = useState([
    { name: "", amount: "", category: "Housing" },
  ]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const addExpense = () =>
    setExpenses((xs) => [...xs, { name: "", amount: "", category: "Housing" }]);

  const removeExpense = (i) =>
    setExpenses((xs) => (xs.length > 1 ? xs.filter((_, j) => j !== i) : xs));

  const updateExpense = (i, field, value) =>
    setExpenses((xs) => xs.map((x, j) => (j === i ? { ...x, [field]: value } : x)));

  const calculateBudget = async () => {
    setLoading(true);

    // Always use current month (YYYY-MM) for “Current Budget”
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
      const res = await fetch(`${API_BASE_URL}/calculate-budget?commit=false`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        if (res.status === 401) {
          localStorage.removeItem("authToken");
          alert("Session expired. Please login again.");
          window.location.reload();
          return;
        }
        throw new Error("Failed to calculate budget.");
      }

      const data = await res.json();
      setResults(data);
      onSaved?.(); // keep triggering refreshes elsewhere if you want
    } catch (err) {
      console.error(err);
      alert(err.message || "Network error. Please try again.");
    } finally {
      setLoading(false);
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

  return (
    <div className="min-h-dvh bg-gradient-to-br from-slate-50 to-blue-50 p-3 sm:p-4">
      <div className="mx-auto w-full max-w-6xl space-y-4 sm:space-y-6">
        {/* Header */}
        <header className="text-center py-3 sm:py-6">
          <h1 className="text-2xl sm:text-4xl font-bold text-gray-800">Son Of Mervan</h1>
          <p className="text-gray-600 text-sm sm:text-base">There are two sides to every dollar</p>
        </header>

        {/* Inputs Card */}
        <section className="bg-white rounded-2xl shadow-xl border border-gray-100 p-4 sm:p-6 md:p-8">
          <div className="flex items-center mb-4 sm:mb-6">
            <DollarSign className="text-blue-500 mr-2 sm:mr-3" size={22} />
            <h2 className="text-xl sm:text-2xl font-semibold text-gray-800">
              Financial Information
            </h2>
          </div>

          {/* Mobile-first: stack; split into 2 cols on md+ */}
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

              {/* Each row collapses to a tidy grid on phones */}
              <div className="max-h-72 sm:max-h-64 overflow-y-auto space-y-2.5">
                {expenses.map((exp, i) => (
                  <div
                    key={i}
                    className="grid grid-cols-1 xs:grid-cols-2 md:grid-cols-12 gap-2 bg-gray-50 px-3 py-3 rounded-xl items-center"
                  >
                    {/* Name */}
                    <input
                      className="md:col-span-5 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      placeholder="Expense name"
                      value={exp.name}
                      onChange={(e) => updateExpense(i, "name", e.target.value)}
                    />
                    {/* Amount */}
                    <input
                      inputMode="decimal"
                      pattern="[0-9]*[.]?[0-9]*"
                      className="md:col-span-2 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      placeholder="£"
                      value={exp.amount}
                      onChange={(e) =>
                        updateExpense(i, "amount", e.target.value.replace(/[^\d.]/g, ""))
                      }
                    />
                    {/* Category */}
                    <select
                      className="md:col-span-3 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      value={exp.category}
                      onChange={(e) => updateExpense(i, "category", e.target.value)}
                    >
                      {CATEGORIES.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                    {/* Remove */}
                    <div className="md:col-span-2 flex justify-end">
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

          {/* Calculate button (sticky on mobile) */}
          <div className="mt-5 sm:mt-8">
            <div className="md:hidden sticky bottom-3 z-20">
              <button
                onClick={calculateBudget}
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
                onClick={calculateBudget}
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
            {/* Cards */}
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
              {/* Savings projection: hide on tiny screens if no savings */}
              {results.remaining_budget > 0 && (
                <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-xl border border-gray-100">
                  <h3 className="text-lg sm:text-xl font-semibold text-gray-800 mb-3 sm:mb-4 flex items-center">
                    <TrendingUp className="mr-2 text-green-500" size={20} />
                    Savings Projection
                  </h3>
                  <div className="h-60 sm:h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={savingsData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="month" />
                        <YAxis tickFormatter={(v) => `£${v.toLocaleString()}`} />
                        <Tooltip formatter={(v) => [`£${Number(v).toLocaleString()}`, "Savings"]} />
                        <Line type="monotone" dataKey="savings" stroke="#10b981" strokeWidth={3} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              <div className="bg-white p-4 sm:p-6 rounded-2xl shadow-xl border border-gray-100">
                <h3 className="text-lg sm:text-xl font-semibold text-gray-800 mb-3 sm:mb-4 flex items-center">
                  <PieChart className="mr-2 text-blue-500" size={20} />
                  Expense Breakdown
                </h3>

                {categoryData.length > 0 && (
                  <div className="h-60 sm:h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={categoryData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="category" interval={0} angle={-30} textAnchor="end" height={60} />
                        <YAxis tickFormatter={(v) => `£${v.toLocaleString()}`} />
                        <Tooltip formatter={(v) => [`£${Number(v).toLocaleString()}`, "Amount"]} />
                        <Bar dataKey="amount" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {results?.expenses_by_category && (
                  <ul className="mt-3 sm:mt-4 space-y-2">
                    {Object.entries(results.expenses_by_category).map(([cat, amt]) => (
                      <li key={cat} className="flex justify-between bg-gray-50 px-3 py-2 rounded-lg">
                        <span className="font-medium text-gray-700">{cat}</span>
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
