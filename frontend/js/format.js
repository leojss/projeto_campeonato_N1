export function formatCurrency(value) {
  if (value === null || value === undefined) return '—';
  const v = Number(value);
  if (Number.isNaN(v)) return '—';
  return 'R$ ' + v.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
}

export function formatOdd(value) {
  if (value === null || value === undefined) return '—';
  return Number(value).toFixed(2);
}

export function formatProfit(value) {
  if (value === null || value === undefined) return '—';
  const v = Number(value);
  const currency = formatCurrency(Math.abs(v));
  return v >= 0 ? `+${currency} ✅` : `-${currency} ❌`;
}

export function formatBrDate(isoDate) {
  if (!isoDate) return '—';
  const datePart = String(isoDate).split('T')[0];
  const parts = datePart.split('-');
  if (parts.length !== 3) return isoDate;
  const [y, m, d] = parts;
  return `${d}/${m}/${y}`;
}

export function formatBrDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

const BET_STATUS_MAP = {
  draft: '📝 Rascunho',
  submitted: '📤 Enviada',
  processing: '⚙️ Processando',
  approved: '✅ Aprovada',
  rejected: '❌ Rejeitada',
  locked: '🔒 Bloqueada',
  settled: '🏁 Liquidada',
  review: '🔍 Em Revisão',
};
export function formatBetStatus(status) {
  return BET_STATUS_MAP[status] || status;
}

const ROUND_STATUS_MAP = {
  scheduled: '📅 Agendada',
  open: '🟢 Aberta',
  closed: '🔴 Encerrada',
  finalized: '🏆 Finalizada',
};
export function formatRoundStatus(status) {
  return ROUND_STATUS_MAP[status] || status;
}
