import React, { useState } from 'react';
import { PlusCircle, Calculator, Trash2, TrendingUp, DollarSign, PieChart } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';

const API_BASE_URL = 'https://son-of-mervan-production.up.railway.app';

const SonOfMervan = ({ token, onSaved }) => {
  const [salary, setSalary] = useState('');
  const [expenses, setExpenses] = useState([{ name: '', amount: '', category: 'Housing' }]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const addExpense = () => {
    setExpenses([...expenses, { name: '', amount: '', category: 'Housing' }]);
  };

  const removeExpense = (index) => {
    if (expenses.length > 1) {
      const newExpenses = expenses.filter((_, i) => i !== index);
      setExpenses(newExpenses);
    }
  };

  const updateExpense = (index, field, value) => {
    const newExpenses = [...expenses];
    newExpenses[index] = { ...newExpenses[index], [field]: value };
    setExpenses(newExpenses);
  };

  const calculateBudget = async () => {
    setLoading(true);

    // Always use current month (YYYY-MM) for “Current Budget”
    const currentMonth = new Date().toISOString().slice(0, 7);

    const budgetData = {
      month: currentMonth,
      monthly_salary: parseFloat(salary) || 0,
      expenses: expenses
        .filter(exp => exp.name && exp.amount !== '')
        .map(exp => ({
          name: exp.name,
          amount: parseFloat(exp.amount) || 0,
          category: exp.category
        }))
    };

    try {
      const response = await fetch(`${API_BASE_URL}/calculate-budget?commit=false`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(budgetData),
      });

      if (response.ok) {
        const data = await response.json();
        setResults(data);
        if (typeof onSaved === 'function') onSaved();
      } else if (response.status === 401) {
        alert('Session expired. Please login again.');
        localStorage.removeItem('authToken');
        window.location.reload();
      } else {
        console.error('Failed to calculate budget');
        alert('Failed to calculate budget. Please try again.');
      }
    } catch (error) {
      console.error('Error:', error);
      alert('Network error. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  // Generate savings projection data
  const generateSavingsData = () => {
    if (!results || results.remaining_budget <= 0) return [];
    const monthlySavings = results.remaining_budget;
    const data = [];
    for (let month = 0; month <= 24; month++) {
      data.push({
        month,
        savings: monthlySavings * month,
        label:
          month === 0 ? 'Now' :
          month === 6 ? '6 Months' :
          month === 12 ? '1 Year' :
          month === 24 ? '2 Years' : `${month}m`
      });
    }
    return data;
  };

  // Generate category data for bar chart
  const generateCategoryData = () => {
    if (!results) return [];
    return Object.entries(results.expenses_by_category).map(([category, amount]) => ({
      category,
      amount,
      percentage: ((amount / results.total_expenses) * 100).toFixed(1)
    }));
  };

  const categories = ['Housing', 'Transportation', 'Food', 'Utilities', 'Insurance', 'Healthcare', 'Entertainment', 'Other'];
  const savingsData = generateSavingsData();
  const categoryData = generateCategoryData();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 p-4">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center py-6">
          <h1 className="text-4xl font-bold text-gray-800 mb-2">Son Of Mervan</h1>
          <p className="text-gray-600">There are two sides to every dollar</p>
        </div>

        {/* Input Section */}
        <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
          <div className="flex items-center mb-6">
            <DollarSign className="text-blue-500 mr-3" size={24} />
            <h2 className="text-2xl font-semibold text-gray-800">Financial Information</h2>
          </div>

          <div className="grid md:grid-cols-2 gap-8 items-start">
            {/* Monthly Salary */}
            <div className="space-y-4">
              {/* Header row with fixed height */}
              <div className="flex items-center justify-between h-10">
                <label className="block text-sm font-semibold text-gray-700">
                  Monthly Salary (£)
                </label>
                {/* Spacer to match button height on the right column */}
                <div className="w-[120px] h-9" />
              </div>

              <div className="flex items-center bg-gray-50 p-3 rounded-xl">
                <input
                  type="number"
                  value={salary}
                  onChange={(e) => setSalary(e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
                  placeholder="Enter your monthly salary"
                />
              </div>
            </div>

            {/* Expenses */}
            <div className="space-y-4">
              {/* Header row with the same fixed height */}
              <div className="flex items-center justify-between h-10">
                <label className="block text-sm font-semibold text-gray-700">
                  Monthly Expenses
                </label>
                <button
                  onClick={addExpense}
                  className="h-9 inline-flex items-center justify-center text-blue-600 hover:text-blue-800 font-semibold px-3 rounded-lg hover:bg-blue-50 transition-all"
                >
                  <PlusCircle size={18} className="mr-2" />
                  Add Expense
                </button>
              </div>

              <div className="max-h-64 overflow-y-auto space-y-3">
                {expenses.map((expense, index) => (
                  <div key={index} className="flex gap-3 items-center bg-gray-50 p-3 rounded-xl">
                    <input
                      type="text"
                      value={expense.name}
                      onChange={(e) => updateExpense(index, 'name', e.target.value)}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
                      placeholder="Expense name"
                    />
                    <input
                      type="number"
                      value={expense.amount}
                      onChange={(e) => updateExpense(index, 'amount', e.target.value)}
                      className="w-24 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
                      placeholder="£"
                    />
                    <select
                      value={expense.category}
                      onChange={(e) => updateExpense(index, 'category', e.target.value)}
                      className="w-32 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
                    >
                      {categories.map((category) => (
                        <option key={category} value={category}>{category}</option>
                      ))}
                    </select>
                    {expenses.length > 1 && (
                      <button
                        onClick={() => removeExpense(index)}
                        className="text-red-500 hover:text-red-700 p-2 hover:bg-red-50 rounded-lg transition-all"
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Calculate Button */}
          <div className="mt-8 text-center">
            <button
              onClick={calculateBudget}
              disabled={loading}
              className="bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-bold py-4 px-8 rounded-xl transition-all transform hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none shadow-lg"
            >
              {loading ? (
                <div className="flex items-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-3"></div>
                  Calculating...
                </div>
              ) : (
                <div className="flex items-center">
                  <Calculator size={20} className="mr-3" />
                  Calculate Budget
                </div>
              )}
            </button>
          </div>
        </div>

        {/* Results Section */}
        {results && (
          <div className="space-y-6">
            {/* Overview Cards */}
            <div className="grid md:grid-cols-3 gap-6">
              <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white p-6 rounded-2xl shadow-xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-blue-100 font-medium">Monthly Salary</span>
                  <DollarSign size={24} className="text-blue-200" />
                </div>
                <div className="text-3xl font-bold">£{results.monthly_salary.toLocaleString()}</div>
              </div>
              
              <div className="bg-gradient-to-br from-red-500 to-red-600 text-white p-6 rounded-2xl shadow-xl">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-red-100 font-medium">Total Expenses</span>
                  <PieChart size={24} className="text-red-200" />
                </div>
                <div className="text-3xl font-bold">£{results.total_expenses.toLocaleString()}</div>
              </div>
              
              <div className={`bg-gradient-to-br ${results.remaining_budget >= 0 ? 'from-green-500 to-green-600' : 'from-red-500 to-red-600'} text-white p-6 rounded-2xl shadow-xl`}>
                <div className="flex items-center justify-between mb-2">
                  <span className={`${results.remaining_budget >= 0 ? 'text-green-100' : 'text-red-100'} font-medium`}>
                    {results.remaining_budget >= 0 ? 'Monthly Savings' : 'Budget Deficit'}
                  </span>
                  <TrendingUp size={24} className={`${results.remaining_budget >= 0 ? 'text-green-200' : 'text-red-200'}`} />
                </div>
                <div className="text-3xl font-bold">£{Math.abs(results.remaining_budget).toLocaleString()}</div>
              </div>
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
              {/* Savings Projection Graph */}
              {results.remaining_budget > 0 && (
                <div className="bg-white p-6 rounded-2xl shadow-xl border border-gray-100">
                  <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
                    <TrendingUp className="mr-3 text-green-500" size={24} />
                    Savings Projection
                  </h3>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={generateSavingsData()}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="month" stroke="#666" tick={{ fontSize: 12 }} />
                        <YAxis stroke="#666" tick={{ fontSize: 12 }} tickFormatter={(v) => `£${v.toLocaleString()}`} />
                        <Tooltip formatter={(v) => [`£${v.toLocaleString()}`, 'Total Savings']} labelFormatter={(m) => `Month ${m}`} />
                        <Line type="monotone" dataKey="savings" stroke="#10b981" strokeWidth={3} dot={{ r: 6 }} activeDot={{ r: 8 }} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Category Breakdown */}
              <div className="bg-white p-6 rounded-2xl shadow-xl border border-gray-100">
                <h3 className="text-xl font-semibold text-gray-800 mb-4 flex items-center">
                  <PieChart className="mr-3 text-blue-500" size={24} />
                  Expense Breakdown
                </h3>
                
                {generateCategoryData().length > 0 && (
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={generateCategoryData()}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="category" stroke="#666" tick={{ fontSize: 12 }} angle={-45} textAnchor="end" height={80} />
                        <YAxis stroke="#666" tick={{ fontSize: 12 }} tickFormatter={(v) => `£${v.toLocaleString()}`} />
                        <Tooltip formatter={(v) => [`£${v.toLocaleString()}`, 'Amount']} />
                        <Bar dataKey="amount" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {results && (
                  <div className="mt-4 space-y-2">
                    {Object.entries(results.expenses_by_category).map(([category, amount]) => (
                      <div key={category} className="flex justify-between items-center py-2 px-3 bg-gray-50 rounded-lg">
                        <span className="font-medium text-gray-700">{category}</span>
                        <span className="font-bold text-gray-900">£{amount.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Recommendations */}
            {results?.recommendations?.length > 0 && (
              <div className="bg-gradient-to-r from-yellow-50 to-orange-50 border border-yellow-200 p-6 rounded-2xl">
                <h3 className="text-xl font-semibold text-yellow-800 mb-4">💡 Recommendations</h3>
                <div className="grid md:grid-cols-2 gap-4">
                  {results.recommendations.map((recommendation, index) => (
                    <div key={index} className="flex items-start bg-white p-4 rounded-xl shadow-sm">
                      <div className="w-2 h-2 bg-yellow-500 rounded-full mt-2 mr-3 flex-shrink-0"></div>
                      <span className="text-gray-700">{recommendation}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default SonOfMervan;
