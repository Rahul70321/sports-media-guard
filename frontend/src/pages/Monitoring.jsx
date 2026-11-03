import { useEffect, useState } from 'react';
import { apiFetch } from '../api';

const Monitoring = () => {
  const [targets, setTargets] = useState([]);
  const [runs, setRuns] = useState([]);
  const [capabilities, setCapabilities] = useState({});
  const [form, setForm] = useState({ name: '', canonical_url: 'mock://sports/highlight', adapter_type: 'mock', interval_seconds: 900 });
  const [error, setError] = useState('');

  const load = async () => {
    const [targetRes, runRes, capabilityRes] = await Promise.all([
      apiFetch('/api/monitor/targets'), apiFetch('/api/monitor/runs'), apiFetch('/api/monitor/adapters'),
    ]);
    if (targetRes.ok) setTargets(await targetRes.json());
    if (runRes.ok) setRuns(await runRes.json());
    if (capabilityRes.ok) setCapabilities(await capabilityRes.json());
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      load().catch((err) => setError(err.message));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const createTarget = async (event) => {
    event.preventDefault();
    setError('');
    const response = await apiFetch('/api/monitor/targets', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form),
    });
    const data = await response.json();
    if (!response.ok) { setError(data.detail || 'Could not create target'); return; }
    await load();
  };

  const runNow = async (id) => {
    await apiFetch(`/api/monitor/targets/${id}/run`, { method: 'POST' });
    await load();
  };

  return (
    <div className="page-enter">
      <h1 className="text-gradient">Continuous Monitoring</h1>
      <p className="text-muted">Only configured, authorized sources are monitored. Unsupported platforms remain unavailable.</p>
      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}
      <form className="glass-panel" onSubmit={createTarget} style={{ display: 'grid', gap: '0.75rem', margin: '1rem 0' }}>
        <input className="form-input" placeholder="Target name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
        <input className="form-input" placeholder="Authorized source URL" value={form.canonical_url} onChange={(e) => setForm({ ...form, canonical_url: e.target.value })} required />
        <select className="form-select" value={form.adapter_type} onChange={(e) => setForm({ ...form, adapter_type: e.target.value })}>
          {Object.keys(capabilities).map((name) => <option key={name}>{name}</option>)}
        </select>
        <button className="btn btn-primary" type="submit">Save Monitoring Target</button>
      </form>
      <div className="glass-panel">
        <h3>Targets</h3>
        {targets.map((target) => (
          <div key={target.id} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', padding: '0.75rem 0' }}>
            <div>
              <strong>{target.name}</strong>
              <div className="text-muted">{target.adapter_type} · {target.authorization_mode} · {target.canonical_url}</div>
              <small>{target.capabilities.authorized_video ? 'Authorized video available' : 'Thumbnail/metadata only or unavailable'}</small>
            </div>
            <button className="btn btn-secondary" onClick={() => runNow(target.id)}>Run now</button>
          </div>
        ))}
      </div>
      <div className="glass-panel" style={{ marginTop: '1rem' }}>
        <h3>Recent Runs</h3>
        {runs.map((run) => <p key={run.id}>{run.adapter_type}: {run.status} — {run.message} ({run.progress}%)</p>)}
      </div>
    </div>
  );
};

export default Monitoring;
