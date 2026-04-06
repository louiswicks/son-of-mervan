import React, { useEffect, useState, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { Calendar, CheckCircle, XCircle, PlusCircle, Trash2, Pencil, Check, X } from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import ConfirmModal from "./ConfirmModal";
import { SkeletonTable } from "./Skeleton";
import {
  useMonthlyTracker,
  useSaveMonthlyTracker,
  useUpdateExpense,
  useDeleteExpense,
} from "../hooks/useExpenses";

const BASE_CATEGORIES = ['Housing','Transportation','Food','Utilities','Insurance','Healthcare','Entertainment','Other'];
const PIE_COLORS = ["#ef4444", "#10b981"]; // Spent, Saved

const buildRowsFromExpenses = (items) => {
  const serverRows = items.map(e => ({
    id: e.id,
    category: e.category,
    projected: e.planned_amount !== undefined ? String(e.planned_amount) : '',
    actual: e.actual_amount !== undefined ? String(e.actual_amount) : '',
    builtin: BASE_CATEGORIES.includes(e.category),
    name: e.name || '',
  }));

  const presentCategories = new Set(serverRows.map(r => r.category));
  const missingBuiltins = BASE_CATEGORIES
    .filter(cat => !presentCategories.has(cat))
    .map(cat => ({ id: null, category: cat, projected: '', actual: '', builtin: true, name: '' }));

  return [...serverRows, ...missingBuiltins];
};

const MonthlyTracker = () => {
  useAuth(); // ensure auth context is available
  const [selectedMonth, setSelectedMonth] = useState('2025-08');
  const [salary, setSalary] = useState('');
  const [rows, setRows] = useState(
    BASE_CATEGORIES.map(cat => ({ category: cat, projected: '', actual: '', builtin: true, name: '', id: null }))
  );
  const [editingIndex, setEditingIndex] = useState(null);
  const [editDraft, setEditDraft] = useState({});
  const [deleteConfirm, setDeleteConfirm] = useState({ open: false, expenseId: null, rowIndex: null });
  const [filterCategory, setFilterCategory] = useState('All');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState({ total: 0, pages: 0, page_size: 25 });

  const { data: trackerData, isLoading } = useMonthlyTracker(selectedMonth, {
    category: filterCategory,
    page: currentPage,
  });

  const saveMutation = useSaveMonthlyTracker(selectedMonth);
  const updateMutation = useUpdateExpense(selectedMonth);
  const deleteMutation = useDeleteExpense(selectedMonth);

  // Sync query data into local rows state
  useEffect(() => {
    if (!trackerData) return;
    const { salary_planned, salary_actual, expenses: expEnvelope = {} } = trackerData;
    const items = expEnvelope.items || [];
    setPagination({
      total: expEnvelope.total ?? 0,
      pages: expEnvelope.pages ?? 0,
      page_size: expEnvelope.page_size ?? 25,
    });

    const allRows = filterCategory === 'All'
      ? buildRowsFromExpenses(items)
      : items.map(e => ({
          id: e.id,
          category: e.category,
          projected: e.planned_amount !== undefined ? String(e.planned_amount) : '',
          actual: e.actual_amount !== undefined ? String(e.actual_amount) : '',
          builtin: BASE_CATEGORIES.includes(e.category),
          name: e.name || '',
        }));

    setRows(allRows);
    const s = salary_actual ?? salary_planned;
    setSalary(s ? String(s) : '');
  }, [trackerData, filterCategory]);

  // Cancel in-progress edits when month or filter changes
  useEffect(() => {
    setEditingIndex(null);
    setEditDraft({});
  }, [selectedMonth, filterCategory]);

  // Derive lastSaved from query data
  const lastSaved = useMemo(() => {
    if (!trackerData) return null;
    const apiSalary = Number(trackerData?.salary_actual ?? trackerData?.salary_planned ?? 0);
    const apiSpent = Number(trackerData?.total_actual ?? 0);
    const apiSaved = Number(
      trackerData?.remaining_actual ?? Math.max(apiSalary - apiSpent, 0)
    );
    return { salary: apiSalary, spent: apiSpent, saved: apiSaved };
  }, [trackerData]);

  const handleUpdate = (index, field, value) => {
    const newRows = [...rows];
    const cleaned = field === 'category' || field === 'name' ? value : value.replace(/[^\d.]/g, '');
    newRows[index][field] = cleaned;
    setRows(newRows);
  };

  const addRow = () => setRows(prev => [
    ...prev,
    { id: null, category: 'Other', projected: '', actual: '', builtin: false, name: '' },
  ]);

  const removeRow = (index) => setRows(prev => prev.filter((_, i) => i !== index));

  // ---- Inline edit handlers (optimistic) ----
  const startEdit = (index) => {
    const row = rows[index];
    setEditingIndex(index);
    setEditDraft({
      name: row.name || '',
      category: row.category || '',
      projected: row.projected || '',
      actual: row.actual || '',
    });
  };

  const cancelEdit = () => {
    setEditingIndex(null);
    setEditDraft({});
  };

  const saveEdit = async (index) => {
    const row = rows[index];
    const draft = editDraft;

    // Optimistically apply edit to UI
    const newRows = [...rows];
    newRows[index] = {
      ...row,
      name: draft.name,
      category: draft.category,
      projected: draft.projected,
      actual: draft.actual,
    };
    setRows(newRows);
    setEditingIndex(null);
    setEditDraft({});

    if (row.id) {
      try {
        await updateMutation.mutateAsync({
          id: row.id,
          payload: {
            name: draft.name || null,
            category: draft.category || null,
            planned_amount: draft.projected !== '' ? Number(draft.projected) : null,
            actual_amount: draft.actual !== '' ? Number(draft.actual) : null,
          },
        });
        // onSuccess in hook: invalidates query → rows refresh
      } catch {
        // Rollback: restore original row and re-open edit
        setRows(rows);
        setEditingIndex(index);
        setEditDraft(draft);
        // onError in hook: shows toast error
      }
    }
  };

  // ---- Delete handlers (optimistic) ----
  const requestDelete = (index) => {
    const row = rows[index];
    if (row.id) {
      setDeleteConfirm({ open: true, expenseId: row.id, rowIndex: index });
    } else {
      removeRow(index);
    }
  };

  const confirmDelete = async () => {
    const { expenseId, rowIndex } = deleteConfirm;
    setDeleteConfirm({ open: false, expenseId: null, rowIndex: null });

    // Optimistically remove from UI
    const previousRows = rows;
    setRows(prev => prev.filter((_, i) => i !== rowIndex));

    try {
      await deleteMutation.mutateAsync(expenseId);
      // onSuccess in hook: invalidates query, shows toast
    } catch {
      // Rollback
      setRows(previousRows);
      // onError in hook: shows toast error
    }
  };

  const handleSave = async () => {
    await saveMutation.mutateAsync({ salary, rows });
    // onSuccess: invalidates query (rows refresh via useEffect) + shows toast
  };

  const projectedTotal = rows.reduce((sum, r) => sum + (Number(r.projected) || 0), 0);
  const actualTotal = rows.reduce((sum, r) => sum + (Number(r.actual) || 0), 0);
  const totalDiff = actualTotal - projectedTotal;
  const totalOver = totalDiff > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-xl sm:text-2xl font-bold text-gray-800 flex items-center">
          <Calendar className="mr-2 text-blue-500" /> Monthly Tracker
        </h2>
        <input
          type="month"
          value={selectedMonth}
          onChange={(e) => { setSelectedMonth(e.target.value); setCurrentPage(1); setFilterCategory('All'); }}
          className="border rounded-lg px-3 py-2 text-[16px] text-gray-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
      </div>

      {/* Filter bar */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
        <label className="text-sm font-medium text-gray-700">Filter by category:</label>
        <select
          value={filterCategory}
          onChange={(e) => { setFilterCategory(e.target.value); setCurrentPage(1); }}
          className="border rounded-lg px-3 py-2 text-[14px] text-gray-700 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 w-full sm:w-auto"
        >
          <option value="All">All categories</option>
          {BASE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {filterCategory !== 'All' && (
          <button
            onClick={() => { setFilterCategory('All'); setCurrentPage(1); }}
            className="text-sm text-blue-600 hover:underline"
          >
            Clear filter
          </button>
        )}
        {pagination.total > 0 && (
          <span className="text-xs text-gray-500 sm:ml-auto">
            {pagination.total} expense{pagination.total !== 1 ? 's' : ''} found
          </span>
        )}
      </div>

      {/* Salary input */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-3 gap-2">
        <label className="text-gray-700 font-medium">Monthly Salary (£):</label>
        <input
          type="text"
          inputMode="decimal"
          pattern="[0-9]*[.]?[0-9]*"
          value={salary}
          onChange={(e) => setSalary(e.target.value.replace(/[^\d.]/g, ''))}
          className="px-3 py-2 border rounded-lg w-full sm:w-48 text-[16px]"
          placeholder="e.g. 2500"
        />
      </div>

      {/* Table or Skeleton */}
      {isLoading ? (
        <SkeletonTable rows={8} />
      ) : (
        <div className="overflow-x-auto -mx-4 sm:mx-0 bg-white rounded-xl shadow-md border">
          <table className="min-w-full text-left border-collapse">
            <thead className="bg-gray-100">
              <tr className="text-[13px] sm:text-sm">
                <th className="p-3">Category</th>
                <th className="p-3">Name (optional)</th>
                <th className="p-3">Projected (£)</th>
                <th className="p-3">Actual (£)</th>
                <th className="p-3">Difference</th>
                <th className="p-3">Status</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody className="text-[13px] sm:text-sm">
              {rows.map((row, i) => {
                const isEditing = editingIndex === i;
                const projectedNum = Number(isEditing ? editDraft.projected : row.projected) || 0;
                const actualNum = Number(isEditing ? editDraft.actual : row.actual) || 0;
                const diff = actualNum - projectedNum;
                const over = diff > 0;

                return (
                  <tr key={`${row.id ?? 'new'}-${row.category}-${i}`} className="border-t">
                    <td className="p-3 font-medium whitespace-nowrap">
                      {isEditing ? (
                        <select
                          value={editDraft.category}
                          onChange={(e) => setEditDraft(d => ({ ...d, category: e.target.value }))}
                          className="px-2 py-1 border rounded-lg"
                        >
                          {BASE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                      ) : row.builtin && !isEditing ? (
                        row.category
                      ) : (
                        <select
                          value={row.category}
                          onChange={(e) => handleUpdate(i, 'category', e.target.value)}
                          className="px-2 py-1 border rounded-lg"
                        >
                          {BASE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                        </select>
                      )}
                    </td>

                    <td className="p-3">
                      {isEditing ? (
                        <input
                          type="text"
                          value={editDraft.name}
                          onChange={(e) => setEditDraft(d => ({ ...d, name: e.target.value }))}
                          className="w-40 sm:w-44 px-2 py-1 border rounded-lg"
                          placeholder="(optional)"
                          autoFocus
                        />
                      ) : (
                        <input
                          type="text"
                          value={row.name || ''}
                          onChange={(e) => handleUpdate(i, 'name', e.target.value)}
                          className="w-40 sm:w-44 px-2 py-1 border rounded-lg"
                          placeholder={row.builtin ? '(optional)' : 'e.g. Gym, Gifts'}
                          disabled={row.id != null}
                        />
                      )}
                    </td>

                    <td className="p-3">
                      {isEditing ? (
                        <input
                          type="text"
                          inputMode="decimal"
                          value={editDraft.projected}
                          onChange={(e) => setEditDraft(d => ({ ...d, projected: e.target.value.replace(/[^\d.]/g, '') }))}
                          className="w-24 sm:w-28 px-2 py-1 border rounded-lg"
                          placeholder="£"
                        />
                      ) : (
                        <input
                          type="text"
                          inputMode="decimal"
                          value={row.projected}
                          onChange={(e) => handleUpdate(i, 'projected', e.target.value)}
                          className="w-24 sm:w-28 px-2 py-1 border rounded-lg"
                          placeholder="£"
                          disabled={row.id != null}
                        />
                      )}
                    </td>

                    <td className="p-3">
                      {isEditing ? (
                        <input
                          type="text"
                          inputMode="decimal"
                          value={editDraft.actual}
                          onChange={(e) => setEditDraft(d => ({ ...d, actual: e.target.value.replace(/[^\d.]/g, '') }))}
                          className="w-24 sm:w-28 px-2 py-1 border rounded-lg"
                          placeholder="£"
                        />
                      ) : (
                        <input
                          type="text"
                          inputMode="decimal"
                          value={row.actual}
                          onChange={(e) => handleUpdate(i, 'actual', e.target.value)}
                          className="w-24 sm:w-28 px-2 py-1 border rounded-lg"
                          placeholder="£"
                          disabled={row.id != null}
                        />
                      )}
                    </td>

                    <td className="p-3 whitespace-nowrap">
                      <span className={over ? 'text-red-600 font-semibold' : 'text-green-600 font-semibold'}>
                        {diff === 0 ? '£0' : `${over ? '+' : ''}£${diff.toFixed(2)}`}
                      </span>
                    </td>

                    <td className="p-3">
                      {over ? (
                        <span className="flex items-center text-red-600">
                          <XCircle size={18} className="mr-1" /> Over
                        </span>
                      ) : (
                        <span className="flex items-center text-green-600">
                          <CheckCircle size={18} className="mr-1" /> Under
                        </span>
                      )}
                    </td>

                    <td className="p-3">
                      <div className="flex items-center gap-1">
                        {isEditing ? (
                          <>
                            <button
                              onClick={() => saveEdit(i)}
                              className="text-green-600 hover:text-green-800 p-1.5 hover:bg-green-50 rounded-lg"
                              title="Save changes"
                            >
                              <Check size={16} />
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="text-gray-500 hover:text-gray-700 p-1.5 hover:bg-gray-100 rounded-lg"
                              title="Cancel"
                            >
                              <X size={16} />
                            </button>
                          </>
                        ) : (
                          <>
                            {row.id != null && (
                              <button
                                onClick={() => startEdit(i)}
                                className="text-blue-500 hover:text-blue-700 p-1.5 hover:bg-blue-50 rounded-lg"
                                title="Edit expense"
                              >
                                <Pencil size={15} />
                              </button>
                            )}
                            {(!row.builtin || row.id != null) && (
                              <button
                                onClick={() => requestDelete(i)}
                                className="text-red-500 hover:text-red-700 p-1.5 hover:bg-red-50 rounded-lg"
                                title="Delete expense"
                              >
                                <Trash2 size={15} />
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>

            <tfoot className="text-[13px] sm:text-sm">
              <tr className="border-t bg-gray-50 font-semibold">
                <td className="p-3">Totals</td>
                <td className="p-3"></td>
                <td className="p-3">£{projectedTotal.toFixed(2)}</td>
                <td className="p-3">£{actualTotal.toFixed(2)}</td>
                <td className="p-3">
                  <span className={totalOver ? 'text-red-700' : 'text-green-700'}>
                    {totalDiff === 0 ? '£0' : `${totalOver ? '+' : ''}£${totalDiff.toFixed(2)}`}
                  </span>
                </td>
                <td className="p-3">{totalOver ? 'Over' : 'Under'}</td>
                <td className="p-3"></td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* Pagination controls */}
      {pagination.pages > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage <= 1}
            className="px-3 py-1.5 border rounded-lg disabled:opacity-40 hover:bg-gray-50"
          >
            &larr; Prev
          </button>
          <span className="text-gray-600">
            Page {currentPage} of {pagination.pages}
          </span>
          <button
            onClick={() => setCurrentPage(p => Math.min(pagination.pages, p + 1))}
            disabled={currentPage >= pagination.pages}
            className="px-3 py-1.5 border rounded-lg disabled:opacity-40 hover:bg-gray-50"
          >
            Next &rarr;
          </button>
        </div>
      )}

      {/* Add row + Save */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-xs sm:text-sm text-gray-500">
          Edit saved rows with the pencil icon, or add new rows below.
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            onClick={addRow}
            className="inline-flex items-center bg-white border px-4 py-2 rounded-lg shadow-sm hover:bg-gray-50 text-[14px] sm:text-sm"
          >
            <PlusCircle size={16} className="mr-2" />
            Add expense row
          </button>

          <button
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 sm:px-6 py-3 rounded-lg shadow-md disabled:opacity-60 text-[14px] sm:text-base"
          >
            {saveMutation.isPending ? 'Saving...' : 'Save Monthly Data'}
          </button>
        </div>
      </div>

      <ConfirmModal
        open={deleteConfirm.open}
        title="Delete expense?"
        message="This expense will be removed and cannot be recovered."
        onConfirm={confirmDelete}
        onCancel={() => setDeleteConfirm({ open: false, expenseId: null, rowIndex: null })}
      />

      {lastSaved && (
        <div className="bg-white rounded-xl shadow-md border p-5 sm:p-6">
          <h3 className="text-base sm:text-lg font-semibold text-gray-800 mb-3 sm:mb-4">
            {selectedMonth} — Salary vs Spent/Saved
          </h3>
          <div>
            <div className="h-56 sm:h-64 overflow-visible">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={[
                      { name: "Spent", value: Math.max(lastSaved.spent, 0) },
                      { name: "Saved", value: Math.max(lastSaved.saved, 0) },
                    ]}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={60}
                    outerRadius={95}
                    stroke="none"
                  >
                    {[{ name: "Spent" }, { name: "Saved" }].map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip wrapperStyle={{ zIndex: 10 }} formatter={(v, n) => [`£${Number(v).toLocaleString()}`, n]} />
                  <Legend verticalAlign="bottom" align="center" />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="space-y-2 sm:space-y-3 text-sm sm:text-base">
              <div className="flex justify-between">
                <span className="text-gray-600">Salary</span>
                <span className="font-semibold">£{lastSaved.salary.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Spent</span>
                <span className="font-semibold text-red-600">£{lastSaved.spent.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Saved</span>
                <span className="font-semibold text-green-600">£{lastSaved.saved.toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MonthlyTracker;
