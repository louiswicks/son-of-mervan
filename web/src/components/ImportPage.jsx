import React, { useRef, useState } from 'react';
import { Upload, AlertTriangle, CheckCircle, X, FileText } from 'lucide-react';
import { useCSVPreview, useCSVConfirm } from '../hooks/useImport';
import { useCategories } from '../hooks/useCategories';

const FALLBACK_CATEGORIES = [
  'Housing', 'Transportation', 'Food', 'Utilities',
  'Insurance', 'Healthcare', 'Entertainment', 'Other',
];

export default function ImportPage() {
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [monthOverride, setMonthOverride] = useState('');
  const [rows, setRows] = useState([]); // preview rows with user edits
  const [result, setResult] = useState(null); // { imported, skipped }
  const [step, setStep] = useState('upload'); // 'upload' | 'preview' | 'done'

  const preview = useCSVPreview();
  const confirm = useCSVConfirm();
  const { data: categoryData } = useCategories();
  const categories = categoryData?.map((c) => c.name) ?? FALLBACK_CATEGORIES;

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  function handleFileChange(e) {
    const file = e.target.files?.[0];
    if (file) setSelectedFile(file);
  }

  function handleDrop(e) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) setSelectedFile(file);
  }

  async function handlePreview() {
    if (!selectedFile) return;
    try {
      const data = await preview.mutateAsync({
        file: selectedFile,
        month: monthOverride || null,
      });
      // Initialise rows with suggested categories; all included by default
      setRows(
        data.rows.map((r) => ({
          ...r,
          category: r.suggested_category,
          include: true,
        }))
      );
      setStep('preview');
    } catch {
      // error surfaced via preview.error
    }
  }

  function toggleInclude(rowId) {
    setRows((prev) =>
      prev.map((r) => (r.row_id === rowId ? { ...r, include: !r.include } : r))
    );
  }

  function toggleAll(checked) {
    setRows((prev) => prev.map((r) => ({ ...r, include: checked })));
  }

  function setCategory(rowId, category) {
    setRows((prev) =>
      prev.map((r) => (r.row_id === rowId ? { ...r, category } : r))
    );
  }

  async function handleConfirm() {
    const payload = rows.map((r) => ({
      row_id: r.row_id,
      description: r.description,
      amount: r.amount,
      month: r.month,
      category: r.category,
      include: r.include,
    }));
    try {
      const data = await confirm.mutateAsync(payload);
      setResult(data);
      setStep('done');
    } catch {
      // error surfaced via confirm.error
    }
  }

  function handleReset() {
    setSelectedFile(null);
    setMonthOverride('');
    setRows([]);
    setResult(null);
    setStep('upload');
    preview.reset();
    confirm.reset();
  }

  // ---------------------------------------------------------------------------
  // Derived stats
  // ---------------------------------------------------------------------------
  const includedCount = rows.filter((r) => r.include).length;
  const duplicateCount = rows.filter((r) => r.is_duplicate).length;
  const allChecked = rows.length > 0 && rows.every((r) => r.include);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (step === 'done') {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center">
        <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Import complete</h2>
        <p className="text-gray-600 dark:text-gray-400 mb-6">
          <span className="font-semibold text-green-600">{result.imported}</span> expense
          {result.imported !== 1 ? 's' : ''} imported
          {result.skipped > 0 && (
            <>, <span className="font-semibold text-gray-500">{result.skipped}</span> skipped</>
          )}
          .
        </p>
        <button
          onClick={handleReset}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Import another file
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Import Bank Statement</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Upload a CSV exported from your bank. Transactions are reviewed before being saved.
        </p>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Step 1 — Upload                                                      */}
      {/* ------------------------------------------------------------------ */}
      {step === 'upload' && (
        <div className="space-y-4">
          {/* Drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-10 text-center cursor-pointer hover:border-blue-400 transition-colors"
          >
            <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
            {selectedFile ? (
              <p className="font-medium text-gray-700 dark:text-gray-300">
                <FileText className="inline w-4 h-4 mr-1" />
                {selectedFile.name}
              </p>
            ) : (
              <>
                <p className="text-gray-600 dark:text-gray-400">
                  Drag &amp; drop your CSV file here, or{' '}
                  <span className="text-blue-600 underline">browse</span>
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  Supports most bank export formats (date, description, amount columns)
                </p>
              </>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={handleFileChange}
            />
          </div>

          {/* Optional month override */}
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-600 dark:text-gray-400 whitespace-nowrap">
              Override month (optional):
            </label>
            <input
              type="month"
              value={monthOverride}
              onChange={(e) => setMonthOverride(e.target.value)}
              className="border border-gray-300 dark:border-gray-600 rounded-md px-3 py-1.5 text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            />
            <span className="text-xs text-gray-400">
              Leave blank to use dates from the CSV
            </span>
          </div>

          {preview.error && (
            <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              {preview.error?.response?.data?.detail ?? 'Failed to parse the CSV. Please check the file format.'}
            </div>
          )}

          <button
            onClick={handlePreview}
            disabled={!selectedFile || preview.isPending}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {preview.isPending ? 'Parsing…' : 'Preview Import'}
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Step 2 — Preview & Review                                           */}
      {/* ------------------------------------------------------------------ */}
      {step === 'preview' && (
        <div className="space-y-4">
          {/* Summary bar */}
          <div className="flex flex-wrap gap-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-xl text-sm">
            <span className="text-gray-700 dark:text-gray-300">
              <strong>{rows.length}</strong> row{rows.length !== 1 ? 's' : ''} parsed
            </span>
            {duplicateCount > 0 && (
              <span className="text-amber-600 dark:text-amber-400 flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" />
                {duplicateCount} possible duplicate{duplicateCount !== 1 ? 's' : ''}
              </span>
            )}
            <span className="text-blue-600 dark:text-blue-400">
              {includedCount} selected for import
            </span>
            <button
              onClick={handleReset}
              className="ml-auto text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-1"
            >
              <X className="w-3.5 h-3.5" /> Cancel
            </button>
          </div>

          {rows.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              No valid rows were found in the CSV.
            </div>
          ) : (
            <>
              <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-800 text-gray-500 dark:text-gray-400 text-xs uppercase">
                    <tr>
                      <th className="px-3 py-3 text-left">
                        <input
                          type="checkbox"
                          checked={allChecked}
                          onChange={(e) => toggleAll(e.target.checked)}
                          aria-label="Select all"
                        />
                      </th>
                      <th className="px-3 py-3 text-left">Date</th>
                      <th className="px-3 py-3 text-left">Description</th>
                      <th className="px-3 py-3 text-right">Amount</th>
                      <th className="px-3 py-3 text-left">Month</th>
                      <th className="px-3 py-3 text-left">Category</th>
                      <th className="px-3 py-3 text-left">Notes</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {rows.map((row) => (
                      <tr
                        key={row.row_id}
                        className={`${
                          !row.include ? 'opacity-40' : ''
                        } hover:bg-gray-50 dark:hover:bg-gray-800/50`}
                      >
                        <td className="px-3 py-2">
                          <input
                            type="checkbox"
                            checked={row.include}
                            onChange={() => toggleInclude(row.row_id)}
                            aria-label={`Include ${row.description}`}
                          />
                        </td>
                        <td className="px-3 py-2 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                          {row.date}
                        </td>
                        <td className="px-3 py-2 text-gray-900 dark:text-white max-w-xs truncate">
                          {row.description}
                        </td>
                        <td className="px-3 py-2 text-right font-medium text-gray-900 dark:text-white whitespace-nowrap">
                          £{row.amount.toFixed(2)}
                        </td>
                        <td className="px-3 py-2 text-gray-500 dark:text-gray-400 whitespace-nowrap">
                          {row.month}
                        </td>
                        <td className="px-3 py-2">
                          <select
                            value={row.category}
                            onChange={(e) => setCategory(row.row_id, e.target.value)}
                            className="border border-gray-300 dark:border-gray-600 rounded px-2 py-1 text-xs bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                          >
                            {categories.map((c) => (
                              <option key={c} value={c}>
                                {c}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          {row.is_duplicate && (
                            <span className="inline-flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 px-2 py-0.5 rounded-full">
                              <AlertTriangle className="w-3 h-3" />
                              Duplicate
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {confirm.error && (
                <div className="flex items-start gap-2 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-sm text-red-700 dark:text-red-400">
                  <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
                  {confirm.error?.response?.data?.detail ?? 'Import failed. Please try again.'}
                </div>
              )}

              <div className="flex items-center gap-3">
                <button
                  onClick={handleConfirm}
                  disabled={includedCount === 0 || confirm.isPending}
                  className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {confirm.isPending
                    ? 'Importing…'
                    : `Import ${includedCount} expense${includedCount !== 1 ? 's' : ''}`}
                </button>
                <button
                  onClick={handleReset}
                  className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  Start over
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
