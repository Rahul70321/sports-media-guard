import { useState, useEffect } from 'react';
import {
  AlertTriangle, Gavel, Cpu, Network, WifiOff,
  AlertCircle, Fingerprint, ScanEye, Shield, Flame, CheckCircle2, XCircle, Info
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from 'recharts';

import { apiFetch } from '../api';

// ─── Risk Level Badge ─────────────────────────────────────────────────────

const RiskBadge = ({ level }) => {
  const config = {
    Critical: { bg: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: 'rgba(239, 68, 68, 0.3)' },
    High: { bg: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b', border: 'rgba(245, 158, 11, 0.3)' },
    Medium: { bg: 'rgba(99, 102, 241, 0.15)', color: '#6366f1', border: 'rgba(99, 102, 241, 0.3)' },
    Low: { bg: 'rgba(16, 185, 129, 0.15)', color: '#10b981', border: 'rgba(16, 185, 129, 0.3)' },
  };
  const c = config[level] || config.Low;
  return (
    <span style={{
      padding: '0.2rem 0.6rem', borderRadius: '9999px', fontSize: '0.7rem',
      fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em',
      background: c.bg, color: c.color, border: `1px solid ${c.border}`
    }}>
      {level}
    </span>
  );
};

// ─── Score Bar ──────────────────────────────────────────────────────────────

const ScoreBar = ({ label, value, max = 100, color = '#6366f1' }) => (
  <div style={{ marginBottom: '0.75rem' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem', fontSize: '0.85rem' }}>
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span style={{ fontWeight: 600, color }}>{value?.toFixed(1)}%</span>
    </div>
    <div style={{ height: '6px', borderRadius: '3px', background: 'var(--bg-tertiary)', overflow: 'hidden' }}>
      <div style={{
        height: '100%', borderRadius: '3px', background: color,
        width: `${Math.min(100, (value / max) * 100)}%`,
        transition: 'width 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
        boxShadow: `0 0 8px ${color}40`,
      }} />
    </div>
  </div>
);


// ─── Main Component ────────────────────────────────────────────────────────

const IncidentReview = () => {
  const [incidents, setIncidents] = useState([]);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [isTakingDown, setIsTakingDown] = useState(false);
  const [error, setError] = useState(null);
  const [takedownError, setTakedownError] = useState(null);

  const fetchIncidents = async () => {
    setError(null);
    try {
      const res = await apiFetch('/api/incidents');
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const data = await res.json();
      setIncidents(data);
    } catch (err) {
      console.error(err);
      setError('Failed to load incidents. Is the backend running?');
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchIncidents();
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const handleTakedown = async (id) => {
    setIsTakingDown(true);
    setTakedownError(null);
    try {
      const res = await apiFetch(`/api/incidents/${id}/takedown`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Takedown failed (${res.status})`);
      }
      const result = await res.json();
      setIncidents(prev => prev.map(inc =>
        inc.id === id ? { ...inc, status: 'takedown_requested', ai_summary: result.ai_legal_summary } : inc
      ));
      if (selectedIncident?.id === id) {
        setSelectedIncident(prev => ({ ...prev, status: 'takedown_requested', ai_summary: result.ai_legal_summary }));
      }
    } catch (err) {
      console.error(err);
      setTakedownError(err.message);
    } finally {
      setIsTakingDown(false);
    }
  };

  // ─── Error State ───────────────────────────────────────────────────────

  if (error) {
    return (
      <div className="page-enter">
        <div className="header-actions">
          <div>
            <h1 className="text-gradient">Incident Review Hub</h1>
            <p className="text-muted">Analyze forensic evidence and dispatch legal notices.</p>
          </div>
        </div>
        <div className="glass-panel" style={{ textAlign: 'center', padding: '3rem' }}>
          <WifiOff size={48} style={{ marginBottom: '1rem', color: 'var(--danger)', opacity: 0.7 }} />
          <h2 style={{ marginBottom: '0.5rem' }}>Connection Error</h2>
          <p className="text-muted" style={{ marginBottom: '1.5rem' }}>{error}</p>
          <button className="btn btn-primary" onClick={fetchIncidents}>Retry</button>
        </div>
      </div>
    );
  }

  // ─── Build chart data from selected incident ──────────────────────────

  const anomalyBarData = selectedIncident?.anomaly_factors?.map(f => ({
    name: f.signal,
    score: f.score,
  })) || [];

  const anomalyBarColors = ['#ef4444', '#f59e0b', '#8b5cf6', '#6366f1', '#3b82f6', '#10b981'];

  // ─── Render ────────────────────────────────────────────────────────────

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="header-actions">
        <div>
          <h1 className="text-gradient">Incident Review Hub</h1>
          <p className="text-muted">AI-powered forensic analysis with multi-signal matching and anomaly scoring.</p>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '2rem', flex: 1, marginTop: '1rem', minHeight: 0 }}>

        {/* ─── Incident List Sidebar ─── */}
        <div className="glass-panel" style={{ width: '350px', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.75rem', overflowY: 'auto', flexShrink: 0 }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <ScanEye size={18} color="var(--accent-primary)" /> Active Incidents
          </h3>
          {incidents.length === 0 ? (
            <p className="text-muted" style={{ padding: '2rem', textAlign: 'center' }}>No incidents found.</p>
          ) : (
            incidents.map(inc => (
              <div
                key={inc.id}
                style={{
                  padding: '0.85rem', borderRadius: 'var(--br-md)', cursor: 'pointer',
                  background: selectedIncident?.id === inc.id ? 'rgba(99, 102, 241, 0.1)' : 'var(--bg-tertiary)',
                  border: selectedIncident?.id === inc.id ? '1px solid var(--accent-primary)' : '1px solid transparent',
                  transition: 'all 0.2s ease'
                }}
                onClick={() => { setSelectedIncident(inc); setTakedownError(null); }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{inc.asset_title}</span>
                  <RiskBadge level={inc.risk_level || 'Low'} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                  <span>{inc.platform}</span>
                  <span style={{ display: 'flex', gap: '0.75rem' }}>
                    <span style={{ color: inc.match_score > 90 ? '#ef4444' : '#f59e0b' }}>
                      Match: {inc.match_score?.toFixed(0)}%
                    </span>
                    <span style={{ color: inc.anomaly_score > 55 ? '#ef4444' : '#6366f1' }}>
                      Risk: {inc.anomaly_score?.toFixed(0)}
                    </span>
                  </span>
                </div>
                {inc.watermark_match && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', marginTop: '0.4rem', fontSize: '0.75rem', color: '#10b981' }}>
                    <Fingerprint size={12} /> Watermark verified
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* ─── Deep Dive Panel ─── */}
        {selectedIncident ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1.25rem', overflowY: 'auto' }}>

            {/* ─── Row 1: Similarity Radar + Anomaly Breakdown ─── */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>

              {/* Similarity Radar */}
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <Fingerprint color="var(--accent-primary)" size={20} />
                  <h3 style={{ fontSize: '1rem' }}>Similarity Matching</h3>
                </div>
                <ScoreBar label="Perceptual Hash (pHash)" value={selectedIncident.phash_score} color="#6366f1" />
                <ScoreBar label="Difference Hash (dHash)" value={selectedIncident.dhash_score} color="#8b5cf6" />
                <ScoreBar label="Color Histogram (HSV)" value={selectedIncident.histogram_score} color="#ec4899" />
                <ScoreBar label="Authorized video frames" value={selectedIncident.video_frame_score || 0} color="#10b981" />
                <p className="text-muted">Evidence: {selectedIncident.evidence_type || 'metadata_only'} · {selectedIncident.confidence_label || 'unclassified'}</p>
                {selectedIncident.evidence_type === 'thumbnail' && <p>This is a thumbnail candidate, not a confirmed full-video match.</p>}
                <div style={{ marginTop: '0.75rem', padding: '0.5rem 0.75rem', borderRadius: 'var(--br-md)', background: 'rgba(99, 102, 241, 0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>Composite Score</span>
                  <span style={{ fontWeight: 700, fontSize: '1.2rem', color: selectedIncident.match_score > 90 ? '#ef4444' : '#6366f1' }}>
                    {selectedIncident.match_score?.toFixed(1)}%
                  </span>
                </div>
              </div>

              {/* Anomaly Breakdown */}
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Flame color={selectedIncident.anomaly_score > 55 ? '#ef4444' : '#f59e0b'} size={20} />
                    <h3 style={{ fontSize: '1rem' }}>Anomaly Score</h3>
                  </div>
                  <RiskBadge level={selectedIncident.risk_level || 'Low'} />
                </div>

                {/* Anomaly score gauge */}
                <div style={{ textAlign: 'center', margin: '0.5rem 0 1rem' }}>
                  <span style={{
                    fontSize: '2.5rem', fontWeight: 800, fontFamily: 'Outfit, sans-serif',
                    color: selectedIncident.anomaly_score >= 75 ? '#ef4444' : selectedIncident.anomaly_score >= 55 ? '#f59e0b' : '#6366f1',
                  }}>
                    {selectedIncident.anomaly_score?.toFixed(0)}
                  </span>
                  <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>/100</span>
                </div>

                {/* Factor chart */}
                {anomalyBarData.length > 0 && (
                  <div style={{ height: '120px' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={anomalyBarData} layout="vertical" margin={{ left: 0, right: 10 }}>
                        <XAxis type="number" domain={[0, 25]} hide />
                        <YAxis type="category" dataKey="name" width={90} tick={{ fill: '#9ca3af', fontSize: 11 }} />
                        <Tooltip
                          contentStyle={{ backgroundColor: '#1e1e24', border: 'none', borderRadius: '8px', fontSize: '0.85rem' }}
                          formatter={(v) => [`${v} pts`, 'Score']}
                        />
                        <Bar dataKey="score" radius={[0, 4, 4, 0]} barSize={14}>
                          {anomalyBarData.map((_, idx) => (
                            <Cell key={idx} fill={anomalyBarColors[idx % anomalyBarColors.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </div>
            </div>

            {/* ─── Row 2: Watermark Verification + Forensic Evidence ─── */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem' }}>

              {/* Watermark Verification */}
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                  <Shield color={selectedIncident.watermark_match ? '#10b981' : '#6b7280'} size={20} />
                  <h3 style={{ fontSize: '1rem' }}>Watermark Verification</h3>
                </div>

                {selectedIncident.watermark_match ? (
                  <div style={{ padding: '1rem', background: 'rgba(16, 185, 129, 0.08)', borderRadius: 'var(--br-md)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#10b981', fontWeight: 600 }}>
                      <CheckCircle2 size={18} /> WATERMARK CONFIRMED
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
                      Forensic watermark <code style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '0.1rem 0.4rem', borderRadius: '4px', color: '#10b981' }}>{selectedIncident.watermark_extracted}</code> was found embedded in the pirated media and matches the registered asset. This is <strong>conclusive proof</strong> of unauthorized distribution.
                    </p>
                  </div>
                ) : selectedIncident.watermark_extracted ? (
                  <div style={{ padding: '1rem', background: 'rgba(245, 158, 11, 0.08)', borderRadius: 'var(--br-md)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: '#f59e0b', fontWeight: 600 }}>
                      <Info size={18} /> WATERMARK PARTIAL
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>
                      Text fragment <code style={{ background: 'rgba(245, 158, 11, 0.1)', padding: '0.1rem 0.4rem', borderRadius: '4px', color: '#f59e0b' }}>{selectedIncident.watermark_extracted}</code> was extracted but could not be matched to a registered asset.
                    </p>
                  </div>
                ) : (
                  <div style={{ padding: '1rem', background: 'var(--bg-tertiary)', borderRadius: 'var(--br-md)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
                      <XCircle size={18} /> NO WATERMARK DETECTED
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
                      No forensic watermark was found. The pirated media may have been re-encoded or captured via screen recording. Detection relies on visual fingerprint matching only.
                    </p>
                  </div>
                )}
              </div>

              {/* Source Info */}
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                  <Network color="var(--accent-primary)" size={20} />
                  <h3 style={{ fontSize: '1rem' }}>Source Intelligence</h3>
                </div>
                <div style={{ display: 'grid', gap: '0.6rem', fontSize: '0.85rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Source URL</span>
                    <a href={selectedIncident.discovered_url} target="_blank" rel="noreferrer"
                      style={{ color: 'var(--accent-primary)', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {selectedIncident.discovered_url}
                    </a>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Platform</span>
                    <span>{selectedIncident.platform}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Status</span>
                    <span className={`badge ${selectedIncident.status === 'pending_review' ? 'badge-warning' : selectedIncident.status === 'takedown_requested' ? 'badge-danger' : 'badge-success'}`}>
                      {selectedIncident.status?.replaceAll('_', ' ')}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>Detected</span>
                    <span>{selectedIncident.created_at ? new Date(selectedIncident.created_at).toLocaleString() : 'N/A'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* ─── Row 3: Anomaly Factors Detail ─── */}
            {selectedIncident.anomaly_factors?.length > 0 && (
              <div className="glass-panel">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                  <AlertTriangle color="#f59e0b" size={20} />
                  <h3 style={{ fontSize: '1rem' }}>Risk Factor Analysis</h3>
                </div>
                <div style={{ display: 'grid', gap: '0.5rem' }}>
                  {selectedIncident.anomaly_factors.map((factor, idx) => (
                    <div key={idx} style={{
                      display: 'flex', alignItems: 'flex-start', gap: '0.75rem',
                      padding: '0.75rem', borderRadius: 'var(--br-md)',
                      background: 'var(--bg-tertiary)', fontSize: '0.85rem',
                    }}>
                      <div style={{
                        minWidth: '36px', height: '36px', borderRadius: '50%',
                        background: `${anomalyBarColors[idx % anomalyBarColors.length]}20`,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontWeight: 700, fontSize: '0.8rem',
                        color: anomalyBarColors[idx % anomalyBarColors.length],
                      }}>
                        +{factor.score}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, marginBottom: '0.15rem' }}>{factor.signal}</div>
                        <div style={{ color: 'var(--text-secondary)', lineHeight: 1.4 }}>{factor.detail}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ─── Row 4: AI Summary ─── */}
            <div className="glass-panel">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <Cpu color="#10b981" size={20} />
                <h3 style={{ fontSize: '1rem' }}>Google AI Legal Summary</h3>
              </div>
              {selectedIncident.ai_summary ? (
                <div style={{
                  padding: '1rem', background: 'rgba(16, 185, 129, 0.05)',
                  borderLeft: '4px solid #10b981', borderRadius: '0 8px 8px 0',
                  whiteSpace: 'pre-wrap', fontSize: '0.85rem', lineHeight: 1.6,
                }}>
                  {selectedIncident.ai_summary}
                </div>
              ) : (
                <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  <p>AI Summary will be generated when takedown is requested via Gemini API.</p>
                </div>
              )}
            </div>

            {/* ─── Row 5: Action Bar ─── */}
            <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h4 style={{ margin: 0 }}>Enforcement Action</h4>
                  <p className="text-muted" style={{ margin: '0.25rem 0 0', fontSize: '0.85rem' }}>Dispatch automated DMCA via Webhook + generate AI legal brief.</p>
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
              {takedownError && (
                <p style={{ color: 'var(--danger)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
                  <AlertCircle size={14} /> {takedownError}
                </p>
              )}
            </div>

          </div>
        ) : (
          <div className="glass-panel" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
            <div style={{ textAlign: 'center' }}>
              <ScanEye size={48} style={{ marginBottom: '1rem', opacity: 0.4 }} />
              <h2>Select an incident to review</h2>
              <p>View multi-signal matching, watermark verification, and anomaly analysis.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default IncidentReview;
