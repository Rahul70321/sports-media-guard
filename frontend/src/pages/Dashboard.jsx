import { useState, useEffect } from 'react';
import { Play, Search, AlertCircle, CheckCircle, ShieldAlert, WifiOff, Trash2, Flame } from 'lucide-react';

import { apiFetch, API_URL } from '../api';

const Dashboard = ({ onOpenLogin }) => {
  const [stats, setStats] = useState({ total_assets: 0, total_incidents: 0, pending_incidents: 0, critical_incidents: 0 });
  const [incidents, setIncidents] = useState([]);
  const [error, setError] = useState(null);
  const [scanUrl, setScanUrl] = useState('https://www.youtube.com/watch?v=dQw4w9WgXcQ');
  const [isScanning, setIsScanning] = useState(false);
  const [scanError, setScanError] = useState(null);
  const [scanMessage, setScanMessage] = useState(null);
  const [testFile, setTestFile] = useState(null);
  const [testMessage, setTestMessage] = useState(null);
  const [testError, setTestError] = useState(null);
  const [isTestScanning, setIsTestScanning] = useState(false);

  const fetchData = async () => {
    setError(null);
    try {
      const [statsRes, incidentsRes] = await Promise.all([
        apiFetch('/api/dashboard/stats'),
        apiFetch('/api/incidents')
      ]);

      if (statsRes.status === 401 || incidentsRes.status === 401) {
        throw new Error('AUTH_REQUIRED');
      }
      if (!statsRes.ok || !incidentsRes.ok) {
        throw new Error(`Server error (${statsRes.status}/${incidentsRes.status})`);
      }

      const statsData = await statsRes.json();
      const incidentsData = await incidentsRes.json();
      setStats(statsData);
      setIncidents(incidentsData);
    } catch (err) {
      console.error("Failed to fetch dashboard data", err);
      setError(err.message === 'AUTH_REQUIRED'
        ? 'Please sign in to view the dashboard.'
        : 'Failed to connect to backend. Is the server running on ' + API_URL + '?');
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchData();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleStartScan = async () => {
    if (!scanUrl.trim()) {
      setScanError('Enter a YouTube video, channel, or search URL before starting a scan.');
      return;
    }
    if (!/^https?:\/\//i.test(scanUrl.trim())) {
      setScanError('Enter a complete URL beginning with https://');
      return;
    }
    setIsScanning(true);
    setScanError(null);
    setScanMessage(null);
    try {
      const res = await apiFetch(`/api/monitor/crawl?url=${encodeURIComponent(scanUrl)}`, {
        method: 'POST'
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if (res.status === 401 && onOpenLogin) {
          onOpenLogin();
        }
        throw new Error(data.detail || `Scan request failed (${res.status})`);
      }
      const data = await res.json().catch(() => ({}));
      setScanMessage(data.message || 'Scan queued.');
      if (!data.job_id) throw new Error('Backend did not return a scan job ID');
      const pollStatus = async () => {
        const statusRes = await apiFetch(`/api/monitor/crawl/${data.job_id}`);
        if (!statusRes.ok) throw new Error('Unable to read scan status');
        const status = await statusRes.json();
        setScanMessage(`${status.message} (${status.progress}%)`);
        if (status.status === 'completed' || status.status === 'failed') {
          setIsScanning(false);
          if (status.status === 'failed') setScanError(status.message);
          await fetchData();
          return;
        }
        window.setTimeout(pollStatus, 1000);
      };
      await pollStatus();
    } catch (err) {
      console.error(err);
      setScanError(err.message || 'Failed to start scan. Check backend connection.');
      setIsScanning(false);
    }
  };

  const handleTestScan = async () => {
    if (!testFile) {
      setTestError('Choose the downloaded candidate video first.');
      return;
    }
    setIsTestScanning(true);
    setTestError(null);
    setTestMessage(null);
    try {
      const formData = new FormData();
      formData.append('file', testFile);
      formData.append('source_url', scanUrl || 'local://test/candidate');
      const res = await apiFetch('/api/monitor/test-media', { method: 'POST', body: formData });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Candidate scan failed (${res.status})`);
      setTestMessage(`${data.message}. Incidents created: ${data.incidents_created}`);
      await fetchData();
    } catch (err) {
      setTestError(err.message);
    } finally {
      setIsTestScanning(false);
    }
  };

  const handleAction = async (id, status) => {
    try {
      const formData = new FormData();
      formData.append('status', status);
      const res = await apiFetch(`/api/incidents/${id}/action`, {
        method: 'POST',
        body: formData
      });
      if (!res.ok) {
        throw new Error(`Action failed (${res.status})`);
      }
      fetchData();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteIncident = async (id) => {
    if (!window.confirm('Delete this incident record?')) return;
    try {
      const res = await apiFetch(`/api/incidents/${id}`, { method: 'DELETE' });
      if (!res.ok) throw new Error('Failed to delete incident');
      fetchData();
    } catch (err) {
      alert(err.message);
    }
  };

  if (error) {
    return (
      <div className="page-enter">
        <div className="header-actions">
          <div>
            <h1 className="text-gradient">Operations Dashboard</h1>
            <p className="text-muted">Real-time media intelligence and threat monitoring.</p>
          </div>
        </div>
        <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem' }}>
          <WifiOff size={48} style={{ marginBottom: '1rem', color: 'var(--danger)', opacity: 0.7 }} />
          <h2 style={{ marginBottom: '0.5rem' }}>Connection Error</h2>
          <p className="text-muted" style={{ marginBottom: '1.5rem' }}>{error}</p>
          <button className="btn btn-primary" onClick={fetchData}>
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

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
        <div className="glass-panel stat-card">
          <span className="text-secondary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Flame size={16} color="var(--danger)" />
            Critical Threats
          </span>
          <span className="stat-value" style={{ color: 'var(--danger)' }}>{stats.critical_incidents || 0}</span>
        </div>
      </div>

      <div className="glass-panel" style={{ marginBottom: '2rem' }}>
        <h3 style={{ marginBottom: '1rem' }}>Active Monitoring</h3>
        <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '1rem' }}>
          Scan a public page from a supported social platform. Private, login-protected, and API-only feeds require platform credentials.
        </p>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <div className="form-group" style={{ flex: 1, marginBottom: 0 }}>
            <input
              type="text"
              className="form-input"
              value={scanUrl}
              onChange={(e) => setScanUrl(e.target.value)}
              placeholder="Enter a public page URL (e.g. https://example.com/sports)"
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
        <p className="text-muted" style={{ fontSize: '0.75rem', marginTop: '0.5rem' }}>
          YouTube scans use the YouTube Data API and analyze public video thumbnails.
        </p>
        {scanError && (
          <p style={{ color: 'var(--danger)', fontSize: '0.85rem', marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertCircle size={14} /> {scanError}
          </p>
        )}
        {scanMessage && !scanError && (
          <p style={{ color: 'var(--success, #22c55e)', fontSize: '0.85rem', marginTop: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <CheckCircle size={14} /> {scanMessage}
          </p>
        )}
      </div>

      <div className="glass-panel" style={{ marginBottom: '2rem' }}>
        <h3 style={{ marginBottom: '0.75rem' }}>Development Candidate Test</h3>
        <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '1rem' }}>
          Upload an authorized transformed copy of your downloaded video to verify video-to-video matching and create a real incident.
        </p>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input type="file" accept="video/*,image/*" onChange={(event) => setTestFile(event.target.files?.[0] || null)} />
          <button className="btn btn-secondary" onClick={handleTestScan} disabled={isTestScanning}>
            {isTestScanning ? 'Analyzing...' : 'Analyze Candidate'}
          </button>
        </div>
        {testError && <p style={{ color: 'var(--danger)', fontSize: '0.85rem', marginTop: '0.75rem' }}>{testError}</p>}
        {testMessage && <p style={{ color: 'var(--success, #22c55e)', fontSize: '0.85rem', marginTop: '0.75rem' }}>{testMessage}</p>}
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
              <th>Evidence</th>
              <th>Risk Level</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {incidents.length === 0 ? (
              <tr>
                <td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>No incidents detected.</td>
              </tr>
            ) : (
              incidents.map(inc => (
                <tr key={inc.id}>
                  <td style={{ fontWeight: 500 }}>{inc.asset_title}</td>
                  <td style={{ maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <a href={inc.discovered_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-primary)' }}>
                      {inc.discovered_url}
                    </a>
                  </td>
                  <td>
                    <span style={{ color: inc.match_score > 90 ? 'var(--danger)' : 'var(--warning)', fontWeight: 600 }}>
                      {inc.match_score?.toFixed(1)}%
                    </span>
                    <div className="text-muted">{inc.confidence_label || 'unclassified'}</div>
                  </td>
                  <td>{inc.evidence_type || 'metadata_only'}</td>
                  <td>
                    <span style={{
                      padding: '0.15rem 0.5rem', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 700,
                      background: inc.risk_level === 'Critical' ? 'rgba(239, 68, 68, 0.15)' : inc.risk_level === 'High' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(99, 102, 241, 0.15)',
                      color: inc.risk_level === 'Critical' ? '#ef4444' : inc.risk_level === 'High' ? '#f59e0b' : '#6366f1'
                    }}>
                      {inc.risk_level || 'Low'}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${inc.status === 'pending_review' ? 'badge-warning' : inc.status === 'takedown_requested' ? 'badge-danger' : 'badge-success'}`}>
                      {inc.status?.replaceAll('_', ' ')}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                      {inc.status === 'pending_review' && (
                        <>
                          <button
                            onClick={() => handleAction(inc.id, 'takedown_requested')}
                            className="btn"
                            style={{ padding: '0.25rem 0.5rem', background: 'rgba(239, 68, 68, 0.2)', color: 'var(--danger)', fontSize: '0.8rem' }}
                          >
                            Takedown
                          </button>
                          <button
                            onClick={() => handleAction(inc.id, 'false_positive')}
                            className="btn"
                            style={{ padding: '0.25rem 0.5rem', background: 'rgba(16, 185, 129, 0.2)', color: 'var(--success)', fontSize: '0.8rem' }}
                          >
                            Dismiss
                          </button>
                        </>
                      )}
                      <button
                        onClick={() => handleDeleteIncident(inc.id)}
                        className="btn"
                        style={{ padding: '0.25rem 0.4rem', background: 'none', color: 'var(--text-muted)' }}
                        title="Delete Record"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
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
