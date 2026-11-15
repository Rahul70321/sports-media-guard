import { useState, useEffect } from 'react';
import { HashRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Shield, Upload, Activity, AlertTriangle, Settings as SettingsIcon, LogOut, Key } from 'lucide-react';

import Dashboard from './pages/Dashboard';
import Monitoring from './pages/Monitoring';
import AssetOnboarding from './pages/AssetOnboarding';
import Settings from './pages/Settings';
import IncidentReview from './pages/IncidentReview';
import { apiFetch, API_URL } from './api';

const Sidebar = ({ user, onOpenLogin, onLogout }) => {
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
        <Link to="/monitoring" className={`nav-link ${location.pathname === '/monitoring' ? 'active' : ''}`}>
          <Activity size={20} />
          <span>Monitoring</span>
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

      {/* User Auth Profile Badge */}
      <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid var(--glass-border)' }}>
        {user ? (
          <div style={{ background: 'var(--bg-tertiary)', padding: '0.75rem', borderRadius: 'var(--br-md)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ overflow: 'hidden' }}>
              <div style={{ fontWeight: 600, fontSize: '0.85rem', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>{user.full_name}</div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{user.email}</div>
            </div>
            <button onClick={onLogout} title="Log Out" style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0.25rem' }}>
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenLogin}
            className="btn btn-secondary"
            style={{ width: '100%', justifyContent: 'flex-start', padding: '0.6rem 0.8rem', fontSize: '0.85rem' }}
          >
            <Key size={16} color="var(--accent-primary)" />
            <span>Sign In / Auth</span>
          </button>
        )}
      </div>
    </div>
  );
};

const AuthModal = ({ isOpen, onClose, onLoginSuccess, initialError }) => {
  const [authMode, setAuthMode] = useState('login'); // 'login' | 'register' | 'forgot' | 'reset'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [fullName, setFullName] = useState('');
  const [error, setError] = useState(initialError || null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [socialLoading, setSocialLoading] = useState(null); // tracks which provider is loading

  useEffect(() => {
    if (initialError) {
      setError(initialError);
    }
  }, [initialError]);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setLoading(true);

    const endpoint = authMode === 'register' ? '/api/auth/register' : '/api/auth/login';
    const payload = authMode === 'register' ? { email, password, full_name: fullName || 'User', role: 'admin' } : { email, password };

    try {
      const res = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Authentication failed');

      localStorage.setItem('token', data.access_token);
      onLoginSuccess(data.user || { email, full_name: fullName || 'User' });
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setLoading(true);

    try {
      const res = await apiFetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to request password reset');

      if (data.reset_token) {
        setResetToken(data.reset_token);
        setSuccessMessage(`Reset token generated (offline dev mode): ${data.reset_token}`);
      } else {
        setSuccessMessage(data.message || 'If that email is registered, a reset token has been issued.');
      }
      setAuthMode('reset');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setLoading(true);

    try {
      const res = await apiFetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: resetToken, new_password: newPassword })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Password reset failed');

      setSuccessMessage('Password updated successfully! You can now sign in with your new password.');
      setPassword('');
      setNewPassword('');
      setResetToken('');
      setAuthMode('login');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSocialLogin = async (provider, useOAuth = false) => {
    setError(null);
    if (provider === 'google' && useOAuth) {
      window.location.assign(`${API_URL}/api/auth/google/start`);
      return;
    }

    const socialProvider = provider.replace('_demo', '');
    setSocialLoading(provider);
    try {
      const res = await apiFetch('/api/auth/social', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: socialProvider })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `${socialProvider} sign-in failed`);

      localStorage.setItem('token', data.access_token);
      onLoginSuccess(data.user);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setSocialLoading(null);
    }
  };

  const handleDirectAdminLogin = async () => {
    setError(null);
    setLoading(true);
    try {
      const res = await apiFetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'admin@sportsguard.io', password: 'admin123' })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Admin login failed');

      localStorage.setItem('token', data.access_token);
      onLoginSuccess(data.user || { email: 'admin@sportsguard.io', full_name: 'Sports Media Admin', role: 'admin' });
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDemoFill = (type) => {
    if (type === 'admin') {
      setEmail('admin@sportsguard.io');
      setPassword('admin123');
      setError(null);
    }
  };

  // Social provider config with brand colors and SVG icons
  const socialProviders = [
    {
      id: 'google',
      label: 'Continue with Google',
      color: '#ffffff',
      textColor: '#3c4043',
      border: '1px solid rgba(255,255,255,0.2)',
      hoverBg: '#f8f9fa',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24">
          <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
          <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
          <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A10.96 10.96 0 001 12c0 1.77.42 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"/>
          <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
        </svg>
      )
    },
    {
      id: 'facebook',
      label: 'Continue with Facebook',
      color: '#1877F2',
      textColor: '#ffffff',
      border: 'none',
      hoverBg: '#166FE5',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
          <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
        </svg>
      )
    },
    {
      id: 'instagram',
      label: 'Continue with Instagram',
      color: 'linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888)',
      textColor: '#ffffff',
      border: 'none',
      hoverBg: 'linear-gradient(45deg, #e08525, #d55a30, #cd1f38, #bd1d5c, #ad1580)',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
          <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
        </svg>
      )
    },
    {
      id: 'gmail',
      label: 'Continue with Gmail',
      color: '#EA4335',
      textColor: '#ffffff',
      border: 'none',
      hoverBg: '#D93025',
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="white">
          <path d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 010 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.91 1.528-1.145C21.69 2.28 24 3.434 24 5.457z"/>
        </svg>
      )
    }
  ];

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
    }}>
      <div className="glass-panel" style={{ width: '420px', padding: '2rem', maxHeight: '90vh', overflowY: 'auto' }}>
        <h2 style={{ marginBottom: '0.5rem' }}>
          {authMode === 'register' ? 'Create Account' : authMode === 'forgot' ? 'Forgot Password' : authMode === 'reset' ? 'Set New Password' : 'Sign In to SportsGuard'}
        </h2>
        <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '1.5rem' }}>
          {authMode === 'register' ? 'Register as a Rights Analyst or Admin' :
           authMode === 'forgot' ? 'Enter your registered email to receive a password reset token' :
           authMode === 'reset' ? 'Enter the reset token and choose your new password' :
           'Choose your preferred sign-in method'}
        </p>

        {error && (
          <div style={{ padding: '0.75rem', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '1rem', wordBreak: 'break-word' }}>
            <div style={{ fontWeight: 600, marginBottom: '0.3rem' }}>{error}</div>
            {error.toLowerCase().includes('client secret') && (
              <>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.6rem', lineHeight: '1.4' }}>
                  The Google Client Secret in <code>.env</code> is invalid or expired. You can use instant sign-in without Google Cloud credentials:
                </div>
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ width: '100%', padding: '0.5rem', fontSize: '0.8rem', justifyContent: 'center', marginBottom: '0.2rem' }}
                  onClick={() => handleSocialLogin('google', false)}
                  disabled={socialLoading !== null}
                >
                  ⚡ Continue with Instant Google Analyst Access
                </button>
              </>
            )}
          </div>
        )}

        {successMessage && (
          <div style={{ padding: '0.75rem', borderRadius: '8px', background: 'rgba(34, 197, 94, 0.1)', border: '1px solid rgba(34, 197, 94, 0.2)', color: 'var(--success, #22c55e)', fontSize: '0.85rem', marginBottom: '1rem', wordBreak: 'break-word' }}>
            {successMessage}
          </div>
        )}

        {/* Quick Demo Credentials Preset - only in login mode */}
        {authMode === 'login' && (
          <div style={{ background: 'var(--bg-tertiary, rgba(255,255,255,0.05))', padding: '0.75rem', borderRadius: 'var(--br-md, 8px)', marginBottom: '1.25rem', border: '1px solid var(--glass-border, rgba(255,255,255,0.08))' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.4rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Instant Access (No Credentials Required):
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ flex: 1, padding: '0.4rem 0.5rem', fontSize: '0.75rem', justifyContent: 'center' }}
                onClick={handleDirectAdminLogin}
                disabled={loading}
              >
                ⚡ 1-Click Admin
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ flex: 1, padding: '0.4rem 0.5rem', fontSize: '0.75rem', justifyContent: 'center' }}
                onClick={() => handleSocialLogin('analyst', false)}
                disabled={socialLoading !== null}
              >
                ⚡ 1-Click Analyst
              </button>
            </div>
          </div>
        )}

        {/* Social Login Buttons - only in login mode */}
        {authMode === 'login' && (
          <>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '1.5rem' }}>
              {socialProviders.map((provider) => (
                <button
                  key={provider.id}
                  onClick={() => handleSocialLogin(provider.id, provider.id === 'google')}
                  disabled={socialLoading !== null}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '0.7rem',
                    width: '100%',
                    padding: '0.7rem 1rem',
                    borderRadius: 'var(--br-md, 8px)',
                    border: provider.border,
                    background: provider.color,
                    color: provider.textColor,
                    fontSize: '0.9rem',
                    fontWeight: 600,
                    cursor: socialLoading ? 'not-allowed' : 'pointer',
                    opacity: socialLoading && socialLoading !== provider.id ? 0.5 : 1,
                    transition: 'all 0.2s ease',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)',
                    position: 'relative',
                    overflow: 'hidden',
                  }}
                  onMouseEnter={(e) => {
                    if (!socialLoading) {
                      e.currentTarget.style.background = provider.hoverBg;
                      e.currentTarget.style.transform = 'translateY(-1px)';
                      e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.2)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = provider.color;
                    e.currentTarget.style.transform = 'translateY(0)';
                    e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)';
                  }}
                >
                  {socialLoading === provider.id ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" style={{ animation: 'spin 1s linear infinite' }}>
                        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" fill="none" strokeDasharray="31.4 31.4" strokeLinecap="round" />
                      </svg>
                      Connecting...
                    </span>
                  ) : (
                    <>
                      {provider.icon}
                      {provider.label}
                    </>
                  )}
                </button>
              ))}
            </div>

            {/* Divider */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: '1rem',
              margin: '0 0 1.5rem', color: 'var(--text-muted)', fontSize: '0.8rem'
            }}>
              <div style={{ flex: 1, height: '1px', background: 'var(--glass-border, rgba(255,255,255,0.1))' }} />
              <span>or continue with email</span>
              <div style={{ flex: 1, height: '1px', background: 'var(--glass-border, rgba(255,255,255,0.1))' }} />
            </div>
          </>
        )}

        {/* Login & Register Form */}
        {(authMode === 'login' || authMode === 'register') && (
          <form onSubmit={handleSubmit}>
            {authMode === 'register' && (
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input type="text" className="form-input" value={fullName} onChange={e => setFullName(e.target.value)} placeholder="Full Name" required />
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Email</label>
              <input type="email" className="form-input" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@example.com" required />
            </div>
            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label className="form-label">Password</label>
                {authMode === 'login' && (
                  <span
                    onClick={() => { setAuthMode('forgot'); setError(null); setSuccessMessage(null); }}
                    style={{ color: 'var(--accent-primary)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 500 }}
                  >
                    Forgot password?
                  </span>
                )}
              </div>
              <input type="password" className="form-input" value={password} onChange={e => setPassword(e.target.value)} placeholder="Password" required />
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }} disabled={loading}>
              {loading ? 'Processing...' : (authMode === 'register' ? 'Register' : 'Sign In with Email')}
            </button>
          </form>
        )}

        {/* Forgot Password Request Form */}
        {authMode === 'forgot' && (
          <form onSubmit={handleForgotPassword}>
            <div className="form-group">
              <label className="form-label">Your Account Email</label>
              <input type="email" className="form-input" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@example.com" required />
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }} disabled={loading}>
              {loading ? 'Requesting Reset...' : 'Send Password Reset Token'}
            </button>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem', fontSize: '0.85rem' }}>
              <span
                onClick={() => { setAuthMode('login'); setError(null); setSuccessMessage(null); }}
                style={{ color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: 600 }}
              >
                ← Back to Sign In
              </span>
              <span
                onClick={() => { setAuthMode('reset'); setError(null); }}
                style={{ color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                Already have a token?
              </span>
            </div>
          </form>
        )}

        {/* Reset Password Submission Form */}
        {authMode === 'reset' && (
          <form onSubmit={handleResetPassword}>
            <div className="form-group">
              <label className="form-label">Reset Token</label>
              <input type="text" className="form-input" value={resetToken} onChange={e => setResetToken(e.target.value)} placeholder="Paste 32-character reset token" required />
            </div>
            <div className="form-group">
              <label className="form-label">New Password (minimum 8 characters)</label>
              <input type="password" className="form-input" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="Enter new password" minLength={8} required />
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }} disabled={loading}>
              {loading ? 'Updating Password...' : 'Set New Password'}
            </button>
            <div style={{ textAlign: 'center', marginTop: '1rem', fontSize: '0.85rem' }}>
              <span
                onClick={() => { setAuthMode('login'); setError(null); setSuccessMessage(null); }}
                style={{ color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: 600 }}
              >
                ← Back to Sign In
              </span>
            </div>
          </form>
        )}

        {/* Switch between Login and Register */}
        {(authMode === 'login' || authMode === 'register') && (
          <div style={{ textAlign: 'center', marginTop: '1rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            {authMode === 'register' ? 'Already have an account?' : "Don't have an account?"}{' '}
            <span
              onClick={() => { setAuthMode(authMode === 'register' ? 'login' : 'register'); setError(null); setSuccessMessage(null); }}
              style={{ color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: 600 }}
            >
              {authMode === 'register' ? 'Sign In' : 'Register'}
            </span>
          </div>
        )}

        <button onClick={onClose} style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '1.2rem' }}>✕</button>
      </div>

      {/* Spinner keyframe animation */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};


