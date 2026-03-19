import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { ArrowRight, ShieldCheck, Database, Zap } from 'lucide-react';

const features = [
  {
    icon: ShieldCheck,
    color: 'text-success',
    title: 'RBAC Security',
    desc:  'Role-based access control with three clearance tiers. Documents stay visible only to authorised roles.',
  },
  {
    icon: Database,
    color: 'text-info',
    title: 'RAG Engine',
    desc:  'Retrieves exact clauses from your uploaded PDFs. Grounded answers with source attribution.',
  },
  {
    icon: Zap,
    color: 'text-gold',
    title: 'Offline Local',
    desc:  'Runs entirely on-device. No cloud calls, no data leaks. Your documents never leave the machine.',
  },
];

export default function Home() {
  const isAuthenticated = !!localStorage.getItem('access_token');

  return (
    <div className="min-h-[100dvh] bg-base flex flex-col items-center justify-center px-4 py-16">

      <motion.div
        className="text-center max-w-2xl mx-auto"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        {/* Wordmark */}
        <div className="flex items-center justify-center gap-2.5 mb-8">
          <div className="flex flex-col gap-[3px]">
            <span className="block h-[2px] w-6 bg-gold" />
            <span className="block h-[2px] w-[18px] bg-gold" />
            <span className="block h-[2px] w-[12px] bg-gold" />
          </div>
          <span className="font-mono text-xl font-medium tracking-[0.2em] text-ink">BEWEIS</span>
        </div>

        <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold text-ink leading-tight tracking-tight mb-4">
          Legal Intelligence,{' '}
          <span className="text-gold">Decentralized.</span>
        </h1>

        <p className="text-sm md:text-base text-ink-muted max-w-lg mx-auto mb-10 leading-relaxed">
          Secure, private, and offline-capable legal AI. Fine-tuned on complex
          regulations — your data never leaves the machine.
        </p>

        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          {isAuthenticated ? (
            <>
              <Link
                to="/chat"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-gold text-ink-inverse text-xs font-mono font-medium tracking-widest uppercase rounded-sm hover:bg-gold/90 active:bg-gold/80 transition-all"
              >
                Start Analysis <ArrowRight className="w-3.5 h-3.5" />
              </Link>
              <Link
                to="/upload"
                className="inline-flex items-center justify-center px-6 py-3 bg-elevated border border-stroke text-xs font-mono font-medium text-ink-muted uppercase tracking-widest rounded-sm hover:border-stroke-strong hover:text-ink transition-all"
              >
                Upload Documents
              </Link>
            </>
          ) : (
            <>
              <Link
                to="/login"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-gold text-ink-inverse text-xs font-mono font-medium tracking-widest uppercase rounded-sm hover:bg-gold/90 active:bg-gold/80 transition-all"
              >
                Get Started <ArrowRight className="w-3.5 h-3.5" />
              </Link>
              <Link
                to="/login"
                className="inline-flex items-center justify-center px-6 py-3 bg-elevated border border-stroke text-xs font-mono font-medium text-ink-muted uppercase tracking-widest rounded-sm hover:border-stroke-strong hover:text-ink transition-all"
              >
                Sign In
              </Link>
            </>
          )}
        </div>
      </motion.div>

      {/* Feature cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-20 max-w-4xl w-full mx-auto">
        {features.map(({ icon: Icon, color, title, desc }, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 + i * 0.15 }}
            className="bg-surface border border-stroke rounded-sm p-5 hover:border-stroke-strong transition-all duration-200"
          >
            <Icon className={`w-5 h-5 ${color} mb-3`} />
            <h3 className="text-sm font-medium text-ink mb-1.5">{title}</h3>
            <p className="text-xs text-ink-muted leading-relaxed">{desc}</p>
          </motion.div>
        ))}
      </div>

      {/* Subtle footer line */}
      <p className="mt-16 text-xs text-ink-faint font-mono">
        v1.0 · local inference · zero telemetry
      </p>
    </div>
  );
}