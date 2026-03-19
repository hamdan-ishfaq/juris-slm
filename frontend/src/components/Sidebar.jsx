import { Link, useLocation, useNavigate } from 'react-router-dom';
import { MessageSquare, Upload, Zap, Shield, LogOut, X } from 'lucide-react';
import { useState, useEffect } from 'react';
import { authAPI } from '../lib/api';

export default function Sidebar({ isOpen, onClose }) {
  const location  = useLocation();
  const navigate  = useNavigate();
  const [user, setUser] = useState(null);
  const [role, setRole] = useState(null);

  useEffect(() => {
    const checkAuth = () => {
      const email    = localStorage.getItem('user_email');
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

  const roleMeta = {
    owner: { label: 'Owner', color: 'text-gold'     },
    admin: { label: 'Admin', color: 'text-info'     },
    user:  { label: 'User',  color: 'text-ink-muted' },
    guest: { label: 'Guest', color: 'text-ink-faint' },
  };
  const badge = roleMeta[role] || roleMeta.user;

  const handleLogout = () => {
    authAPI.logout();
    setUser(null);
    setRole(null);
    navigate('/login');
    onClose();
  };

  const navItems = [
    { path: '/chat',         icon: MessageSquare, label: 'Chat',         show: true              },
    { path: '/upload',       icon: Upload,        label: 'Upload',       show: true              },
    { path: '/diagnostics',  icon: Zap,           label: 'Diagnostics',  show: role === 'owner'  },
    { path: '/manage-users', icon: Shield,        label: 'Manage Users', show: role === 'owner'  },
  ];

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 bg-overlay z-40 md:hidden"
          onClick={onClose}
        />
      )}

      <aside className={`
        fixed md:sticky top-0 left-0 h-[100dvh] w-56 bg-surface border-r border-stroke
        flex flex-col z-50 transition-transform duration-200 ease-in-out
        ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}>

        {/* Logo */}
        <div className="px-4 py-4 border-b border-stroke flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5" onClick={onClose}>
            <div className="flex flex-col gap-[3px]">
              <span className="block h-[2px] w-5 bg-gold"   />
              <span className="block h-[2px] w-[14px] bg-gold" />
              <span className="block h-[2px] w-[10px] bg-gold" />
            </div>
            <span className="font-mono text-sm font-medium tracking-[0.14em] text-ink">BEWEIS</span>
          </Link>
          <button
            onClick={onClose}
            className="md:hidden p-1.5 text-ink-faint hover:text-ink rounded-sm transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* User */}
        {user && (
          <div className="px-4 py-3 border-b border-stroke">
            <p className="text-xs font-mono text-ink-muted truncate mb-1">{user.email}</p>
            <div className={`flex items-center gap-1.5 text-xs font-mono font-medium ${badge.color}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0" />
              {badge.label}
            </div>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2 px-2">
          <ul className="space-y-0.5">
            {navItems.filter(i => i.show).map(({ path, icon: Icon, label }) => (
              <li key={path}>
                <Link
                  to={path}
                  onClick={onClose}
                  className={`
                    flex items-center gap-2.5 px-3 py-2.5 rounded-sm text-xs font-medium
                    transition-all duration-150 border
                    ${isActive(path)
                      ? 'bg-gold-dim text-gold border-gold/20'
                      : 'text-ink-muted hover:text-ink hover:bg-elevated border-transparent'
                    }
                  `}
                >
                  <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>

        {/* Logout */}
        {user && (
          <div className="p-2 border-t border-stroke">
            <button
              onClick={handleLogout}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-sm text-xs font-medium text-ink-faint hover:text-danger hover:bg-danger-dim transition-all duration-150"
            >
              <LogOut className="w-3.5 h-3.5" />
              Logout
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
