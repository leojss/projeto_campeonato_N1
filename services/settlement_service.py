"""
services/settlement_service.py — SettlementService
Motor de liquidação automática de apostas e atualização de saldo dos competidores.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict

from config.supabase_client import get_admin_client
from repositories.bet_repository import BetRepository
from repositories.competitor_repository import CompetitorRepository
from models.bet import Bet, BetSelection
from agents.liquidador import AgentLiquidador
from agents.auditoria import AgentAuditoria


class SettlementService:
    """Serviço responsável pela liquidação de apostas e atualização de saldos."""

    @staticmethod
    def run_auto_settlement() -> Dict:
        """
        Executa a rotina de conferência e liquidação para todas as seleções pendentes.
        
        Returns:
            Dicionário com o resumo da execução (seleções processadas, apostas liquidadas, logs).
        """
        results = {
            "selections_checked": 0,
            "selections_resolved": 0,
            "bets_settled": 0,
            "logs": []
        }

        # 1. Obtém seleções que ainda estão pendentes
        pending_selections = BetRepository.get_pending_selections()
        if not pending_selections:
            results["logs"].append("Nenhuma seleção de aposta pendente para auditar.")
            return results

        results["logs"].append(f"Encontrada(s) {len(pending_selections)} seleção(ões) pendente(s). Chamando IA resolvedora...")
        
        # 2. Inicializa resolvedor de IA
        liquidador = AgentLiquidador()
        client = get_admin_client()

        # Guarda IDs de apostas afetadas para validar fechamento delas depois
        affected_bet_ids = set()

        for sel in pending_selections:
            results["selections_checked"] += 1
            event_name = sel.event_name or sel.description
            results["logs"].append(f"Auditando tip: '{sel.description}' no evento '{event_name}'...")
            
            # Resolve via IA
            resolution = liquidador.resolve_selection(sel)
            status = resolution.get("result_status", "pending")
            justification = resolution.get("justificativa", "")
            sources = resolution.get("fontes", [])

            # Delay de segurança para respeitar o limite de requisições da API Gemini
            import time
            time.sleep(4.0)

            if status != "pending":
                # Atualiza a seleção no banco
                update_data = {
                    "result_status": status,
                    "resolved_at": datetime.utcnow().isoformat(),
                    "resolution_source": sources[0] if sources else "Gemini IA"
                }
                
                success = BetRepository.update_selection(sel.id, update_data)
                if success:
                    results["selections_resolved"] += 1
                    affected_bet_ids.add(sel.bet_id)
                    results["logs"].append(
                        f"  -> RESOLVIDO: Status: {status.upper()} | Justificativa: {justification}"
                    )
                else:
                    results["logs"].append(f"  -> ERRO: Falha ao salvar a resolução da seleção {sel.id} no banco.")
            else:
                results["logs"].append(f"  -> PENDENTE: IA não conseguiu determinar o resultado. Justificativa: {justification}")

        # 3. Processa liquidação definitiva das apostas afetadas
        if affected_bet_ids:
            results["logs"].append("\nVerificando apostas para liquidação definitiva...")
            for bet_id in affected_bet_ids:
                bet = BetRepository.get_bet_by_id(bet_id)
                if not bet or bet.status == "settled":
                    continue
                
                # Carrega todas as seleções da aposta para checar se todas estão resolvidas
                selections = BetRepository.get_selections_by_bet(bet_id)
                all_resolved = all(s.result_status != "pending" for s in selections)
                
                if all_resolved:
                    results["logs"].append(f"Liquidadando Aposta ID {bet_id[:8]} do competidor...")
                    # Liquida a aposta individualmente
                    settled_outcome = SettlementService.settle_single_bet(bet, selections)
                    if settled_outcome:
                        results["bets_settled"] += 1
                        results["logs"].append(f"  -> Aposta liquidada com sucesso! Resultado final: {settled_outcome.upper()}")
                    else:
                        results["logs"].append(f"  -> ERRO ao liquidar a aposta {bet_id[:8]}.")
                else:
                    results["logs"].append(f"  -> Aposta ID {bet_id[:8]} possui outras seleções ainda pendentes.")

        return results

    @staticmethod
    def settle_single_bet(bet: Bet, selections: List[BetSelection]) -> str | None:
        """
        Calcula o lucro/perda da aposta e atualiza os pontos do competidor localmente.
        
        Args:
            bet: Objeto Bet da aposta mãe.
            selections: Lista de BetSelection da aposta.
            
        Returns:
            Outcome string ('win' | 'loss' | 'void') ou None em caso de erro.
        """
        client = get_admin_client()
        
        # 1. Determina o resultado financeiro (outcome)
        outcome = "win"
        has_loss = any(s.result_status == "lost" for s in selections)
        all_void = all(s.result_status in ["void", "push"] for s in selections)
        
        if has_loss:
            outcome = "loss"
            gross_return = 0.0
            net_profit = -float(bet.stake_value)
        elif all_void:
            outcome = "void"
            gross_return = float(bet.stake_value)
            net_profit = 0.0
        else:
            outcome = "win"
            # Recalcula a Odd final desconsiderando seleções anuladas (odd = 1.0)
            recalculated_odd = 1.0
            for s in selections:
                if s.result_status == "won":
                    recalculated_odd *= float(s.odd)
                # void e push consideram odd 1.0 (não alteram a multiplicação)
            
            recalculated_odd = round(recalculated_odd, 4)
            gross_return = float(bet.stake_value) * recalculated_odd
            net_profit = gross_return - float(bet.stake_value)

        # Ajusta precisões
        gross_return = round(gross_return, 2)
        net_profit = round(net_profit, 2)

        try:
            # 2. Cria o registro na tabela settlements (Unique constraint garante idempotência)
            settlement_data = {
                "bet_id": bet.id,
                "outcome": outcome,
                "gross_return": gross_return,
                "net_profit": net_profit
            }
            client.table("settlements").insert(settlement_data).execute()
            
            # 3. Atualiza o status da aposta para 'settled'
            BetRepository.update_bet_status(bet.id, "settled", f"Liquidada automaticamente via IA. Lucro: R$ {net_profit:.2f}")

            # 4. Atualiza o saldo de pontos do competidor no profile
            # Busca pontos atuais
            profile = CompetitorRepository.get_competitor_profile(bet.competitor_id)
            if profile:
                current_points = float(profile.get("points", 100.00))
                new_points = round(current_points + net_profit, 2)
                
                # Persiste novos pontos no profile
                client.table("profiles").update({"points": new_points}).eq("id", profile.get("id")).execute()
                
                # 5. Log de auditoria
                AgentAuditoria.log(
                    action="BET_SETTLED",
                    actor_id=bet.competitor_id,
                    entity_name="bets",
                    entity_id=bet.id,
                    payload={
                        "outcome": outcome,
                        "net_profit": net_profit,
                        "old_points": current_points,
                        "new_points": new_points
                    }
                )
            
            return outcome
        except Exception as e:
            # Registra falha de liquidação
            AgentAuditoria.log(
                action="SETTLEMENT_FAILED",
                actor_id=bet.competitor_id,
                entity_name="bets",
                entity_id=bet.id,
                payload={"error": str(e)}
            )
            return None
