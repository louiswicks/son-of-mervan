// src/components/InsightsPage.jsx
import React, { useState, useRef } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import {
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle,
  Info, BarChart2, Heart, Sparkles, RefreshCw,
} from "lucide-react";
import { useMonthlySummary, useSpendingTrends, useSpendingHeatmap, useHealthScore } from "../hooks/useInsights";
import { requestAIReview } from "../api/insights";
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

// -------------------- health score --------------------

const BAND_STYLES = {
  green: {
    ring: "ring-green-400 dark:ring-green-500",
    text: "text-green-600 dark:text-green-400",
    bg: "bg-green-50 dark:bg-green-900/20",
    bar: "bg-green-500",
    label: "Good",
  },
  amber: {
    ring: "ring-amber-400 dark:ring-amber-500",
    text: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-50 dark:bg-amber-900/20",
    bar: "bg-amber-400",
    label: "Fair",
  },
  red: {
    ring: "ring-red-400 dark:ring-red-500",
    text: "text-red-600 dark:text-red-400",
    bg: "bg-red-50 dark:bg-red-900/20",
    bar: "bg-red-500",
    label: "Needs Work",
  },
};

function ComponentRow({ label, score, weight, detail }) {
  const pct = Math.min(100, Math.max(0, score));
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-gray-700 dark:text-gray-300">{label}</span>
        <span className="text-gray-500 dark:text-gray-400 text-xs">{score}/100 · {(weight * 100).toFixed(0)}% weight</span>
      </div>
      <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full bg-indigo-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">{detail}</p>
    </div>
  );
}

function HealthScoreCard({ month }) {
  const { data, isLoading } = useHealthScore(month);

  if (isLoading) {
    return (
      <section className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
        <div className="animate-pulse space-y-3">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-48" />
          <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
      </section>
    );
  }

  if (!data) return null;

  const band = BAND_STYLES[data.band] || BAND_STYLES.amber;

  return (
    <section className={`rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5 ${band.bg}`}>
      <div className="flex items-center gap-3 mb-4">
        <Heart size={22} className={band.text} />
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Financial Health Score</h2>
        <span className={`ml-auto text-xs font-semibold px-2 py-0.5 rounded-full ring-1 ${band.ring} ${band.text}`}>
          {band.label}
        </span>
      </div>

      {/* Score dial */}
      <div className="flex items-center gap-6 mb-5">
        <div className={`text-6xl font-extrabold tabular-nums ${band.text}`}>
          {data.score}
        </div>
        <div className="flex-1 space-y-1">
          <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400 mb-1">
            <span>0</span><span>50</span><span>100</span>
          </div>
          <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${band.bar}`}
              style={{ width: `${data.score}%` }}
            />
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            Red 0–39 · Amber 40–69 · Green 70–100
          </p>
        </div>
      </div>

      {/* Component breakdown */}
      <div className="space-y-4 mb-5 border-t border-gray-200 dark:border-gray-700 pt-4">
        <ComponentRow
          label="Savings Rate"
          score={data.components.savings_rate.score}
          weight={data.components.savings_rate.weight}
          detail={data.components.savings_rate.detail}
        />
        <ComponentRow
          label="Budget Adherence"
          score={data.components.budget_adherence.score}
          weight={data.components.budget_adherence.weight}
          detail={data.components.budget_adherence.detail}
        />
        <ComponentRow
          label="Emergency Fund"
          score={data.components.emergency_fund.score}
          weight={data.components.emergency_fund.weight}
          detail={data.components.emergency_fund.detail}
        />
      </div>

      {/* Plain-English explanations */}
      <ul className="space-y-1 border-t border-gray-200 dark:border-gray-700 pt-4">
        {data.explanations.map((text, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400">
            <Info size={14} className="flex-shrink-0 mt-0.5 text-gray-400" />
            {text}
          </li>
        ))}
      </ul>
    </section>
  );
}

// -------------------- AI review --------------------

const MAX_DAILY_REVIEWS = 3;

function AIReviewSection({ month }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [usedToday, setUsedToday] = useState(0);
  const abortRef = useRef(false);

  const remaining = MAX_DAILY_REVIEWS - usedToday;
  const disabled = loading || remaining <= 0;

  const handleReview = async () => {
    setText("");
    setError(null);
    setLoading(true);
    abortRef.current = false;

    await requestAIReview(
      month,
      (chunk) => {
        if (!abortRef.current) setText((prev) => prev + chunk);
      },
      () => {
        setLoading(false);
        setUsedToday((n) => n + 1);
      },
      (err) => {
        setError(err.message);
        setLoading(false);
      }
    );
  };

  return (
    <section className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <Sparkles size={20} className="text-indigo-500 dark:text-indigo-400" />
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">AI Financial Review</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Personalised coaching from Claude · {remaining} of {MAX_DAILY_REVIEWS} uses left today
            </p>
          </div>
        </div>
        <button
          onClick={handleReview}
          disabled={disabled}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors min-h-[40px] ${
            disabled
              ? "bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-600 cursor-not-allowed"
              : "bg-indigo-600 hover:bg-indigo-700 text-white"
          }`}
        >
          {loading ? (
            <>
              <RefreshCw size={14} className="animate-spin" />
              Reviewing…
            </>
          ) : (
            <>
              <Sparkles size={14} />
              Get AI Review
            </>
          )}
        </button>
      </div>

      {error && (
        <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 mb-3">
          <AlertTriangle size={15} className="text-red-500 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
        </div>
      )}

      {remaining <= 0 && !text && (
        <p className="text-sm text-amber-600 dark:text-amber-400 text-center py-2">
          Daily limit reached. AI reviews reset at midnight UTC.
        </p>
      )}

      {!text && !loading && !error && remaining > 0 && (
        <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-4">
          Click "Get AI Review" to receive a personalised summary and recommendations for {month}.
          Your data is anonymised before being sent — no transaction names are shared.
        </p>
      )}

      {text && (
        <div className="prose prose-sm dark:prose-invert max-w-none">
          <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap leading-relaxed">
            {text}
            {loading && (
              <span className="inline-block w-0.5 h-4 bg-indigo-500 animate-pulse ml-0.5 align-middle" />
            )}
          </p>
        </div>
      )}
    </section>
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

      {/* ---- Health Score ---- */}
      <HealthScoreCard month={selectedMonth} />

      {/* ---- AI Financial Review ---- */}
      <AIReviewSection month={selectedMonth} />

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
