import { getUser, setToken, setUser } from './api.js';
import { navigate } from './router.js';

const NAV_ITEMS = [
  { hash: '#/competidores', label: '📊 Ranking Geral' },
  { hash: '#/apostas', label: '🎲 Cadastrar Apostas' },
  { hash: '#/admin', label: '⚙️ Painel Administrativo', adminOnly: true },
];

export function renderSidebar(container, currentHash) {
  const user = getUser();

  container.innerHTML = `
    <div class="sidebar-header">
      <img src="/assets/images/logo.png" class="sidebar-logo" alt="logo" onerror="this.style.display='none'">
      <h3>Campeonato N1</h3>
      <span class="sidebar-version">v2.0.0</span>
    </div>
    <div class="sidebar-user">
      <div>👤 <strong>${user?.full_name || user?.email || ''}</strong></div>
      <div class="sidebar-role">${user?.role === 'admin' ? '🛡️ Administrador' : '🏆 Competidor'}</div>
    </div>
    <nav class="sidebar-nav">
      ${NAV_ITEMS.filter((i) => !i.adminOnly || user?.role === 'admin')
        .map((i) => `<button class="nav-btn ${currentHash === i.hash ? 'active' : ''}" data-hash="${i.hash}">${i.label}</button>`)
        .join('')}
    </nav>
    <button class="nav-btn logout-btn" id="btn-logout">🚪 Sair</button>
  `;

  container.querySelectorAll('.nav-btn[data-hash]').forEach((btn) => {
    btn.addEventListener('click', () => navigate(btn.dataset.hash));
  });

  container.querySelector('#btn-logout').addEventListener('click', () => {
    setToken(null);
    setUser(null);
    navigate('#/login');
  });
}
