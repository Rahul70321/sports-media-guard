import { useState, useEffect } from 'react';
import { 
  Settings as SettingsIcon, 
  ShieldCheck, 
  Eye, 
  Target, 
  BellRing, 
  Gavel, 
  Lock, 
  Webhook, 
  Save,
  CheckCircle,
  AlertCircle
} from 'lucide-react';
import { apiFetch } from '../api';

const Settings = () => {
  const [activeTab, setActiveTab] = useState('general');
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(null); // 'success' | 'error' | null
  const [loadError, setLoadError] = useState(null);
  const [settings, setSettings] = useState({
    // 1. General
    orgName: 'Global Sports League',
    contactEmail: 'legal@globalsports.com',
    timeZone: 'UTC',
    
    // 2. Rights
    defaultSensitivity: 'High',
    allowMonetization: false,
    
    // 3. Monitoring
    monitorYoutube: true,
    monitorTwitch: true,
    monitorX: true,
    monitorPirateSites: true,
    scanFrequency: 'Aggressive',
    
    // 4. Detection
    videoMatchThreshold: 80,
    audioMatchThreshold: 75,
    partialMatches: true,
    
    // 5. Alerts
    alertChannel: 'Email + Slack',
    digestMode: false,
    
    // 6. Takedown
    takedownMode: 'Semi-Auto',
    
    // 7. Security
    requireMFA: true,
    
    // 8. Integrations
    webhookUrl: '',
  });

  useEffect(() => {
    apiFetch('/api/settings')
      .then(res => {
        if (!res.ok) throw new Error(`Server error (${res.status})`);
        return res.json();
      })
      .then(data => {
        if (Object.keys(data).length > 0) {
          setSettings(prev => ({ ...prev, ...data }));
        }
      })
      .catch(err => {
        console.error(err);
        setLoadError('Failed to load settings from server. Using defaults.');
      });
  }, []);

  const handleChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setSaveStatus(null); // clear save status when editing
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      const res = await apiFetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      if (!res.ok) throw new Error(`Save failed (${res.status})`);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (err) {
      console.error(err);
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  };

  const tabs = [
    { id: 'general', label: 'Organization', icon: <SettingsIcon size={18} /> },
    { id: 'rights', label: 'Asset & Rights', icon: <ShieldCheck size={18} /> },
    { id: 'monitoring', label: 'Monitoring', icon: <Eye size={18} /> },
    { id: 'detection', label: 'Detection', icon: <Target size={18} /> },
    { id: 'alerts', label: 'Alerts', icon: <BellRing size={18} /> },
    { id: 'takedown', label: 'Takedowns', icon: <Gavel size={18} /> },
    { id: 'security', label: 'Security', icon: <Lock size={18} /> },
    { id: 'integrations', label: 'Integrations', icon: <Webhook size={18} /> },
  ];

  return (
    <div className="page-enter" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="header-actions">
        <div>
          <h1 className="text-gradient">Platform Settings</h1>
          <p className="text-muted">Configure organization defaults, detection aggressiveness, and enforcement rules.</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {saveStatus === 'success' && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--success)', fontSize: '0.9rem', animation: 'pageFadeIn 0.3s ease forwards' }}>
              <CheckCircle size={16} /> Saved
            </span>
          )}
          {saveStatus === 'error' && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--danger)', fontSize: '0.9rem', animation: 'pageFadeIn 0.3s ease forwards' }}>
              <AlertCircle size={16} /> Save failed
            </span>
          )}
          <button className="btn btn-primary" onClick={handleSave} disabled={isSaving}>
            <Save size={18} />
            {isSaving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>

      {loadError && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.75rem',
          padding: '0.75rem 1rem', marginBottom: '1rem', borderRadius: 'var(--br-lg)',
          background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.2)',
          color: 'var(--warning)', fontSize: '0.85rem'
        }}>
          <AlertCircle size={16} />
          <span>{loadError}</span>
        </div>
      )}

      <div style={{ display: 'flex', gap: '2rem', flex: 1 }}>
        {/* Settings Sidebar */}
        <div className="glass-panel" style={{ width: '250px', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', height: 'fit-content' }}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              className={`settings-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Settings Content */}
        <div className="glass-panel" style={{ flex: 1 }}>
          {activeTab === 'general' && (
            <div className="settings-section page-enter">
              <h2>Organization Profile</h2>
              <p className="text-muted" style={{ marginBottom: '1.5rem' }}>Basic info so the platform knows who it is protecting.</p>
              
              <div className="form-group">
                <label className="form-label">Organization Name</label>
                <input type="text" className="form-input" value={settings.orgName} onChange={e => handleChange('orgName', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Contact Email</label>
                <input type="email" className="form-input" value={settings.contactEmail} onChange={e => handleChange('contactEmail', e.target.value)} />
              </div>
              <div className="form-group">
                <label className="form-label">Time Zone</label>
                <select className="form-select" value={settings.timeZone} onChange={e => handleChange('timeZone', e.target.value)}>
                  <option>UTC</option>
                  <option>America/New_York</option>
                  <option>Europe/London</option>
                </select>
              </div>
            </div>
          )}

          {activeTab === 'rights' && (
            <div className="settings-section page-enter">
              <h2>Asset & Rights Defaults</h2>
              <p className="text-muted" style={{ marginBottom: '1.5rem' }}>Settings that control how newly onboarded assets are treated by default.</p>
              
              <div className="form-group">
                <label className="form-label">Default Sensitivity</label>
                <select className="form-select" value={settings.defaultSensitivity} onChange={e => handleChange('defaultSensitivity', e.target.value)}>
                  <option>High (Live Feeds, Premium)</option>
                  <option>Medium (Promos, Highlights)</option>
                  <option>Low (Graphics, Logos)</option>
                </select>
              </div>
              
              <div className="form-group toggle-group">
                <label className="form-label">Allow Fan Monetization (Default)</label>
                <label className="switch">
                  <input type="checkbox" checked={settings.allowMonetization} onChange={e => handleChange('allowMonetization', e.target.checked)} />
                  <span className="slider round"></span>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'monitoring' && (
            <div className="settings-section page-enter">
              <h2>Monitoring & Scanning</h2>
              <p className="text-muted" style={{ marginBottom: '1.5rem' }}>Controls where and how the system scans the internet.</p>
              
              <div className="form-group">
                <label className="form-label">Scan Frequency / Intensity</label>
                <select className="form-select" value={settings.scanFrequency} onChange={e => handleChange('scanFrequency', e.target.value)}>
                  <option>Aggressive (Live events, every 1-2 mins)</option>
                  <option>Standard (Every 10-15 mins)</option>
                  <option>Low (Daily scan)</option>
                </select>
              </div>

              <h4 style={{ marginTop: '2rem', marginBottom: '1rem' }}>Platforms to Monitor</h4>
              
              <div className="form-group toggle-group">
                <label className="form-label">YouTube</label>
                <label className="switch">
                  <input type="checkbox" checked={settings.monitorYoutube} onChange={e => handleChange('monitorYoutube', e.target.checked)} />
                  <span className="slider round"></span>
                </label>
              </div>
              <div className="form-group toggle-group">
                <label className="form-label">Twitch</label>
                <label className="switch">
                  <input type="checkbox" checked={settings.monitorTwitch} onChange={e => handleChange('monitorTwitch', e.target.checked)} />
                  <span className="slider round"></span>
                </label>
              </div>
              <div className="form-group toggle-group">
                <label className="form-label">X / Twitter</label>
                <label className="switch">
                  <input type="checkbox" checked={settings.monitorX} onChange={e => handleChange('monitorX', e.target.checked)} />
                  <span className="slider round"></span>
                </label>
              </div>
              <div className="form-group toggle-group">
                <label className="form-label">Pirate Sites & Forums</label>
                <label className="switch">
                  <input type="checkbox" checked={settings.monitorPirateSites} onChange={e => handleChange('monitorPirateSites', e.target.checked)} />
                  <span className="slider round"></span>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'detection' && (
            <div className="settings-section page-enter">
              <h2>Detection Thresholds</h2>
              <p className="text-muted" style={{ marginBottom: '1.5rem' }}>Settings that balance catching real piracy vs avoiding noise. These thresholds are actively used by the matching engine.</p>
              
              <div className="form-group">
                <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Video Similarity Threshold</span>
                  <span>{settings.videoMatchThreshold}%</span>
                </label>
                <input 
                  type="range" 
                  min="0" max="100" 
                  className="range-slider" 
                  value={settings.videoMatchThreshold} 
                  onChange={e => handleChange('videoMatchThreshold', parseInt(e.target.value))} 
                />
                <small className="text-muted" style={{ marginTop: '0.5rem' }}>Lower values catch more variants but increase false positives. This value is used by the backend matching engine.</small>
              </div>
              
              <div className="form-group" style={{ marginTop: '1.5rem' }}>
                <label className="form-label" style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Audio Similarity Threshold</span>
                  <span>{settings.audioMatchThreshold}%</span>
                </label>
                <input 
                  type="range" 
                  min="0" max="100" 
                  className="range-slider" 
                  value={settings.audioMatchThreshold} 
                  onChange={e => handleChange('audioMatchThreshold', parseInt(e.target.value))} 
                />
              </div>

              <div className="form-group toggle-group" style={{ marginTop: '2rem' }}>
                <label className="form-label">Treat Partial Matches as Suspicious</label>
                <label className="switch">
                  <input type="checkbox" checked={settings.partialMatches} onChange={e => handleChange('partialMatches', e.target.checked)} />
                  <span className="slider round"></span>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'alerts' && (
            <div className="settings-section page-enter">
              <h2>Alerts & Notifications</h2>
              <p className="text-muted" style={{ marginBottom: '1.5rem' }}>Settings for who gets notified, for what, and how often.</p>
              
              <div className="form-group">
                <label className="form-label">Alert Channels</label>
                <select className="form-select" value={settings.alertChannel} onChange={e => handleChange('alertChannel', e.target.value)}>
                  <option>Email Only</option>
                  <option>Slack / Teams Webhook</option>
                  <option>Email + Slack</option>
                </select>
              </div>

              <div className="form-group toggle-group" style={{ marginTop: '1.5rem' }}>
                <label className="form-label">Summary Digest Mode (Avoid Fatigue)</label>
                <label className="switch">
                  <input type="checkbox" checked={settings.digestMode} onChange={e => handleChange('digestMode', e.target.checked)} />
                  <span className="slider round"></span>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'takedown' && (
            <div className="settings-section page-enter">
              <h2>Takedown & Enforcement</h2>
              <p className="text-muted" style={{ marginBottom: '1.5rem' }}>Control how aggressive auto-takedowns are.</p>
              
              <div className="form-group">
                <label className="form-label">Takedown Mode</label>
                <select className="form-select" value={settings.takedownMode} onChange={e => handleChange('takedownMode', e.target.value)}>
                  <option>Manual Only (System suggests; human decides)</option>
                  <option>Semi-Auto (Auto-takedown for Critical incidents only)</option>
                  <option>Full Auto (Auto-takedown for all confident matches)</option>
                </select>
              </div>
            </div>
          )}

          {activeTab === 'security' && (
            <div className="settings-section page-enter">
              <h2>Security & Access</h2>
              <p className="text-muted" style={{ marginBottom: '1.5rem' }}>Settings for who can do what and general security posture.</p>
              
              <div className="form-group toggle-group">
                <label className="form-label">Force MFA for Admin and Legal roles</label>
                <label className="switch">
                  <input type="checkbox" checked={settings.requireMFA} onChange={e => handleChange('requireMFA', e.target.checked)} />
                  <span className="slider round"></span>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'integrations' && (
            <div className="settings-section page-enter">
              <h2>Integrations & Webhooks</h2>
              <p className="text-muted" style={{ marginBottom: '1.5rem' }}>Allows the system to fit into existing workflows.</p>
              
              <div className="form-group">
                <label className="form-label">Custom Webhook URL</label>
                <input 
                  type="url" 
                  className="form-input" 
                  placeholder="https://your-server.com/webhook"
                  value={settings.webhookUrl} 
                  onChange={e => handleChange('webhookUrl', e.target.value)} 
                />
                <small className="text-muted" style={{ marginTop: '0.5rem' }}>Receives JSON payloads for new incidents and takedowns.</small>
              </div>
            </div>
          )}
          
        </div>
      </div>
    </div>
  );
};

export default Settings;
