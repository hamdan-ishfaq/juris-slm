import { Link, useLocation, useNavigate } from 'react-router-dom';
import { MessageSquare, Upload, Zap, Shield, LogOut, X, Scale } from 'lucide-react';
import { useState, useEffect } from 'react';
import { authAPI } from '../lib/api';

export default function Sidebar({ isOpen, onClose }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState(null);

  useEffect(() => {
    const checkAuth = () => {
      const email = localStorage.getItem('user_email');
      const userRole = localStorage.getItem('user_role');
      if (email) {
        setUser({ email });
        setRole(userRole || 'user');
      }
    };

    checkAuth();
    window.addEventListener('storage', checkAuth);
    return () => window.removeEventListener('storage', checkAuth);
  }, [location]);

  const isActive = (path) => location.pathname === path;

  const getRoleBadge = () => {
    const badges = {
      owner: { icon: '🟡', label: 'Owner', color: 'text-amber-300' },
      admin: { icon: '🔴', label: 'Admin', color: 'text-red-400' },
      user: { icon: '🔵', label: 'User', color: 'text-blue-400' },
      guest: { icon: '⚪', label: 'Guest', color: 'text-gray-400' }
    };
    return badges[role] || badges.user;
  };

  const badge = getRoleBadge();

  const handleLogout = () => {
    authAPI.logout();
    setUser(null);
    setRole(null);
    navigate('/login');
    onClose();
  };

  const handleLinkClick = () => {
    onClose(); // Close sidebar on mobile after navigation
  };

  const navItems = [
    { path: '/chat', icon: MessageSquare, label: 'Chat', show: true },
    { path: '/upload', icon: Upload, label: 'Upload', show: true },
    { path: '/diagnostics', icon: Zap, label: 'Diagnostics', show: role === 'owner' },
    { path: '/manage-users', icon: Shield, label: 'Manage Users', show: role === 'owner' }
  ];

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed md:sticky top-0 left-0 h-[100dvh] w-72 bg-white border-r border-neutral-200 shadow-sm 
          flex flex-col z-50 transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" onClick={handleLinkClick}>
            <Scale className="w-6 h-6 text-blue-500" />
            <span className="text-lg font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
              BEWEIS
            </span>
          </Link>
          <button
            onClick={onClose}
            className="md:hidden p-2 text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* User Info */}
        {user && (
          <div className="p-4 border-b border-neutral-200">
            <div className="flex flex-col gap-1">
              <span className="text-sm text-neutral-700 font-medium truncate">{user.email}</span>
              <span className={`text-xs font-semibold flex items-center gap-1 ${badge.color}`}>
                {badge.icon} {badge.label}
              </span>
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-3">
          <ul className="space-y-1">
            {navItems.filter(item => item.show).map((item) => {
              const Icon = item.icon;
              const active = isActive(item.path);
              return (
                <li key={item.path}>
                  <Link
                    to={item.path}
                    onClick={handleLinkClick}
                    className={`
                      flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium
                      transition-all duration-200
                      ${active 
                        ? 'bg-primary-100 text-primary-700' 
                        : 'text-neutral-600 hover:text-primary-700 hover:bg-neutral-100'
                      }
                    `}
                  >
                    <Icon className="w-5 h-5 flex-shrink-0" />
                    <span>{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* Logout Button */}
        {user && (
          <div className="p-3 border-t border-neutral-200">
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium text-neutral-600 hover:text-danger-600 hover:bg-danger-50 transition-colors"
            >
              <LogOut className="w-5 h-5" />
              <span>Logout</span>
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
