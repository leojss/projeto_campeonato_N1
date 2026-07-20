import { api, getUser } from '../api.js';
import { formatCurrency, formatBrDate } from '../format.js';

export async function renderCompetidores(main) {
  main.innerHTML = '<h2>📊 Ranking Geral</h2><div class="spinner-wrap"><div class="spinner"></div></div>';
  const [competitors, roundsData] = await Promise.all([api.get('/competitors'), api.get('/rounds')]);

  if (!competitors.length) {
    main.innerHTML = '<h2>📊 Ranking Geral</h2><div class="alert alert-info">📭 Nenhum competidor cadastrado nesta competição.</div>';
    return;
  }

  const [p1, p2, p3] = competitors;

  main.innerHTML = `
    <h2>📊 Ranking Geral</h2>
    <div class="podium-box">
      <div class="podium-place">
        <div class="podium-avatar">🥈</div>
        <div class="podium-name" title="${p2?.display_name ?? '—'}">${p2?.display_name ?? '—'}</div>
        <div class="podium-score podium-silver">🎯 ${p2?.winning_bets ?? 0} acertos</div>
        <div class="podium-score-points">🪙 ${formatCurrency(p2?.points ?? 0)}</div>
        <div class="podium-bar bar-silver">2º</div>
      </div>
      <div class="podium-place">
        <div class="podium-avatar">👑</div>
        <div class="podium-name" title="${p1?.display_name ?? '—'}">${p1?.display_name ?? '—'}</div>
        <div class="podium-score">🎯 ${p1?.winning_bets ?? 0} acertos</div>
        <div class="podium-score-points">🪙 ${formatCurrency(p1?.points ?? 0)}</div>
        <div class="podium-bar bar-gold">1º</div>
      </div>
      <div class="podium-place">
        <div class="podium-avatar">🥉</div>
        <div class="podium-name" title="${p3?.display_name ?? '—'}">${p3?.display_name ?? '—'}</div>
        <div class="podium-score podium-bronze">🎯 ${p3?.winning_bets ?? 0} acertos</div>
        <div class="podium-score-points">🪙 ${formatCurrency(p3?.points ?? 0)}</div>
        <div class="podium-bar bar-bronze">3º</div>
      </div>
    </div>
    <h3>🏆 Classificação Completa</h3>
    <div id="ranking-list"></div>

    <h3>🗓️ Ranking da Semana</h3>
    <div id="weekly-ranking"><div class="spinner-wrap"><div class="spinner"></div></div></div>
  `;

  const isAdmin = getUser()?.role === 'admin';
  const listEl = document.getElementById('ranking-list');
  const statusMap = { active: '🟢 Ativo', inactive: '⚫ Inativo', suspended: '🔴 Suspenso' };

  listEl.innerHTML = competitors.map((c, idx) => {
    const pos = idx + 1;
    const medal = pos === 1 ? '🥇' : pos === 2 ? '🥈' : pos === 3 ? '🥉' : `<strong>${pos}º</strong>`;
    const roundInfo = c.round_bets_count !== null && c.round_bets_count !== undefined
      ? `<div class="text-muted">Apostas nesta rodada: ${c.round_bets_count}</div>`
      : '';
    const actionHtml = isAdmin
      ? `<select class="status-select" data-id="${c.id}">
          ${['active', 'inactive', 'suspended'].map((s) => `<option value="${s}" ${s === c.status ? 'selected' : ''}>${statusMap[s]}</option>`).join('')}
         </select>`
      : `<div class="status-label">${statusMap[c.status] || c.status}</div>`;

    return `
      <div class="card ranking-row">
        <div class="rank-medal">${medal}</div>
        <div class="rank-info">
          <div class="rank-name">${c.display_name}</div>
          ${roundInfo}
        </div>
        <div class="rank-stats">
          <div>🎯 <strong>${c.winning_bets} acerto(s)</strong></div>
          <div>🪙 <strong>${formatCurrency(c.points)}</strong> saldo</div>
        </div>
        <div class="rank-action">${actionHtml}</div>
      </div>
    `;
  }).join('');

  if (isAdmin) {
    listEl.querySelectorAll('.status-select').forEach((sel) => {
      sel.addEventListener('change', async () => {
        try {
          await api.patch(`/competitors/${sel.dataset.id}/status`, { status: sel.value });
        } catch (err) {
          alert(err.message);
        }
      });
    });
  }

  await renderWeeklyRanking(roundsData);
}

async function renderWeeklyRanking(roundsData) {
  const box = document.getElementById('weekly-ranking');
  const activeRoundId = roundsData.active_round_id;

  if (!activeRoundId) {
    box.innerHTML = '<div class="alert alert-info">Nenhuma rodada ativa no momento.</div>';
    return;
  }

  const active = roundsData.rounds.find((r) => r.id === activeRoundId);

  let ranking;
  try {
    ranking = await api.get(`/rounds/${activeRoundId}/ranking`);
  } catch (err) {
    box.innerHTML = `<div class="alert alert-error">❌ ${err.message}</div>`;
    return;
  }

  if (!ranking.length) {
    box.innerHTML = '<div class="alert alert-info">O ranking da semana será exibido após a liquidação das apostas.</div>';
    return;
  }

  box.innerHTML = `
    ${active ? `<p class="text-muted">Semana ${active.week_number} (${formatBrDate(active.start_date)} – ${formatBrDate(active.end_date)})</p>` : ''}
    <div class="table-wrap"><table class="data-table">
      <thead><tr><th>Pos.</th><th>Competidor</th><th>Apostas</th><th>Ganhas</th><th>Taxa de Acerto</th></tr></thead>
      <tbody>
        ${ranking.map((entry) => {
          const medal = entry.position === 1 ? '🥇' : entry.position === 2 ? '🥈' : entry.position === 3 ? '🥉' : `${entry.position}º`;
          return `<tr>
            <td>${medal}</td>
            <td>${entry.display_name}</td>
            <td>${entry.total_bets}</td>
            <td>${entry.winning_bets}</td>
            <td>${(entry.win_rate * 100).toFixed(1)}%</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table></div>
  `;
}
