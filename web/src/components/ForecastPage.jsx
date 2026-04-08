// src/components/ForecastPage.jsx
import React, { useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp, TrendingDown, AlertTriangle, DollarSign } from "lucide-react";
import { useForecast } from "../hooks/useForecast";
import PageWrapper from "./PageWrapper";
import Card from "./Card";

// -------------------- helpers --------------------

function fmt(value, currency = "GBP") {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

function monthLabel(yyyyMm) {
  const [year, month] = yyyyMm.split("-");
  return new Date(Number(year), Number(month) - 1, 1).toLocaleString("en-GB", {
    month: "short",
    year: "2-digit",
  });
}

// -------------------- custom tooltip --------------------

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  if (!d) return null;
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg p-3 text-sm min-w-[180px]">
      <p className="font-semibold text-gray-800 dark:text-white mb-2">{monthLabel(label)}</p>
      <div className="space-y-1">
        <div className="flex justify-between gap-4">
          <span className="text-gray-500 dark:text-gray-400">Income</span>
          <span className="font-medium text-green-600 dark:text-green-400">{fmt(d.projected_income)}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500 dark:text-gray-400">Expenses</span>
          <span className="font-medium text-red-500 dark:text-red-400">{fmt(d.projected_expenses)}</span>
        </div>
        <div className="border-t border-gray-100 dark:border-gray-700 pt-1 flex justify-between gap-4">
          <span className="text-gray-500 dark:text-gray-400">Monthly net</span>
          <span className={`font-semibold ${d.projected_balance >= 0 ? "text-blue-600 dark:text-blue-400" : "text-red-600 dark:text-red-400"}`}>
            {fmt(d.projected_balance)}
          </span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-gray-500 dark:text-gray-400">Running total</span>
          <span className={`font-semibold ${d.running_balance >= 0 ? "text-gray-700 dark:text-gray-200" : "text-red-600 dark:text-red-400"}`}>
            {fmt(d.running_balance)}
          </span>
        </div>
        {d.deficit && (
          <div className="mt-1 flex items-center gap-1 text-red-500 dark:text-red-400 text-xs font-medium">
            <AlertTriangle size={12} />
            Deficit month
          </div>
        )}
      </div>
    </div>
  );
}

// -------------------- summary card --------------------

function SummaryCard({ title, value, icon: Icon, positive }) {
  const colour = positive
    ? "text-green-600 dark:text-green-400"
    : "text-red-500 dark:text-red-400";
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 flex items-center gap-3">
      <div className={`p-2 rounded-lg ${positive ? "bg-green-50 dark:bg-green-900/20" : "bg-red-50 dark:bg-red-900/20"}`}>
        <Icon size={20} className={colour} />
      </div>
      <div>
        <p className="text-xs text-gray-500 dark:text-gray-400">{title}</p>
        <p className={`text-lg font-bold ${colour}`}>{value}</p>
      </div>
    </div>
  );
}

// -------------------- main page --------------------

