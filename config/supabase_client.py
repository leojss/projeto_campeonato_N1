"""
config/supabase_client.py — Singleton do cliente Supabase.

Mantém uma única instância do cliente para toda a aplicação,
evitando re-conexões desnecessárias a cada rerun do Streamlit.
"""

from __future__ import annotations

from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

_anon_client: Client | None = None
_admin_client: Client | None = None


def get_client() -> Client:
    """
    Retorna o cliente Supabase com chave anônima (para operações do usuário,
    respeitando as políticas RLS).
    """
    global _anon_client
    if _anon_client is None:
        _anon_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    return _anon_client


def get_admin_client() -> Client:
    """
    Retorna o cliente Supabase com chave service_role (para operações do sistema,
    como auditoria e agentes de IA). Ignora RLS — use com cuidado.
    """
    global _admin_client
    if _admin_client is None:
        if not SUPABASE_SERVICE_ROLE_KEY:
            raise EnvironmentError(
                "SUPABASE_SERVICE_ROLE_KEY não configurada. "
                "Esta chave é necessária para operações administrativas do sistema."
            )
        _admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    return _admin_client


def reset_clients() -> None:
    """Reseta os clientes (útil para testes unitários)."""
    global _anon_client, _admin_client
    _anon_client = None
    _admin_client = None
