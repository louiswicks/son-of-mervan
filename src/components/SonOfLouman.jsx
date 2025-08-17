// src/components/SonOfMervan.js
import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { DollarSign, TrendingUp, Calculator, PlusCircle, Trash2, Wallet, Target } from 'lucide-react';

const SonOfMervan = () => {
  const [salary, setSalary] = useState('');
  const [expenses, setExpenses] = useState([
    { name: 'Rent', amount: '', category: 'rent' },
    { name: 'Utilities', amount: '', category: 'utilities' }
  ]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const expenseCategories = [
    'rent', 'utilities', 'groceries', 'transportation', 'insurance',
    'entertainment', 'dining_out', 'healthcare', 'subscriptions',
    'clothing', 'savings_goals', 'miscellaneous'
  ];

  const addExpense = () => {
    setExpenses([...expenses, { name: '', amount: '', category: 'miscellaneous' }]);
  };

  const removeExpense = (index) => {
    setExpenses(expenses.filter((_, i) => i !== index));
  };

  const updateExpense = (index, field, value) => {
    const updatedExpenses = expenses.map((expense, i) => 
      i === index ? { ...expense, [field]: value } : expense
    );
    setExpenses(updatedExpenses);
  };

  const calculateBudget = async () => {
    setLoading(true);
    
    const budgetData = {
      monthly_salary: parseFloat(salary) || 0,
      expenses: expenses
        .filter(exp => exp.name && exp.amount)
        .map(exp => ({
          name: exp.name,
          amount: parseFloat(exp.amount) || 0,
          category: exp.category
        }))
    };

    try {
      const response = await fetch('http://localhost:8000/calculate-budget', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(budgetData),
      });

      if (response.ok) {
        const data = await response.json();
        setResults(data);
      } else {
        console.error('Failed to calculate budget');
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-GB', {
      style: 'currency',
      currency: 'GBP'
    }).format(amount);
  };

  const getSavingsColor = (savings) => {
    if (savings > 0) return 'text-emerald-700';
    if (savings < 0) return 'text-rose-700';
    return 'text-amber-700';
  };

  const getSavingsBackground = (savings) => {
    if (savings > 0) return 'bg-emerald-50 border-emerald-200';
    if (savings < 0) return 'bg-rose-50 border-rose-200';
    return 'bg-amber-50 border-amber-200';
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-slate-900 rounded-2xl mb-4">
            <Wallet className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-5xl font-bold text-slate-900 mb-3">Son of Mervan</h1>
          <p className="text-xl text-slate-600 max-w-2xl mx-auto">
            Smart budgeting made simple. Track your expenses and visualize your financial future.
          </p>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
          {/* Input Section */}
          <div className="xl:col-span-1">
            <div className="bg-white border border-gray-200 rounded-2xl p-8 shadow-sm">
              <div className="flex items-center mb-8">
                <div className="bg-blue-100 p-2 rounded-lg mr-3">
                  <Calculator className="h-5 w-5 text-blue-600" />
                </div>
                <h2 className="text-2xl font-semibold text-slate-900">Budget Input</h2>
              </div>

              {/* Monthly Salary Input */}
              <div className="mb-8">
                <label className="block text-sm font-medium text-slate-700 mb-3">
                  Monthly Income
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <span className="text-slate-500 text-lg">£</span>
                  </div>
                  <input
                    type="number"
                    value={salary}
                    onChange={(e) => setSalary(e.target.value)}
                    placeholder="0"
                    className="w-full pl-8 pr-4 py-4 text-lg border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                  />
                </div>
              </div>

              {/* Expenses */}
              <div className="mb-8">
                <div className="flex justify-between items-center mb-4">
                  <label className="text-sm font-medium text-slate-700">
                    Monthly Expenses
                  </label>
                  <button
                    onClick={addExpense}
                    className="flex items-center text-blue-600 hover:text-blue-700 text-sm font-medium transition-colors"
                  >
                    <PlusCircle className="h-4 w-4 mr-1" />
                    Add
                  </button>
                </div>
                
                <div className="space-y-4">
                  {expenses.map((expense, index) => (
                    <div key={index} className="p-4 border border-gray-200 rounded-xl">
                      <div className="flex gap-3 mb-3">
                        <input
                          type="text"
                          placeholder="Expense name"
                          value={expense.name}
                          onChange={(e) => updateExpense(index, 'name', e.target.value)}
                          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                        />
                        <button
                          onClick={() => removeExpense(index)}
                          className="p-2 text-rose-600 hover:text-rose-700 hover:bg-rose-50 rounded-lg transition-colors"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                      <div className="flex gap-3">
                        <div className="relative flex-1">
                          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <span className="text-slate-500">£</span>
                          </div>
                          <input
                            type="number"
                            placeholder="0"
                            value={expense.amount}
                            onChange={(e) => updateExpense(index, 'amount', e.target.value)}
                            className="w-full pl-7 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                          />
                        </div>
                        <select
                          value={expense.category}
                          onChange={(e) => updateExpense(index, 'category', e.target.value)}
                          className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors text-sm"
                        >
                          {expenseCategories.map(cat => (
                            <option key={cat} value={cat}>
                              {cat.replace('_', ' ')}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <button
                onClick={calculateBudget}
                disabled={loading}
                className="w-full bg-slate-900 text-white py-4 px-6 rounded-xl hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-lg transition-colors"
              >
                {loading ? 'Calculating...' : 'Calculate Budget'}
              </button>
            </div>
          </div>

          {/* Results Section */}
          {results && (
            <div className="xl:col-span-2">
              <div className="bg-white border border-gray-200 rounded-2xl p-8 shadow-sm">
                <div className="flex items-center mb-8">
                  <div className="bg-emerald-100 p-2 rounded-lg mr-3">
                    <TrendingUp className="h-5 w-5 text-emerald-600" />
                  </div>
                  <h2 className="text-2xl font-semibold text-slate-900">Financial Overview</h2>
                </div>

                {/* Summary Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                  <div className="text-center p-6 bg-blue-50 border border-blue-100 rounded-xl">
                    <div className="text-sm font-medium text-slate-600 mb-2">Monthly Income</div>
                    <div className="text-3xl font-bold text-blue-700">
                      {formatCurrency(results.monthly_salary)}
                    </div>
                  </div>
                  <div className="text-center p-6 bg-rose-50 border border-rose-100 rounded-xl">
                    <div className="text-sm font-medium text-slate-600 mb-2">Total Expenses</div>
                    <div className="text-3xl font-bold text-rose-700">
                      {formatCurrency(results.total_expenses)}
                    </div>
                  </div>
                  <div className={`text-center p-6 rounded-xl border ${getSavingsBackground(results.monthly_savings)}`}>
                    <div className="text-sm font-medium text-slate-600 mb-2">Monthly Savings</div>
                    <div className={`text-3xl font-bold ${getSavingsColor(results.monthly_savings)}`}>
                      {formatCurrency(results.monthly_savings)}
                    </div>
                  </div>
                </div>

                {/* Savings Projections */}
                <div className="mb-8">
                  <div className="flex items-center mb-6">
                    <Target className="h-5 w-5 text-slate-600 mr-2" />
                    <h3 className="text-xl font-semibold text-slate-900">Savings Timeline</h3>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {results.savings_projections.map((projection, index) => (
                      <div key={index} className={`p-6 rounded-xl border-2 ${getSavingsBackground(projection.total_saved)}`}>
                        <div className="text-sm font-medium text-slate-600 mb-2 uppercase tracking-wider">
                          {projection.period_name}
                        </div>
                        <div className={`text-2xl font-bold ${getSavingsColor(projection.total_saved)}`}>
                          {formatCurrency(projection.total_saved)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Savings Chart */}
                {results.monthly_savings > 0 && (
                  <div className="border border-gray-200 rounded-xl p-6">
                    <h3 className="text-xl font-semibold text-slate-900 mb-6">Savings Growth Projection</h3>
                    <div className="h-80">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={results.savings_projections[2].monthly_breakdown}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                          <XAxis 
                            dataKey="month" 
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#64748b', fontSize: 12 }}
                          />
                          <YAxis 
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#64748b', fontSize: 12 }}
                            tickFormatter={(value) => `£${(value/1000).toFixed(1)}k`}
                          />
                          <Tooltip 
                            contentStyle={{
                              backgroundColor: '#ffffff',
                              border: '1px solid #e2e8f0',
                              borderRadius: '12px',
                              boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)'
                            }}
                            formatter={(value) => [formatCurrency(value), 'Total Saved']}
                            labelFormatter={(label) => `Month ${label}`}
                          />
                          <Line 
                            type="monotone" 
                            dataKey="cumulative_savings" 
                            stroke="#059669" 
                            strokeWidth={4}
                            dot={{ fill: '#059669', strokeWidth: 0, r: 6 }}
                            activeDot={{ r: 8, fill: '#047857' }}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {results.monthly_savings < 0 && (
                  <div className="bg-rose-50 border-2 border-rose-200 rounded-xl p-6">
                    <div className="flex items-center mb-3">
                      <div className="bg-rose-100 p-2 rounded-lg mr-3">
                        <Target className="h-5 w-5 text-rose-600" />
                      </div>
                      <h3 className="text-lg font-semibold text-rose-900">Budget Alert</h3>
                    </div>
                    <p className="text-rose-800 text-lg">
                      You're spending <strong>{formatCurrency(Math.abs(results.monthly_savings))}</strong> more than you earn each month. 
                      Consider reducing expenses or increasing income to achieve your financial goals.
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SonOfMervan;