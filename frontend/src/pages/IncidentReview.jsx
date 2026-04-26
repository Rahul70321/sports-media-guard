import React, { useState, useEffect } from 'react';
import { AlertTriangle, ShieldAlert, Activity, Gavel, Cpu, Network } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const IncidentReview = () => {
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [isTakingDown, setIsTakingDown] = useState(false);

  useEffect(() => {
    fetch('http://localhost:8000/api/incidents')
      .then(res => res.json())
      .then(data => setIncidents(data))
      .catch(err => console.error(err));
  }, []);

  const handleTakedown = async (id) => {
    setIsTakingDown(true);
    try {
      const res = await fetch(`http://localhost:8000/api/incidents/${id}/takedown`, {
        method: 'POST'
      });
      const result = await res.json();
      
      // Update local state with the AI summary
      setIncidents(prev => prev.map(inc => 
        inc.id === id ? { ...inc, status: 'takedown_requested', ai_summary: result.ai_legal_summary } : inc
      ));
      
      if (selectedIncident && selectedIncident.id === id) {
        setSelectedIncident(prev => ({ ...prev, status: 'takedown_requested', ai_summary: result.ai_legal_summary }));
      }
      
    } catch (err) {
      console.error(err);
    } finally {
      setIsTakingDown(false);
    }
  };

  // Mock propagation data for the graph
  const propagationData = [
    { time: '0h', violations: 1 },
    { time: '2h', violations: 3 },
    { time: '4h', violations: 12 },
    { time: '6h', violations: 45 },
    { time: '8h', violations: 120 },
    { time: '10h', violations: 110 }, // Assuming takedowns start taking effect
  ];

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="header-actions">
        <div>
          <h1 className="text-gradient">Incident Review Hub</h1>
          <p className="text-muted">Analyze propagation graphs, review forensic evidence, and dispatch legal notices.</p>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '2rem', flex: 1, marginTop: '1rem' }}>
        
        {/* Incident List Sidebar */}
        <div className="glass-panel" style={{ width: '350px', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem', overflowY: 'auto' }}>
          <h3>Active Incidents</h3>
          {incidents.length === 0 ? (
            <p className="text-muted">No incidents found.</p>
          ) : (
            incidents.map(inc => (
              <div 
                key={inc.id} 
                className={`incident-card ${selectedIncident?.id === inc.id ? 'active' : ''}`}
                style={{
                  padding: '1rem',
                  borderRadius: 'var(--br-md)',
                  background: selectedIncident?.id === inc.id ? 'rgba(99, 102, 241, 0.1)' : 'var(--bg-tertiary)',
                  border: selectedIncident?.id === inc.id ? '1px solid var(--accent-primary)' : '1px solid transparent',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease'
                }}
                onClick={() => setSelectedIncident(inc)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span style={{ fontWeight: '600' }}>{inc.asset_title}</span>
                  <span className={`status-badge status-${inc.status}`}>{inc.status.replace('_', ' ')}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  <span>Platform: {inc.platform}</span>
                  <span style={{ color: inc.match_score > 90 ? '#ef4444' : '#f59e0b' }}>
                    Match: {inc.match_score}%
                  </span>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Deep Dive Panel */}
        {selectedIncident ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem', overflowY: 'auto' }}>
            
            {/* Top Stats */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                  <ShieldAlert color="var(--accent-primary)" />
                  <h3>Forensic Evidence</h3>
                </div>
                <p><strong>Source URL:</strong> <a href={selectedIncident.discovered_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent-primary)' }}>{selectedIncident.discovered_url}</a></p>
                <p><strong>Visual Match:</strong> {selectedIncident.match_score}%</p>
                <p><strong>Invisible Watermark:</strong> <span style={{ color: '#10b981' }}>Detected (ORG-Valid)</span></p>
                <p><strong>Anomaly Risk:</strong> <span style={{ color: '#ef4444' }}>High (First seen in unauthorized region)</span></p>
              </div>

              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                  <Network color="var(--accent-primary)" />
                  <h3>Propagation Velocity</h3>
                </div>
                <div style={{ height: '150px', width: '100%' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={propagationData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                      <XAxis dataKey="time" stroke="#888" fontSize={12} />
                      <YAxis stroke="#888" fontSize={12} />
                      <Tooltip contentStyle={{ backgroundColor: '#1e1e24', border: 'none', borderRadius: '8px' }} />
                      <Line type="monotone" dataKey="violations" stroke="#6366f1" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* AI Summary Section */}
            <div className="glass-panel">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <Cpu color="#10b981" />
                <h3>Google AI Legal Summary</h3>
              </div>
              
              {selectedIncident.ai_summary ? (
                <div style={{ padding: '1rem', background: 'rgba(16, 185, 129, 0.05)', borderLeft: '4px solid #10b981', borderRadius: '0 8px 8px 0', whiteSpace: 'pre-wrap', fontSize: '0.9rem', lineHeight: '1.6' }}>
                  {selectedIncident.ai_summary}
                </div>
              ) : (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <p>AI Summary will be generated when takedown is requested via Gemini API.</p>
                </div>
              )}
            </div>

            {/* Action Bar */}
            <div className="glass-panel" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h4 style={{ margin: 0 }}>Enforcement Action</h4>
                <p className="text-muted" style={{ margin: '0.5rem 0 0 0', fontSize: '0.85rem' }}>Dispatch automated DMCA via Webhook.</p>
              </div>
              <button 
                className="btn btn-primary" 
                style={{ background: '#ef4444', borderColor: '#ef4444' }}
                onClick={() => handleTakedown(selectedIncident.id)}
                disabled={isTakingDown || selectedIncident.status === 'takedown_requested'}
              >
                <Gavel size={18} />
                {isTakingDown ? 'Processing...' : (selectedIncident.status === 'takedown_requested' ? 'Takedown Dispatched' : 'Issue Takedown')}
              </button>
            </div>

          </div>
        ) : (
          <div className="glass-panel" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
            <div style={{ textAlign: 'center' }}>
              <Activity size={48} style={{ marginBottom: '1rem', opacity: 0.5 }} />
              <h2>Select an incident to review</h2>
              <p>View propagation graphs, forensic data, and AI insights.</p>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default IncidentReview;