export default function ForecastPage() {
  const [months, setMonths] = useState(3);
  const [salaryInput, setSalaryInput] = useState("");
  const [salaryOverride, setSalaryOverride] = useState(null);

  const { data, isLoading, isError } = useForecast(months, salaryOverride);

  const projection = data?.projection ?? [];
  const deficitCount = projection.filter((m) => m.deficit).length;
  const finalRunning = projection.at(-1)?.running_balance ?? 0;
  const totalExpenses = projection.reduce((s, m) => s + m.projected_expenses, 0);

  // Build chart data: add a "today" anchor point at running_balance = 0
  const chartData = [
    { month: "Today", projected_income: 0, projected_expenses: 0, projected_balance: 0, running_balance: 0, deficit: false },
    ...projection,
  ];

  const handleApplyOverride = () => {
    const v = parseFloat(salaryInput);
    setSalaryOverride(!isNaN(v) && v >= 0 ? v : null);
  };

  const handleClearOverride = () => {
    setSalaryInput("");
    setSalaryOverride(null);
  };

  return (
    <PageWrapper>
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Cashflow Forecast</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Projected balance based on your planned income and recurring expenses.
        </p>
      </div>

      {/* Controls */}
      <Card className="!p-4">
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-end">
          {/* Months selector */}
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Projection period
            </label>
            <div className="flex gap-2">
              {[3, 6, 12].map((n) => (
                <button
                  key={n}
                  onClick={() => setMonths(n)}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    months === n
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600"
                  }`}
                >
                  {n}m
                </button>
              ))}
            </div>
          </div>

          {/* Salary override */}
          <div className="flex-1 min-w-0">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
              Salary override (optional)
            </label>
            <div className="flex gap-2">
              <input
                type="number"
                min="0"
                placeholder={data ? `Stored: ${fmt(data.monthly_income)}` : "Monthly salary…"}
                value={salaryInput}
                onChange={(e) => setSalaryInput(e.target.value)}
                className="flex-1 min-w-0 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={handleApplyOverride}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
              >
                Apply
              </button>
              {salaryOverride !== null && (
                <button
                  onClick={handleClearOverride}
                  className="px-3 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-600"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>
      </Card>

      {/* Summary cards */}
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <SummaryCard
            title="Monthly income"
            value={fmt(data.monthly_income)}
            icon={DollarSign}
            positive={true}
          />
          <SummaryCard
            title={`Total expenses (${months}m)`}
            value={fmt(totalExpenses)}
            icon={TrendingDown}
            positive={false}
          />
          <SummaryCard
            title={`Projected saving (${months}m)`}
            value={fmt(finalRunning)}
            icon={TrendingUp}
            positive={finalRunning >= 0}
          />
          <SummaryCard
            title="Deficit months"
            value={deficitCount === 0 ? "None" : `${deficitCount} of ${months}`}
            icon={AlertTriangle}
            positive={deficitCount === 0}
          />
        </div>
      )}

      {/* Chart */}
      <Card>
        <h3 className="text-base font-semibold text-gray-800 dark:text-white mb-4">
          Running balance forecast
        </h3>

        {isLoading && (
          <div className="h-64 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
          </div>
        )}

        {isError && (
          <div className="h-64 flex items-center justify-center text-red-500 dark:text-red-400 text-sm">
            Failed to load forecast. Please try again.
          </div>
        )}

        {!isLoading && !isError && (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
              <defs>
                <linearGradient id="balanceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--color-chart-income, #3b82f6)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--color-chart-income, #3b82f6)" stopOpacity={0.05} />
                </linearGradient>
                <linearGradient id="deficitGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ef4444" stopOpacity={0.05} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-chart-grid, #e5e7eb)" />
              <XAxis
                dataKey="month"
                tickFormatter={(v) => v === "Today" ? "Today" : monthLabel(v)}
                tick={{ fontSize: 12, fill: "var(--color-chart-label, #6b7280)" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tickFormatter={(v) => fmt(v)}
                tick={{ fontSize: 11, fill: "var(--color-chart-label, #6b7280)" }}
                axisLine={false}
                tickLine={false}
                width={80}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="4 4" strokeWidth={1.5} />
              <Area
                type="monotone"
                dataKey="running_balance"
                stroke="#3b82f6"
                strokeWidth={2.5}
                fill="url(#balanceGradient)"
                name="Running balance"
                dot={(props) => {
                  const { cx, cy, payload } = props;
                  if (payload.month === "Today") return null;
                  return (
                    <circle
                      key={payload.month}
                      cx={cx}
                      cy={cy}
                      r={5}
                      fill={payload.deficit ? "#ef4444" : "#3b82f6"}
                      stroke="white"
                      strokeWidth={2}
                    />
                  );
                }}
                activeDot={{ r: 7, stroke: "white", strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Card>

      {/* Monthly breakdown table */}
      {!isLoading && !isError && projection.length > 0 && (
        <Card className="overflow-hidden !p-0">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h3 className="text-base font-semibold text-gray-800 dark:text-white">Monthly breakdown</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-750">
                <tr>
                  {["Month", "Income", "Expenses", "Net", "Running total", ""].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {projection.map((m) => (
                  <tr
                    key={m.month}
                    className={m.deficit ? "bg-red-50/50 dark:bg-red-900/10" : ""}
                  >
                    <td className="px-4 py-3 font-medium text-gray-800 dark:text-white">
                      {monthLabel(m.month)}
                    </td>
                    <td className="px-4 py-3 text-green-600 dark:text-green-400">
                      {fmt(m.projected_income)}
                    </td>
                    <td className="px-4 py-3 text-red-500 dark:text-red-400">
                      {fmt(m.projected_expenses)}
                    </td>
                    <td className={`px-4 py-3 font-semibold ${m.projected_balance >= 0 ? "text-blue-600 dark:text-blue-400" : "text-red-600 dark:text-red-400"}`}>
                      {fmt(m.projected_balance)}
                    </td>
                    <td className={`px-4 py-3 font-semibold ${m.running_balance >= 0 ? "text-gray-700 dark:text-gray-200" : "text-red-600 dark:text-red-400"}`}>
                      {fmt(m.running_balance)}
                    </td>
                    <td className="px-4 py-3">
                      {m.deficit && (
                        <span className="inline-flex items-center gap-1 text-xs text-red-600 dark:text-red-400 font-medium bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded-full">
                          <AlertTriangle size={11} />
                          Deficit
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Empty state */}
      {!isLoading && !isError && projection.length === 0 && (
        <Card className="!p-12 text-center">
          <TrendingUp size={40} className="mx-auto text-gray-300 dark:text-gray-600 mb-3" />
          <p className="text-gray-500 dark:text-gray-400 font-medium">No forecast data yet</p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
            Add a budget plan or recurring expenses to see your cashflow projection.
          </p>
        </Card>
      )}
    </PageWrapper>
  );
}
