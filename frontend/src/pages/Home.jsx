import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, ShieldCheck, Zap, Database } from 'lucide-react';

export default function Home() {
  const isAuthenticated = !!localStorage.getItem('access_token');

  return (
    <div className="min-h-[100dvh] bg-neutral-50 pt-16 md:pt-20 flex flex-col items-center justify-center text-center px-4">
      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
      >
        <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-7xl font-extrabold text-neutral-900 mb-4 md:mb-6 tracking-tight leading-tight">
          Legal Intelligence, <br />
          <span className="text-blue-500">Decentralized.</span>
        </h1>
        <p className="text-base md:text-xl text-gray-400 max-w-2xl mx-auto mb-6 md:mb-10 px-2">
          Secure, private, and offline-capable legal AI. 
          Fine-tuned on complex regulations to protect your data.
        </p>
        
        <div className="flex flex-col sm:flex-row gap-3 md:gap-4 justify-center">
          {isAuthenticated ? (
            <>
              <Link to="/chat" className="px-6 md:px-8 py-3 md:py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-base md:text-lg transition-all flex items-center justify-center gap-2 min-h-[44px]">
                Start Analysis <ArrowRight className="w-4 h-4 md:w-5 md:h-5" />
              </Link>
              <Link to="/upload" className="px-6 md:px-8 py-3 md:py-4 bg-gray-800 hover:bg-gray-700 text-white rounded-xl font-bold text-base md:text-lg transition-all min-h-[44px]">
                Upload Docs
              </Link>
            </>
          ) : (
            <>
              <Link to="/login" className="px-6 md:px-8 py-3 md:py-4 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-base md:text-lg transition-all flex items-center justify-center gap-2 min-h-[44px]">
                Get Started <ArrowRight className="w-4 h-4 md:w-5 md:h-5" />
              </Link>
              <Link to="/login" className="px-6 md:px-8 py-3 md:py-4 bg-gray-800 hover:bg-gray-700 text-white rounded-xl font-bold text-base md:text-lg transition-all min-h-[44px]">
                Login
              </Link>
            </>
          )}
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8 mt-12 md:mt-24 max-w-6xl mx-auto w-full">
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
            className="p-5 md:p-6 bg-white rounded-xl md:rounded-2xl border border-neutral-200 shadow-sm"
          >
            <div className="mb-3 md:mb-4">{item.icon}</div>
            <h3 className="text-lg md:text-xl font-bold text-neutral-900 mb-2">{item.title}</h3>
            <p className="text-sm md:text-base text-neutral-600">{item.desc}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}