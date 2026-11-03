import { useState, useEffect, useRef } from 'react';
import { UploadCloud, FileVideo, ShieldCheck, Check, AlertCircle, Search, Trash2, Eye, Film, Image as ImageIcon, Download } from 'lucide-react';
import { apiFetch, API_URL } from '../api';

const AssetOnboarding = () => {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [rightsPolicy, setRightsPolicy] = useState('exclusive_broadcast');
  const [isUploading, setIsUploading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null);
  const [uploadResult, setUploadResult] = useState(null);

  // Asset Registry List State
  const [assets, setAssets] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [policyFilter, setPolicyFilter] = useState('');
  const [selectedAssetDetail, setSelectedAssetDetail] = useState(null);
  const fileInputRef = useRef(null);

  const fetchAssets = async () => {
    try {
      const params = new URLSearchParams();
      if (searchQuery) params.append('q', searchQuery);
      if (typeFilter) params.append('media_type', typeFilter);
      if (policyFilter) params.append('rights_policy', policyFilter);

      const res = await apiFetch(`/api/assets?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to fetch assets');
      const data = await res.json();
      setAssets(data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchAssets();
    }, 0);
    return () => window.clearTimeout(timer);
    // fetchAssets is intentionally recreated with the current filter values.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchQuery, typeFilter, policyFilter]);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.currentTarget.classList.add('active');
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('active');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.currentTarget.classList.remove('active');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
      setError(null);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file || !title) return;

    setIsUploading(true);
    setError(null);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('rights_policy', rightsPolicy);

    const token = localStorage.getItem('token');
    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

    try {
      const response = await apiFetch('/api/assets/upload', {
        method: 'POST',
        headers,
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setUploadResult(data);
        setSuccess(true);
        fetchAssets();
      } else {
        const data = await response.json().catch(() => ({}));
        setError(data.detail || `Upload failed with status ${response.status}`);
      }
    } catch (err) {
      console.error("Upload failed", err);
      setError('Network error — could not reach the server. Is the backend running?');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDownloadAsset = (assetId) => {
    const link = document.createElement('a');
    link.href = `${API_URL}/api/assets/${assetId}/download`;
    link.setAttribute('download', '');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleDeleteAsset = async (id, assetTitle) => {
    if (!window.confirm(`Are you sure you want to delete asset "${assetTitle}"? This will also remove associated incidents.`)) return;

    try {
      const token = localStorage.getItem('token');
      const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
      const res = await apiFetch(`/api/assets/${id}`, { method: 'DELETE', headers });
      if (!res.ok) throw new Error('Delete failed');
      fetchAssets();
    } catch (err) {
      alert('Error deleting asset: ' + err.message);
    }
  };

  const handleViewDetail = async (id) => {
    try {
      const res = await apiFetch(`/api/assets/${id}`);
      if (!res.ok) throw new Error('Failed to load asset details');
      const data = await res.json();
      setSelectedAssetDetail(data);
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="page-enter">
      <div className="header-actions">
        <div>
          <h1 className="text-gradient">Asset Registration & Management</h1>
          <p className="text-muted">Register official media, manage asset registry, and inspect forensic signatures.</p>
        </div>
      </div>

      {/* Upload Panel */}
      <div style={{ maxWidth: '900px', margin: '0 auto 3rem' }}>
        <div className="glass-panel">
          <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <UploadCloud size={20} color="var(--accent-primary)" /> Register New Asset
          </h3>
          {success ? (
            <div style={{ textAlign: 'center', padding: '2.5rem 0' }}>
              <div style={{
                width: '70px', height: '70px', borderRadius: '50%',
                background: 'rgba(16, 185, 129, 0.1)', display: 'flex',
                alignItems: 'center', justifyContent: 'center', margin: '0 auto 1rem'
              }}>
                <Check size={36} color="var(--success)" />
              </div>
              <h2>Asset Registered & Fingerprinted</h2>
              <p className="text-muted" style={{ marginTop: '0.5rem' }}>
                Multi-algorithm fingerprints indexed and active monitoring enabled.
              </p>

              {uploadResult && (
                <div style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.75rem' }}>
                  <div style={{
                    background: 'var(--bg-tertiary)', borderRadius: 'var(--br-lg)',
                    padding: '1rem 1.5rem', width: '100%', maxWidth: '400px',
                    textAlign: 'left', fontSize: '0.85rem', display: 'grid', gap: '0.4rem'
                  }}>
                    <div><strong style={{ color: 'var(--text-muted)' }}>Watermark ID:</strong>{' '}
                      <code style={{ color: 'var(--accent-primary)' }}>{uploadResult.watermark_id}</code>
                    </div>
                    <div><strong style={{ color: 'var(--text-muted)' }}>pHash:</strong>{' '}
                      <code style={{ fontSize: '0.8rem' }}>{uploadResult.fingerprints?.phash || 'N/A'}</code>
                    </div>
                    <div><strong style={{ color: 'var(--text-muted)' }}>dHash:</strong>{' '}
                      <code style={{ fontSize: '0.8rem' }}>{uploadResult.fingerprints?.dhash || 'N/A'}</code>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem' }}>
                    <button
                      className="btn btn-primary"
                      style={{ padding: '0.6rem 1.5rem' }}
                      onClick={() => handleDownloadAsset(uploadResult.asset_id)}
                    >
                      <Download size={18} /> Download Protected File
                    </button>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '0.6rem 1.5rem' }}
                      onClick={() => { setSuccess(false); setFile(null); setTitle(''); setUploadResult(null); }}
                    >
                      Register Another
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <form onSubmit={handleUpload}>
              {error && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: '0.75rem',
                  padding: '1rem', marginBottom: '1.5rem', borderRadius: 'var(--br-lg)',
                  background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)',
                  color: 'var(--danger)', fontSize: '0.9rem'
                }}>
                  <AlertCircle size={18} />
                  <span>{error}</span>
                </div>
              )}

              <div
                className="drop-zone"
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  type="file"
                  style={{ display: 'none' }}
                  ref={fileInputRef}
                  onChange={(e) => { e.target.files && setFile(e.target.files[0]); setError(null); }}
                  accept="video/*,image/*"
                />

                {file ? (
                  <>
                    <FileVideo className="drop-zone-icon" />
                    <h3 style={{ color: 'var(--accent-primary)' }}>{file.name}</h3>
                    <p className="text-muted">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
                  </>
                ) : (
                  <>
                    <UploadCloud className="drop-zone-icon" />
                    <h3>Drag & Drop media here</h3>
                    <p className="text-muted">or click to browse files (MP4, JPG, PNG)</p>
                  </>
                )}
              </div>

              <div style={{ marginTop: '1.5rem', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                <div className="form-group">
                  <label className="form-label">Asset Title / Event Name</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="e.g. Champions League Final 2026 - Highlights"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Rights Policy</label>
                  <select
                    className="form-select"
                    value={rightsPolicy}
                    onChange={(e) => setRightsPolicy(e.target.value)}
                  >
                    <option value="exclusive_broadcast">Exclusive Broadcast (No Social Shares)</option>
                    <option value="region_locked_na">Region Locked (North America Only)</option>
                    <option value="embargo_24h">24-Hour Embargo</option>
                    <option value="permissive">Permissive (Monitor Only)</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                className="btn btn-primary"
                style={{ width: '100%', padding: '0.85rem', marginTop: '1rem' }}
                disabled={!file || !title || isUploading}
              >
                <ShieldCheck size={20} />
                {isUploading ? 'Generating Fingerprints & Embedding Watermark...' : 'Register & Protect Asset'}
              </button>
            </form>
          )}
        </div>
      </div>

      {/* Asset Registry Explorer Section */}
      <div className="glass-panel">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h3>Asset Registry ({assets.length})</h3>
            <p className="text-muted" style={{ fontSize: '0.85rem' }}>Search, filter, inspect, and manage active media assets.</p>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <div style={{ position: 'relative', width: '220px' }}>
              <input
                type="text"
                className="form-input"
                placeholder="Search assets..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{ paddingLeft: '2.2rem', fontSize: '0.85rem' }}
              />
              <Search size={14} style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            </div>

            <select className="form-select" value={typeFilter} onChange={e => setTypeFilter(e.target.value)} style={{ width: '130px', fontSize: '0.85rem' }}>
              <option value="">All Types</option>
              <option value="image">Image</option>
              <option value="video">Video</option>
            </select>

            <select className="form-select" value={policyFilter} onChange={e => setPolicyFilter(e.target.value)} style={{ width: '170px', fontSize: '0.85rem' }}>
              <option value="">All Policies</option>
              <option value="exclusive_broadcast">Exclusive</option>
              <option value="region_locked_na">Region Locked</option>
              <option value="embargo_24h">Embargo 24h</option>
            </select>
          </div>
        </div>

        {/* Table of Assets */}
        <table className="data-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Title</th>
              <th>Watermark ID</th>
              <th>Rights Policy</th>
              <th>Registered</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {assets.length === 0 ? (
              <tr>
                <td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>No assets registered yet.</td>
              </tr>
            ) : (
              assets.map(asset => (
                <tr key={asset.id}>
                  <td>
                    {asset.media_type === 'video' ? <Film size={18} color="var(--accent-secondary)" /> : <ImageIcon size={18} color="var(--accent-primary)" />}
                  </td>
                  <td style={{ fontWeight: 600 }}>{asset.title}</td>
                  <td>
                    <code style={{ fontSize: '0.8rem', background: 'rgba(99, 102, 241, 0.1)', padding: '0.1rem 0.4rem', borderRadius: '4px', color: 'var(--accent-primary)' }}>
                      {asset.watermark_id || 'N/A'}
                    </code>
                  </td>
                  <td>
                    <span style={{ fontSize: '0.8rem', textTransform: 'capitalize' }}>{asset.rights_policy?.replaceAll('_', ' ')}</span>
                  </td>
                  <td style={{ fontSize: '0.85rem' }}>
                    {asset.created_at ? new Date(asset.created_at).toLocaleDateString() : 'N/A'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        onClick={() => handleDownloadAsset(asset.id)}
                        className="btn btn-secondary"
                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
                        title="Download Protected File"
                      >
                        <Download size={14} />
                      </button>
                      <button
                        onClick={() => handleViewDetail(asset.id)}
                        className="btn btn-secondary"
                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
                        title="View Asset Signatures"
                      >
                        <Eye size={14} /> Details
                      </button>
                      <button
                        onClick={() => handleDeleteAsset(asset.id, asset.title)}
                        className="btn"
                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem', background: 'rgba(239, 68, 68, 0.15)', color: 'var(--danger)' }}
                        title="Delete Asset"
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

      {/* Asset Detail Modal */}
      {selectedAssetDetail && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="glass-panel" style={{ width: '550px', padding: '2rem', maxHeight: '90vh', overflowY: 'auto' }}>
            <h2 style={{ marginBottom: '0.5rem' }}>{selectedAssetDetail.title}</h2>
            <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '1.5rem' }}>Asset ID #{selectedAssetDetail.id} — Metadata & Forensic Signatures</p>

            <div style={{ display: 'grid', gap: '1rem', fontSize: '0.9rem' }}>
              <div><strong>Watermark ID:</strong> <code style={{ color: 'var(--accent-primary)' }}>{selectedAssetDetail.watermark_id}</code></div>
              <div><strong>Media Type:</strong> {selectedAssetDetail.media_type}</div>
              <div><strong>Rights Policy:</strong> {selectedAssetDetail.rights_policy}</div>
              <div><strong>Active Incidents:</strong> {selectedAssetDetail.incident_count}</div>
              <div><strong>Primary pHash:</strong> <code style={{ fontSize: '0.8rem' }}>{selectedAssetDetail.fingerprints?.phash || 'N/A'}</code></div>
              <div><strong>dHash:</strong> <code style={{ fontSize: '0.8rem' }}>{selectedAssetDetail.fingerprints?.dhash || 'N/A'}</code></div>
              <div><strong>HSV Color Histogram:</strong> {selectedAssetDetail.fingerprints?.has_histogram ? 'Generated (32-bin HSV)' : 'None'}</div>
              <div><strong>Video Frame Hashes:</strong> {selectedAssetDetail.fingerprints?.video_frames_count || 0} frames sampled</div>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1.5rem' }}>
              <button
                onClick={() => handleDownloadAsset(selectedAssetDetail.id)}
                className="btn btn-primary"
                style={{ flex: 1 }}
              >
                <Download size={16} /> Download Protected File
              </button>
              <button
                onClick={() => setSelectedAssetDetail(null)}
                className="btn btn-secondary"
                style={{ flex: 1 }}
              >
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AssetOnboarding;
