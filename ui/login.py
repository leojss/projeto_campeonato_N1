"""
ui/login.py — Tela de login do sistema.
"""

from __future__ import annotations

import streamlit as st

from services.auth_service import AuthService, AuthError
from agents.auditoria import AgentAuditoria


def render_login() -> None:
    """Renderiza a tela de autenticação."""

    # Layout centralizado
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # Header com Logo Futurista IA
        import base64
        try:
            with open("assets/images/logo.png", "rb") as f:
                logo_base64 = base64.b64encode(f.read()).decode()
            logo_html = f'<img src="data:image/png;base64,{logo_base64}" style="width: 110px; height: 110px; border-radius: 24px; box-shadow: 0 0 25px rgba(99, 102, 241, 0.5); margin-bottom: 1.5rem; border: 1.5px solid #6366f1;"/>'
        except Exception:
            logo_html = '<div style="font-size: 4rem; margin-bottom: 1rem;">🎯</div>'

        st.markdown(
            f"""
            <div style="text-align: center; padding: 1.5rem 0 0.5rem;">
                {logo_html}
                <h1 style="color: #6366f1; font-size: 2.2rem; margin: 0; font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.5px;">Campeonato N1</h1>
                <p style="color: #94a3b8; margin-top: 0.5rem; font-size: 0.95rem;">
                    Competição Interna — Faça login para continuar
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Card de login
        st.markdown(
            """
            <style>
            .login-card {
                background: linear-gradient(135deg, #1e293b, #0f172a);
                border: 1px solid #334155;
                border-radius: 16px;
                padding: 2rem;
                box-shadow: 0 25px 50px rgba(0,0,0,0.4);
            }
            </style>
            <div class="login-card"></div>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            st.markdown("### 🔐 Entrar na plataforma")

            with st.form("login_form", clear_on_submit=False):
                email = st.text_input(
                    "📧 E-mail",
                    placeholder="seu@email.com",
                    key="login_email",
                )
                password = st.text_input(
                    "🔑 Senha",
                    type="password",
                    placeholder="••••••••",
                    key="login_password",
                )

                st.markdown("<br>", unsafe_allow_html=True)
                submitted = st.form_submit_button(
                    "Entrar →",
                    use_container_width=True,
                    type="primary",
                )

            if submitted:
                if not email or not password:
                    st.error("⚠️ Preencha e-mail e senha.")
                    return

                with st.spinner("Autenticando..."):
                    try:
                        auth_data = AuthService.login(email, password)
                        
                        if auth_data["profile"].role != "admin":
                            AuthService.logout()
                            st.error("❌ Acesso negado. Esta plataforma é de uso exclusivo do administrador.")
                            return
                            
                        AuthService.populate_session(auth_data)

                        # Auditoria de login
                        AgentAuditoria.log_login(
                            actor_id=auth_data["user_id"],
                            email=email,
                        )

                        st.success("✅ Login realizado com sucesso!")
                        st.rerun()

                    except AuthError as e:
                        st.error(f"❌ {str(e)}")
                    except Exception as e:
                        st.error(f"❌ Erro inesperado: {str(e)}")

        # Rodapé
        st.markdown(
            """
            <div style="text-align:center; color: #475569; font-size: 0.8rem; margin-top: 2rem;">
                Não possui acesso? Fale com o administrador da competição.
            </div>
            """,
            unsafe_allow_html=True,
        )
