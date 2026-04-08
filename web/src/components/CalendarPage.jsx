// src/components/CalendarPage.jsx
import React, { useState, useMemo } from "react";
import { CalendarDays, Target, ChevronLeft, ChevronRight, Repeat } from "lucide-react";
import { useRecurring } from "../hooks/useRecurring";
import { useSavingsGoals } from "../hooks/useSavings";
import PageWrapper from "./PageWrapper";

const CATEGORY_COLORS = {
  Housing: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  Transportation: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  Food: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  Utilities: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  Insurance: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  Healthcare: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
  Entertainment: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
  Other: "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200",
};

const GOAL_COLOR =
  "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200";

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const FREQ_ICON = {
  monthly: "↻",
  weekly: "↻w",
  yearly: "↻y",
  daily: "↻d",
};

/**
 * Returns true if a recurring expense should appear in the given year/month.
 * monthIdx is 0-based (0 = January).
 */
function isRecurringActiveInMonth(expense, year, monthIdx) {
  const cellStart = new Date(year, monthIdx, 1);
  const cellEnd = new Date(year, monthIdx + 1, 0); // last day of month

  const start = new Date(expense.start_date);
  const end = expense.end_date ? new Date(expense.end_date) : null;

  // Expense ends before this month begins
  if (end && end < cellStart) return false;
  // Expense starts after this month ends
  if (start > cellEnd) return false;

  // Yearly: only the anniversary month
  if (expense.frequency === "yearly") {
    return start.getMonth() === monthIdx;
  }

  // Monthly / weekly / daily: active every month within the date range
  return true;
}

/**
 * Returns true if a savings goal target date falls in the given year/month.
 */
function isGoalDueInMonth(goal, year, monthIdx) {
  if (!goal.target_date) return false;
  const due = new Date(goal.target_date);
  return due.getFullYear() === year && due.getMonth() === monthIdx;
}

// ── Month card ─────────────────────────────────────────────────────────────

function MonthCard({ name, activeRecurring, dueGoals, isCurrentMonth }) {
  const hasItems = activeRecurring.length > 0 || dueGoals.length > 0;

  return (
    <div
      className={`bg-white dark:bg-gray-900 rounded-xl border p-4 shadow-sm min-h-[120px] ${
        isCurrentMonth
          ? "border-blue-400 dark:border-blue-600 ring-1 ring-blue-300 dark:ring-blue-700"
          : "border-gray-200 dark:border-gray-700"
      }`}
    >
      <h2
        className={`text-sm font-semibold mb-2 flex items-center gap-1.5 ${
          isCurrentMonth
            ? "text-blue-600 dark:text-blue-400"
            : "text-gray-700 dark:text-gray-300"
        }`}
      >
        {name}
        {isCurrentMonth && (
          <span className="text-xs font-normal bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 px-1.5 py-0.5 rounded-full">
            Now
          </span>
        )}
      </h2>

      {!hasItems ? (
        <p className="text-xs text-gray-400 dark:text-gray-600 italic">No events</p>
      ) : (
        <div className="space-y-1">
          {activeRecurring.map((exp) => (
            <div
              key={exp.id}
              className={`px-2 py-1 rounded-lg text-xs font-medium truncate ${
                CATEGORY_COLORS[exp.category] ?? CATEGORY_COLORS.Other
              }`}
              title={`${exp.name} — ${exp.category} (${exp.frequency})`}
            >
              <span className="opacity-60 mr-1">{FREQ_ICON[exp.frequency] ?? "↻"}</span>
              {exp.name}
            </div>
          ))}
          {dueGoals.map((goal) => (
            <div
              key={goal.id}
              className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${GOAL_COLOR}`}
              title={`Savings Goal: ${goal.name} — due ${goal.target_date}`}
            >
              <Target className="w-3 h-3 shrink-0" />
              <span className="truncate">{goal.name}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function CalendarPage() {
  const today = new Date();
  const currentYear = today.getFullYear();
  const currentMonth = today.getMonth(); // 0-based

  const [year, setYear] = useState(currentYear);

  const { data: recurring = [], isLoading: loadingRecurring } = useRecurring();
  const { data: goals = [], isLoading: loadingGoals } = useSavingsGoals();
  const isLoading = loadingRecurring || loadingGoals;

  const months = useMemo(
    () =>
      MONTH_NAMES.map((name, idx) => ({
        name,
        idx,
        activeRecurring: recurring.filter((exp) =>
          isRecurringActiveInMonth(exp, year, idx)
        ),
        dueGoals: goals.filter((g) => isGoalDueInMonth(g, year, idx)),
        isCurrentMonth: year === currentYear && idx === currentMonth,
      })),
    [year, recurring, goals, currentYear, currentMonth]
  );

  const goalsWithDeadlines = goals.filter((g) => g.target_date).length;

  return (
    <PageWrapper>
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <CalendarDays className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              Financial Calendar
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Recurring expenses and savings goal deadlines at a glance
            </p>
          </div>
        </div>

        {/* Year navigator */}
        <div className="flex items-center gap-1">
          <button
            onClick={() => setYear((y) => y - 1)}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400 min-h-[44px] min-w-[44px] flex items-center justify-center"
            aria-label="Previous year"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="text-lg font-semibold text-gray-900 dark:text-gray-100 w-16 text-center">
            {year}
          </span>
          <button
            onClick={() => setYear((y) => y + 1)}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-400 min-h-[44px] min-w-[44px] flex items-center justify-center"
            aria-label="Next year"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* ── Legend ── */}
      <div className="flex flex-wrap items-center gap-2 mb-6 p-3 bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400 mr-1">
          <Repeat className="w-3 h-3" />
          <span>Recurring:</span>
        </div>
        {Object.entries(CATEGORY_COLORS).map(([cat, cls]) => (
          <span
            key={cat}
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}
          >
            {cat}
          </span>
        ))}
        <span className="mx-2 text-gray-300 dark:text-gray-600">|</span>
        <span
          className={`px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 ${GOAL_COLOR}`}
        >
          <Target className="w-3 h-3" />
          Savings Goal Deadline
        </span>
      </div>

      {/* ── Calendar grid ── */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className="h-32 bg-gray-100 dark:bg-gray-800 rounded-xl animate-pulse"
              aria-label="Loading"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {months.map((m) => (
            <MonthCard key={m.idx} {...m} />
          ))}
        </div>
      )}

      {/* ── Summary footer ── */}
      {!isLoading && (
        <div className="mt-6 flex flex-wrap gap-6 text-sm text-gray-500 dark:text-gray-400 border-t border-gray-200 dark:border-gray-700 pt-4">
          <span>
            <strong className="text-gray-700 dark:text-gray-300">{recurring.length}</strong>{" "}
            active recurring expense{recurring.length !== 1 ? "s" : ""}
          </span>
          <span>
            <strong className="text-gray-700 dark:text-gray-300">{goalsWithDeadlines}</strong>{" "}
            savings goal{goalsWithDeadlines !== 1 ? "s" : ""} with deadlines
          </span>
          {recurring.length === 0 && goalsWithDeadlines === 0 && (
            <span className="text-gray-400 dark:text-gray-600 italic">
              Add recurring expenses or savings goals with target dates to see them here.
            </span>
          )}
        </div>
      )}
    </PageWrapper>
  );
}
