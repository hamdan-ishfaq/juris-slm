import { Link, useLocation } from 'react-router-dom';
import { Scale, MessageSquare, Upload, Phone } from 'lucide-react';
import { BarChart2 } from 'lucide-react';

export default function Navbar() {
  const location = useLocation();

  const isActive = (path) => location.pathname === path 
    ? "text-blue-400 bg-gray-800" 
    : "text-gray-400 hover:text-white hover:bg-gray-800";

  return (
    <nav className="fixed top-0 w-full bg-gray-900/80 backdrop-blur-md border-b border-gray-800 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-2">
            <Scale className="w-8 h-8 text-blue-500" />
            <span className="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
              Juris AI
            </span>
          </Link>
          
          <div className="flex gap-4">
            <Link to="/chat" className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${isActive('/chat')}`}>
              <MessageSquare className="w-4 h-4" /> Chat
            </Link>
            <Link to="/upload" className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${isActive('/upload')}`}>
              <Upload className="w-4 h-4" /> Upload
            </Link>
            <Link to="/contact" className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${isActive('/contact')}`}>
              <Phone className="w-4 h-4" /> Contact
            </Link>
            <Link to="/eval" className={`px-3 py-2 rounded-md text-sm font-medium transition-colors flex items-center gap-2 ${isActive('/eval')}`}>
             <BarChart2 className="w-4 h-4" /> Diagnostics
            </Link>
          </div>
        </div>
      </div>
    </nav>
  );
}