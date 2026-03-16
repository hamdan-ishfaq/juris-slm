import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Navbar from './components/Navbar';
import Home from './pages/Home';
import Chat from './pages/Chat';
import Upload from './pages/Upload';
import Contact from './pages/Contact';
import Evaluation from './pages/Evaluation';
import Diagnostics from './pages/Diagnostics';
import Login from './pages/Login';
import ManageUsers from './pages/ManageUsers';

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('access_token');
  if (!token) {
    return <Navigate to="/" replace />;
  }
  return children;
}

function OwnerRoute({ children }) {
  const role = (localStorage.getItem('user_role') || '').toLowerCase();
  if (role !== 'owner') {
    return <Navigate to="/" replace />;
  }
  return children;
}

function AppContent() {
  const location = useLocation();
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('access_token'));

  useEffect(() => {
    const handleStorageChange = () => {
      setIsAuthenticated(!!localStorage.getItem('access_token'));
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  // Check auth state on every render
  useEffect(() => {
    const isAuth = !!localStorage.getItem('access_token');
    setIsAuthenticated(isAuth);
  });

  return (
    <div className="min-h-[100dvh] bg-neutral-50 text-neutral-900 font-sans flex flex-col">
      {/* Conditionally render Navbar - Hide on Chat page */}
      {location.pathname !== '/chat' && <Navbar />}
        <div className={location.pathname === '/chat' ? '' : 'flex-1'}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Home />} />
          <Route 
            path="/chat" 
            element={
              <ProtectedRoute>
                <Chat />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/upload" 
            element={
              <ProtectedRoute>
                <Upload />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/contact" 
            element={
              <ProtectedRoute>
                <Contact />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/eval" 
            element={
              <ProtectedRoute>
                <Evaluation />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/diagnostics" 
            element={
              <ProtectedRoute>
                <Diagnostics />
              </ProtectedRoute>
            } 
          />
          <Route
            path="/manage-users"
            element={
              <ProtectedRoute>
                <OwnerRoute>
                  <ManageUsers />
                </OwnerRoute>
              </ProtectedRoute>
            }
          />
        </Routes>
      </div>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;