import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Shield, Upload, Activity, AlertTriangle, Settings as SettingsIcon } from 'lucide-react';

import Dashboard from './pages/Dashboard';
import AssetOnboarding from './pages/AssetOnboarding';
import Settings from './pages/Settings';

const Sidebar = () => {
  const location = useLocation();
  
  return (
    <div className="sidebar">
      <div className="brand">
        <Shield size={28} color="var(--accent-primary)" />
        <span>SportsGuard</span>
      </div>
      
      <div className="nav-links">
        <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
          <Activity size={20} />
          <span>Dashboard</span>
        </Link>
        <Link to="/upload" className={`nav-link ${location.pathname === '/upload' ? 'active' : ''}`}>
          <Upload size={20} />
          <span>Register Asset</span>
        </Link>
        <Link to="/incidents" className={`nav-link ${location.pathname === '/incidents' ? 'active' : ''}`}>
          <AlertTriangle size={20} />
          <span>Incidents</span>
        </Link>
        <Link to="/settings" className={`nav-link ${location.pathname === '/settings' ? 'active' : ''}`}>
          <SettingsIcon size={20} />
          <span>Settings</span>
        </Link>
      </div>
    </div>
  );
};

function App() {
  return (
    <Router>
      <div className="app-container">
        <Sidebar />
        <div className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<AssetOnboarding />} />
            {/* Simple placeholder for incidents page */}
            <Route path="/incidents" element={
              <div className="page-enter">
                <div className="header-actions">
                  <div>
                    <h1 className="text-gradient">Incident Review</h1>
                    <p className="text-muted">Review and manage flagged media violations.</p>
                  </div>
                </div>
                <div className="glass-panel">
                  <p className="text-secondary">Please use the Dashboard to view recent incidents.</p>
                </div>
              </div>
            } />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </div>
      </div>
    </Router>
  );
}

export default App;
