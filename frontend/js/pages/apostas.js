import { api, getUser } from '../api.js';
import { formatOdd, formatBrDate, formatBetStatus } from '../format.js';

let activeTab = 'historico';
let novaApostaMode = 'imagem';

export async function renderApostas(main) {
  main.innerHTML = `
    <h2>🎯 Minhas Apostas</h2>
    <div class="tabs">
      <button class="tab-btn ${activeTab === 'historico' ? 'active' : ''}" data-tab="historico">📋 Histórico</button>
      <button class="tab-btn ${activeTab === 'nova' ? 'active' : ''}" data-tab="nova">➕ Nova Aposta</button>
    </div>
    <div id="tab-content"></div>
  `;

  main.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      activeTab = btn.dataset.tab;
      renderApostas(main);
    });
  });

  const content = document.getElementById('tab-content');
  content.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
  if (activeTab === 'historico') {
    await renderHistorico(content);
  } else {
    await renderNovaAposta(content);
  }
}

async function renderHistorico(container) {
  const competitors = await api.get('/competitors');
  if (!competitors.length) {
    container.innerHTML = '<div class="alert alert-info">📭 Nenhum competidor cadastrado no sistema.</div>';
    return;
  }

  container.innerHTML = `
    <label>Filtrar Histórico por Jogador</label>
    <select id="hist-filter">
      <option value="">Todos</option>
      ${competitors.map((c) => `<option value="${c.id}">${c.display_name}</option>`).join('')}
    </select>
    <div id="hist-list"></div>
  `;

  const listEl = document.getElementById('hist-list');
  const filterEl = document.getElementById('hist-filter');

  async function loadBets() {
    listEl.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div></div>';
    const compId = filterEl.value;
    const bets = await api.get(compId ? `/bets?competitor_id=${compId}&limit=30` : '/bets?limit=50');
    if (!bets.length) {
      listEl.innerHTML = '<div class="alert alert-info">📭 Nenhuma aposta registrada para a seleção atual.</div>';
      return;
    }
    listEl.innerHTML = `<p><strong>${bets.length} aposta(s) encontrada(s)</strong></p>` + bets.map(betRowHtml).join('');

    listEl.querySelectorAll('.expander-header').forEach((h) => {
      h.addEventListener('click', () => h.parentElement.classList.toggle('open'));
    });
    listEl.querySelectorAll('.btn-delete-bet').forEach((btn) => {
      btn.addEventListener('click', async (ev) => {
        ev.stopPropagation();
        if (!confirm('Confirma a exclusão desta aposta?')) return;
        try {
          await api.delete(`/bets/${btn.dataset.id}`);
          await loadBets();
        } catch (err) {
          alert(err.message);
        }
      });
    });
  }

  filterEl.addEventListener('change', loadBets);
  await loadBets();
}

function betRowHtml(bet) {
  const descricao = bet.selections && bet.selections[0] ? bet.selections[0].description : null;

  return `
    <div class="expander">
      <div class="expander-header">
        👤 ${bet.competitor_name} | ${formatBetStatus(bet.status)} | 📅 ${formatBrDate(bet.target_date)} | Odd ${formatOdd(bet.total_odd)}
      </div>
      <div class="expander-body">
        <div class="metrics-row">
          <div class="metric"><div class="metric-label">Odd Total</div><div class="metric-value">${formatOdd(bet.total_odd)}</div></div>
          <div class="metric"><div class="metric-label">Status</div><div class="metric-value">${formatBetStatus(bet.status)}</div></div>
          ${bet.ocr_confidence ? `<div class="metric"><div class="metric-label">Confiança IA</div><div class="metric-value">${Math.round(bet.ocr_confidence * 100)}%</div></div>` : ''}
        </div>
        <hr>
        <strong>🎯 Aposta:</strong>
        <p>${descricao || '<span class="text-muted">Não identificada pela IA.</span>'}</p>
        ${bet.notes ? `<hr><span class="text-muted">📝 <strong>Notas do Sistema:</strong> ${bet.notes}</span>` : ''}
        ${bet.status !== 'settled' ? `<br><button class="btn btn-danger btn-block btn-delete-bet" data-id="${bet.id}">🗑️ Excluir Aposta</button>` : ''}
      </div>
    </div>
  `;
}

