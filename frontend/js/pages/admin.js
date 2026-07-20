import { api } from '../api.js';
import { formatOdd, formatBrDate, formatBrDateTime, formatBetStatus, formatRoundStatus } from '../format.js';

let activeTab = 'revisao';
const TABS = [
  { key: 'revisao', label: '🔍 Revisão de Apostas' },
  { key: 'rodada', label: '🗓️ Gestão de Rodada' },
  { key: 'liquidacao', label: '💸 Liquidação' },
  { key: 'competidores', label: '👥 Competidores' },
  { key: 'logs', label: '📊 Logs de Auditoria' },
];

const RENDERERS = {
  revisao: renderRevisao,
  rodada: renderGestaoRodada,
  liquidacao: renderLiquidacao,
  competidores: renderAdminCompetidores,
  logs: renderLogs,
};

export async function renderAdmin(main) {
  main.innerHTML = `
    <h2>⚙️ Painel Administrativo</h2>
    <div class="tabs">
      ${TABS.map((t) => `<button class="tab-btn ${activeTab === t.key ? 'active' : ''}" data-tab="${t.key}">${t.label}</button>`).join('')}
    </div>
    <div id="admin-tab-content"><div class="spinner-wrap"><div class="spinner"></div></div></div>
  `;

  main.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      activeTab = btn.dataset.tab;
      renderAdmin(main);
    });
  });

  const content = document.getElementById('admin-tab-content');
  await RENDERERS[activeTab](content);
}

// --- Revisão de apostas -----------------------------------------------

async function renderRevisao(container) {
  const pending = await api.get('/bets/pending-review');
  if (!pending.length) {
    container.innerHTML = '<div class="alert alert-success">✅ Nenhuma aposta pendente de revisão!</div>';
    return;
  }

  container.innerHTML = `<div class="alert alert-info"><strong>${pending.length} aposta(s)</strong> aguardando revisão.</div><div id="pending-list"></div>`;
  const listEl = document.getElementById('pending-list');

  listEl.innerHTML = pending.map((bet) => {
    const descricao = bet.selections && bet.selections[0] ? bet.selections[0].description : null;
    return `
    <div class="expander" data-bet-id="${bet.id}">
      <div class="expander-header">📋 ${bet.competitor_name} | ${formatBrDate(bet.target_date)} | Odd ${formatOdd(bet.total_odd)} | ${formatBetStatus(bet.status)}</div>
      <div class="expander-body">
        <div class="two-col">
          <div>
            <div><strong>Competidor:</strong> ${bet.competitor_name}</div>
            <div><strong>Data:</strong> ${formatBrDate(bet.target_date)}</div>
            <div><strong>Odd Total:</strong> ${formatOdd(bet.total_odd)}</div>
          </div>
          <div>
            <div><strong>Confiança IA:</strong> ${bet.ocr_confidence ? Math.round(bet.ocr_confidence * 100) + '%' : 'N/D'}</div>
            <div><strong>Status:</strong> ${formatBetStatus(bet.status)}</div>
            ${bet.notes ? `<div class="text-muted">📝 ${bet.notes}</div>` : ''}
          </div>
        </div>
        <div class="bet-image-wrap"><img class="bet-image lazy-image" data-bet-id="${bet.id}" alt="Comprovante"></div>
        <strong>🎯 Aposta (lida pela IA):</strong>
        <p>${descricao || '<span class="text-muted">Não identificada pela IA.</span>'}</p>
        <label>Ajustar Odd Total</label>
        <input type="number" step="0.01" min="1" class="adj-odd" value="${bet.total_odd}">
        <label>Observações (opcional)</label>
        <textarea class="adj-notes"></textarea>
        <div class="two-col">
          <button class="btn btn-primary btn-approve">✅ Aprovar</button>
          <button class="btn btn-danger btn-reject">❌ Rejeitar</button>
        </div>
      </div>
    </div>
  `;
  }).join('');

  listEl.querySelectorAll('.expander-header').forEach((h) => h.addEventListener('click', () => h.parentElement.classList.toggle('open')));

  listEl.querySelectorAll('.expander').forEach((exp) => {
    const betId = exp.dataset.betId;
    exp.querySelector('.btn-approve').addEventListener('click', async (ev) => {
      ev.stopPropagation();
      const odd = parseFloat(exp.querySelector('.adj-odd').value);
      const notes = exp.querySelector('.adj-notes').value;
      try {
        await api.post(`/bets/${betId}/approve`, { total_odd: odd, notes: notes || null });
        await renderRevisao(container);
      } catch (err) {
        alert(err.message);
      }
    });
    exp.querySelector('.btn-reject').addEventListener('click', async (ev) => {
      ev.stopPropagation();
      const notes = exp.querySelector('.adj-notes').value;
      try {
        await api.post(`/bets/${betId}/reject`, { notes: notes || null });
        await renderRevisao(container);
      } catch (err) {
        alert(err.message);
      }
    });
  });

  listEl.querySelectorAll('.lazy-image').forEach(async (img) => {
    try {
      const blob = await api.get(`/bets/${img.dataset.betId}/image`);
      img.src = URL.createObjectURL(blob);
    } catch {
      const msg = document.createElement('div');
      msg.className = 'text-muted';
      msg.textContent = 'Não foi possível carregar a imagem do comprovante.';
      img.replaceWith(msg);
    }
  });
}

