import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, ArrowRight, Lock, Database, Scale } from 'lucide-react';

const Landing = () => {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Navbar */}
      <nav className="flex justify-between items-center p-6 max-w-7xl mx-auto">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-8 h-8 text-juris-600" />
          <span className="text-2xl font-bold tracking-tight text-juris-900">Juris AI</span>
        </div>
        <Link to="/login" className="px-6 py-2 bg-juris-600 text-white rounded-lg font-medium hover:bg-juris-700 transition-colors">
          Login Portal
        </Link>
      </nav>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-6 py-20 text-center">
        <div className="inline-flex items-center px-3 py-1 rounded-full bg-juris-100 text-juris-700 text-sm font-medium mb-8">
          <span className="flex h-2 w-2 rounded-full bg-juris-600 mr-2"></span>
          System Online • v1.0.4
        </div>
        
        <h1 className="text-5xl md:text-7xl font-extrabold text-slate-900 mb-6 tracking-tight">
          Legal Intelligence, <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-juris-600 to-indigo-600">
            Securely Guarded.
          </span>
        </h1>
        
        <p className="text-xl text-slate-600 mb-10 max-w-2xl mx-auto leading-relaxed">
          An enterprise-grade legal assistant powered by fine-tuned LLMs and role-based vector security. 
          Designed for confidentiality.
        </p>

        <div className="flex justify-center gap-4">
          <Link to="/login" className="flex items-center px-8 py-4 bg-juris-900 text-white rounded-xl font-bold hover:bg-slate-800 transition-all shadow-lg hover:shadow-xl">
            Access System <ArrowRight className="ml-2 w-5 h-5" />
          </Link>
        </div>

        {/* Feature Grid */}
        <div className="grid md:grid-cols-3 gap-8 mt-24 text-left">
          <FeatureCard 
            icon={<Lock className="w-6 h-6 text-juris-600" />}
            title="RBAC Security"
            desc="Granular access control ensuring Guest and Admin data separation."
          />
          <FeatureCard 
            icon={<Database className="w-6 h-6 text-juris-600" />}
            title="RAG Memory"
            desc="Vector database retrieval for accurate, fact-based legal citations."
          />
          <FeatureCard 
            icon={<Scale className="w-6 h-6 text-juris-600" />}
            title="Legal Fine-Tuning"
            desc="Specialized language models trained on case law and statutes."
          />
        </div>
      </main>
    </div>
  );
};

const FeatureCard = ({ icon, title, desc }) => (
  <div className="p-6 bg-white rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
    <div className="p-3 bg-juris-50 rounded-lg w-fit mb-4">{icon}</div>
    <h3 className="text-xl font-bold mb-2">{title}</h3>
    <p className="text-slate-500">{desc}</p>
  </div>
);

export default Landing;