"""
app.py — Ponto de entrada do Web App Controle de Apostas N1.

Execução:
    streamlit run app.py

O roteador detecta o estado de autenticação e o perfil do usuário
para renderizar a tela correta.
"""

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Configuração global da página — deve ser o PRIMEIRO comando Streamlit
st.set_page_config(
    page_title="Campeonato N1",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Web App de Controle — Competição Interna N1",
    },
)

# --- Injeção de CSS global ---
st.markdown(
    """
    <style>
    /* Remove padding padrão do Streamlit */
    .block-container { padding-top: 1.5rem; }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #0f172a;
    }
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] caption {
        color: #e2e8f0 !important;
    }

    /* Botões secundários específicos da Sidebar */
    [data-testid="stSidebar"] .stButton > button {
        background-color: #1e293b !important;
        color: #cbd5e1 !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        transition: all 0.2s ease;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #334155 !important;
        color: #ffffff !important;
        border-color: #475569 !important;
        transform: translateY(-1px);
    }

    /* Sobrescreve o botão primário ativo na Sidebar */
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
        color: white !important;
        border: none !important;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4) !important;
    }

    /* Botões primários gerais */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }

    /* Cards / containers com borda */
    div[data-testid="stVerticalBlock"] > div.element-container > div.stAlert {
        border-radius: 12px;
    }

    /* Métricas */
    [data-testid="stMetric"] {
        background: #1e293b !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        border: 1px solid #334155 !important;
    }
    /* Ajusta cores internas das métricas para alto contraste */
    [data-testid="stMetric"] label,
    [data-testid="stMetric"] [data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_session_state() -> None:
    """Inicializa todas as chaves do session_state na primeira execução."""
    defaults = {
        "authenticated": False,
        "user_id": None,
        "user_email": None,
        "user_role": None,          # "competidor" | "admin"
        "competitor_id": None,
        "profile_id": None,
        "full_name": None,
        "supabase_session": None,
        "current_page": "competidores",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_sidebar() -> None:
    """Renderiza o menu lateral com base no perfil do usuário."""
    from config.settings import APP_NAME, APP_VERSION

    with st.sidebar:
        try:
            st.image("assets/images/logo.png", width=90)
        except Exception:
            pass
        st.markdown(f"### {APP_NAME}")
        st.caption(f"v{APP_VERSION}")
        st.divider()

        # Informações do usuário logado
        st.markdown(f"👤 **{st.session_state.full_name or st.session_state.user_email}**")
        role_label = "🛡️ Administrador" if st.session_state.user_role == "admin" else "🏆 Competidor"
        st.caption(role_label)
        st.divider()

        # Navegação simplificada para fluxo centralizado no Administrador
        nav_options = {
            "📊 Ranking Geral": "competidores",
            "🎲 Cadastrar Apostas": "apostas",
            "⚙️ Painel Administrativo": "admin",
        }

        for label, page_key in nav_options.items():
            is_active = st.session_state.current_page == page_key
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"nav_{page_key}", use_container_width=True, type=btn_type):
                st.session_state.current_page = page_key
                st.rerun()

        st.divider()
        if st.button("🚪 Sair", key="btn_logout", use_container_width=True):
            _handle_logout()


def _handle_logout() -> None:
    """Realiza logout e limpa o session_state."""
    try:
        from services.auth_service import AuthService
        AuthService.logout()
    except Exception:
        pass

    # Limpa o estado da sessão
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def _render_page() -> None:
    """Roteia para a tela correta com base em `current_page`."""
    page = st.session_state.get("current_page", "dashboard")

    if page == "dashboard":
        from ui.dashboard import render_dashboard
        render_dashboard()
    elif page == "apostas":
        from ui.apostas import render_apostas
        render_apostas()
    elif page == "competidores":
        from ui.competidores import render_competidores
        render_competidores()
    elif page == "rodada":
        from ui.rodada import render_rodada
        render_rodada()
    elif page == "admin":
        if st.session_state.user_role == "admin":
            from ui.admin import render_admin
            render_admin()
        else:
            st.error("❌ Acesso negado. Esta área é exclusiva para administradores.")
    else:
        from ui.dashboard import render_dashboard
        render_dashboard()


def main() -> None:
    _init_session_state()

    if not st.session_state.authenticated:
        from ui.login import render_login
        render_login()
        return

    # Usuário autenticado: renderiza layout completo
    _render_sidebar()
    _render_page()


if __name__ == "__main__":
    main()
