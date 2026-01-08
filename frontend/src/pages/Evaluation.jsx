import { useState } from 'react';
import { Play, CheckCircle, XCircle, Activity, BrainCircuit, BarChart3 } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Evaluation() {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);

  const runDiagnostics = async () => {
    setLoading(true);
    setReport(null);
    try {
      const res = await fetch('http://localhost:8000/evaluate');
      const data = await res.json();
      setReport(data);
    } catch (err) {
      console.error("Evaluation failed", err);
    } finally {
      setLoading(false);
    }
  };

  const getGradeColor = (score) => {
    if (score >= 0.8) return "text-green-400";
    if (score >= 0.6) return "text-yellow-400";
    return "text-red-400";
  };

  return (
    <div className="min-h-screen bg-gray-950 pt-24 px-4 pb-12">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">System Diagnostics</h1>
            <p className="text-gray-400">Evaluate RAG Logic & Reasoning Accuracy</p>
          </div>
          <button 
            onClick={runDiagnostics} 
            disabled={loading}
            className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-800 disabled:cursor-not-allowed text-white font-bold rounded-xl transition-all"
          >
            {loading ? <Activity className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5" />}
            {loading ? "Running Tests..." : "Run Evaluation Suite"}
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="text-center py-20 bg-gray-900/50 rounded-2xl border border-gray-800">
            <BrainCircuit className="w-16 h-16 text-blue-500 mx-auto mb-4 animate-pulse" />
            <h3 className="text-xl text-white font-semibold">Testing Intelligence...</h3>
            <p className="text-gray-500">Processing test cases through the neural network.</p>
          </div>
        )}

        {/* Results Dashboard */}
        {report && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
            {/* Top Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              <div className="bg-gray-900 p-6 rounded-2xl border border-gray-800">
                <div className="flex items-center gap-3 mb-2">
                  <CheckCircle className="w-6 h-6 text-green-500" />
                  <span className="text-gray-400 font-medium">Accuracy Score</span>
                </div>
                <div className={`text-4xl font-bold ${getGradeColor(report.overall_score)}`}>
                  {(report.overall_score * 100).toFixed(1)}%
                </div>
              </div>
              
              <div className="bg-gray-900 p-6 rounded-2xl border border-gray-800">
                <div className="flex items-center gap-3 mb-2">
                  <Activity className="w-6 h-6 text-blue-500" />
                  <span className="text-gray-400 font-medium">Avg Latency</span>
                </div>
                <div className="text-4xl font-bold text-white">
                  {report.average_latency.toFixed(2)}s
                </div>
              </div>

              <div className="bg-gray-900 p-6 rounded-2xl border border-gray-800">
                <div className="flex items-center gap-3 mb-2">
                  <BarChart3 className="w-6 h-6 text-purple-500" />
                  <span className="text-gray-400 font-medium">Test Cases</span>
                </div>
                <div className="text-4xl font-bold text-white">
                  {report.results.length} / {report.results.length}
                </div>
              </div>
            </div>

            {/* Detailed Table */}
            <div className="bg-gray-900 rounded-2xl border border-gray-800 overflow-hidden">
              <table className="w-full text-left">
                <thead className="bg-gray-800/50 text-gray-400 text-sm uppercase">
                  <tr>
                    <th className="px-6 py-4">Test Case</th>
                    <th className="px-6 py-4">AI Response (Snippet)</th>
                    <th className="px-6 py-4">Latency</th>
                    <th className="px-6 py-4">Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800 text-gray-300">
                  {report.results.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-800/30 transition">
                      <td className="px-6 py-4">
                        <div className="font-medium text-white">{item.category}</div>
                        <div className="text-xs text-gray-500 mt-1">{item.question}</div>
                      </td>
                      <td className="px-6 py-4 max-w-xs truncate text-gray-400 italic">
                        "{item.ai_answer}"
                      </td>
                      <td className="px-6 py-4 font-mono text-sm">
                        {item.latency.toFixed(2)}s
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-3 py-1 rounded-full text-xs font-bold bg-opacity-20 ${
                          item.score >= 0.8 ? "bg-green-500 text-green-400" :
                          item.score >= 0.6 ? "bg-yellow-500 text-yellow-400" :
                          "bg-red-500 text-red-400"
                        }`}>
                          {(item.score * 100).toFixed(0)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}