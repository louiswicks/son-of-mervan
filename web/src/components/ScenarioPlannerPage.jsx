// src/components/ScenarioPlannerPage.jsx
import React, { useState, useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { Sliders, Target } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useSavingsGoals } from "../hooks/useSavings";
import { getMonthlySummary } from "../api/insights";
import { useProfile } from "../hooks/useProfile";
import { currencySymbol } from "../hooks/useCurrency";

function currentYearMonth() {
  return new Date().toISOString().slice(0, 7);
}

function fmt(n, symbol = "£") {
  const abs = Math.abs(n);
  const formatted = abs.toLocaleString("en-GB", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  return `${symbol}${formatted}`;
}

function monthsLabel(n) {
  if (n === Infinity || n > 999) return "n/a";
  if (n <= 0) return "0 months";
  return `${n} month${n === 1 ? "" : "s"}`;
}

// ── Summary card ──────────────────────────────────────────────────────────────

function SummaryCard({ label, value, sub, color }) {
  return (
    <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-4">
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
        {label}
      </p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Category slider row ───────────────────────────────────────────────────────

function CategorySlider({ category, amount, pct, onChange, symbol }) {
  const delta = (amount * pct) / 100;
  const newAmount = amount + delta;

  return (
    <div className="py-3 border-b border-gray-100 dark:border-gray-800 last:border-0">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-gray-800 dark:text-gray-200">
          {category}
        </span>
        <div className="flex items-center gap-3 text-sm tabular-nums">
          <span className="text-gray-400 dark:text-gray-500">
            {fmt(amount, symbol)} → {fmt(newAmount, symbol)}
          </span>
          <span
            className={`font-semibold w-16 text-right ${
              delta > 0
                ? "text-red-500 dark:text-red-400"
                : delta < 0
                ? "text-green-600 dark:text-green-400"
                : "text-gray-400"
            }`}
          >
            {delta !== 0
              ? `${delta > 0 ? "+" : ""}${fmt(delta, symbol)}`
              : "—"}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-green-600 dark:text-green-400 w-8 shrink-0">
          −50%
        </span>
        <input
          type="range"
          min={-50}
          max={50}
          step={5}
          value={pct}
          onChange={(e) => onChange(Number(e.target.value))}
          className="flex-1 h-2 accent-blue-600 cursor-pointer"
          aria-label={`Adjust ${category} spending`}
        />
        <span className="text-xs text-red-500 dark:text-red-400 w-8 text-right shrink-0">
          +50%
        </span>
        <span className="text-xs font-semibold text-gray-600 dark:text-gray-300 w-10 text-right tabular-nums">
          {pct > 0 ? "+" : ""}
          {pct}%
        </span>
      </div>
    </div>
  );
}

// ── Goal impact row ───────────────────────────────────────────────────────────

function GoalImpactRow({ name, remaining, baselineMonths, scenarioMonths, delta, symbol }) {
  if (remaining <= 0) {
    return (
      <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
        <span className="text-sm text-gray-700 dark:text-gray-300">{name}</span>
        <span className="text-sm font-semibold text-green-600 dark:text-green-400">
          Achieved!
        </span>
      </div>
    );
  }

  const noSavings =
    baselineMonths === Infinity || scenarioMonths === Infinity;

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0 gap-1">
      <div>
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
          {name}
        </span>
        <span className="text-xs text-gray-400 dark:text-gray-500 ml-2">
          {fmt(remaining, symbol)} remaining
        </span>
      </div>

      {noSavings ? (
        <span className="text-sm text-orange-500 dark:text-orange-400">
          Needs positive monthly savings
        </span>
      ) : (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-500 dark:text-gray-400">
            {monthsLabel(baselineMonths)}
          </span>
          <span className="text-gray-400">→</span>
          <span
            className={`font-semibold ${
              delta > 0
                ? "text-green-600 dark:text-green-400"
                : delta < 0
                ? "text-red-500 dark:text-red-400"
                : "text-gray-700 dark:text-gray-300"
            }`}
          >
            {monthsLabel(scenarioMonths)}
          </span>
          {delta !== 0 && (
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                delta > 0
                  ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
                  : "bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400"
              }`}
            >
              {delta > 0
                ? `${delta}mo sooner`
                : `${Math.abs(delta)}mo later`}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ScenarioPlannerPage() {
  const month = currentYearMonth();
  const { data: profileData } = useProfile();
  const symbol = currencySymbol(profileData?.base_currency || "GBP");

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["monthly-summary-scenario", month],
    queryFn: () => getMonthlySummary(month),
    staleTime: 60_000,
  });

  const { data: goals, isLoading: goalsLoading } = useSavingsGoals();

  // Per-category planned amounts from the monthly summary
  const categoryAmounts = useMemo(() => {
    if (!summary?.categories) return {};
    const result = {};
    Object.entries(summary.categories).forEach(([cat, data]) => {
      if ((data.planned || 0) > 0) result[cat] = data.planned;
    });
    return result;
  }, [summary]);

  // The baseline monthly savings = salary_planned - total_planned (from summary)
  // summary doesn't directly expose salary; use net_income as proxy when categories are present
  // Fall back to deriving from net_income (actual) or from sum of planned vs salary
  const baselineSavings = useMemo(() => {
    if (!summary) return 0;
    // net_income reflects salary_actual - total_actual; we use planned figures via categories
    // total_planned = sum of all category planned amounts
    const totalPlanned = Object.values(categoryAmounts).reduce((s, v) => s + v, 0);
    // We need the salary. summary.salary_actual is the best we have.
    // If no salary data, fall back to 0 (sliders still work, projections will show 0 baseline).
    const salary = summary.salary_actual ?? 0;
    return salary - totalPlanned;
  }, [summary, categoryAmounts]);

  // Sliders: percentage change per category (−50 … +50, step 5)
  const [sliders, setSliders] = useState({});
  const getPct = (cat) => sliders[cat] ?? 0;

  const setSlider = (cat, val) =>
    setSliders((prev) => ({ ...prev, [cat]: val }));

  // Total spending adjustment caused by sliders
  const spendingAdjustment = useMemo(() => {
    return Object.entries(categoryAmounts).reduce((total, [cat, amount]) => {
      return total + (amount * getPct(cat)) / 100;
    }, 0);
  }, [categoryAmounts, sliders]); // eslint-disable-line react-hooks/exhaustive-deps

  // Scenario monthly savings = baseline − spendingAdjustment
  // Spending more (positive slider) reduces savings; spending less increases savings.
  const scenarioSavings = baselineSavings - spendingAdjustment;
  const savingsDelta = scenarioSavings - baselineSavings;

  // 24-month projection chart data
  const chartData = useMemo(() => {
    return Array.from({ length: 24 }, (_, i) => {
      const m = i + 1;
      return {
        month: `M${m}`,
        Baseline: Math.round(m * baselineSavings),
        Scenario: Math.round(m * scenarioSavings),
      };
    });
  }, [baselineSavings, scenarioSavings]);

  // Goal projections
  const goalProjections = useMemo(() => {
    if (!goals?.length) return [];
    return goals.map((goal) => {
      const remaining = (goal.target_amount || 0) - (goal.current_amount || 0);
      const baselineMonths =
        baselineSavings > 0 ? Math.ceil(remaining / baselineSavings) : Infinity;
      const scenarioMonths =
        scenarioSavings > 0 ? Math.ceil(remaining / scenarioSavings) : Infinity;
      const delta =
        baselineMonths === Infinity || scenarioMonths === Infinity
          ? 0
          : baselineMonths - scenarioMonths;
      return { ...goal, remaining, baselineMonths, scenarioMonths, delta };
    });
  }, [goals, baselineSavings, scenarioSavings]);

  const isLoading = summaryLoading || goalsLoading;
  const hasCategories = Object.keys(categoryAmounts).length > 0;

  // ── Render ──────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="h-24 rounded-2xl bg-gray-200 dark:bg-gray-800 animate-pulse"
          />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
          What-If Planner
        </h2>
        <p className="text-gray-500 dark:text-gray-400 mt-1 text-sm">
          Drag sliders to see how spending changes affect your savings and goal
          timelines. All calculations are instant — nothing is saved.
        </p>
      </div>

      {!hasCategories ? (
        /* Empty state */
        <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-10 text-center">
          <Sliders
            size={40}
            className="mx-auto text-gray-300 dark:text-gray-600 mb-3"
          />
          <p className="text-gray-600 dark:text-gray-300 font-medium">
            No planned budget for {month}
          </p>
          <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">
            Add planned expenses on the Budget page first, then come back to
            explore scenarios.
          </p>
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <SummaryCard
              label="Baseline monthly savings"
              value={fmt(baselineSavings, symbol)}
              color="text-gray-900 dark:text-white"
            />
            <SummaryCard
              label="Monthly adjustment"
              value={`${savingsDelta >= 0 ? "+" : ""}${fmt(savingsDelta, symbol)}`}
              sub={
                spendingAdjustment > 0
                  ? `Spending ${fmt(spendingAdjustment, symbol)} more`
                  : spendingAdjustment < 0
                  ? `Spending ${fmt(Math.abs(spendingAdjustment), symbol)} less`
                  : "No changes yet"
              }
              color={
                savingsDelta > 0
                  ? "text-green-600 dark:text-green-400"
                  : savingsDelta < 0
                  ? "text-red-500 dark:text-red-400"
                  : "text-gray-500 dark:text-gray-400"
              }
            />
            <SummaryCard
              label="Scenario monthly savings"
              value={fmt(scenarioSavings, symbol)}
              color={
                scenarioSavings > baselineSavings
                  ? "text-green-600 dark:text-green-400"
                  : scenarioSavings < baselineSavings
                  ? "text-red-500 dark:text-red-400"
                  : "text-gray-900 dark:text-white"
              }
            />
          </div>

          {/* Category sliders */}
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-gray-900 dark:text-white">
                Adjust spending
              </h3>
              {Object.keys(sliders).some((k) => sliders[k] !== 0) && (
                <button
                  onClick={() => setSliders({})}
                  className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
                >
                  Reset all
                </button>
              )}
            </div>
            <div>
              {Object.entries(categoryAmounts).map(([cat, amount]) => (
                <CategorySlider
                  key={cat}
                  category={cat}
                  amount={amount}
                  pct={getPct(cat)}
                  onChange={(val) => setSlider(cat, val)}
                  symbol={symbol}
                />
              ))}
            </div>
          </div>

          {/* 24-month projection chart */}
          <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
            <h3 className="font-semibold text-gray-900 dark:text-white mb-4">
              24-month savings projection
            </h3>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart
                data={chartData}
                margin={{ top: 4, right: 8, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="sp-baseline" x1="0" y1="0" x2="0" y2="1">
                    <stop
                      offset="5%"
                      stopColor="var(--color-chart-1,#6366f1)"
                      stopOpacity={0.25}
                    />
                    <stop
                      offset="95%"
                      stopColor="var(--color-chart-1,#6366f1)"
                      stopOpacity={0.02}
                    />
                  </linearGradient>
                  <linearGradient id="sp-scenario" x1="0" y1="0" x2="0" y2="1">
                    <stop
                      offset="5%"
                      stopColor="var(--color-chart-2,#22c55e)"
                      stopOpacity={0.25}
                    />
                    <stop
                      offset="95%"
                      stopColor="var(--color-chart-2,#22c55e)"
                      stopOpacity={0.02}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="var(--color-border,#e5e7eb)"
                />
                <XAxis
                  dataKey="month"
                  tick={{
                    fontSize: 11,
                    fill: "var(--color-text-muted,#9ca3af)",
                  }}
                  tickLine={false}
                  interval={5}
                />
                <YAxis
                  tick={{
                    fontSize: 11,
                    fill: "var(--color-text-muted,#9ca3af)",
                  }}
                  tickLine={false}
                  tickFormatter={(v) =>
                    v >= 1000
                      ? `${symbol}${(v / 1000).toFixed(0)}k`
                      : `${symbol}${v}`
                  }
                />
                <Tooltip
                  formatter={(value) => [
                    `${symbol}${value.toLocaleString()}`,
                    undefined,
                  ]}
                  contentStyle={{
                    background: "var(--color-surface,#fff)",
                    border: "1px solid var(--color-border,#e5e7eb)",
                    borderRadius: "8px",
                    fontSize: "13px",
                  }}
                />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="Baseline"
                  stroke="var(--color-chart-1,#6366f1)"
                  fill="url(#sp-baseline)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                <Area
                  type="monotone"
                  dataKey="Scenario"
                  stroke="var(--color-chart-2,#22c55e)"
                  fill="url(#sp-scenario)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Goal impact */}
          {goalProjections.length > 0 && (
            <div className="bg-white dark:bg-gray-900 rounded-2xl shadow-sm border border-gray-200 dark:border-gray-700 p-5">
              <h3 className="font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                <Target size={16} className="text-blue-500" />
                Impact on savings goals
              </h3>
              <div>
                {goalProjections.map((g) => (
                  <GoalImpactRow
                    key={g.id}
                    name={g.name}
                    remaining={g.remaining}
                    baselineMonths={g.baselineMonths}
                    scenarioMonths={g.scenarioMonths}
                    delta={g.delta}
                    symbol={symbol}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
