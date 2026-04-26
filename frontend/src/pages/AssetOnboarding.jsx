import React, { useState, useRef } from 'react';
import { UploadCloud, FileVideo, ShieldCheck, Check } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const AssetOnboarding = () => {
  const [file, setFile] = useState(null);
  const [title, setTitle] = useState('');
  const [rightsPolicy, setRightsPolicy] = useState('exclusive_broadcast');
  const [isUploading, setIsUploading] = useState(false);
  const [success, setSuccess] = useState(false);
  
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

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
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file || !title) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', title);
    formData.append('rights_policy', rightsPolicy);

    try {
      const response = await fetch('http://localhost:8000/api/assets/upload', {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        setSuccess(true);
        setTimeout(() => {
          navigate('/');
        }, 2000);
      }
    } catch (error) {
      console.error("Upload failed", error);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="page-enter">
      <div className="header-actions">
        <div>
          <h1 className="text-gradient">Asset Registration</h1>
          <p className="text-muted">Register official media to generate forensic fingerprints.</p>
        </div>
      </div>

      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        <div className="glass-panel">
          {success ? (
            <div style={{ textAlign: 'center', padding: '3rem 0' }}>
              <div style={{ 
                width: '80px', height: '80px', borderRadius: '50%', 
                background: 'rgba(16, 185, 129, 0.1)', display: 'flex', 
                alignItems: 'center', justifyContent: 'center', margin: '0 auto 1.5rem' 
              }}>
                <Check size={40} color="var(--success)" />
              </div>
              <h2>Asset Protected</h2>
              <p className="text-muted" style={{ marginTop: '0.5rem' }}>
                Fingerprint generated and added to active monitoring.
              </p>
            </div>
          ) : (
            <form onSubmit={handleUpload}>
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
                  onChange={(e) => e.target.files && setFile(e.target.files[0])}
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

              <div style={{ marginTop: '2rem', display: 'grid', gap: '1.5rem' }}>
                <div className="form-group">
                  <label className="form-label">Asset Title / Event Name</label>
                  <input 
                    type="text" 
                    className="form-input" 
                    placeholder="e.g. Champions League Final 2026 - Highlghts"
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

                <button 
                  type="submit" 
                  className="btn btn-primary" 
                  style={{ width: '100%', padding: '1rem', marginTop: '1rem' }}
                  disabled={!file || !title || isUploading}
                >
                  <ShieldCheck size={20} />
                  {isUploading ? 'Generating Fingerprint...' : 'Register & Protect Asset'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default AssetOnboarding;
