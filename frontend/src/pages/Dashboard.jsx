import React, { useState, useEffect } from 'react';
import { Play, Search, AlertCircle, CheckCircle, ShieldAlert } from 'lucide-react';

const Dashboard = () => {
  const [stats, setStats] = useState({ total_assets: 0, total_incidents: 0, pending_incidents: 0 });
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanUrl, setScanUrl] = useState('https://old.reddit.com/r/sports/new/');
  const [isScanning, setIsScanning] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [statsRes, incidentsRes] = await Promise.all([
        fetch('http://localhost:8000/api/dashboard/stats'),
        fetch('http://localhost:8000/api/incidents')
      ]);
      const statsData = await statsRes.json();
      const incidentsData = await incidentsRes.json();
      setStats(statsData);
      setIncidents(incidentsData);
      setLoading(false);
    } catch (err) {
      console.error("Failed to fetch dashboard data", err);
      setLoading(false);
    }
  };

  const handleStartScan = async () => {
    setIsScanning(true);
    try {
      await fetch(`http://localhost:8000/api/monitor/crawl?url=${encodeURIComponent(scanUrl)}`, {
        method: 'POST'
      });
      // Show scanning visual for a bit, then refresh
      setTimeout(() => {
        setIsScanning(false);
        fetchData();
      }, 5000);
    } catch (err) {
      console.error(err);
      setIsScanning(false);
    }
  };

  const handleAction = async (id, status) => {
    try {
      const formData = new FormData();
      formData.append('status', status);
      await fetch(`http://localhost:8000/api/incidents/${id}/action`, {
        method: 'POST',
        body: formData
      });
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="page-enter">
      <div className="header-actions">
        <div>
          <h1 className="text-gradient">Operations Dashboard</h1>
          <p className="text-muted">Real-time media intelligence and threat monitoring.</p>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="glass-panel stat-card">
          <span className="text-secondary">Protected Assets</span>
          <span className="stat-value">{stats.total_assets}</span>
        </div>
        <div className="glass-panel stat-card">
          <span className="text-secondary">Total Detections</span>
          <span className="stat-value">{stats.total_incidents}</span>
        </div>
        <div className="glass-panel stat-card">
          <span className="text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertCircle size={16} color="var(--warning)" />
            Pending Review
          </span>
          <span className="stat-value">{stats.pending_incidents}</span>
        </div>
      </div>

      <div className="glass-panel" style={{ marginBottom: '2rem' }}>
        <h3 style={{ marginBottom: '1rem' }}>Active Monitoring</h3>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <input 
              type="text" 
              className="form-input" 
              value={scanUrl}
              onChange={(e) => setScanUrl(e.target.value)}
              placeholder="Enter URL to scan (e.g. reddit.com/r/sports)"
            />
          </div>
          <button 
            className="btn btn-primary" 
            onClick={handleStartScan}
            disabled={isScanning}
          >
            {isScanning ? <Search className="animate-spin" size={18} /> : <Play size={18} />}
            {isScanning ? 'Crawling...' : 'Trigger Scan'}
          </button>
        </div>
      </div>

      <div className="glass-panel">
        <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ShieldAlert size={20} color="var(--danger)" />
          Recent Incidents
        </h3>
        
        <table className="data-table">
          <thead>
            <tr>
              <th>Asset</th>
              <th>Platform / URL</th>
              <th>Confidence</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {incidents.length === 0 ? (
              <tr>
                <td colSpan="5" style={{ textAlign: 'center', padding: '2rem' }}>No incidents detected.</td>
              </tr>
            ) : (
              incidents.map(inc => (
                <tr key={inc.id}>
                  <td style={{ fontWeight: 500 }}>{inc.asset_title}</td>
                  <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <a href={inc.discovered_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-primary)' }}>
                      {inc.discovered_url}
                    </a>
                  </td>
                  <td>
                    <span style={{ 
                      color: inc.match_score > 95 ? 'var(--danger)' : 'var(--warning)',
                      fontWeight: 600
                    }}>
                      {inc.match_score.toFixed(1)}%
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${inc.status === 'pending_review' ? 'badge-warning' : inc.status === 'takedown_requested' ? 'badge-danger' : 'badge-success'}`}>
                      {inc.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td>
                    {inc.status === 'pending_review' && (
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button 
                          onClick={() => handleAction(inc.id, 'takedown_requested')}
                          className="btn" 
                          style={{ padding: '0.25rem 0.5rem', background: 'rgba(239, 68, 68, 0.2)', color: 'var(--danger)' }}
                        >
                          Takedown
                        </button>
                        <button 
                          onClick={() => handleAction(inc.id, 'false_positive')}
                          className="btn" 
                          style={{ padding: '0.25rem 0.5rem', background: 'rgba(16, 185, 129, 0.2)', color: 'var(--success)' }}
                        >
                          Dismiss
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Dashboard;
