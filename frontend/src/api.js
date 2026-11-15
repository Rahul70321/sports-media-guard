const configuredUrl = import.meta.env.VITE_API_URL;
const storedUrl = typeof window !== 'undefined' ? localStorage.getItem('custom_api_url') : null;
const isLocalhost = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

const API_URL = storedUrl || configuredUrl || (isLocalhost ? 'http://localhost:8000' : 'https://sports-media-guard.onrender.com');

export const apiFetch = (endpoint, options = {}) => {
  const token = localStorage.getItem('token');
  const headers = new Headers(options.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return fetch(`${API_URL}${endpoint}`, { ...options, headers });
};

export { API_URL };