function App() {
  const [user, setUser] = useState(null);
  const [authError, setAuthError] = useState(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  useEffect(() => {
    const hash = window.location.hash || '';
    const queryPart = hash.includes('?') ? hash.split('?')[1] : '';
    const params = new URLSearchParams(queryPart);
    const oauthToken = params.get('oauth_token');
    const err = params.get('auth_error');

    if (oauthToken) {
      localStorage.setItem('token', oauthToken);
      window.history.replaceState({}, document.title, `${window.location.pathname}#/?`);
    } else if (err) {
      setAuthError(decodeURIComponent(err));
      setIsAuthOpen(true);
      window.history.replaceState({}, document.title, `${window.location.pathname}#/?`);
    }
  }, []);

  useEffect(() => {
    // Validate stored token on startup
    const token = localStorage.getItem('token');
    if (token) {
      apiFetch('/api/auth/me')
        .then(res => res.ok ? res.json() : null)
        .then(data => {
          if (data) setUser(data);
          else localStorage.removeItem('token');
        })
        .catch(() => {});
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    setUser(null);
  };

  return (
    <Router>
      <div className="app-container">
        <Sidebar user={user} onOpenLogin={() => { setAuthError(null); setIsAuthOpen(true); }} onLogout={handleLogout} />
        <div className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard user={user} onOpenLogin={() => { setAuthError(null); setIsAuthOpen(true); }} />} />
            <Route path="/monitoring" element={<Monitoring user={user} />} />
            <Route path="/upload" element={<AssetOnboarding user={user} />} />
            <Route path="/incidents" element={<IncidentReview user={user} />} />
            <Route path="/settings" element={<Settings user={user} />} />
          </Routes>
        </div>
      </div>
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => { setIsAuthOpen(false); setAuthError(null); }}
        onLoginSuccess={setUser}
        initialError={authError}
      />
    </Router>
  );
}

export default App;
