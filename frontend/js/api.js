const API_BASE = 'http://localhost:8000';

function _getToken() {
  return sessionStorage.getItem('token') || localStorage.getItem('token');
}

function _clearAuth() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  sessionStorage.removeItem('token');
  sessionStorage.removeItem('user');
}

async function api(path, options = {}) {
  const token = _getToken();
  const headers = { ...options.headers };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    _clearAuth();
    window.location.href = '/';
  }
  return res.json();
}
