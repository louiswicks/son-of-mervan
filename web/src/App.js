import React, { useState, useEffect } from 'react';
import LoginPage from './components/LoginPage';
import SonOfMervan from './components/SonOfMervan';
import MonthlyTracker from './components/MonthlyTracker';
import AnnualOverview from './components/AnnualOverview';
import './App.css';

const API_BASE_URL = 'https://son-of-mervan-production.up.railway.app';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('budget');

  // NEW: when this changes, AnnualOverview refetches
  const [refreshKey, setRefreshKey] = useState(0);
  const handleAnyDataSaved = () => setRefreshKey(k => k + 1);

  useEffect(() => {
    const savedToken = localStorage.getItem('authToken');
    if (savedToken) {
      verifyToken(savedToken);
    } else {
      setLoading(false);
    }
  }, []);

  const verifyToken = async (token) => {
    try {
      const response = await fetch(`${API_BASE_URL}/verify-token`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (response.ok) {
        setToken(token);
        setIsAuthenticated(true);
      } else {
        localStorage.removeItem('authToken');
      }
    } catch (error) {
      console.error('Token verification failed:', error);
      localStorage.removeItem('authToken');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = (newToken) => {
    localStorage.setItem('authToken', newToken);
    setToken(newToken);
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    setToken(null);
    setIsAuthenticated(false);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-900 via-purple-900 to-indigo-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-white"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header with nav + logout */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <h1 className="text-2xl font-bold text-gray-900">SYITB</h1>
            <div className="flex space-x-4">
              <button
                onClick={() => setActiveTab('budget')}
                className={`px-3 py-1.5 rounded-lg font-medium text-sm ${
                  activeTab === 'budget'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                Current Budget
              </button>
              <button
                onClick={() => setActiveTab('monthly')}
                className={`px-3 py-1.5 rounded-lg font-medium text-sm ${
                  activeTab === 'monthly'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                Monthly Tracker
              </button>
              <button
                onClick={() => setActiveTab('annual')}
                className={`px-3 py-1.5 rounded-lg font-medium text-sm ${
                  activeTab === 'annual'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                Annual Overview
              </button>
              <button
                onClick={handleLogout}
                className="bg-gray-600 hover:bg-gray-700 text-white px-3 py-1.5 rounded-lg font-medium text-sm"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto p-6">
        {activeTab === 'budget' && (
          <SonOfMervan token={token} onSaved={handleAnyDataSaved} />
        )}
        {activeTab === 'monthly' && (
          <MonthlyTracker token={token} onSaved={handleAnyDataSaved} />
        )}
        {activeTab === 'annual' && (
          <AnnualOverview token={token} refreshKey={refreshKey} />
        )}
      </main>
    </div>
  );
}

export default App;
