import React, { useState } from 'react';
import axios from 'axios';

const Diagnostics = () => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [stats, setStats] = useState({ test_count: 0, passed: 0, failed: 0 });

  const runEvaluation = async () => {
    setLoading(true);
    setError('');
    setResults([]);

    try {
      const response = await axios.post('http://localhost:8000/evaluate');
      
      if (response.data.status === 'completed') {
        setResults(response.data.results);
        setStats({
          test_count: response.data.test_count,
          passed: response.data.passed,
          failed: response.data.failed
        });
      }
    } catch (err) {
      setError(`Error running evaluation: ${err.message}`);
      console.error('Evaluation error:', err);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (result) => {
    if (result.status === 'PASS') {
      return 'text-green-600 bg-green-50';
    } else if (result.status === 'FAIL') {
      return 'text-red-600 bg-red-50';
    }
    return 'text-gray-600 bg-gray-50';
  };

  const getGuestResultColor = (result) => {
    // If Guest result shows access denied AND it should deny, that's good
    if (result.should_deny_guest && result.guest_response.toLowerCase().includes('access denied')) {
      return 'text-green-600';
    }
    // If Guest got answer AND should not be denied, that's good
    if (!result.should_deny_guest && !result.guest_response.toLowerCase().includes('access denied')) {
      return 'text-green-600';
    }
    return 'text-red-600';
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">🚀 System Diagnostics</h1>
          <p className="text-gray-300">
            Automated evaluation of JurisGuardRAG logic, retrieval, and security capabilities
          </p>
        </div>

        {/* Run Button */}
        <div className="mb-8">
          <button
            onClick={runEvaluation}
            disabled={loading}
            className={`px-6 py-3 rounded-lg font-semibold text-white transition-all duration-200 ${
              loading
                ? 'bg-gray-600 cursor-not-allowed'
                : 'bg-gradient-to-r from-purple-600 to-pink-600 hover:shadow-lg'
            }`}
          >
            {loading ? '⏳ Running Tests...' : '▶️ Run Full System Evaluation'}
          </button>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-8 p-4 bg-red-900 border border-red-700 rounded-lg text-red-200">
            {error}
          </div>
        )}

        {/* Stats Summary */}
        {results.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <div className="bg-slate-800 border border-purple-500 rounded-lg p-6 text-center">
              <div className="text-3xl font-bold text-purple-400">{stats.test_count}</div>
              <div className="text-gray-300 mt-2">Total Tests</div>
            </div>
            <div className="bg-slate-800 border border-green-500 rounded-lg p-6 text-center">
              <div className="text-3xl font-bold text-green-400">{stats.passed}</div>
              <div className="text-gray-300 mt-2">Passed</div>
            </div>
            <div className="bg-slate-800 border border-red-500 rounded-lg p-6 text-center">
              <div className="text-3xl font-bold text-red-400">{stats.failed}</div>
              <div className="text-gray-300 mt-2">Failed</div>
            </div>
          </div>
        )}

        {/* Results Table */}
        {results.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-purple-500 bg-slate-800">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-700 border-b border-purple-500">
                  <th className="px-4 py-3 text-left text-purple-300 font-semibold">ID</th>
                  <th className="px-4 py-3 text-left text-purple-300 font-semibold">Category</th>
                  <th className="px-4 py-3 text-left text-purple-300 font-semibold">Question</th>
                  <th className="px-4 py-3 text-left text-purple-300 font-semibold">Guest Result</th>
                  <th className="px-4 py-3 text-left text-purple-300 font-semibold">Admin Result</th>
                  <th className="px-4 py-3 text-center text-purple-300 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {results.map((result, idx) => (
                  <tr key={idx} className="border-b border-slate-700 hover:bg-slate-700 transition-colors">
                    <td className="px-4 py-3 text-gray-300">{result.id}</td>
                    <td className="px-4 py-3 text-gray-300 text-sm">{result.category}</td>
                    <td className="px-4 py-3 text-gray-300 text-sm max-w-xs truncate">
                      <span title={result.question}>{result.question.substring(0, 40)}...</span>
                    </td>
                    <td className={`px-4 py-3 text-sm font-semibold ${getGuestResultColor(result)}`}>
                      {result.guest_response.substring(0, 30)}...
                    </td>
                    <td className="px-4 py-3 text-sm text-blue-400 font-semibold">
                      {result.admin_response.substring(0, 30)}...
                    </td>
                    <td className={`px-4 py-3 text-center font-bold text-lg ${getStatusColor(result)}`}>
                      {result.status === 'PASS' ? '✅' : '❌'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Empty State */}
        {!loading && results.length === 0 && !error && (
          <div className="text-center text-gray-400 py-16">
            <p className="text-lg">Click "Run Full System Evaluation" to test the system</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Diagnostics;
