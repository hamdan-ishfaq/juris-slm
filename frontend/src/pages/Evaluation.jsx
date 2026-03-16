import { useState } from 'react';
import { motion } from 'framer-motion';

export default function Evaluation() {
  const [results, setResults] = useState(null);

  return (
    <div className="min-h-screen bg-gray-950 pt-24 pb-12 px-4">
      <div className="max-w-4xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="text-4xl font-bold text-white mb-4">Evaluation</h1>
          <p className="text-gray-400 mb-12">
            Test the BEWEIS system performance and accuracy.
          </p>

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-8">
            <h2 className="text-2xl font-bold text-white mb-6">System Evaluation</h2>
            <p className="text-gray-400 mb-6">
              For detailed system diagnostics and testing, please visit the Diagnostics page.
            </p>
            <a
              href="/diagnostics"
              className="inline-block px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-semibold transition-all"
            >
              Go to Diagnostics
            </a>
          </div>
        </motion.div>
      </div>
    </div>
  );
}