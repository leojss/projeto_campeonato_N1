const API_BASE = '/api';

export function getToken() {
  return localStorage.getItem('n1_token');
}

export function setToken(token) {
  if (token) localStorage.setItem('n1_token', token);
  else localStorage.removeItem('n1_token');
}

export function getUser() {
  const raw = localStorage.getItem('n1_user');
  return raw ? JSON.parse(raw) : null;
}

export function setUser(user) {
  if (user) localStorage.setItem('n1_user', JSON.stringify(user));
  else localStorage.removeItem('n1_user');
}

async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let fetchBody = body;
  if (body !== undefined && !isForm) {
    headers['Content-Type'] = 'application/json';
    fetchBody = JSON.stringify(body);
  }

  const res = await fetch(`${API_BASE}${path}`, { method, headers, body: fetchBody });

  if (res.status === 401) {
    setToken(null);
    setUser(null);
    if (window.location.hash !== '#/login') {
      window.location.hash = '#/login';
    }
    throw new Error('Sessão expirada. Faça login novamente.');
  }

  const contentType = res.headers.get('content-type') || '';
  const isJson = contentType.includes('application/json');
  const data = isJson ? await res.json().catch(() => null) : await res.blob();

  if (!res.ok) {
    const detail = (data && data.detail) ? data.detail : `Erro ${res.status}`;
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }

  return data;
}

export const api = {
  get: (path) => request(path),
  post: (path, body, opts = {}) => request(path, { method: 'POST', body, ...opts }),
  patch: (path, body) => request(path, { method: 'PATCH', body }),
  delete: (path) => request(path, { method: 'DELETE' }),
};
