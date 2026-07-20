import { api, setToken, setUser } from '../api.js';
import { navigate } from '../router.js';

export function renderLogin(main) {
  main.innerHTML = `
    <div class="login-wrap">
      <div class="login-card">
        <img src="/assets/images/logo.png" class="login-logo" alt="logo" onerror="this.style.display='none'">
        <h1 class="login-title">Campeonato N1</h1>
        <p class="login-subtitle">Competição Interna — Faça login para continuar</p>
        <form id="login-form">
          <label>📧 E-mail</label>
          <input type="email" id="login-email" placeholder="seu@email.com" required autocomplete="username">
          <label>🔑 Senha</label>
          <input type="password" id="login-password" placeholder="••••••••" required autocomplete="current-password">
          <div id="login-alert"></div>
          <br>
          <button type="submit" class="btn btn-primary btn-block">Entrar →</button>
        </form>
        <p class="login-footer">Não possui acesso? Fale com o administrador da competição.</p>
      </div>
    </div>
  `;

  const form = document.getElementById('login-form');
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const alertBox = document.getElementById('login-alert');
    alertBox.innerHTML = '';
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const submitBtn = form.querySelector('button[type="submit"]');

    if (!email || !password) {
      alertBox.innerHTML = '<div class="alert alert-error">⚠️ Preencha e-mail e senha.</div>';
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Autenticando...';
    try {
      const data = await api.post('/auth/login', { email, password });
      setToken(data.access_token);
      setUser(data.user);
      navigate('#/competidores');
    } catch (err) {
      alertBox.innerHTML = `<div class="alert alert-error">❌ ${err.message}</div>`;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Entrar →';
    }
  });
}
