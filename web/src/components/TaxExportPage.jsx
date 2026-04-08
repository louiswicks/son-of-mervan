import React, { useState } from "react";
import { FileText, Download, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import { getTaxSummary, exportTaxPDF } from "../api/export";

// Current UK tax year: if we're past April 5, the current tax year has started
function currentUKTaxYear() {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1; // 1-based
  // Before April 6 → still in previous tax year
  return month < 4 || (month === 4 && now.getDate() < 6) ? year - 1 : year;
}

function buildYearOptions() {
  const current = currentUKTaxYear();
  const options = [];
  for (let y = current; y >= current - 4; y--) {
    options.push(y);
  }
  return options;
}

function SummaryCard({ label, value, sub, colour }) {
  return (
    <div className={`rounded-xl p-4 ${colour} flex flex-col gap-1`}>
      <span className="text-xs font-medium text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-xl font-bold text-gray-900 dark:text-white">{value}</span>
      {sub && <span className="text-xs text-gray-500 dark:text-gray-400">{sub}</span>}
    </div>
  );
}

function DeductibleBadge({ yes }) {
  return yes ? (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 px-2 py-0.5 rounded-full">
      <CheckCircle size={11} /> Potentially deductible
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full">
      <XCircle size={11} /> Personal
    </span>
  );
}

export default function TaxExportPage() {
  const yearOptions = buildYearOptions();
  const [taxYear, setTaxYear] = useState(yearOptions[0]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleLoad() {
    setLoading(true);
    setError(null);
    setSummary(null);
    try {
      const data = await getTaxSummary(taxYear);
      setSummary(data);
    } catch (e) {
      setError(e?.response?.data?.detail ?? "Failed to load tax summary.");
    } finally {
      setLoading(false);
    }
  }

  async function handleDownloadPDF() {
    setPdfLoading(true);
    try {
      await exportTaxPDF(taxYear);
    } catch (e) {
      setError(e?.response?.data?.detail ?? "Failed to generate PDF.");
    } finally {
      setPdfLoading(false);
    }
  }

  const fmt = (n) =>
    typeof n === "number"
      ? n.toLocaleString("en-GB", { style: "currency", currency: "GBP" })
      : "—";

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <FileText size={24} className="text-blue-600 dark:text-blue-400" />
            Tax Year Summary
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            UK Self Assessment expense overview — April to April
          </p>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="flex gap-3 p-4 rounded-xl bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
        <AlertTriangle size={18} className="text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
        <p className="text-sm text-amber-800 dark:text-amber-300">
          <strong>Not professional tax advice.</strong> This summary is a convenience tool only.
          Deductibility depends on your individual circumstances. Always consult a qualified
          accountant or refer to HMRC guidance before submitting your Self Assessment return.
        </p>
      </div>

      {/* Tax year selector */}
      <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h2 className="font-semibold text-gray-900 dark:text-white mb-4">Select Tax Year</h2>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">
              Tax Year
            </label>
            <select
              value={taxYear}
              onChange={(e) => {
                setTaxYear(Number(e.target.value));
                setSummary(null);
                setError(null);
              }}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>
                  {y}/{y + 1} (6 Apr {y} – 5 Apr {y + 1})
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end gap-2">
            <button
              onClick={handleLoad}
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              {loading ? "Loading…" : "Load Summary"}
            </button>
            {summary && (
              <button
                onClick={handleDownloadPDF}
                disabled={pdfLoading}
                className="flex items-center gap-1.5 bg-gray-700 hover:bg-gray-800 disabled:opacity-60 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                <Download size={14} />
                {pdfLoading ? "Generating…" : "Download PDF"}
              </button>
            )}
          </div>
        </div>
        {error && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
        )}
      </div>

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-20 rounded-xl bg-gray-100 dark:bg-gray-800 animate-pulse" />
            ))}
          </div>
          <div className="h-64 rounded-xl bg-gray-100 dark:bg-gray-800 animate-pulse" />
        </div>
      )}

      {/* Summary */}
      {summary && !loading && (
        <>
          {/* Period note */}
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Period: <strong>{summary.period_start}</strong> to <strong>{summary.period_end}</strong>
            &nbsp;·&nbsp; Months with data: <strong>{summary.months_with_data} / 12</strong>
          </p>

          {/* KPI cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <SummaryCard
              label="Total Income"
              value={fmt(summary.total_income)}
              colour="bg-blue-50 dark:bg-blue-900/20 border border-blue-100 dark:border-blue-800"
            />
            <SummaryCard
              label="Total Expenses"
              value={fmt(summary.total_expenses)}
              colour="bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800"
            />
            <SummaryCard
              label="Net Savings"
              value={fmt(summary.net_savings)}
              sub={`${summary.savings_rate.toFixed(1)}% savings rate`}
              colour={
                summary.net_savings >= 0
                  ? "bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-800"
                  : "bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800"
              }
            />
            <SummaryCard
              label="Potentially Deductible"
              value={fmt(summary.potentially_deductible_total)}
              sub="Advisory — verify with accountant"
              colour="bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-800"
            />
          </div>

          {/* No data notice */}
          {summary.months_with_data === 0 && (
            <div className="text-center py-12 text-gray-400 dark:text-gray-500">
              <FileText size={40} className="mx-auto mb-3 opacity-40" />
              <p className="font-medium">No spending data found for this tax year.</p>
              <p className="text-sm mt-1">Track expenses in the Monthly Tracker to see them here.</p>
            </div>
          )}

          {/* Category breakdown table */}
          {summary.category_breakdown.length > 0 && (
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-200 dark:border-gray-700">
                <h2 className="font-semibold text-gray-900 dark:text-white">
                  Expense Breakdown by Category
                </h2>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Mapped to HMRC Self Assessment expense headings
                </p>
              </div>

              {/* Desktop table */}
              <div className="hidden sm:block overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                      <th className="text-left px-4 py-3 font-medium">Category</th>
                      <th className="text-left px-4 py-3 font-medium">HMRC Heading</th>
                      <th className="text-right px-4 py-3 font-medium">Total Spent</th>
                      <th className="text-center px-4 py-3 font-medium">Months</th>
                      <th className="text-left px-4 py-3 font-medium">Deductibility</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {summary.category_breakdown.map((row) => (
                      <tr
                        key={row.category}
                        className={
                          row.potentially_deductible
                            ? "bg-emerald-50/30 dark:bg-emerald-900/10 hover:bg-emerald-50/60 dark:hover:bg-emerald-900/20"
                            : "hover:bg-gray-50 dark:hover:bg-gray-800"
                        }
                      >
                        <td className="px-4 py-3 font-medium text-gray-900 dark:text-white">
                          {row.category}
                        </td>
                        <td className="px-4 py-3 text-gray-600 dark:text-gray-300">
                          {row.hmrc_category}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-gray-900 dark:text-white">
                          {fmt(row.total_actual)}
                        </td>
                        <td className="px-4 py-3 text-center text-gray-600 dark:text-gray-400">
                          {row.months_with_data}
                        </td>
                        <td className="px-4 py-3">
                          <DeductibleBadge yes={row.potentially_deductible} />
                        </td>
                      </tr>
                    ))}
                    {/* Totals row */}
                    <tr className="bg-gray-100 dark:bg-gray-800 font-semibold">
                      <td className="px-4 py-3 text-gray-900 dark:text-white" colSpan={2}>
                        Total
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-gray-900 dark:text-white">
                        {fmt(summary.total_expenses)}
                      </td>
                      <td colSpan={2} />
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Mobile cards */}
              <div className="sm:hidden divide-y divide-gray-100 dark:divide-gray-800">
                {summary.category_breakdown.map((row) => (
                  <div key={row.category} className="p-4 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-900 dark:text-white">
                        {row.category}
                      </span>
                      <span className="font-mono text-gray-900 dark:text-white">
                        {fmt(row.total_actual)}
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {row.hmrc_category} · {row.months_with_data} months
                    </p>
                    <DeductibleBadge yes={row.potentially_deductible} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Footer note */}
          <p className="text-xs text-gray-400 dark:text-gray-500 text-center pb-4">
            "Potentially deductible" categories are flagged based on common HMRC allowable expense
            types for self-employed individuals. This does <em>not</em> guarantee deductibility
            for your specific circumstances.
          </p>
        </>
      )}
    </div>
  );
}
