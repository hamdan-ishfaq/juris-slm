import { useState } from 'react';
import { motion } from 'framer-motion';
import { UploadCloud, CheckCircle, AlertTriangle, FileText } from 'lucide-react';

export default function UploadPage() {
  const [status, setStatus] = useState('idle'); // idle, uploading, success, error
  const [message, setMessage] = useState('');

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    if (file.type !== 'application/pdf') {
      setStatus('error');
      setMessage('Only PDF files are allowed.');
      return;
    }

    setStatus('uploading');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error('Upload failed');
      const data = await res.json();
      setStatus('success');
      setMessage(`Successfully learned: ${data.filename}`);
    } catch (err) {
      setStatus('error');
      setMessage('Server error. Is the backend running?');
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 pt-20 px-4">
      <div className="max-w-2xl mx-auto">
        <h2 className="text-3xl font-bold text-white mb-2">Knowledge Base</h2>
        <p className="text-gray-400 mb-8">Upload legal documents (contracts, memos) to train the AI instantly.</p>

        <motion.div 
          className="border-2 border-dashed border-gray-700 rounded-3xl p-12 text-center bg-gray-900/50 hover:bg-gray-900 hover:border-blue-500 transition-colors cursor-pointer"
          whileHover={{ scale: 1.01 }}
        >
          <input 
            type="file" 
            accept=".pdf" 
            className="hidden" 
            id="file-upload" 
            onChange={handleFileChange}
          />
          <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
            <div className="w-20 h-20 bg-gray-800 rounded-full flex items-center justify-center mb-6">
              <UploadCloud className="w-10 h-10 text-blue-500" />
            </div>
            <span className="text-xl font-semibold text-white mb-2">Click to Upload PDF</span>
            <span className="text-sm text-gray-500">Max size 50MB</span>
          </label>
        </motion.div>

        {status !== 'idle' && (
          <motion.div 
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mt-6 p-4 rounded-xl flex items-center gap-3 ${
              status === 'success' ? 'bg-green-900/20 text-green-400 border border-green-900' : 
              status === 'error' ? 'bg-red-900/20 text-red-400 border border-red-900' : 
              'bg-blue-900/20 text-blue-400 border border-blue-900'
            }`}
          >
            {status === 'success' && <CheckCircle className="w-5 h-5" />}
            {status === 'error' && <AlertTriangle className="w-5 h-5" />}
            {status === 'uploading' && <FileText className="w-5 h-5 animate-pulse" />}
            <span>{status === 'uploading' ? 'Reading and indexing document...' : message}</span>
          </motion.div>
        )}
      </div>
    </div>
  );
}