async function renderNovaAposta(container) {
  const user = getUser();
  const isAdmin = user && user.role === 'admin';

  const [competitors, roundsData] = await Promise.all([api.get('/competitors'), api.get('/rounds')]);

  if (!competitors.length) {
    container.innerHTML = '<div class="alert alert-error">⛔ Nenhum competidor cadastrado. Cadastre competidores primeiro no Painel Admin.</div>';
    return;
  }
  if (!roundsData.rounds.length) {
    container.innerHTML = '<div class="alert alert-error">⛔ Nenhuma rodada cadastrada no sistema. Crie uma rodada no Painel Admin primeiro.</div>';
    return;
  }

  const rounds = roundsData.rounds;
  const activeRoundId = roundsData.active_round_id;
  const defaultRoundIdx = Math.max(0, rounds.findIndex((r) => r.id === activeRoundId));

  const roundLabel = (r) => {
    const status = r.status === 'open' ? '🟢 Aberta' : r.status === 'closed' ? '🔴 Fechada' : r.status === 'finalized' ? '🏆 Finalizada' : '📅 Agendada';
    return `Semana ${r.week_number} (${formatBrDate(r.start_date)} – ${formatBrDate(r.end_date)}) — ${status}`;
  };

  const userCompId = user?.competitor_id;
  const availableCompetitors = (!isAdmin && userCompId) 
    ? competitors.filter(c => c.id === userCompId)
    : competitors;

  const imageBlockHtml = `
      <label>📸 Comprovante da Aposta</label>
      <input type="file" id="f-file" accept="image/jpeg,image/png,image/webp" ${novaApostaMode === 'imagem' ? 'required' : ''}>
      <p class="text-muted">A IA irá ler a imagem e preencher automaticamente a odd total e a descrição da aposta. (JPG, PNG, WebP — máx 10MB)</p>
      <img id="f-preview" class="preview-img hidden">
  `;

  const manualBlockHtml = `
      <label>📊 Odd Total</label>
      <input type="number" id="m-odd" step="0.01" min="1" placeholder="Ex: 2.35" ${novaApostaMode === 'manual' ? 'required' : ''}>
      <label>🎯 Descreva a aposta</label>
      <textarea id="m-descricao" placeholder="Ex: Real Madrid vence o Barcelona; Mais de 2.5 gols no jogo do Flamengo x Vasco" ${novaApostaMode === 'manual' ? 'required' : ''}></textarea>
  `;

  container.innerHTML = `
    <h3>🚀 Realizar Nova Aposta</h3>
    <div class="tabs">
      <button type="button" class="tab-btn ${novaApostaMode === 'imagem' ? 'active' : ''}" data-mode="imagem">📸 Comprovante (IA)</button>
      <button type="button" class="tab-btn ${novaApostaMode === 'manual' ? 'active' : ''}" data-mode="manual">✍️ Manual</button>
    </div>
    <form id="nova-aposta-form">
      <label>👤 Selecione o Competidor (Apostador)</label>
      <select id="f-competitor" required ${!isAdmin && availableCompetitors.length === 1 ? 'disabled' : ''}>
        ${availableCompetitors.map((c) => `<option value="${c.id}" ${c.id === userCompId ? 'selected' : ''}>${c.display_name}</option>`).join('')}
      </select>

      <label>📅 Selecione a Rodada da Aposta</label>
      <select id="f-round" required>
        ${rounds.map((r, i) => `<option value="${r.id}" data-start="${r.start_date}" data-end="${r.end_date}" ${i === defaultRoundIdx ? 'selected' : ''}>${roundLabel(r)}</option>`).join('')}
      </select>

      ${isAdmin ? `
      <label class="checkbox-label">
        <input type="checkbox" id="f-force"> ⚠️ Forçar cadastro (ignorar prazo de envio expirado)
      </label>` : ''}

      <label>📅 Data de referência da aposta</label>
      <input type="date" id="f-date" required>
      <p class="text-muted">O prazo de envio é até 23:59 do dia anterior à data escolhida.</p>

      <hr>
      ${novaApostaMode === 'imagem' ? imageBlockHtml : manualBlockHtml}

      <hr>
      <div id="submit-alert"></div>
      <div id="pipeline-log" class="pipeline-log hidden"></div>
      <button type="submit" class="btn btn-primary btn-block" id="submit-btn">${novaApostaMode === 'imagem' ? '🤖 Analisar e Enviar Aposta' : '✅ Registrar Aposta'}</button>
    </form>
  `;

  container.querySelectorAll('.tab-btn[data-mode]').forEach((btn) => {
    btn.addEventListener('click', () => {
      novaApostaMode = btn.dataset.mode;
      renderNovaAposta(container);
    });
  });

  const dateInput = document.getElementById('f-date');
  const roundSelect = document.getElementById('f-round');
  const competitorSelect = document.getElementById('f-competitor');
  const forceCheckbox = document.getElementById('f-force');

  function applyDateBounds() {
    const opt = roundSelect.selectedOptions[0];
    const min = opt.dataset.start;
    const max = opt.dataset.end;
    dateInput.min = min;
    dateInput.max = max;
    const defaultDate = new Date();
    defaultDate.setDate(defaultDate.getDate() + 1);
    let iso = defaultDate.toISOString().slice(0, 10);
    if (iso < min) iso = min;
    if (iso > max) iso = max;
    dateInput.value = iso;
  }
  applyDateBounds();
  roundSelect.addEventListener('change', applyDateBounds);

  document.getElementById('f-file')?.addEventListener('change', (ev) => {
    const preview = document.getElementById('f-preview');
    const file = ev.target.files[0];
    if (file) {
      preview.src = URL.createObjectURL(file);
      preview.classList.remove('hidden');
    } else {
      preview.classList.add('hidden');
    }
  });

  document.getElementById('nova-aposta-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const submitBtn = document.getElementById('submit-btn');
    const alertBox = document.getElementById('submit-alert');
    const logBox = document.getElementById('pipeline-log');
    alertBox.innerHTML = '';

    const isManual = novaApostaMode === 'manual';
    const forceSubmission = forceCheckbox && forceCheckbox.checked;

    let file = null;
    let odd = null;
    let descricao = null;

    if (isManual) {
      odd = parseFloat(document.getElementById('m-odd').value);
      descricao = document.getElementById('m-descricao').value.trim();
      if (!odd || odd <= 0) {
        alertBox.innerHTML = '<div class="alert alert-error">⚠️ Informe a odd total da aposta.</div>';
        return;
      }
      if (!descricao) {
        alertBox.innerHTML = '<div class="alert alert-error">⚠️ Descreva a aposta.</div>';
        return;
      }
    } else {
      file = document.getElementById('f-file').files[0];
      if (!file) {
        alertBox.innerHTML = '<div class="alert alert-error">⚠️ O upload da imagem do comprovante é obrigatório.</div>';
        return;
      }
    }

    submitBtn.disabled = true;
    submitBtn.textContent = isManual ? 'Registrando...' : 'Processando...';
    if (!isManual) {
      logBox.classList.remove('hidden');
      logBox.textContent = '⏳ Processando aposta por IA (validando prazos, enviando imagem, lendo com IA, validando regras e salvando)... pode levar alguns segundos.';
    }

    try {
      let result;
      if (isManual) {
        result = await api.post('/bets/manual', {
          competitor_id: competitorSelect.value,
          round_id: roundSelect.value,
          target_date: dateInput.value,
          total_odd: odd,
          aposta_descricao: descricao,
          force_submission: !!forceSubmission,
        });
      } else {
        const form = new FormData();
        form.append('competitor_id', competitorSelect.value);
        form.append('round_id', roundSelect.value);
        form.append('target_date', dateInput.value);
        form.append('force_submission', forceSubmission ? 'true' : 'false');
        form.append('file', file);
        result = await api.post('/bets', form, { isForm: true });
      }

      logBox.classList.add('hidden');

      if (result.status === 'approved') {
        alertBox.innerHTML = isManual
          ? '<div class="alert alert-success">🎉 Aposta registrada com sucesso!</div>'
          : `
          <div class="alert alert-success">🎉 Aposta registrada com sucesso! A IA identificou os dados perfeitamente.</div>
          <div class="alert alert-info">
            <strong>Dados extraídos:</strong><br>
            📊 Odd total: ${formatOdd(result.extracted.total_odd ?? 1.5)}<br>
            🎯 Aposta: ${result.extracted.aposta_descricao || '—'}
          </div>`;
      } else if (result.status === 'review') {
        alertBox.innerHTML = `<div class="alert alert-warning">🔍 ${result.message}</div>`;
      } else {
        alertBox.innerHTML = `<div class="alert alert-error">❌ Aposta rejeitada pelo sistema. ${result.message}</div>`;
      }

      ev.target.reset();
      applyDateBounds();
      document.getElementById('f-preview')?.classList.add('hidden');
    } catch (err) {
      logBox.classList.add('hidden');
      alertBox.innerHTML = `<div class="alert alert-error">❌ ${err.message}</div>`;
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = isManual ? '✅ Registrar Aposta' : '🤖 Analisar e Enviar Aposta';
    }
  });
}
