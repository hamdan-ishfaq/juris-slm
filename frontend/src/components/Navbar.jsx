import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Menu, X, LogOut, MessageSquare, Upload, Shield, Zap } from 'lucide-react';
import { authAPI } from '../lib/api';
import Button from './ui/Button';

const Navbar = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [username, setUsername] = useState(null);
  const [role, setRole] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const checkAuth = () => {
      // FIXED: keys now match what api.js writes on login
      const token = localStorage.getItem('access_token');
      const storedUsername = localStorage.getItem('user_email');
      const storedRole = localStorage.getItem('user_role');

      if (token && storedUsername) {
        setUsername(storedUsername);
        setRole(storedRole);
      } else {
        setUsername(null);
        setRole(null);
      }
    };

    checkAuth();
    window.addEventListener('storage', checkAuth);
    return () => window.removeEventListener('storage', checkAuth);
  }, []);

  const handleLogout = () => {
    authAPI.logout();
    setUsername(null);
    setRole(null);
    navigate('/login');
  };

  const isActive = (path) => {
    return location.pathname === path
      ? 'bg-primary-100 text-primary-700'
      : 'text-neutral-700 hover:bg-neutral-100';
  };

  if (!username) return null;

  return (
    <nav className="bg-white border-b border-neutral-200 sticky top-0 z-50 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 md:px-6">
        <div className="flex justify-between items-center h-16">
          <Link to="/chat" className="flex items-center gap-2">
            <span className="text-xl font-bold text-primary-700">
              BEWEIS
            </span>
          </Link>

          <div className="hidden md:flex gap-2 items-center">
            <Link
              to="/chat"
              className={'px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 flex items-center gap-2 ' + isActive('/chat')}
            >
              <MessageSquare className="w-4 h-4" /> Chat
            </Link>
            <Link
              to="/upload"
              className={'px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 flex items-center gap-2 ' + isActive('/upload')}
            >
              <Upload className="w-4 h-4" /> Upload
            </Link>
            {role === 'owner' && (
              <>
                <Link
                  to="/diagnostics"
                  className={'px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 flex items-center gap-2 ' + isActive('/diagnostics')}
                >
                  <Zap className="w-4 h-4" /> Diagnostics
                </Link>
                <Link
                  to="/manage-users"
                  className={'px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 flex items-center gap-2 ' + isActive('/manage-users')}
                >
                  <Shield className="w-4 h-4" /> Manage
                </Link>
              </>
            )}
            <div className="ml-4 pl-4 border-l border-neutral-200 flex items-center gap-3">
              <span className="text-sm text-neutral-600">
                {username}
                {role === 'owner' && (
                  <span className="ml-2 px-2 py-0.5 bg-primary-100 text-primary-700 text-xs font-medium rounded">
                    Owner
                  </span>
                )}
              </span>
              <Button variant="ghost" size="sm" onClick={handleLogout}>
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          </div>

          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-neutral-700 hover:bg-neutral-100 rounded-md"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {mobileMenuOpen && (
        <div className="md:hidden bg-white border-t border-neutral-200">
          <div className="px-4 py-4 space-y-2">
            <Link
              to="/chat"
              onClick={() => setMobileMenuOpen(false)}
              className={'block px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 ' + isActive('/chat')}
            >
              <MessageSquare className="w-4 h-4" /> Chat
            </Link>
            <Link
              to="/upload"
              onClick={() => setMobileMenuOpen(false)}
              className={'block px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 ' + isActive('/upload')}
            >
              <Upload className="w-4 h-4" /> Upload
            </Link>
            {role === 'owner' && (
              <>
                <Link
                  to="/diagnostics"
                  onClick={() => setMobileMenuOpen(false)}
                  className={'block px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 ' + isActive('/diagnostics')}
                >
                  <Zap className="w-4 h-4" /> Diagnostics
                </Link>
                <Link
                  to="/manage-users"
                  onClick={() => setMobileMenuOpen(false)}
                  className={'block px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 ' + isActive('/manage-users')}
                >
                  <Shield className="w-4 h-4" /> Manage
                </Link>
              </>
            )}
            <div className="pt-4 mt-4 border-t border-neutral-200">
              <p className="px-4 text-sm text-neutral-600 mb-2">
                {username}
                {role === 'owner' && (
                  <span className="ml-2 px-2 py-0.5 bg-primary-100 text-primary-700 text-xs font-medium rounded">
                    Owner
                  </span>
                )}
              </p>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleLogout}
                className="w-full justify-start"
              >
                <LogOut className="w-4 h-4 mr-2" /> Logout
              </Button>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;