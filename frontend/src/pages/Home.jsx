import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, ShieldCheck, Zap, Database } from 'lucide-react';

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-950 pt-20 flex flex-col items-center justify-center text-center px-4">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
      >
        <h1 className="text-5xl md:text-7xl font-extrabold text-white mb-6 tracking-tight">
          Legal Intelligence, <br />
          <span className="text-blue-500">Decentralized.</span>
        </h1>
        <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10">
          Secure, private, and offline-capable legal AI. 
          Fine-tuned on complex regulations to protect your data.
        </p>
        
        <div className="flex gap-4 justify-center">
          <Link to="/chat" className="px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-lg transition-all flex items-center gap-2">
            Start Analysis <ArrowRight className="w-5 h-5" />
          </Link>
          <Link to="/upload" className="px-8 py-4 bg-gray-800 hover:bg-gray-700 text-white rounded-xl font-bold text-lg transition-all">
            Upload Docs
          </Link>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mt-24 max-w-6xl mx-auto">
        {[
          { icon: <ShieldCheck className="w-8 h-8 text-green-400" />, title: "RBAC Security", desc: "Role-Based Access Control ensures data privacy." },
          { icon: <Database className="w-8 h-8 text-purple-400" />, title: "RAG Engine", desc: "Retrieves exact clauses from your uploaded PDFs." },
          { icon: <Zap className="w-8 h-8 text-yellow-400" />, title: "Offline Local", desc: "Runs entirely on your RTX 4050. No cloud leaks." }
        ].map((item, idx) => (
          <motion.div 
            key={idx}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 + (idx * 0.2) }}
            className="p-6 bg-gray-900 rounded-2xl border border-gray-800"
          >
            <div className="mb-4">{item.icon}</div>
            <h3 className="text-xl font-bold text-white mb-2">{item.title}</h3>
            <p className="text-gray-400">{item.desc}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}