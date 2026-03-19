import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Home from './pages/Home';
import Chat from './pages/Chat';
import Upload from './pages/Upload';
import Diagnostics from './pages/Diagnostics';
import Login from './pages/Login';
import ManageUsers from './pages/ManageUsers';

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('access_token');
  if (!token) return <Navigate to="/login" replace />;
  return children;
}

function OwnerRoute({ children }) {
  const role = (localStorage.getItem('user_role') || '').toLowerCase();
  if (role !== 'owner') return <Navigate to="/" replace />;
  return children;
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/"           element={<Home />} />
        <Route path="/login"      element={<Login />} />
        <Route path="/chat"       element={<ProtectedRoute><Chat /></ProtectedRoute>} />
        <Route path="/upload"     element={<ProtectedRoute><Upload /></ProtectedRoute>} />
        <Route path="/diagnostics" element={<OwnerRoute><Diagnostics /></OwnerRoute>} />
        <Route path="/manage-users" element={<OwnerRoute><ManageUsers /></OwnerRoute>} />
        <Route path="*"           element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