// --- Gestão de rodada ---------------------------------------------------

async function renderGestaoRodada(container) {
  const roundsData = await api.get('/rounds');
  const active = roundsData.active_round_id ? roundsData.rounds.find((r) => r.id === roundsData.active_round_id) : null;

  let activeHtml;
  if (active) {
    activeHtml = `
      <div class="alert alert-success"><strong>Rodada ativa:</strong> Semana ${active.week_number} (${formatBrDate(active.start_date)} – ${formatBrDate(active.end_date)})</div>
      <div>Status: ${formatRoundStatus(active.status)}</div>
      <div class="two-col">
        ${active.status === 'open' ? '<button class="btn btn-primary" id="btn-close-round">🔴 Fechar Rodada</button>' : '<div></div>'}
        ${active.status === 'closed' ? '<button class="btn btn-primary" id="btn-finalize-round">🏆 Finalizar e Calcular Vencedor</button>' : '<div></div>'}
      </div>
    `;
  } else {
    activeHtml = `
      <div class="alert alert-warning">Nenhuma rodada ativa no momento.</div>
      <button class="btn btn-primary" id="btn-create-round">🟢 Criar Nova Rodada</button>
    `;
  }

  container.innerHTML = `
    <h3>🗓️ Gestão de Rodada</h3>
    ${activeHtml}
    <hr>
    <strong>Histórico de Rodadas</strong>
    <div>${roundsData.rounds.map((r) => `<div>- Semana ${r.week_number} (${formatBrDate(r.start_date)} – ${formatBrDate(r.end_date)}) | ${formatRoundStatus(r.status)}</div>`).join('')}</div>
    <div id="round-action-alert"></div>
  `;

  const alertBox = document.getElementById('round-action-alert');

  document.getElementById('btn-close-round')?.addEventListener('click', async () => {
    try {
      await api.post(`/rounds/${active.id}/close`, {});
      await renderGestaoRodada(container);
    } catch (err) {
      alertBox.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
    }
  });

  document.getElementById('btn-finalize-round')?.addEventListener('click', async () => {
    try {
      const res = await api.post(`/rounds/${active.id}/finalize`, {});
      await renderGestaoRodada(container);
      alert(res.winner_name ? `🏆 Vencedor: ${res.winner_name}!` : 'Nenhum vencedor determinado (sem apostas liquidadas).');
    } catch (err) {
      alertBox.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
    }
  });

  document.getElementById('btn-create-round')?.addEventListener('click', async () => {
    try {
      await api.post('/rounds', {});
      await renderGestaoRodada(container);
    } catch (err) {
      alertBox.innerHTML = `<div class="alert alert-error">${err.message}</div>`;
    }
  });
}

// --- Liquidação -----------------------------------------------------------

