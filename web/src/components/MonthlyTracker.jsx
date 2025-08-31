import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Calendar, CheckCircle, XCircle, PlusCircle, Trash2 } from 'lucide-react';

const API_BASE_URL = import.meta?.env?.VITE_API_URL || 'https://son-of-mervan-production.up.railway.app';
const BASE_CATEGORIES = ['Housing', 'Transportation', 'Food', 'Utilities', 'Insurance', 'Healthcare', 'Entertainment', 'Other'];

const MonthlyTracker = ({ token, onSaved }) => {
  const [selectedMonth, setSelectedMonth] = useState('2025-08');
  const [saving, setSaving] = useState(false);
  const [salary, setSalary] = useState('');

  // rows: { category, projected, actual, builtin: boolean, name?: string }
  const [rows, setRows] = useState(
    BASE_CATEGORIES.map(cat => ({ category: cat, projected: '', actual: '', builtin: true, name: '' }))
  );

  // Load month data (rolls up by category)
  useEffect(() => {
    const load = async () => {
      try {
        const res = await axios.get(`${API_BASE_URL}/monthly-tracker/${selectedMonth}`, {
          headers: { Authorization: `Bearer ${token || localStorage.getItem('authToken')}` },
          params: { _r: Date.now() },
        });

        const { salary_planned, salary_actual, rows: serverRows = [] } = res.data || {};
        const byCat = Object.fromEntries(serverRows.map(r => [r.category, r]));

        // Fill built-ins from server totals
        const builtins = BASE_CATEGORIES.map(cat => ({
          category: cat,
          projected: byCat[cat]?.projected !== undefined ? String(byCat[cat].projected) : '',
          actual:    byCat[cat]?.actual    !== undefined ? String(byCat[cat].actual)    : '',
          builtin: true,
          name: '',
        }));

        // We don’t have per-line items from the server (only totals), so extra rows can’t be restored verbatim.
        // If you want that, we can change the backend to return line items instead of category sums.

        setRows(builtins);
        const s = (salary_actual ?? salary_planned);
        setSalary(s ? String(s) : '');
      } catch {
        // leave defaults if nothing yet
      }
    };
    load();
  }, [selectedMonth, token]);

  const handleUpdate = (index, field, value) => {
    const newRows = [...rows];
    const cleaned = field === 'category' || field === 'name'
      ? value
      : value.replace(/[^\d.]/g, '');
    newRows[index][field] = cleaned;
    setRows(newRows);
  };

  const addRow = () => {
    setRows(prev => [
      ...prev,
      { category: 'Other', projected: '', actual: '', builtin: false, name: '' },
    ]);
  };

  const removeRow = (index) => {
    setRows(prev => prev.filter((_, i) => i !== index));
  };

  // Totals (live)
  const projectedTotal = rows.reduce((sum, r) => sum + (Number(r.projected) || 0), 0);
  const actualTotal = rows.reduce((sum, r) => sum + (Number(r.actual) || 0), 0);
  const totalDiff = actualTotal - projectedTotal;
  const totalOver = totalDiff > 0;

  const handleSave = async () => {
    try {
      setSaving(true);

      // 1) Save PLANNED (projected)
      const plannedExpenses = rows
        .filter(r => r.projected !== '' && !isNaN(Number(r.projected)))
        .map(r => ({
          name: r.name?.trim() ? r.name.trim() : r.category,   // name optional for extra rows
          amount: Number(r.projected) || 0,
          category: r.category,
        }));

      const plannedPayload = {
        month: selectedMonth,
        monthly_salary: salary !== '' ? Number(salary) : 0,
        expenses: plannedExpenses,
      };

      await axios.post(`${API_BASE_URL}/calculate-budget`, plannedPayload, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token || localStorage.getItem('authToken')}`,
        },
      });

      // 2) Save ACTUAL
      const actualExpenses = rows
        .filter(r => r.actual !== '' && !isNaN(Number(r.actual)))
        .map(r => ({
          name: r.name?.trim() ? r.name.trim() : r.category,
          amount: Number(r.actual) || 0,
          category: r.category,
        }));

      const actualPayload = {
        salary: salary !== '' ? Number(salary) : null,
        expenses: actualExpenses,
      };

      await axios.post(`${API_BASE_URL}/monthly-tracker/${selectedMonth}`, actualPayload, {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token || localStorage.getItem('authToken')}`,
        },
      });

      if (typeof onSaved === 'function') onSaved();
      alert('Monthly data saved successfully!');
      // We do NOT clear state—values stay for editing.
    } catch (err) {
      console.error('Error saving monthly data:', err);
      alert('Failed to save monthly data.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-800 flex items-center">
          <Calendar className="mr-2 text-blue-500" /> Monthly Tracker
        </h2>
        <input
          type="month"
          value={selectedMonth}
          onChange={(e) => setSelectedMonth(e.target.value)}
          className="border rounded-lg px-3 py-2 text-gray-700 focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Salary input */}
      <div className="flex items-center space-x-3">
        <label className="text-gray-700 font-medium">Monthly Salary (£):</label>
        <input
          type="text"
          inputMode="decimal"
          pattern="[0-9]*[.]?[0-9]*"
          value={salary}
          onChange={(e) => setSalary(e.target.value.replace(/[^\d.]/g, ''))}
          className="px-3 py-2 border rounded-lg w-40"
          placeholder="e.g. 2500"
        />
      </div>

      {/* Table */}
      <div className="overflow-x-auto bg-white rounded-xl shadow-md border">
        <table className="w-full text-left border-collapse">
          <thead className="bg-gray-100">
            <tr>
              <th className="p-3">Category</th>
              <th className="p-3">Name (optional)</th>
              <th className="p-3">Projected (£)</th>
              <th className="p-3">Actual (£)</th>
              <th className="p-3">Difference</th>
              <th className="p-3">Status</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const projectedNum = Number(row.projected) || 0;
              const actualNum = Number(row.actual) || 0;
              const diff = actualNum - projectedNum;
              const over = diff > 0;

              return (
                <tr key={`${row.builtin ? 'base' : 'extra'}-${row.category}-${i}`} className="border-t">
                  <td className="p-3 font-medium">
                    {row.builtin ? (
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
                    <input
                      type="text"
                      value={row.name || ''}
                      onChange={(e) => handleUpdate(i, 'name', e.target.value)}
                      className="w-44 px-2 py-1 border rounded-lg"
                      placeholder={row.builtin ? '(optional)' : 'e.g. Gym, Gifts'}
                    />
                  </td>

                  <td className="p-3">
                    <input
                      type="text"
                      inputMode="decimal"
                      value={row.projected}
                      onChange={(e) => handleUpdate(i, 'projected', e.target.value)}
                      className="w-28 px-2 py-1 border rounded-lg"
                      placeholder="£"
                    />
                  </td>

                  <td className="p-3">
                    <input
                      type="text"
                      inputMode="decimal"
                      value={row.actual}
                      onChange={(e) => handleUpdate(i, 'actual', e.target.value)}
                      className="w-28 px-2 py-1 border rounded-lg"
                      placeholder="£"
                    />
                  </td>

                  <td className="p-3">
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
                    {!row.builtin && (
                      <button
                        onClick={() => removeRow(i)}
                        className="text-red-600 hover:text-red-800 p-2 hover:bg-red-50 rounded-lg"
                        title="Remove row"
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>

          {/* Totals row */}
          <tfoot>
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

      {/* Add row + Save */}
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-500">
          Extra rows are rolled up by category after reload.
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={addRow}
            className="inline-flex items-center bg-white border px-4 py-2 rounded-lg shadow-sm hover:bg-gray-50"
          >
            <PlusCircle size={16} className="mr-2" />
            Add expense row
          </button>

          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded-lg shadow-md disabled:opacity-60"
          >
            {saving ? 'Saving...' : 'Save Monthly Data'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default MonthlyTracker;
