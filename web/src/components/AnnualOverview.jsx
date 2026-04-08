import React, { useMemo, useState } from "react";
import { BarChart3, Calendar, Download, LineChart as LineIcon, PiggyBank } from "lucide-react";
import { exportCSV } from "../api/export";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";
import { useAnnualSummary } from "../hooks/useAnnualSummary";
import { SkeletonCard, SkeletonChart } from "./Skeleton";
import { useTheme } from "../hooks/useTheme";
import PageWrapper from "./PageWrapper";
import Card from "./Card";

const monthLabels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

const AnnualExportButton = ({ year }) => {
  const [loading, setLoading] = useState(false);

  const handleExport = async () => {
    setLoading(true);
    try {
      await exportCSV(`${year}-01`, `${year}-12`);
    } catch (e) {
      console.error('CSV export failed', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleExport}
      disabled={loading}
      className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 min-h-[44px] text-sm font-medium"
      title="Export year as CSV"
    >
      <Download size={16} />
      {loading ? 'Exporting…' : 'CSV'}
    </button>
  );
};

const AnnualOverview = () => {
  const thisYear = new Date().getFullYear().toString();
  const [year, setYear] = useState(thisYear);

  const { data, isLoading } = useAnnualSummary(year);
  const resolved = useMemo(() => data || { months: [], totals: {} }, [data]);
  const { theme } = useTheme();

  const chartColors = useMemo(() => ({
    primary:  theme === "dark" ? "#60a5fa" : "#3b82f6",
    success:  theme === "dark" ? "#34d399" : "#10b981",
    danger:   theme === "dark" ? "#f87171" : "#ef4444",
    grid:     theme === "dark" ? "#334155" : "#e5e7eb",
    axis:     theme === "dark" ? "#94a3b8" : "#6b7280",
    tooltipBg:     theme === "dark" ? "#1e293b" : "#ffffff",
    tooltipBorder: theme === "dark" ? "#334155" : "#e5e7eb",
    tooltipText:   theme === "dark" ? "#f1f5f9" : "#111827",
  }), [theme]);

  const chartData = useMemo(() => {
    return (resolved.months || []).map((m, i) => ({
      name: monthLabels[i],
      Planned: Number(m.total_planned || 0),
      Actual: Number(m.total_actual || 0),
    }));
  }, [resolved]);

  const savingsTrendData = useMemo(() => {
    const months = Array.isArray(resolved?.months) ? resolved.months : [];
    return months.map((m, i) => {
      const actualSalary = Number(m.actual_salary ?? 0);
      const totalActual  = Number(m.total_actual ?? 0);
      const savings = Math.max(0, actualSalary - totalActual);
      return {
        name: monthLabels[i] ?? m.month ?? `M${i+1}`,
        Savings: isFinite(savings) ? savings : 0,
      };
    });
  }, [resolved]);

  const savingsMax = useMemo(() => {
    const vals = savingsTrendData.map(d => d.Savings);
    const max = Math.max(0, ...vals);
    return max > 0 ? Math.ceil(max * 1.1) : 100;
  }, [savingsTrendData]);

  const tooltipStyle = {
    backgroundColor: chartColors.tooltipBg,
    border: `1px solid ${chartColors.tooltipBorder}`,
    color: chartColors.tooltipText,
  };

  return (
    <PageWrapper>
      {/* Header + Year Picker */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-800 dark:text-gray-100 flex items-center">
          <Calendar className="mr-2 text-blue-500" /> Annual Overview
        </h2>
        <div className="flex items-center space-x-2">
          <label className="text-gray-700 dark:text-gray-300">Year:</label>
          <select
            value={year}
            onChange={(e) => setYear(e.target.value)}
            className="border dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
          >
            {Array.from({ length: 6 }).map((_, idx) => {
              const y = (new Date().getFullYear() - 2 + idx).toString();
              return (
                <option key={y} value={y}>
                  {y}
                </option>
              );
            })}
          </select>
          <AnnualExportButton year={year} />
        </div>
      </div>

      {/* KPI Cards */}
      {isLoading ? (
        <div className="grid md:grid-cols-3 gap-6">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : (
        <div className="grid md:grid-cols-3 gap-6">
          <Card>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">Total Planned Spend</span>
              <BarChart3 className="text-blue-500" />
            </div>
            <div className="text-3xl font-bold mt-2">
              £{Number(resolved?.totals?.total_planned || 0).toLocaleString()}
            </div>
          </Card>
          <Card>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">Total Actual Spend</span>
              <LineIcon className="text-purple-500" />
            </div>
            <div className="text-3xl font-bold mt-2">
              £{Number(resolved?.totals?.total_actual || 0).toLocaleString()}
            </div>
          </Card>
          <Card>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500 dark:text-gray-400">Total Remaining (Savings)</span>
              <PiggyBank className="text-green-600" />
            </div>
            <div className="text-3xl font-bold mt-2">
              £{Number(resolved?.totals?.remaining_actual || 0).toLocaleString()}
            </div>
          </Card>
        </div>
      )}

      {/* Trend Charts */}
      {isLoading ? (
        <>
          <SkeletonChart />
          <SkeletonChart />
        </>
      ) : (
        <>
          <Card>
            <h3 className="text-lg font-semibold mb-4 dark:text-gray-100">Spending Trend</h3>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                  <XAxis dataKey="name" tick={{ fill: chartColors.axis }} />
                  <YAxis tickFormatter={(v) => `£${v}`} tick={{ fill: chartColors.axis }} />
                  <Tooltip
                    formatter={(v) => `£${Number(v).toLocaleString()}`}
                    contentStyle={tooltipStyle}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="Planned" stroke={chartColors.primary} strokeWidth={3} dot={false} />
                  <Line type="monotone" dataKey="Actual" stroke={chartColors.success} strokeWidth={3} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <h3 className="text-lg font-semibold mb-4 dark:text-gray-100">Savings Trend (Actual)</h3>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={savingsTrendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                  <XAxis dataKey="name" tick={{ fill: chartColors.axis }} />
                  <YAxis
                    domain={[0, savingsMax]}
                    tickFormatter={(v) => `£${v}`}
                    allowDecimals={false}
                    tick={{ fill: chartColors.axis }}
                  />
                  <Tooltip
                    formatter={(v) => `£${Number(v).toLocaleString()}`}
                    contentStyle={tooltipStyle}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="Savings"
                    stroke={chartColors.danger}
                    strokeWidth={3}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </>
      )}

      {/* Month Table */}
      {isLoading ? (
        <Card className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex gap-4">
              {[60, 80, 100, 100, 110, 70].map((w, j) => (
                <div key={j} className="animate-pulse bg-gray-200 dark:bg-gray-700 rounded h-5" style={{ width: w }} />
              ))}
            </div>
          ))}
        </Card>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead className="bg-gray-100 dark:bg-gray-700">
              <tr>
                <th className="p-3">Month</th>
                <th className="p-3">Salary</th>
                <th className="p-3">Planned Spend</th>
                <th className="p-3">Actual Spend</th>
                <th className="p-3">Remaining (Savings)</th>
                <th className="p-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {(resolved.months || []).map((m, i) => {
                const over = Number(m.total_actual || 0) > Number(m.total_planned || 0);
                return (
                  <tr key={m.month} className="border-t dark:border-gray-700">
                    <td className="p-3 font-medium">{monthLabels[i]}</td>
                    <td className="p-3">£{Number(m.planned_salary || 0).toLocaleString()}</td>
                    <td className="p-3">£{Number(m.total_planned || 0).toLocaleString()}</td>
                    <td className="p-3">£{Number(m.total_actual || 0).toLocaleString()}</td>
                    <td className="p-3">£{Number(m.remaining_actual || 0).toLocaleString()}</td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-1 rounded text-xs font-semibold ${
                          over ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"
                        }`}
                      >
                        {over ? "Over" : "Under"}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot>
              <tr className="border-t dark:border-gray-700 bg-gray-50 dark:bg-gray-700 font-semibold">
                <td className="p-3">Totals</td>
                <td className="p-3">£{Number(resolved?.totals?.planned_salary || 0).toLocaleString()}</td>
                <td className="p-3">£{Number(resolved?.totals?.total_planned || 0).toLocaleString()}</td>
                <td className="p-3">£{Number(resolved?.totals?.total_actual || 0).toLocaleString()}</td>
                <td className="p-3">£{Number(resolved?.totals?.remaining_actual || 0).toLocaleString()}</td>
                <td className="p-3"></td>
              </tr>
            </tfoot>
          </table>
        </Card>
      )}
    </PageWrapper>
  );
};

export default AnnualOverview;