async function renderLiquidacao(container) {
  container.innerHTML = `
    <h3>💸 Liquidação de Apostas</h3>
    <h4>🤖 Resolvedor Automático por IA</h4>
    <p>Esta ferramenta consulta os resultados reais dos jogos na web em tempo real usando inteligência artificial (Gemini + Google Search) e resolve as seleções e apostas pendentes.</p>
    <button class="btn btn-secondary btn-block" id="btn-auto-settle">🤖 Executar Liquidador Automático</button>
    <div id="auto-settle-result"></div>
    <hr>
    <div id="approved-bets-list"><div class="spinner-wrap"><div class="spinner"></div></div></div>
  `;

  document.getElementById('btn-auto-settle').addEventListener('click', async () => {
    const btn = document.getElementById('btn-auto-settle');
    const resultBox = document.getElementById('auto-settle-result');
    btn.disabled = true;
    btn.textContent = 'Conferindo jogos e liquidando apostas com a IA...';
    try {
      const results = await api.post('/admin/settlements/auto-run', {});
      let html = `<div class="alert alert-success">✅ Concluído! Seleções analisadas: ${results.selections_checked} | Seleções resolvidas: ${results.selections_resolved} | Apostas liquidadas: ${results.bets_settled}</div>`;
      if (results.quota_warning) {
        html += `<div class="alert alert-warning">⚠️ <strong>Limite de Cota do Gemini Atingido:</strong> A sua chave de API gratuita do Gemini excedeu o limite total de uso diário ou mensal permitido pelo Google AI Studio.<br><br>
          <strong>Como resolver:</strong><br>
          1. Acesse o Google AI Studio e ative o faturamento (Billing) para migrar ao plano Pay-as-you-go.<br>
          2. Ou gere uma nova chave de API gratuita em outra conta do Google e atualize seu <code>.env</code>.<br>
          3. Enquanto isso, você pode <strong>liquidar manualmente</strong> as apostas da rodada atual utilizando o painel abaixo!</div>`;
      }
      html += `<div class="expander open"><div class="expander-header">Ver logs detalhados do resolvedor</div><div class="expander-body"><pre class="log-pre">${(results.logs || []).join('\n')}</pre></div></div>`;
      resultBox.innerHTML = html;
      await loadApprovedBets();
    } catch (err) {
      resultBox.innerHTML = `<div class="alert alert-error">❌ Erro ao executar o resolvedor: ${err.message}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = '🤖 Executar Liquidador Automático';
    }
  });

  async function loadApprovedBets() {
    const listEl = document.getElementById('approved-bets-list');
    listEl.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    const bets = await api.get('/admin/approved-bets');
    if (!bets.length) {
      listEl.innerHTML = '<div class="alert alert-info">Nenhuma aposta aprovada aguardando liquidação.</div>';
      return;
    }
    listEl.innerHTML = `<div class="alert alert-info"><strong>${bets.length}</strong> aposta(s) aguardando liquidação.</div>` +
      bets.map((bet) => {
        const descricao = bet.selections && bet.selections[0] ? bet.selections[0].description : null;
        return `
        <div class="expander" data-bet-id="${bet.id}">
          <div class="expander-header">💰 ${bet.competitor_name} | ${formatBrDate(bet.target_date)} | Odd ${formatOdd(bet.total_odd)}</div>
          <div class="expander-body">
            <strong>🎯 Aposta:</strong>
            <p>${descricao || '<span class="text-muted">Não identificada pela IA.</span>'}</p>
            <label>Resultado:</label>
            <div class="radio-row">
              <label><input type="radio" name="outcome-${bet.id}" value="win" checked> 🏆 Ganhou</label>
              <label><input type="radio" name="outcome-${bet.id}" value="loss"> 💸 Perdeu</label>
              <label><input type="radio" name="outcome-${bet.id}" value="void"> ↩️ Anulada</label>
            </div>
            <button class="btn btn-primary btn-block btn-settle">💾 Liquidar</button>
          </div>
        </div>`;
      }).join('');

    listEl.querySelectorAll('.expander-header').forEach((h) => h.addEventListener('click', () => h.parentElement.classList.toggle('open')));
    listEl.querySelectorAll('.btn-settle').forEach((btn) => {
      btn.addEventListener('click', async (ev) => {
        ev.stopPropagation();
        const exp = btn.closest('.expander');
        const betId = exp.dataset.betId;
        const outcome = exp.querySelector(`input[name="outcome-${betId}"]:checked`).value;
        const outcomeLabel = outcome === 'win' ? '🏆 Ganhou' : outcome === 'loss' ? '💸 Perdeu' : '↩️ Anulada';
        try {
          await api.post('/admin/settlements', { bet_id: betId, outcome });
          alert(`Aposta liquidada: ${outcomeLabel}`);
          await loadApprovedBets();
        } catch (err) {
          alert(err.message);
        }
      });
    });
  }

  await loadApprovedBets();
}

// --- Cadastro de competidores --------------------------------------------

async function renderAdminCompetidores(container) {
  container.innerHTML = `
    <h3>👥 Cadastro de Competidores</h3>
    <div id="cadastro-alert"></div>
    <form id="cadastro-form">
      <label>Nome completo</label>
      <input type="text" id="c-full-name" required>
      <label>Nome de exibição</label>
      <input type="text" id="c-display-name">
      <p class="text-muted">O competidor será cadastrado localmente no banco para ranking e controle de apostas.</p>
      <button type="submit" class="btn btn-primary">Cadastrar Competidor</button>
    </form>
  `;

  document.getElementById('cadastro-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const alertBox = document.getElementById('cadastro-alert');
    const fullName = document.getElementById('c-full-name').value.trim();
    const displayName = document.getElementById('c-display-name').value.trim();
    if (!fullName) return;
    try {
      const res = await api.post('/competitors', { full_name: fullName, display_name: displayName || null });
      alertBox.innerHTML = `<div class="alert alert-success">✅ Competidor '${res.display_name}' cadastrado com sucesso!</div>`;
      ev.target.reset();
    } catch (err) {
      alertBox.innerHTML = `<div class="alert alert-error">❌ Erro ao cadastrar competidor: ${err.message}</div>`;
    }
  });
}

// --- Logs de auditoria ------------------------------------------------------

async function renderLogs(container) {
  container.innerHTML = `
    <h3>📊 Logs de Auditoria</h3>
    <div class="two-col">
      <div>
        <label>Filtrar por ação</label>
        <select id="log-action-filter">
          ${['Todas', 'LOGIN', 'BET_SUBMITTED', 'BET_REJECTED', 'ROUND_CLOSED', 'WINNER_DEFINED', 'BET_MANUAL_ADJUST', 'UPLOAD_BLOCKED', 'LIMIT_EXCEEDED', 'DEADLINE_EXCEEDED'].map((a) => `<option value="${a}">${a}</option>`).join('')}
        </select>
      </div>
      <div>
        <label>Limite de registros</label>
        <input type="number" id="log-limit" min="10" max="500" value="100">
      </div>
    </div>
    <div id="logs-list"></div>
  `;

  async function loadLogs() {
    const listEl = document.getElementById('logs-list');
    listEl.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    const action = document.getElementById('log-action-filter').value;
    const limit = document.getElementById('log-limit').value;
    const logs = await api.get(`/admin/audit-logs?action=${encodeURIComponent(action)}&limit=${limit}`);
    if (!logs.length) {
      listEl.innerHTML = '<div class="alert alert-info">Nenhum log encontrado.</div>';
      return;
    }
    listEl.innerHTML = `<p><strong>${logs.length} registro(s)</strong></p>
      <div class="table-wrap"><table class="data-table">
        <thead><tr><th>Data/Hora</th><th>Ação</th><th>Entidade</th><th>ID Entidade</th><th>Actor</th></tr></thead>
        <tbody>
          ${logs.map((l) => `<tr>
            <td>${formatBrDateTime(l.created_at)}</td>
            <td>${l.action}</td>
            <td>${l.entity_name || '—'}</td>
            <td>${l.entity_id ? (l.entity_id.length > 8 ? l.entity_id.slice(0, 8) + '...' : l.entity_id) : '—'}</td>
            <td>${l.actor_id ? l.actor_id.slice(0, 8) + '...' : 'Sistema'}</td>
          </tr>`).join('')}
        </tbody>
      </table></div>`;
  }

  document.getElementById('log-action-filter').addEventListener('change', loadLogs);
  document.getElementById('log-limit').addEventListener('change', loadLogs);
  await loadLogs();
}
