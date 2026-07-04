"""
utils/formatting.py — Formatação de valores para exibição em português brasileiro.
"""

from __future__ import annotations

from decimal import Decimal


def format_currency(value: float | Decimal | None, prefix: str = "R$") -> str:
    """
    Formata um valor numérico como moeda em pt-BR.

    Exemplo: 1250.75 → "R$ 1.250,75"
    """
    if value is None:
        return "—"
    try:
        v = float(value)
        # Formata com separadores brasileiros
        formatted = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{prefix} {formatted}"
    except (TypeError, ValueError):
        return "—"


def format_odd(value: float | None) -> str:
    """
    Formata uma odd para exibição.

    Exemplo: 2.5 → "2.50"
    """
    if value is None:
        return "—"
    return f"{float(value):.2f}"


def format_percentage(value: float | None, decimals: int = 1) -> str:
    """
    Formata um valor de 0.0 a 1.0 como percentual.

    Exemplo: 0.756 → "75.6%"
    """
    if value is None:
        return "—"
    return f"{float(value) * 100:.{decimals}f}%"


def format_profit(net_profit: float | None) -> str:
    """
    Formata lucro/prejuízo com sinal e cor indicativa (usando emoji).

    Exemplo positivo:  "+R$ 150,00 ✅"
    Exemplo negativo: "-R$ 50,00 ❌"
    """
    if net_profit is None:
        return "—"
    v = float(net_profit)
    currency = format_currency(abs(v))
    if v >= 0:
        return f"+{currency} ✅"
    return f"-{currency} ❌"


def format_bet_status(status: str) -> str:
    """Retorna label legível e emoji para o status da aposta."""
    mapping = {
        "draft":       "📝 Rascunho",
        "submitted":   "📤 Enviada",
        "processing":  "⚙️ Processando",
        "approved":    "✅ Aprovada",
        "rejected":    "❌ Rejeitada",
        "locked":      "🔒 Bloqueada",
        "settled":     "🏁 Liquidada",
        "review":      "🔍 Em Revisão",
    }
    return mapping.get(status, status.capitalize())


def format_round_status(status: str) -> str:
    """Retorna label legível para o status da rodada."""
    mapping = {
        "scheduled": "📅 Agendada",
        "open":      "🟢 Aberta",
        "closed":    "🔴 Encerrada",
        "finalized": "🏆 Finalizada",
    }
    return mapping.get(status, status.capitalize())


def format_outcome(outcome: str | None) -> str:
    """Retorna label para o resultado da aposta."""
    mapping = {
        "win":  "🏆 Ganhou",
        "loss": "💸 Perdeu",
        "void": "↩️ Anulada",
    }
    if outcome is None:
        return "⏳ Pendente"
    return mapping.get(outcome, outcome.capitalize())


def truncate_text(text: str, max_len: int = 50) -> str:
    """Trunca um texto longo para exibição em tabelas."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
