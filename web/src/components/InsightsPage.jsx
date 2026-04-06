// src/components/InsightsPage.jsx
import React, { useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import {
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle,
  Info, BarChart2,
} from "lucide-react";
import { useMonthlySummary, useSpendingTrends, useSpendingHeatmap } from "../hooks/useInsights";
import { SkeletonCard } from "./Skeleton";
import { useTheme } from "../hooks/useTheme";

// -------------------- helpers --------------------

function currentMonthStr() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function fmtMonth(m) {
  // "2025-03" → "Mar 25"
  const [y, mo] = m.split("-");
  const d = new Date(parseInt(y), parseInt(mo) - 1, 1);
  return d.toLocaleDateString("en-GB", { month: "short", year: "2-digit" });
}

const CATEGORY_COLORS = {
  Housing: "#6366f1",
  Food: "#f59e0b",
  Transportation: "#3b82f6",
  Utilities: "#10b981",
  Insurance: "#8b5cf6",
  Healthcare: "#ef4444",
  Entertainment: "#ec4899",
  Other: "#6b7280",
};

function catColor(cat) {
  return CATEGORY_COLORS[cat] || "#6b7280";
}

const HEATMAP_COLORS = [
  "bg-gray-100 dark:bg-gray-800",       // 0 — no data
  "bg-blue-200 dark:bg-blue-900",       // 1 — low
  "bg-blue-400 dark:bg-blue-700",       // 2 — medium
  "bg-blue-600 dark:bg-blue-500",       // 3 — high
  "bg-blue-800 dark:bg-blue-300",       // 4 — very high
];

const MONTH_LABELS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

// -------------------- sub-components --------------------

function InsightCard({ insight }) {
  const positive = insight.positive;
  const icons = {
    net_income: positive ? CheckCircle : AlertTriangle,
    trend: positive ? TrendingDown : TrendingUp,
    overspend: AlertTriangle,
  };
  const Icon = icons[insight.type] || Info;

  return (
    <div
      className={`flex items-start gap-3 p-4 rounded-xl border ${
        positive
          ? "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800"
          : "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800"
      }`}
    >
      <Icon
        size={20}
        className={`flex-shrink-0 mt-0.5 ${
          positive ? "text-green-600 dark:text-green-400" : "text-red-500 dark:text-red-400"
        }`}
      />
      <p className={`text-sm font-medium ${
        positive
          ? "text-green-800 dark:text-green-200"
          : "text-red-800 dark:text-red-200"
      }`}>
        {insight.text}
      </p>
    </div>
  );
}

function PctBadge({ pct }) {
  if (pct === null || pct === undefined) return <span className="text-gray-400 text-xs">—</span>;
  const up = pct > 0;
  return (
    <span
      className={`inline-flex items-center gap-0.5 text-xs font-semibold px-1.5 py-0.5 rounded-full ${
        up
          ? "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300"
          : "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300"
      }`}
    >
      {up ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
      {Math.abs(pct).toFixed(1)}%
    </span>
  );
}

function CategoryTable({ categories }) {
  if (!categories || Object.keys(categories).length === 0) {
    return (
      <p className="text-sm text-gray-500 dark:text-gray-400 py-4 text-center">
        No expense data for this month.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto -mx-4 sm:mx-0">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="text-left text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide border-b border-gray-200 dark:border-gray-700">
            <th className="pb-2 pl-4 sm:pl-0 pr-4">Category</th>
            <th className="pb-2 pr-4 text-right">Planned</th>
            <th className="pb-2 pr-4 text-right">Actual</th>
            <th className="pb-2 pr-4 text-right">Prev Month</th>
            <th className="pb-2 pr-4 text-right">Change</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
          {Object.entries(categories).map(([cat, data]) => (
            <tr key={cat} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
              <td className="py-2 pl-4 sm:pl-0 pr-4">
                <div className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: catColor(cat) }}
                  />
                  <span className="font-medium text-gray-800 dark:text-gray-200">{cat}</span>
                  {data.over_budget && (
                    <AlertTriangle size={12} className="text-red-500 flex-shrink-0" />
                  )}
                </div>
              </td>
              <td className="py-2 pr-4 text-right text-gray-600 dark:text-gray-400">
                £{data.planned.toFixed(2)}
              </td>
              <td className={`py-2 pr-4 text-right font-medium ${
                data.over_budget
                  ? "text-red-600 dark:text-red-400"
                  : "text-gray-800 dark:text-gray-200"
              }`}>
                £{data.actual.toFixed(2)}
              </td>
              <td className="py-2 pr-4 text-right text-gray-500 dark:text-gray-400">
                {data.prev_month_actual > 0 ? `£${data.prev_month_actual.toFixed(2)}` : "—"}
              </td>
              <td className="py-2 pr-4 text-right">
                <PctBadge pct={data.pct_change} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TrendChart({ data, chartColors }) {
  if (!data?.overall_trend?.length) return null;
  const plotData = data.overall_trend.map((m) => ({
    name: fmtMonth(m.month),
    Spending: m.total_actual,
    Income: m.salary_actual,
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={plotData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
        <XAxis dataKey="name" tick={{ fill: chartColors.axis, fontSize: 11 }} />
        <YAxis
          tick={{ fill: chartColors.axis, fontSize: 11 }}
          tickFormatter={(v) => `£${v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v}`}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: chartColors.tooltipBg,
            border: `1px solid ${chartColors.tooltipBorder}`,
            borderRadius: "8px",
            color: chartColors.tooltipText,
            fontSize: 12,
          }}
          formatter={(value) => [`£${value.toFixed(2)}`, undefined]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line
          type="monotone"
          dataKey="Income"
          stroke={chartColors.success}
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="Spending"
          stroke={chartColors.danger}
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

function CategoryTrendChart({ data, chartColors }) {
  if (!data?.category_trends || Object.keys(data.category_trends).length === 0) return null;
  const months = data.months || [];
  const plotData = months.map((m, i) => {
    const point = { name: fmtMonth(m) };
    for (const [cat, series] of Object.entries(data.category_trends)) {
      point[cat] = series[i]?.amount ?? 0;
    }
    return point;
  });

  const cats = Object.keys(data.category_trends);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={plotData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
        <XAxis dataKey="name" tick={{ fill: chartColors.axis, fontSize: 11 }} />
        <YAxis
          tick={{ fill: chartColors.axis, fontSize: 11 }}
          tickFormatter={(v) => `£${v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v}`}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: chartColors.tooltipBg,
            border: `1px solid ${chartColors.tooltipBorder}`,
            borderRadius: "8px",
            color: chartColors.tooltipText,
            fontSize: 12,
          }}
          formatter={(value) => [`£${value.toFixed(2)}`, undefined]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {cats.map((cat) => (
          <Line
            key={cat}
            type="monotone"
            dataKey={cat}
            stroke={catColor(cat)}
            strokeWidth={2}
            dot={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function Heatmap({ data }) {
  if (!data?.months?.length) return null;

  return (
    <div>
      <div className="grid grid-cols-6 sm:grid-cols-12 gap-1.5">
        {data.months.map((m) => {
          const label = MONTH_LABELS[parseInt(m.month.split("-")[1]) - 1];
          return (
            <div key={m.month} className="flex flex-col items-center gap-1">
              <div
                className={`w-full aspect-square rounded-md ${HEATMAP_COLORS[m.level]} border border-gray-200 dark:border-gray-700 transition-all`}
                title={`${m.month}: £${m.total_actual.toFixed(2)}`}
              />
              <span className="text-[10px] text-gray-500 dark:text-gray-400">{label}</span>
            </div>
          );
        })}
      </div>
      {/* Legend */}
      <div className="flex items-center gap-2 mt-3">
        <span className="text-xs text-gray-500 dark:text-gray-400">Less</span>
        {HEATMAP_COLORS.map((cls, i) => (
          <div
            key={i}
            className={`w-4 h-4 rounded-sm ${cls} border border-gray-200 dark:border-gray-700`}
          />
        ))}
        <span className="text-xs text-gray-500 dark:text-gray-400">More</span>
      </div>
    </div>
  );
}

// -------------------- main page --------------------

export default function InsightsPage() {
  const [selectedMonth, setSelectedMonth] = useState(currentMonthStr);
  const [trendWindow, setTrendWindow] = useState(6);
  const [heatmapYear, setHeatmapYear] = useState(new Date().getFullYear());
  const { theme } = useTheme();

  const { data: summary, isLoading: summaryLoading } = useMonthlySummary(selectedMonth);
  const { data: trends, isLoading: trendsLoading } = useSpendingTrends(trendWindow);
  const { data: heatmap, isLoading: heatmapLoading } = useSpendingHeatmap(heatmapYear);

  const isDark = theme === "dark";
  const chartColors = {
    primary: isDark ? "#818cf8" : "#4f46e5",
    success: isDark ? "#34d399" : "#059669",
    danger: isDark ? "#f87171" : "#dc2626",
    grid: isDark ? "#374151" : "#e5e7eb",
    axis: isDark ? "#9ca3af" : "#6b7280",
    tooltipBg: isDark ? "#1f2937" : "#ffffff",
    tooltipBorder: isDark ? "#374151" : "#e5e7eb",
    tooltipText: isDark ? "#f3f4f6" : "#111827",
  };

  const currentYear = new Date().getFullYear();

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <BarChart2 size={24} className="text-indigo-600 dark:text-indigo-400" />
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Spending Insights</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Trends, comparisons, and plain-English summaries of your spending
          </p>
        </div>
      </div>

      {/* ---- Section 1: Monthly Summary ---- */}
      <section className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Monthly Summary
          </h2>
          <input
            type="month"
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg px-3 py-1.5 text-sm min-h-[40px]"
          />
        </div>

        {summaryLoading ? (
          <div className="space-y-3">
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : !summary ? (
          <p className="text-sm text-gray-500 dark:text-gray-400 py-4 text-center">
            No data available for this month.
          </p>
        ) : (
          <>
            {/* KPI row */}
            <div className="grid grid-cols-3 gap-3 mb-5">
              <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-3 text-center">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Income</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  £{summary.salary_actual.toFixed(2)}
                </p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-800 rounded-xl p-3 text-center">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Spent</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  £{summary.total_actual.toFixed(2)}
                </p>
              </div>
              <div
                className={`rounded-xl p-3 text-center ${
                  summary.net_income >= 0
                    ? "bg-green-50 dark:bg-green-900/20"
                    : "bg-red-50 dark:bg-red-900/20"
                }`}
              >
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Net</p>
                <p
                  className={`text-lg font-bold ${
                    summary.net_income >= 0
                      ? "text-green-700 dark:text-green-300"
                      : "text-red-600 dark:text-red-400"
                  }`}
                >
                  {summary.net_income >= 0 ? "+" : ""}£{summary.net_income.toFixed(2)}
                </p>
              </div>
            </div>

            {/* Insight cards */}
            {summary.insights?.length > 0 && (
              <div className="space-y-2 mb-5">
                {summary.insights.map((ins, i) => (
                  <InsightCard key={i} insight={ins} />
                ))}
              </div>
            )}

            {/* Category table */}
            <CategoryTable categories={summary.categories} />
          </>
        )}
      </section>

      {/* ---- Section 2: 6-month trend ---- */}
      <section className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Income vs Spending Trend
          </h2>
          <select
            value={trendWindow}
            onChange={(e) => setTrendWindow(Number(e.target.value))}
            className="border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg px-3 py-1.5 text-sm min-h-[40px]"
          >
            <option value={3}>Last 3 months</option>
            <option value={6}>Last 6 months</option>
            <option value={12}>Last 12 months</option>
          </select>
        </div>
        {trendsLoading ? (
          <SkeletonCard />
        ) : (
          <TrendChart data={trends} chartColors={chartColors} />
        )}
      </section>

      {/* ---- Section 3: per-category trend ---- */}
      <section className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Category Trends
        </h2>
        {trendsLoading ? (
          <SkeletonCard />
        ) : !trends || Object.keys(trends.category_trends ?? {}).length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400 py-4 text-center">
            No category data yet. Start tracking your expenses!
          </p>
        ) : (
          <CategoryTrendChart data={trends} chartColors={chartColors} />
        )}
      </section>

      {/* ---- Section 4: annual heatmap ---- */}
      <section className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Annual Spending Heatmap
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Darker = higher spending. Hover a square to see the amount.
            </p>
          </div>
          <select
            value={heatmapYear}
            onChange={(e) => setHeatmapYear(Number(e.target.value))}
            className="border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-200 rounded-lg px-3 py-1.5 text-sm min-h-[40px]"
          >
            {[0, 1, 2].map((offset) => {
              const y = currentYear - offset;
              return (
                <option key={y} value={y}>
                  {y}
                </option>
              );
            })}
          </select>
        </div>
        {heatmapLoading ? (
          <SkeletonCard />
        ) : (
          <Heatmap data={heatmap} />
        )}
      </section>
    </div>
  );
}
