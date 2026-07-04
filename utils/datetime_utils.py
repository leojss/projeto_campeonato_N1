"""
utils/datetime_utils.py — Utilitários de data e hora no fuso America/Sao_Paulo.
"""

from __future__ import annotations

from datetime import datetime, date, time, timedelta
import pytz

from config.settings import TIMEZONE, UPLOAD_DEADLINE_HOUR, UPLOAD_DEADLINE_MINUTE

TZ_BR = pytz.timezone(TIMEZONE)


def get_now_br() -> datetime:
    """Retorna o datetime atual no fuso horário de São Paulo."""
    return datetime.now(tz=TZ_BR)


def get_today_br() -> date:
    """Retorna a data atual no fuso horário de São Paulo."""
    return get_now_br().date()


def get_upload_deadline(target_date: date) -> datetime:
    """
    Retorna o prazo máximo de upload para uma aposta com target_date informado.
    Regra: dia anterior ao target_date às 23:59:59 (fuso BR).

    Args:
        target_date: Data de referência da aposta.

    Returns:
        Deadline como datetime ciente do fuso horário BR.
    """
    deadline_date = target_date - timedelta(days=1)
    deadline_naive = datetime.combine(
        deadline_date,
        time(hour=UPLOAD_DEADLINE_HOUR, minute=UPLOAD_DEADLINE_MINUTE, second=59),
    )
    return TZ_BR.localize(deadline_naive)


def is_deadline_passed(target_date: date) -> bool:
    """
    Verifica se o prazo de submissão para target_date já passou.

    Returns:
        True se o prazo expirou (não é mais possível enviar).
    """
    deadline = get_upload_deadline(target_date)
    return get_now_br() > deadline


def get_current_week_range() -> tuple[date, date]:
    """
    Retorna o intervalo da semana atual: (domingo, sábado).

    Returns:
        Tupla (start_date, end_date) onde start=domingo, end=sábado.
    """
    today = get_today_br()
    # weekday(): segunda=0 ... domingo=6
    # isoweekday(): segunda=1 ... domingo=7
    # Para domingo como início da semana:
    days_since_sunday = today.weekday() + 1  # segunda=1, ..., domingo=7 → 0 se domingo
    if today.weekday() == 6:  # domingo
        days_since_sunday = 0
    sunday = today - timedelta(days=days_since_sunday)
    saturday = sunday + timedelta(days=6)
    return sunday, saturday


def format_deadline_remaining(target_date: date) -> str:
    """
    Retorna uma string legível mostrando quanto tempo resta até o deadline.

    Exemplo: "Encerra em 2h 15min" ou "Prazo encerrado"
    """
    deadline = get_upload_deadline(target_date)
    now = get_now_br()

    if now > deadline:
        return "⛔ Prazo encerrado"

    remaining = deadline - now
    total_seconds = int(remaining.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60

    if hours > 0:
        return f"⏳ Encerra em {hours}h {minutes}min"
    return f"⏳ Encerra em {minutes}min"


def localize_datetime(dt: datetime | str) -> datetime:
    """
    Garante que um datetime está no fuso BR. 
    Se for string (como o retorno do Supabase), converte para datetime.
    Se for naive, localiza. Se já tiver timezone, converte para BR.
    """
    if isinstance(dt, str):
        # Trata o formato com 'Z' (UTC) comumente retornado pelo JSON do Supabase
        cleaned_dt = dt.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned_dt)
        
    if dt.tzinfo is None:
        return TZ_BR.localize(dt)
    return dt.astimezone(TZ_BR)


def format_br_datetime(dt: datetime | None) -> str:
    """Formata datetime para exibição em pt-BR: dd/mm/yyyy HH:MM"""
    if dt is None:
        return "—"
    dt_br = localize_datetime(dt)
    return dt_br.strftime("%d/%m/%Y %H:%M")


def format_br_date(d: date | str | None) -> str:
    """Formata date para exibição em pt-BR: dd/mm/yyyy"""
    if d is None:
        return "—"
    if isinstance(d, str):
        try:
            # Pega apenas a parte da data caso venha um datetime completo em formato ISO string
            date_part = d.split("T")[0]
            d = date.fromisoformat(date_part)
        except ValueError:
            return d
    return d.strftime("%d/%m/%Y")
