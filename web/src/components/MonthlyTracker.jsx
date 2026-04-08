import React, { useEffect, useState, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { Calendar, CheckCircle, XCircle, PlusCircle, Trash2, Pencil, Check, X, Download, Clock, Search } from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import ConfirmModal from "./ConfirmModal";
import { SkeletonTable } from "./Skeleton";
import {
  useMonthlyTracker,
  useSaveMonthlyTracker,
  useUpdateExpense,
  useDeleteExpense,
  useExpenseSearch,
} from "../hooks/useExpenses";
import { exportCSV, exportPDF } from "../api/export";
import { useExpenseAudit } from "../hooks/useAudit";
import { useProfile } from "../hooks/useProfile";
import { currencySymbol, useCurrencies } from "../hooks/useCurrency";
import { useSpendingPace, useCategorySuggestion } from "../hooks/useInsights";
import { useCategories } from "../hooks/useCategories";

const FALLBACK_CATEGORIES = ['Housing','Transportation','Food','Utilities','Insurance','Healthcare','Entertainment','Other'];
const PIE_COLORS = ["#ef4444", "#10b981"]; // Spent, Saved

const ExportMenu = ({ month }) => {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(null); // 'csv' | 'pdf' | null

  const handleExport = async (type) => {
    setOpen(false);
    setLoading(type);
    try {
      if (type === 'csv') {
        await exportCSV(month, month);
      } else {
        await exportPDF(month);
      }
    } catch (e) {
      console.error('Export failed', e);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(o => !o)}
        disabled={!!loading}
        className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 min-h-[44px] text-sm font-medium"
        title="Export data"
      >
        <Download size={16} />
        {loading ? 'Exporting…' : 'Export'}
      </button>
      {open && (
        <div className="absolute right-0 mt-1 w-44 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg z-20">
          <button
            onClick={() => handleExport('csv')}
            className="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-t-lg"
          >
            Download CSV
          </button>
          <button
            onClick={() => handleExport('pdf')}
            className="w-full text-left px-4 py-2.5 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700 rounded-b-lg"
          >
            Download PDF Report
          </button>
        </div>
      )}
    </div>
  );
};

const ACTION_LABEL = { create: 'Created', update: 'Updated', delete: 'Deleted' };
const ACTION_COLOR = {
  create: 'text-green-600 dark:text-green-400',
  update: 'text-blue-600 dark:text-blue-400',
  delete: 'text-red-600 dark:text-red-400',
};

const AuditDrawer = ({ expenseId, expenseName, onClose }) => {
  const { data: entries, isLoading, isError } = useExpenseAudit(expenseId, true);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-labelledby="audit-drawer-title">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* Panel */}
      <div className="relative w-full max-w-sm bg-white dark:bg-gray-900 h-full shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b dark:border-gray-700">
          <div>
            <h2 id="audit-drawer-title" className="font-semibold text-gray-900 dark:text-gray-100 text-base">Change History</h2>
            {expenseName && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate max-w-[220px]">{expenseName}</p>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 dark:text-gray-400 min-w-[44px] min-h-[44px] flex items-center justify-center"
            aria-label="Close history"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {isLoading && (
            <p className="text-sm text-gray-500 dark:text-gray-400">Loading history…</p>
          )}
          {isError && (
            <p className="text-sm text-gray-500 dark:text-gray-400">No history available for this expense.</p>
          )}
          {entries && entries.length === 0 && (
            <p className="text-sm text-gray-500 dark:text-gray-400">No changes recorded yet.</p>
          )}
          {entries && entries.length > 0 && (
            <ol className="space-y-4">
              {entries.map((entry) => {
                const before = entry.changed_fields?.before;
                const after = entry.changed_fields?.after;
                const snapshot = after || before;
                return (
                  <li key={entry.id} className="border-l-2 border-gray-200 dark:border-gray-700 pl-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-semibold uppercase tracking-wide ${ACTION_COLOR[entry.action] || ''}`}>
                        {ACTION_LABEL[entry.action] || entry.action}
                      </span>
                      <span className="text-xs text-gray-400 dark:text-gray-500">
                        {new Date(entry.timestamp).toLocaleString()}
                      </span>
                    </div>
                    {snapshot && (
                      <div className="text-xs text-gray-700 dark:text-gray-300 space-y-0.5">
                        {entry.action === 'update' && before && after ? (
                          <>
                            {Object.keys(after).map((key) => (
                              before[key] !== after[key] ? (
                                <div key={key}>
                                  <span className="font-medium capitalize">{key.replace(/_/g, ' ')}:</span>{' '}
                                  <span className="line-through text-gray-400">{String(before[key])}</span>
                                  {' → '}
                                  <span className="text-gray-900 dark:text-gray-100">{String(after[key])}</span>
                                </div>
                              ) : null
                            ))}
                          </>
                        ) : (
                          <>
                            <div><span className="font-medium">Name:</span> {snapshot.name || '—'}</div>
                            <div><span className="font-medium">Category:</span> {snapshot.category}</div>
                            <div><span className="font-medium">Planned:</span> {currencySymbol(snapshot.currency || 'GBP')}{Number(snapshot.planned_amount).toFixed(2)}</div>
                            <div><span className="font-medium">Actual:</span> {currencySymbol(snapshot.currency || 'GBP')}{Number(snapshot.actual_amount).toFixed(2)}</div>
                          </>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
};

const CategorySuggestionChip = ({ name, onAccept }) => {
  const [debouncedName, setDebouncedName] = useState(name);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedName(name), 300);
    return () => clearTimeout(timer);
  }, [name]);
  const { data } = useCategorySuggestion(debouncedName);
  if (!data?.suggestion) return null;
  return (
    <button
      type="button"
      onClick={() => onAccept(data.suggestion)}
      className="mt-1 block text-xs px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-700 hover:bg-blue-100 dark:hover:bg-blue-900/50 whitespace-nowrap"
      title={`Based on ${data.count} past expense${data.count !== 1 ? 's' : ''}`}
      aria-label={`Suggest category: ${data.suggestion}`}
    >
      Suggested: {data.suggestion}
    </button>
  );
};

const buildRowsFromExpenses = (items, defaultCurrency = 'GBP', categories = FALLBACK_CATEGORIES) => {
  const serverRows = items.map(e => ({
    id: e.id,
    category: e.category,
    projected: e.planned_amount !== undefined ? String(e.planned_amount) : '',
    actual: e.actual_amount !== undefined ? String(e.actual_amount) : '',
    builtin: categories.includes(e.category),
    name: e.name || '',
    currency: e.currency || defaultCurrency,
    note: e.note || '',
    tags: e.tags || [],
  }));

  const presentCategories = new Set(serverRows.map(r => r.category));
  const missingBuiltins = categories
    .filter(cat => !presentCategories.has(cat))
    .map(cat => ({ id: null, category: cat, projected: '', actual: '', builtin: true, name: '', currency: defaultCurrency }));

  return [...serverRows, ...missingBuiltins];
};

const MonthlyTracker = () => {
  useAuth(); // ensure auth context is available
  const { data: profile } = useProfile();
  const { data: currencies = [] } = useCurrencies();
  const baseCurrency = profile?.base_currency || 'GBP';
  const sym = currencySymbol(baseCurrency);

  const { data: categoriesData } = useCategories();
  const BASE_CATEGORIES = useMemo(
    () => categoriesData?.map(c => c.name) ?? FALLBACK_CATEGORIES,
    [categoriesData]
  );

  const [selectedMonth, setSelectedMonth] = useState('2025-08');
  const [salary, setSalary] = useState('');
  const [rows, setRows] = useState(
    FALLBACK_CATEGORIES.map(cat => ({ category: cat, projected: '', actual: '', builtin: true, name: '', id: null, currency: 'GBP' }))
  );
  const [editingIndex, setEditingIndex] = useState(null);
  const [editDraft, setEditDraft] = useState({});
  const [deleteConfirm, setDeleteConfirm] = useState({ open: false, expenseId: null, rowIndex: null });
  const [historyExpense, setHistoryExpense] = useState(null); // { id, name }
  const [filterCategory, setFilterCategory] = useState('All');
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState({ total: 0, pages: 0, page_size: 25 });

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [searchCategory, setSearchCategory] = useState('All');
  const [searchFrom, setSearchFrom] = useState('');
  const [searchTo, setSearchTo] = useState('');
  const [searchPage, setSearchPage] = useState(1);
  const isSearchMode = Boolean(debouncedQuery || searchFrom || searchTo);

  // Debounce search query 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
      setSearchPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const { data: searchData, isLoading: searchLoading } = useExpenseSearch({
    q: debouncedQuery || undefined,
    category: searchCategory !== 'All' ? searchCategory : undefined,
    from: searchFrom || undefined,
    to: searchTo || undefined,
    page: searchPage,
    perPage: 20,
  });

  const { data: trackerData, isLoading } = useMonthlyTracker(selectedMonth, {
    category: filterCategory,
    page: currentPage,
  });

  const { data: paceData } = useSpendingPace(selectedMonth);

  const saveMutation = useSaveMonthlyTracker(selectedMonth);
  const updateMutation = useUpdateExpense(selectedMonth);
  const deleteMutation = useDeleteExpense(selectedMonth);

  // Sync query data into local rows state
  useEffect(() => {
    if (!trackerData) return;
    const { salary_planned, salary_actual, expenses: expEnvelope = {} } = trackerData;
    const items = expEnvelope.items || [];
    const serverCurrency = trackerData.base_currency || baseCurrency;
    setPagination({
      total: expEnvelope.total ?? 0,
      pages: expEnvelope.pages ?? 0,
      page_size: expEnvelope.page_size ?? 25,
    });

    const allRows = filterCategory === 'All'
      ? buildRowsFromExpenses(items, serverCurrency, BASE_CATEGORIES)
      : items.map(e => ({
          id: e.id,
          category: e.category,
          projected: e.planned_amount !== undefined ? String(e.planned_amount) : '',
          actual: e.actual_amount !== undefined ? String(e.actual_amount) : '',
          builtin: BASE_CATEGORIES.includes(e.category),
          name: e.name || '',
          currency: e.currency || serverCurrency,
          note: e.note || '',
          tags: e.tags || [],
        }));

    setRows(allRows);
    const s = salary_actual ?? salary_planned;
    setSalary(s ? String(s) : '');
  }, [trackerData, filterCategory, baseCurrency]);

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
    { id: null, category: 'Other', projected: '', actual: '', builtin: false, name: '', currency: baseCurrency, note: '', tags: [] },
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
      currency: row.currency || baseCurrency,
      note: row.note || '',
      tags: row.tags || [],
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
      currency: draft.currency || baseCurrency,
      note: draft.note || '',
      tags: draft.tags || [],
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
            currency: draft.currency || baseCurrency,
            note: draft.note || null,
            tags: draft.tags && draft.tags.length > 0 ? draft.tags : null,
          },
        });
      } catch {
        setRows(rows);
        setEditingIndex(index);
        setEditDraft(draft);
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

    const previousRows = rows;
    setRows(prev => prev.filter((_, i) => i !== rowIndex));

    try {
      await deleteMutation.mutateAsync(expenseId);
    } catch {
      setRows(previousRows);
    }
  };

  const handleSave = async () => {
    await saveMutation.mutateAsync({ salary, rows });
  };

  const projectedTotal = rows.reduce((sum, r) => sum + (Number(r.projected) || 0), 0);
  const actualTotal = rows.reduce((sum, r) => sum + (Number(r.actual) || 0), 0);
  const totalDiff = actualTotal - projectedTotal;
  const totalOver = totalDiff > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-xl sm:text-2xl font-bold text-gray-800 dark:text-gray-100 flex items-center">
          <Calendar className="mr-2 text-blue-500" /> Monthly Tracker
        </h2>
        <div className="flex items-center gap-2">
          <input
            type="month"
            value={selectedMonth}
            onChange={(e) => { setSelectedMonth(e.target.value); setCurrentPage(1); setFilterCategory('All'); }}
            className="border rounded-lg px-3 py-2 text-[16px] text-gray-700 dark:text-gray-200 dark:bg-gray-800 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[44px]"
          />
          <ExportMenu month={selectedMonth} />
        </div>
      </div>

      {/* Cross-month search bar */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-4 space-y-3">
        <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide flex items-center gap-1.5">
          <Search size={13} /> Search across all months
        </p>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end sm:gap-3">
          <div className="flex-1 min-w-0 relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" aria-hidden="true" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search expense names…"
              aria-label="Search expense names"
              className="w-full pl-8 pr-3 py-2 border rounded-lg text-sm text-gray-700 dark:text-gray-200 dark:bg-gray-700 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 min-h-[40px]"
            />
          </div>
          <select
            value={searchCategory}
            onChange={(e) => { setSearchCategory(e.target.value); setSearchPage(1); }}
            aria-label="Filter search by category"
            className="border rounded-lg px-3 py-2 text-sm text-gray-700 dark:text-gray-200 dark:bg-gray-700 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 min-h-[40px] sm:w-40"
          >
            <option value="All">All categories</option>
            {BASE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <div className="flex items-center gap-2">
            <input
              type="month"
              value={searchFrom}
              onChange={(e) => { setSearchFrom(e.target.value); setSearchPage(1); }}
              aria-label="Search from month"
              className="border rounded-lg px-2 py-2 text-sm text-gray-700 dark:text-gray-200 dark:bg-gray-700 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 min-h-[40px]"
            />
            <span className="text-gray-400 text-sm" aria-hidden="true">–</span>
            <input
              type="month"
              value={searchTo}
              onChange={(e) => { setSearchTo(e.target.value); setSearchPage(1); }}
              aria-label="Search to month"
              className="border rounded-lg px-2 py-2 text-sm text-gray-700 dark:text-gray-200 dark:bg-gray-700 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 min-h-[40px]"
            />
          </div>
          {isSearchMode && (
            <button
              onClick={() => { setSearchQuery(''); setDebouncedQuery(''); setSearchCategory('All'); setSearchFrom(''); setSearchTo(''); setSearchPage(1); }}
              className="text-sm text-blue-600 hover:underline whitespace-nowrap min-h-[40px]"
            >
              Clear search
            </button>
          )}
        </div>

        {/* Search results */}
        {isSearchMode && (
          <div className="mt-2">
            {searchLoading ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 py-2">Searching…</p>
            ) : !searchData || searchData.total === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 py-2">No expenses found.</p>
            ) : (
              <>
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                  {searchData.total} result{searchData.total !== 1 ? 's' : ''}
                </p>
                <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-100 dark:bg-gray-700">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Month</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Name</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-600 dark:text-gray-300">Category</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-600 dark:text-gray-300">Planned</th>
                        <th className="px-3 py-2 text-right font-medium text-gray-600 dark:text-gray-300">Actual</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                      {searchData.items.map((item) => (
                        <tr key={item.id} className="bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-750">
                          <td className="px-3 py-2 text-gray-500 dark:text-gray-400 whitespace-nowrap">{item.month}</td>
                          <td className="px-3 py-2 text-gray-800 dark:text-gray-200">{item.name || <span className="italic text-gray-400">—</span>}</td>
                          <td className="px-3 py-2 text-gray-600 dark:text-gray-300">{item.category}</td>
                          <td className="px-3 py-2 text-right text-gray-600 dark:text-gray-300">{item.planned_amount.toFixed(2)}</td>
                          <td className="px-3 py-2 text-right font-medium text-gray-800 dark:text-gray-200">{item.actual_amount.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {searchData.pages > 1 && (
                  <div className="flex items-center justify-between mt-3">
                    <button
                      onClick={() => setSearchPage(p => Math.max(1, p - 1))}
                      disabled={searchPage <= 1}
                      className="px-3 py-1 text-sm rounded-lg border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      Previous
                    </button>
                    <span className="text-xs text-gray-500">Page {searchPage} of {searchData.pages}</span>
                    <button
                      onClick={() => setSearchPage(p => Math.min(searchData.pages, p + 1))}
                      disabled={searchPage >= searchData.pages}
                      className="px-3 py-1 text-sm rounded-lg border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
        <label htmlFor="tracker-filter-category" className="text-sm font-medium text-gray-700 dark:text-gray-300">Filter by category:</label>
        <select
          id="tracker-filter-category"
          value={filterCategory}
          onChange={(e) => { setFilterCategory(e.target.value); setCurrentPage(1); }}
          className="border rounded-lg px-3 py-2 text-sm text-gray-700 dark:text-gray-200 dark:bg-gray-800 dark:border-gray-600 focus:ring-2 focus:ring-blue-500 w-full sm:w-auto min-h-[44px]"
        >
          <option value="All">All categories</option>
          {BASE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        {filterCategory !== 'All' && (
          <button
            onClick={() => { setFilterCategory('All'); setCurrentPage(1); }}
            className="text-sm text-blue-600 hover:underline min-h-[44px] sm:min-h-0 text-left"
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

      {/* Spending pace warnings */}
      {paceData?.warnings?.length > 0 && (
        <div className="rounded-lg border border-amber-300 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-700 p-4 space-y-1.5" role="alert" aria-live="polite">
          <p className="text-sm font-semibold text-amber-800 dark:text-amber-300 flex items-center gap-1.5">
            <span aria-hidden="true">⚠️</span> Spending pace alert
          </p>
          <ul className="space-y-0.5">
            {paceData.warnings.map((w) => (
              <li key={w.category} className="text-sm text-amber-700 dark:text-amber-400">
                {w.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Salary input */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-3 gap-2">
        <label htmlFor="tracker-salary" className="text-gray-700 dark:text-gray-300 font-medium">Monthly Salary ({sym}):</label>
        <input
          id="tracker-salary"
          type="text"
          inputMode="decimal"
          pattern="[0-9]*[.]?[0-9]*"
          value={salary}
          onChange={(e) => setSalary(e.target.value.replace(/[^\d.]/g, ''))}
          className="px-3 py-2 border rounded-lg w-full sm:w-48 text-[16px] dark:bg-gray-800 dark:border-gray-600 dark:text-gray-200 min-h-[44px]"
          placeholder="e.g. 2500"
        />
      </div>

      {isLoading ? (
        <SkeletonTable rows={8} />
      ) : (
        <>
          {/* Mobile card layout (below sm) */}
          <div className="block sm:hidden space-y-3">
            {rows.map((row, i) => {
              const isEditing = editingIndex === i;
              const projectedNum = Number(isEditing ? editDraft.projected : row.projected) || 0;
              const actualNum = Number(isEditing ? editDraft.actual : row.actual) || 0;
              const diff = actualNum - projectedNum;
              const over = diff > 0;
              const hasValues = projectedNum !== 0 || actualNum !== 0;

              return (
                <div
                  key={`${row.id ?? 'new'}-${row.category}-${i}`}
                  className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 space-y-3"
                >
                  {/* Category + actions */}
                  <div className="flex items-center gap-2">
                    <div className="flex-1 min-w-0">
                      {isEditing ? (
                        <>
                          <select
                            value={editDraft.category}
                            onChange={(e) => setEditDraft(d => ({ ...d, category: e.target.value }))}
                            className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 min-h-[44px]"
                          >
                            {BASE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                          </select>
                          <CategorySuggestionChip
                            name={editDraft.name}
                            onAccept={(cat) => setEditDraft(d => ({ ...d, category: cat }))}
                          />
                        </>
                      ) : row.builtin ? (
                        <span className="font-semibold text-gray-800 dark:text-gray-200">{row.category}</span>
                      ) : (
                        <>
                          <select
                            value={row.category}
                            onChange={(e) => handleUpdate(i, 'category', e.target.value)}
                            className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 min-h-[44px]"
                          >
                            {BASE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                          </select>
                          <CategorySuggestionChip
                            name={row.name}
                            onAccept={(cat) => handleUpdate(i, 'category', cat)}
                          />
                        </>
                      )}
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {isEditing ? (
                        <>
                          <button
                            onClick={() => saveEdit(i)}
                            className="min-w-[44px] min-h-[44px] flex items-center justify-center text-green-600 hover:bg-green-50 dark:hover:bg-green-900/30 rounded-lg"
                            aria-label="Save changes"
                          >
                            <Check size={20} />
                          </button>
                          <button
                            onClick={cancelEdit}
                            className="min-w-[44px] min-h-[44px] flex items-center justify-center text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                            aria-label="Cancel edit"
                          >
                            <X size={20} />
                          </button>
                        </>
                      ) : (
                        <>
                          {row.id != null && (
                            <button
                              onClick={() => startEdit(i)}
                              className="min-w-[44px] min-h-[44px] flex items-center justify-center text-blue-500 hover:bg-blue-50 dark:hover:bg-blue-900/30 rounded-lg"
                              aria-label="Edit expense"
                            >
                              <Pencil size={18} />
                            </button>
                          )}
                          {row.id != null && (
                            <button
                              onClick={() => setHistoryExpense({ id: row.id, name: row.name || row.category })}
                              className="min-w-[44px] min-h-[44px] flex items-center justify-center text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                              aria-label="View change history"
                            >
                              <Clock size={18} />
                            </button>
                          )}
                          {(!row.builtin || row.id != null) && (
                            <button
                              onClick={() => requestDelete(i)}
                              className="min-w-[44px] min-h-[44px] flex items-center justify-center text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg"
                              aria-label="Delete expense"
                            >
                              <Trash2 size={18} />
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  {/* Name input */}
                  <input
                    type="text"
                    value={isEditing ? editDraft.name : (row.name || '')}
                    onChange={
                      isEditing
                        ? (e) => setEditDraft(d => ({ ...d, name: e.target.value }))
                        : (e) => handleUpdate(i, 'name', e.target.value)
                    }
                    className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 min-h-[44px]"
                    placeholder={row.builtin ? 'Name (optional)' : 'e.g. Gym, Gifts'}
                    disabled={!isEditing && row.id != null}
                    autoFocus={isEditing}
                  />

                  {/* Projected + Actual */}
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">Projected ({isEditing ? currencySymbol(editDraft.currency || baseCurrency) : currencySymbol(row.currency || baseCurrency)})</label>
                      <input
                        type="text"
                        inputMode="decimal"
                        value={isEditing ? editDraft.projected : row.projected}
                        onChange={
                          isEditing
                            ? (e) => setEditDraft(d => ({ ...d, projected: e.target.value.replace(/[^\d.]/g, '') }))
                            : (e) => handleUpdate(i, 'projected', e.target.value)
                        }
                        className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 min-h-[44px]"
                        placeholder={sym}
                        disabled={!isEditing && row.id != null}
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">Actual ({isEditing ? currencySymbol(editDraft.currency || baseCurrency) : currencySymbol(row.currency || baseCurrency)})</label>
                      <input
                        type="text"
                        inputMode="decimal"
                        value={isEditing ? editDraft.actual : row.actual}
                        onChange={
                          isEditing
                            ? (e) => setEditDraft(d => ({ ...d, actual: e.target.value.replace(/[^\d.]/g, '') }))
                            : (e) => handleUpdate(i, 'actual', e.target.value)
                        }
                        className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 min-h-[44px]"
                        placeholder={sym}
                      />
                    </div>
                  </div>

                  {/* Currency selector (mobile) */}
                  {(isEditing || row.id == null) && (
                    <div>
                      <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">Currency</label>
                      <select
                        value={isEditing ? (editDraft.currency || baseCurrency) : (row.currency || baseCurrency)}
                        onChange={
                          isEditing
                            ? (e) => setEditDraft(d => ({ ...d, currency: e.target.value }))
                            : (e) => handleUpdate(i, 'currency', e.target.value)
                        }
                        className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 min-h-[44px]"
                      >
                        {currencies.length > 0
                          ? currencies.map(c => <option key={c.code} value={c.code}>{c.symbol} {c.code}</option>)
                          : <option value={baseCurrency}>{baseCurrency}</option>
                        }
                      </select>
                    </div>
                  )}
                  {(!isEditing && row.id != null && row.currency && row.currency !== baseCurrency) && (
                    <div className="text-xs text-blue-600 dark:text-blue-400 font-medium">{row.currency}</div>
                  )}

                  {/* Note (mobile) */}
                  {isEditing && (
                    <div>
                      <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">Note (optional)</label>
                      <textarea
                        value={editDraft.note || ''}
                        onChange={(e) => setEditDraft(d => ({ ...d, note: e.target.value }))}
                        maxLength={500}
                        rows={2}
                        className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 resize-none"
                        placeholder="Add a note…"
                      />
                    </div>
                  )}
                  {!isEditing && row.note && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 italic truncate">{row.note}</div>
                  )}

                  {/* Tags (mobile) */}
                  {isEditing && (
                    <div>
                      <label className="text-xs text-gray-500 dark:text-gray-400 mb-1 block">Tags (up to 5, comma-separated)</label>
                      <input
                        type="text"
                        value={(editDraft.tags || []).join(', ')}
                        onChange={(e) => {
                          const parts = e.target.value.split(',').map(t => t.trimStart()).filter(Boolean);
                          setEditDraft(d => ({ ...d, tags: parts.slice(0, 5) }));
                        }}
                        className="w-full px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 min-h-[44px]"
                        placeholder="e.g. work, reimbursable"
                      />
                    </div>
                  )}
                  {!isEditing && row.tags && row.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {row.tags.map((t, ti) => (
                        <span key={ti} className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded-full">{t}</span>
                      ))}
                    </div>
                  )}

                  {/* Difference + Status */}
                  {hasValues && (
                    <div className="flex justify-between items-center text-sm pt-2 border-t border-gray-100 dark:border-gray-700">
                      <span className={`font-semibold ${over ? 'text-red-600' : 'text-green-600'}`}>
                        {diff === 0 ? `${currencySymbol(row.currency || baseCurrency)}0` : `${over ? '+' : ''}${currencySymbol(row.currency || baseCurrency)}${diff.toFixed(2)}`}
                      </span>
                      <span className={`flex items-center ${over ? 'text-red-600' : 'text-green-600'}`}>
                        {over
                          ? <><XCircle size={15} className="mr-1" /> Over</>
                          : <><CheckCircle size={15} className="mr-1" /> Under</>
                        }
                      </span>
                    </div>
                  )}
                </div>
              );
            })}

            {/* Mobile totals */}
            <div className="bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
              <div className="grid grid-cols-3 gap-2 text-sm font-semibold text-center">
                <div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Projected</div>
                  <div>{sym}{projectedTotal.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Actual</div>
                  <div>{sym}{actualTotal.toFixed(2)}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Difference</div>
                  <div className={totalOver ? 'text-red-700' : 'text-green-700'}>
                    {totalDiff === 0 ? `${sym}0` : `${totalOver ? '+' : ''}${sym}${totalDiff.toFixed(2)}`}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Desktop table layout (sm and above) */}
          <div className="hidden sm:block overflow-x-auto bg-white dark:bg-gray-800 rounded-xl shadow-md border dark:border-gray-700">
            <table className="min-w-full text-left border-collapse">
              <thead className="bg-gray-100 dark:bg-gray-700">
                <tr className="text-sm">
                  <th className="p-3 dark:text-gray-200">Category</th>
                  <th className="p-3 dark:text-gray-200">Name (optional)</th>
                  <th className="p-3 dark:text-gray-200">Projected</th>
                  <th className="p-3 dark:text-gray-200">Actual</th>
                  <th className="p-3 dark:text-gray-200">Currency</th>
                  <th className="p-3 dark:text-gray-200">Note / Tags</th>
                  <th className="p-3 dark:text-gray-200">Difference</th>
                  <th className="p-3 dark:text-gray-200">Status</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody className="text-sm">
                {rows.map((row, i) => {
                  const isEditing = editingIndex === i;
                  const projectedNum = Number(isEditing ? editDraft.projected : row.projected) || 0;
                  const actualNum = Number(isEditing ? editDraft.actual : row.actual) || 0;
                  const diff = actualNum - projectedNum;
                  const over = diff > 0;

                  return (
                    <tr key={`${row.id ?? 'new'}-${row.category}-${i}`} className="border-t dark:border-gray-700 dark:text-gray-200">
                      <td className="p-3 font-medium whitespace-nowrap">
                        {isEditing ? (
                          <>
                            <select
                              value={editDraft.category}
                              onChange={(e) => setEditDraft(d => ({ ...d, category: e.target.value }))}
                              className="px-2 py-1 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                            >
                              {BASE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                            <CategorySuggestionChip
                              name={editDraft.name}
                              onAccept={(cat) => setEditDraft(d => ({ ...d, category: cat }))}
                            />
                          </>
                        ) : row.builtin && !isEditing ? (
                          row.category
                        ) : (
                          <>
                            <select
                              value={row.category}
                              onChange={(e) => handleUpdate(i, 'category', e.target.value)}
                              className="px-2 py-1 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                            >
                              {BASE_CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                            <CategorySuggestionChip
                              name={row.name}
                              onAccept={(cat) => handleUpdate(i, 'category', cat)}
                            />
                          </>
                        )}
                      </td>

                      <td className="p-3">
                        {isEditing ? (
                          <input
                            type="text"
                            value={editDraft.name}
                            onChange={(e) => setEditDraft(d => ({ ...d, name: e.target.value }))}
                            className="w-40 sm:w-44 px-2 py-1 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                            placeholder="(optional)"
                            autoFocus
                          />
                        ) : (
                          <input
                            type="text"
                            value={row.name || ''}
                            onChange={(e) => handleUpdate(i, 'name', e.target.value)}
                            className="w-40 sm:w-44 px-2 py-1 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
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
                            className="w-24 sm:w-28 px-2 py-1 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                            placeholder={currencySymbol(editDraft.currency || baseCurrency)}
                          />
                        ) : (
                          <input
                            type="text"
                            inputMode="decimal"
                            value={row.projected}
                            onChange={(e) => handleUpdate(i, 'projected', e.target.value)}
                            className="w-24 sm:w-28 px-2 py-1 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                            placeholder={currencySymbol(row.currency || baseCurrency)}
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
                            className="w-24 sm:w-28 px-2 py-1 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                            placeholder={currencySymbol(editDraft.currency || baseCurrency)}
                          />
                        ) : (
                          <input
                            type="text"
                            inputMode="decimal"
                            value={row.actual}
                            onChange={(e) => handleUpdate(i, 'actual', e.target.value)}
                            className="w-24 sm:w-28 px-2 py-1 border rounded-lg dark:bg-gray-700 dark:border-gray-600"
                            placeholder={currencySymbol(row.currency || baseCurrency)}
                            disabled={row.id != null}
                          />
                        )}
                      </td>

                      {/* Currency column */}
                      <td className="p-3">
                        {isEditing || row.id == null ? (
                          <select
                            value={isEditing ? (editDraft.currency || baseCurrency) : (row.currency || baseCurrency)}
                            onChange={
                              isEditing
                                ? (e) => setEditDraft(d => ({ ...d, currency: e.target.value }))
                                : (e) => handleUpdate(i, 'currency', e.target.value)
                            }
                            className="px-2 py-1 border rounded-lg text-xs dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                          >
                            {currencies.length > 0
                              ? currencies.map(c => <option key={c.code} value={c.code}>{c.code}</option>)
                              : <option value={baseCurrency}>{baseCurrency}</option>
                            }
                          </select>
                        ) : (
                          <span className={`text-xs font-medium ${(row.currency || baseCurrency) !== baseCurrency ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500 dark:text-gray-400'}`}>
                            {row.currency || baseCurrency}
                          </span>
                        )}
                      </td>

                      {/* Note / Tags column (desktop) */}
                      <td className="p-3 max-w-[200px]">
                        {isEditing ? (
                          <div className="flex flex-col gap-1">
                            <textarea
                              value={editDraft.note || ''}
                              onChange={(e) => setEditDraft(d => ({ ...d, note: e.target.value }))}
                              maxLength={500}
                              rows={2}
                              className="w-full px-2 py-1 border rounded-lg text-xs dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200 resize-none"
                              placeholder="Note…"
                            />
                            <input
                              type="text"
                              value={(editDraft.tags || []).join(', ')}
                              onChange={(e) => {
                                const parts = e.target.value.split(',').map(t => t.trimStart()).filter(Boolean);
                                setEditDraft(d => ({ ...d, tags: parts.slice(0, 5) }));
                              }}
                              className="w-full px-2 py-1 border rounded-lg text-xs dark:bg-gray-700 dark:border-gray-600 dark:text-gray-200"
                              placeholder="Tags (comma-separated)"
                            />
                          </div>
                        ) : (
                          <div className="flex flex-col gap-1">
                            {row.note && <span className="text-xs text-gray-500 dark:text-gray-400 italic truncate" title={row.note}>{row.note}</span>}
                            {row.tags && row.tags.length > 0 && (
                              <div className="flex flex-wrap gap-1">
                                {row.tags.map((t, ti) => (
                                  <span key={ti} className="text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded-full">{t}</span>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </td>

                      <td className="p-3 whitespace-nowrap">
                        <span className={over ? 'text-red-600 font-semibold' : 'text-green-600 font-semibold'}>
                          {diff === 0 ? `${currencySymbol(row.currency || baseCurrency)}0` : `${over ? '+' : ''}${currencySymbol(row.currency || baseCurrency)}${diff.toFixed(2)}`}
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
                              {row.id != null && (
                                <button
                                  onClick={() => setHistoryExpense({ id: row.id, name: row.name || row.category })}
                                  className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1.5 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                                  title="View change history"
                                >
                                  <Clock size={15} />
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

              <tfoot className="text-sm">
                <tr className="border-t bg-gray-50 dark:bg-gray-700 font-semibold dark:text-gray-200">
                  <td className="p-3">Totals</td>
                  <td className="p-3"></td>
                  <td className="p-3">{sym}{projectedTotal.toFixed(2)}</td>
                  <td className="p-3">{sym}{actualTotal.toFixed(2)}</td>
                  <td className="p-3"></td>
                  <td className="p-3">
                    <span className={totalOver ? 'text-red-700' : 'text-green-700'}>
                      {totalDiff === 0 ? `${sym}0` : `${totalOver ? '+' : ''}${sym}${totalDiff.toFixed(2)}`}
                    </span>
                  </td>
                  <td className="p-3">{totalOver ? 'Over' : 'Under'}</td>
                  <td className="p-3"></td>
                </tr>
              </tfoot>
            </table>
          </div>
        </>
      )}

      {/* Pagination controls */}
      {pagination.pages > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage <= 1}
            className="px-4 py-2 border rounded-lg disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700 min-h-[44px]"
          >
            &larr; Prev
          </button>
          <span className="text-gray-600 dark:text-gray-400">
            Page {currentPage} of {pagination.pages}
          </span>
          <button
            onClick={() => setCurrentPage(p => Math.min(pagination.pages, p + 1))}
            disabled={currentPage >= pagination.pages}
            className="px-4 py-2 border rounded-lg disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-gray-700 min-h-[44px]"
          >
            Next &rarr;
          </button>
        </div>
      )}

      {/* Add row + Save */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-xs sm:text-sm text-gray-500 dark:text-gray-400">
          Edit saved rows with the pencil icon, or add new rows below.
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            onClick={addRow}
            className="inline-flex items-center bg-white dark:bg-gray-800 border dark:border-gray-600 px-4 py-2.5 rounded-lg shadow-sm hover:bg-gray-50 dark:hover:bg-gray-700 text-sm min-h-[44px]"
          >
            <PlusCircle size={16} className="mr-2" />
            Add expense row
          </button>

          <button
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 sm:px-6 py-3 rounded-lg shadow-md disabled:opacity-60 text-sm sm:text-base min-h-[44px]"
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

      {historyExpense && (
        <AuditDrawer
          expenseId={historyExpense.id}
          expenseName={historyExpense.name}
          onClose={() => setHistoryExpense(null)}
        />
      )}

      {lastSaved && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-md border dark:border-gray-700 p-5 sm:p-6">
          <h3 className="text-base sm:text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3 sm:mb-4">
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
                  <Tooltip wrapperStyle={{ zIndex: 10 }} formatter={(v, n) => [`${sym}${Number(v).toLocaleString()}`, n]} />
                  <Legend verticalAlign="bottom" align="center" />
                </PieChart>
              </ResponsiveContainer>
            </div>

            <div className="space-y-2 sm:space-y-3 text-sm sm:text-base">
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Salary</span>
                <span className="font-semibold">{sym}{lastSaved.salary.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Spent</span>
                <span className="font-semibold text-red-600">{sym}{lastSaved.spent.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600 dark:text-gray-400">Saved</span>
                <span className="font-semibold text-green-600">{sym}{lastSaved.saved.toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MonthlyTracker;
