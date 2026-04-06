import React, { useEffect, useMemo, useState } from "react";
import { BarChart3, Calendar, LineChart as LineIcon, PiggyBank } from "lucide-react";
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
import { getAnnualOverview } from "../api/expenses";

const monthLabels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

const AnnualOverview = () => {
  const thisYear = new Date().getFullYear().toString();
  const [year, setYear] = useState(thisYear);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState({ months: [], totals: {} });

  const fetchData = async (y) => {
    setLoading(true);
    try {
      const resData = await getAnnualOverview(y);
      setData(resData);
    } catch (e) {
      console.error("Failed to load annual overview", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData(year);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year]); // eslint-disable-line react-hooks/exhaustive-deps

  const chartData = useMemo(() => {
    return (data.months || []).map((m, i) => ({
      name: monthLabels[i],
      Planned: Number(m.total_planned || 0),
      Actual: Number(m.total_actual || 0),
    }));
  }, [data]);

  const savingsTrendData = useMemo(() => {
    const months = Array.isArray(data?.months) ? data.months : [];
    return months.map((m, i) => {
      const actualSalary = Number(m.actual_salary ?? 0);
      const totalActual  = Number(m.total_actual ?? 0);
      // clamp negative savings to 0 for the chart
      const savings = Math.max(0, actualSalary - totalActual);
      return {
        name: monthLabels[i] ?? m.month ?? `M${i+1}`,
        Savings: isFinite(savings) ? savings : 0,
      };
    });
  }, [data]);

  // compute a safe max so the line doesn't sit on the axis
  const savingsMax = useMemo(() => {
    const vals = savingsTrendData.map(d => d.Savings);
    const max = Math.max(0, ...vals);
    // if all zeros, use a small ceiling so the line is visible above the axis
    return max > 0 ? Math.ceil(max * 1.1) : 100;
  }, [savingsTrendData]);

  return (
    <div className="space-y-6">
      {/* Header + Year Picker */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-800 flex items-center">
          <Calendar className="mr-2 text-blue-500" /> Annual Overview
        </h2>
        <div className="flex items-center space-x-2">
          <label className="text-gray-700">Year:</label>
          <select
            value={year}
            onChange={(e) => setYear(e.target.value)}
            className="border rounded-lg px-3 py-2"
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
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid md:grid-cols-3 gap-6">
        <div className="bg-white border rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500">Total Planned Spend</span>
            <BarChart3 className="text-blue-500" />
          </div>
          <div className="text-3xl font-bold mt-2">
            £{Number(data?.totals?.total_planned || 0).toLocaleString()}
          </div>
        </div>
        <div className="bg-white border rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500">Total Actual Spend</span>
            <LineIcon className="text-purple-500" />
          </div>
          <div className="text-3xl font-bold mt-2">
            £{Number(data?.totals?.total_actual || 0).toLocaleString()}
          </div>
        </div>
        <div className="bg-white border rounded-xl p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-500">Total Remaining (Savings)</span>
            <PiggyBank className="text-green-600" />
          </div>
          <div className="text-3xl font-bold mt-2">
            £{Number(data?.totals?.remaining_actual || 0).toLocaleString()}
          </div>
        </div>
      </div>

      {/* Trend Chart */}
      <div className="bg-white border rounded-xl p-6 shadow-sm">
        <h3 className="text-lg font-semibold mb-4">Spending Trend</h3>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis tickFormatter={(v) => `£${v}`} />
              <Tooltip formatter={(v) => `£${Number(v).toLocaleString()}`} />
              <Legend />
              <Line type="monotone" dataKey="Planned" stroke="#3b82f6" strokeWidth={3} dot={false} />
              <Line type="monotone" dataKey="Actual" stroke="#10b981" strokeWidth={3} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Savings Trend */}
      <div className="bg-white border rounded-xl p-6 shadow-sm">
        <h3 className="text-lg font-semibold mb-4">Savings Trend (Actual)</h3>
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={savingsTrendData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis
                domain={[0, savingsMax]}
                tickFormatter={(v) => `£${v}`}
                allowDecimals={false}
              />
              <Tooltip formatter={(v) => `£${Number(v).toLocaleString()}`} />
              <Legend />
              <Line
                type="monotone"
                dataKey="Savings"
                stroke="#ef4444"
                strokeWidth={3}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Month Table */}
      <div className="bg-white border rounded-xl p-6 shadow-sm overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-gray-100">
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
            {(data.months || []).map((m, i) => {
              const over = Number(m.total_actual || 0) > Number(m.total_planned || 0);
              return (
                <tr key={m.month} className="border-t">
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

          {/* Year totals row */}
          <tfoot>
            <tr className="border-t bg-gray-50 font-semibold">
              <td className="p-3">Totals</td>
              <td className="p-3">£{Number(data?.totals?.planned_salary || 0).toLocaleString()}</td>
              <td className="p-3">£{Number(data?.totals?.total_planned || 0).toLocaleString()}</td>
              <td className="p-3">£{Number(data?.totals?.total_actual || 0).toLocaleString()}</td>
              <td className="p-3">£{Number(data?.totals?.remaining_actual || 0).toLocaleString()}</td>
              <td className="p-3"></td>
            </tr>
          </tfoot>
        </table>
      </div>

      {loading && (
        <div className="text-sm text-gray-500">Loading {year}…</div>
      )}
    </div>
  );
};

export default AnnualOverview;
