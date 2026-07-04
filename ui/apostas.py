"""
ui/apostas.py — Tela de gestão de apostas: histórico e nova aposta.
Pipeline completo: formulário → upload → OCR → validação → persistência.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from services.auth_service import AuthService
from services.bet_service import BetService, BetValidationError
from services.upload_service import UploadService, DeadlineError
from services.round_service import RoundService
from agents.leitura_imagem import AgentLeituraImagem
from agents.normalizacao_aposta import AgentNormalizacaoAposta
from agents.validador_regras import AgentValidadorRegras
from agents.persistencia import AgentPersistencia
from agents.auditoria import AgentAuditoria
from repositories.bet_repository import BetRepository
from utils.datetime_utils import (
    get_today_br, format_br_date, format_br_datetime,
    is_deadline_passed, format_deadline_remaining,
)
from utils.file_utils import read_streamlit_file, FileValidationError
from utils.formatting import format_bet_status, format_currency, format_odd
from config.settings import MAX_BETS_PER_DAY, MIN_ODD, MAX_COMBINED


def render_apostas() -> None:
    """Renderiza a tela de apostas (histórico + nova aposta)."""
    AuthService.require_authenticated()

    st.markdown("## 🎯 Minhas Apostas")

    tab_historico, tab_nova = st.tabs(["📋 Histórico", "➕ Nova Aposta"])

    with tab_historico:
        _render_historico()

    with tab_nova:
        _render_nova_aposta()


def _render_historico() -> None:
    """Exibe o histórico de apostas (filtrável por competidor)."""
    from repositories.competitor_repository import CompetitorRepository
    
    competitors_list = CompetitorRepository.get_all_competitors()
    if not competitors_list:
        st.info("📭 Nenhum competidor cadastrado no sistema.")
        return

    # Mapeamentos para dropdown e consulta rápida
    comp_map = {c.display_name: c.id for c in competitors_list}
    comp_names_map = {c.id: c.display_name for c in competitors_list}
    
    options = ["Todos"] + [c.display_name for c in competitors_list]
    selected_comp = st.selectbox("Filtrar Histórico por Jogador", options=options, key="hist_filter_player")

    # Filtra as apostas com base no dropdown
    if selected_comp == "Todos":
        bets = BetRepository.get_all_bets(limit=50)
    else:
        target_id = comp_map[selected_comp]
        bets = BetRepository.get_bets_by_competitor(target_id, limit=30)

    if not bets:
        st.info("📭 Nenhuma aposta registrada para a seleção atual.")
        return

    st.markdown(f"**{len(bets)} aposta(s) encontrada(s)**")

    for bet in bets:
        status_label = format_bet_status(bet.status)
        date_label = format_br_date(bet.target_date)
        player_name = comp_names_map.get(bet.competitor_id, "Desconhecido")
        
        with st.expander(
            f"👤 {player_name} | {status_label} | 📅 {date_label} | Odd {format_odd(bet.total_odd)} | {format_currency(bet.stake_value)}",
            expanded=False,
        ):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Odd Total", format_odd(bet.total_odd))
                st.metric("Seleções", bet.combined_count)
            with col2:
                st.metric("Valor", format_currency(bet.stake_value))
                retorno = bet.stake_value * bet.total_odd
                st.metric("Retorno Potencial", format_currency(retorno))
            with col3:
                st.metric("Status", status_label)
                if bet.ocr_confidence:
                    st.metric("Confiança IA", f"{bet.ocr_confidence:.0%}")

            # Busca e lista as seleções individuais da aposta
            selections = BetRepository.get_selections_by_bet(bet.id)
            if selections:
                st.markdown("---")
                st.markdown("**🎮 Seleções e Palpites Detalhados:**")
                for s in selections:
                    status_emoji = "🟡" if s.result_status == "pending" else \
                                   "🟢" if s.result_status == "won" else \
                                   "🔴" if s.result_status == "lost" else \
                                   "⚫"
                    status_text = "Pendente" if s.result_status == "pending" else \
                                  "Ganhou" if s.result_status == "won" else \
                                  "Perdeu" if s.result_status == "lost" else \
                                  "Anulada"
                    st.markdown(
                        f"{status_emoji} **Seleção {s.selection_order}:** {s.description} | Odd: **{s.odd:.2f}** "
                        f"({status_text})"
                    )

            if bet.notes:
                st.markdown("---")
                st.caption(f"📝 **Notas do Sistema:** {bet.notes}")

            # Permite exclusão de apostas não liquidadas para liberar limite diário
            if bet.status != "settled":
                st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                if st.button("🗑️ Excluir Aposta", key=f"del_bet_{bet.id}", use_container_width=True):
                    try:
                        from agents.auditoria import AgentAuditoria
                        
                        if BetRepository.delete_bet(bet.id):
                            # Registra auditoria
                            AgentAuditoria.log(
                                "BET_DELETED",
                                actor_id=st.session_state.get("user_id"),
                                entity_name="bets",
                                entity_id=bet.id,
                                payload={"reason": "Excluido pelo admin", "target_date": str(bet.target_date), "player": player_name},
                            )
                            st.success("✅ Aposta excluída com sucesso! Limite diário liberado.")
                            st.rerun()
                        else:
                            st.error("❌ Não foi possível excluir a aposta.")
                    except Exception as e:
                        st.error(f"❌ Erro ao excluir: {e}")


def _render_nova_aposta() -> None:
    """Formulário de nova aposta simplificado — sem digitação manual."""
    AuthService.require_authenticated()

    actor_id = st.session_state.get("user_id")
    today = get_today_br()

    # --- Busca todas as rodadas para o seletor ---
    from repositories.round_repository import RoundRepository
    rounds_list = RoundRepository.get_all_rounds(limit=50)
    if not rounds_list:
        st.error("⛔ Nenhuma rodada cadastrada no sistema. Crie uma rodada no Painel Admin primeiro.")
        return

    # Mapeamento para o selectbox de rodadas
    round_options = []
    round_map = {}
    default_round_index = 0
    active_round = RoundService.get_active_round()

    for idx, r in enumerate(rounds_list):
        status_label = "🟢 Aberta" if r.status == "open" else "🔴 Fechada" if r.status == "closed" else "🏁 Finalizada"
        label = f"{r.label} ({status_label})"
        round_options.append(label)
        round_map[label] = r
        if active_round and r.id == active_round.id:
            default_round_index = idx

    # --- Busca Competidores para seleção pelo Admin ---
    from repositories.competitor_repository import CompetitorRepository
    competitors_list = CompetitorRepository.get_all_competitors()
    if not competitors_list:
        st.error("⛔ Nenhum competidor cadastrado. Cadastre competidores primeiro no Painel Admin.")
        return

    comp_map = {c.display_name: c.id for c in competitors_list}
    comp_names = [c.display_name for c in competitors_list]

    st.markdown("### 🚀 Realizar Nova Aposta (Preenchimento por IA)")

    with st.form("nova_aposta_form", clear_on_submit=True):
        
        # Seletor de Competidor para atribuição da aposta
        selected_comp_name = st.selectbox(
            "👤 Selecione o Competidor (Apostador)",
            options=comp_names,
            key="aposta_competidor_name",
            help="Escolha para qual jogador esta aposta será atribuída."
        )
        competitor_id = comp_map[selected_comp_name]

        # Seletor de Rodada
        selected_round_label = st.selectbox(
            "📅 Selecione a Rodada da Aposta",
            options=round_options,
            index=default_round_index,
            key="aposta_round_label",
            help="Escolha a qual rodada esta aposta deve pertencer."
        )
        selected_round = round_map[selected_round_label]
        round_id = selected_round.id

        # Checkbox para forçar cadastro ignorando prazo/restrições
        force_submission = st.checkbox(
            "⚠️ Forçar cadastro (ignorar prazo de envio expirado)",
            value=False,
            key="aposta_force_submission",
            help="Marque esta opção para permitir o cadastro desta aposta mesmo que o prazo oficial de envio já tenha passado."
        )

        # --- Data de referência ---
        min_date = selected_round.start_date
        max_date = selected_round.end_date
        
        # Ajusta valor padrão seguro de data para o st.date_input
        default_date = today + timedelta(days=1)
        if default_date < min_date:
            default_date = min_date
        elif default_date > max_date:
            default_date = max_date

        target_date = st.date_input(
            "📅 Data de referência da aposta",
            value=default_date,
            min_value=min_date,
            max_value=max_date,
            help="Data para a qual a aposta se refere. O upload deve ser feito até 23:59 do dia anterior.",
            key="aposta_target_date",
        )

        # --- Verificação de prazo em tempo real ---
        is_passed = is_deadline_passed(target_date)
        bets_count = BetRepository.count_bets_today(competitor_id, target_date)
        
        if is_passed:
            if force_submission:
                st.warning(
                    f"⚠️ Prazo oficialmente expirado para {format_br_date(target_date)}, "
                    "mas a gravação será permitida devido à concessão (cadastro forçado ativo)."
                )
            else:
                st.error(
                    f"⛔ Prazo expirado para {format_br_date(target_date)}. "
                    "Marque a opção 'Forçar cadastro' se houver decisão de concessão."
                )
        else:
            if bets_count >= MAX_BETS_PER_DAY:
                st.error(
                    f"⛔ Limite diário atingido para {selected_comp_name} em {format_br_date(target_date)}: "
                    f"{bets_count}/{MAX_BETS_PER_DAY} apostas."
                )
            else:
                remaining_deadline = format_deadline_remaining(target_date)
                st.info(
                    f"✅ Prazo: {remaining_deadline} | "
                    f"Apostas de {selected_comp_name}: {bets_count}/{MAX_BETS_PER_DAY}"
                )

        st.divider()

        # --- Upload da imagem ---
        st.markdown("**📸 Comprovante da Aposta**")
        uploaded_file = st.file_uploader(
            "Faça upload da imagem do comprovante (JPG, PNG, WebP — máx 10MB)",
            type=["jpg", "jpeg", "png", "webp"],
            key="aposta_imagem",
            help="A IA irá analisar esta imagem para preencher o valor, odds e seleções automaticamente.",
        )

        if uploaded_file:
            st.image(uploaded_file, caption="Preview da imagem", width="stretch")

        st.divider()
        submitted = st.form_submit_button(
            "🤖 Analisar e Enviar Aposta",
            use_container_width=True,
            type="primary",
        )

    # --- Processamento pós-submit ---
    if submitted:
        if is_deadline_passed(target_date) and not force_submission:
            st.error("⛔ Não é possível enviar: o prazo expirou. Ative o cadastro forçado para prosseguir.")
            return

        _process_bet_submission(
            competitor_id=competitor_id,
            actor_id=actor_id,
            round_id=round_id,
            target_date=target_date,
            uploaded_file=uploaded_file,
            force_submission=force_submission,
        )


def _process_bet_submission(
    competitor_id: str,
    actor_id: str,
    round_id: str,
    target_date: date,
    uploaded_file,
    force_submission: bool = False,
) -> None:
    """Executa o pipeline de aposta sem digitação, extraindo tudo por IA."""
    from models.bet import Bet
    from repositories.bet_repository import BetRepository as BR
    from utils.datetime_utils import get_upload_deadline

    # Validações iniciais (frontend)
    if not uploaded_file:
        st.error("⚠️ O upload da imagem do comprovante é obrigatório.")
        return

    with st.status("Processando aposta por IA...", expanded=True) as status_container:

        # Passo 1: Validações básicas de prazo e limite diário (antes de rodar a IA)
        st.write("✅ Validando prazos e limites...")
        if is_deadline_passed(target_date) and not force_submission:
            status_container.update(label="❌ Prazo expirado", state="error")
            st.error(f"Prazo expirado para apostas na data {format_br_date(target_date)}.")
            AgentAuditoria.log_deadline_exceeded(actor_id, str(target_date))
            return
            
        bets_today = BR.count_bets_today(competitor_id, target_date)
        if bets_today >= MAX_BETS_PER_DAY:
            status_container.update(label="❌ Limite diário excedido", state="error")
            st.error(f"Limite diário de {MAX_BETS_PER_DAY} apostas atingido para o jogador selecionado nessa data.")
            AgentAuditoria.log_limit_exceeded(actor_id, str(target_date), bets_today)
            return

        # Passo 2: Valida arquivo de imagem
        st.write("📤 Validando arquivo...")
        file_content, filename, mime_type = read_streamlit_file(uploaded_file)

        try:
            if not force_submission:
                UploadService.validate_upload(file_content, filename, mime_type, target_date)
            else:
                from utils.file_utils import validate_image_file
                validate_image_file(file_content, filename, mime_type)
        except DeadlineError as e:
            status_container.update(label="❌ Prazo expirado", state="error")
            st.error(str(e))
            return
        except FileValidationError as e:
            status_container.update(label="❌ Arquivo inválido", state="error")
            st.error(str(e))
            return

        # Cria aposta temporária no banco (draft/processing) para obter ID único
        st.write("💾 Registrando submissão...")
        temp_bet = Bet(
            competitor_id=competitor_id,
            round_id=round_id,
            target_date=target_date,
            stake_value=1.0,      # Provisório
            total_odd=1.5,        # Provisório
            combined_count=1,     # Provisório
            status="processing",
            deadline_at=get_upload_deadline(target_date),
        )
        temp_bet = BR.create_bet(temp_bet)

        # Upload para o Supabase Storage
        try:
            storage_path = UploadService.upload_image(
                file_content, filename, mime_type, competitor_id, temp_bet.id
            )
            AgentAuditoria.log_upload_completed(actor_id, temp_bet.id, storage_path)
        except Exception as e:
            BR.update_bet_status(temp_bet.id, "rejected", f"Falha no upload: {e}")
            status_container.update(label="❌ Falha no upload", state="error")
            st.error(f"Falha ao enviar imagem para o storage: {e}")
            return

        # Passo 3: Leitura da imagem com IA (Gemini Vision)
        st.write("🤖 Analisando imagem do comprovante com IA...")
        try:
            agent_leitura = AgentLeituraImagem()
            reading_result = agent_leitura.read_image(file_content, {"target_date": str(target_date)})
            AgentAuditoria.log_ocr_processed(temp_bet.id, reading_result.confidence_score, "extracted")
        except Exception as e:
            from agents.leitura_imagem import ImageReadingResult
            reading_result = ImageReadingResult(error=str(e), needs_review=True)
            AgentAuditoria.log_ocr_failed(temp_bet.id, str(e))
            st.warning("⚠️ Falha na leitura automática da IA. Aposta enviada para revisão.")

        # Passo 4: Normalização dos dados extraídos
        st.write("🔄 Normalizando dados da aposta...")
        agent_norm = AgentNormalizacaoAposta()
        normalized = agent_norm.normalize(
            reading_result,
            metadata={"target_date": target_date},
        )

        # Passo 5: Validação das regras (pós-leitura da IA)
        st.write("🔍 Verificando regras de negócio...")
        agent_valid = AgentValidadorRegras()
        validation = agent_valid.validate(
            normalized,
            competitor_id,
            form_data={"target_date": target_date},
            existing_bet_id=temp_bet.id,
            force_submission=force_submission,
        )

        # Passo 6: Persistência e atualização definitiva no Supabase
        st.write("💾 Salvando dados finais no banco...")
        agent_persist = AgentPersistencia()
        result = agent_persist.persist(
            normalized_bet=normalized,
            validation_result=validation,
            image_reading=reading_result,
            storage_path=storage_path,
            original_filename=filename,
            mime_type=mime_type,
            file_size=len(file_content),
            competitor_id=competitor_id,
            round_id=round_id,
            actor_id=actor_id,
            form_data={"target_date": target_date},
            existing_bet_id=temp_bet.id,
        )

        status_container.update(label="✨ Processamento concluído", state="complete")

    # --- Feedback final para o administrador ---
    if result.status == "approved":
        st.success("🎉 Aposta registrada com sucesso! A IA identificou os valores perfeitamente.")
        
        # Exibe os dados que a IA leu
        val_stake = normalized.stake_value if normalized.stake_value else 0.0
        val_odd = normalized.total_odd if normalized.total_odd else 1.5
        st.info(
            f"**Dados extraídos:**\n"
            f"- 💰 **Valor:** R$ {val_stake:.2f}\n"
            f"- 📊 **Odd total:** {val_odd:.2f}\n"
            f"- 🎲 **Seleções:** {len(normalized.selections)} combinada(s)"
        )
        st.balloons()
    elif result.status == "review":
        val_odd = normalized.total_odd if normalized.total_odd else 1.50
        num_selections = len(normalized.selections) if normalized.selections else 0
        has_selections = num_selections > 0
        missing_stake = any("Valor da aposta" in w for w in validation.warnings)
        
        if reading_result.confidence_score >= 0.75 and has_selections and missing_stake:
            st.warning(
                f"🔍 **Aposta registrada e enviada para revisão manual (Falta o valor apostado na imagem)**.\n\n"
                f"**A IA leu com sucesso os seguintes dados (Confiança: {reading_result.confidence_score:.0%}):**\n"
                f"- 📊 **Odd total:** {val_odd:.2f}\n"
                f"- 🎲 **Seleções:** {num_selections} combinada(s) detectada(s)\n\n"
                f"Como o valor apostado não foi localizado no comprovante (ex: imagem cortada no rodapé), "
                f"o sistema definiu o valor temporário de R$ 1,00. O administrador irá ajustar para o valor correto ao aprovar no Painel Administrativo."
            )
        else:
            st.warning(
                "🔍 Aposta registrada e enviada para revisão manual.\n"
                "A imagem do comprovante foi salva com sucesso, mas a IA teve dificuldades de ler "
                "ou a confiança ficou abaixo do esperado. O administrador fará a validação."
            )
    else:
        st.error(f"❌ Aposta rejeitada pelo sistema. {result.message}")
