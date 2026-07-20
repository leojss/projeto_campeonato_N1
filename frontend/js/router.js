import { getToken, getUser } from './api.js';
import { renderLogin } from './pages/login.js';
import { renderCompetidores } from './pages/competidores.js';
import { renderApostas } from './pages/apostas.js';
import { renderAdmin } from './pages/admin.js';
import { renderSidebar } from './sidebar.js';

const routes = {
  '#/login': { render: renderLogin, public: true },
  '#/competidores': { render: renderCompetidores },
  '#/apostas': { render: renderApostas },
  '#/admin': { render: renderAdmin, adminOnly: true },
};

const DEFAULT_ROUTE = '#/competidores';

export function navigate(hash) {
  if (window.location.hash === hash) {
    handleRoute();
  } else {
    window.location.hash = hash;
  }
}

export async function handleRoute() {
  const hash = window.location.hash || DEFAULT_ROUTE;
  const route = routes[hash] || routes[DEFAULT_ROUTE];
  const token = getToken();
  const user = getUser();

  const sidebar = document.getElementById('sidebar');
  const main = document.getElementById('main-content');
  const app = document.getElementById('app');

  if (!route.public && !token) {
    sidebar.classList.add('hidden');
    app.classList.add('no-sidebar');
    if (hash !== '#/login') {
      window.location.hash = '#/login';
      return;
    }
    return renderLogin(main);
  }

  if (route.public) {
    sidebar.classList.add('hidden');
    app.classList.add('no-sidebar');
  } else {
    sidebar.classList.remove('hidden');
    app.classList.remove('no-sidebar');
    renderSidebar(sidebar, hash);
  }

  if (route.adminOnly && (!user || user.role !== 'admin')) {
    main.innerHTML = '<div class="alert alert-error">⛔ Acesso negado. Esta área é exclusiva para administradores.</div>';
    return;
  }

  main.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
  try {
    await route.render(main);
  } catch (err) {
    main.innerHTML = `<div class="alert alert-error">❌ ${err.message}</div>`;
  }
}

window.addEventListener('hashchange', handleRoute);
