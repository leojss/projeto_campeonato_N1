"""
create_test_users.py — Script utilitário para criar usuários de teste no Supabase.

Este script utiliza a chave service_role para criar os usuários diretamente
no Supabase Auth (sem necessidade de confirmação de e-mail) e os vincula
nas tabelas `profiles` e `competitors`.

Execução:
    python create_test_users.py
"""

from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório atual ao path para importar os módulos do projeto
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

from config.supabase_client import get_admin_client
from repositories.competitor_repository import CompetitorRepository
from models.competitor import Profile, Competitor
from agents.auditoria import AgentAuditoria
from models.audit import AuditAction

def create_user(email: str, password: str, full_name: str, role: str) -> str | None:
    """Cria um usuário no Supabase Auth e retorna o auth_user_id."""
    client = get_admin_client()
    email_clean = email.strip().lower()
    
    print(f"Criando usuário Auth para {email_clean} ({role})...")
    try:
        # Cria no Supabase Auth usando o painel Admin (ignora confirmação de e-mail)
        response = client.auth.admin.create_user({
            "email": email_clean,
            "password": password,
            "email_confirm": True
        })
        auth_user_id = response.user.id
        print(f"✅ Usuário {email_clean} criado no Auth. UUID: {auth_user_id}")
        return auth_user_id
    except Exception as e:
        # Se já existir no Auth, vamos tentar obter o usuário
        if "already exists" in str(e).lower() or "already registered" in str(e).lower():
            print(f"ℹ️ Usuário {email_clean} já existe no Supabase Auth. Buscando UUID...")
            try:
                # Busca lista de usuários para encontrar o UUID
                users_resp = client.auth.admin.list_users()
                for user in users_resp.users:
                    if user.email.lower() == email_clean:
                        print(f"✅ UUID encontrado: {user.id}")
                        return user.id
            except Exception as read_err:
                print(f"❌ Erro ao buscar usuário existente: {read_err}")
        else:
            print(f"❌ Erro ao criar usuário {email_clean} no Auth: {e}")
    return None

def main():
    print("=== Cadastro de Usuários de Teste ===")
    
    # 1. Usuário Administrador de Teste
    admin_email = "admin@apostasn1.com"
    admin_pass = "admin123"
    admin_auth_id = create_user(admin_email, admin_pass, "Administrador de Teste", "admin")
    
    if admin_auth_id:
        try:
            # Verifica se já existe perfil
            existing_profile = CompetitorRepository.get_profile_by_auth_id(admin_auth_id)
            if not existing_profile:
                profile = Profile(
                    auth_user_id=admin_auth_id,
                    full_name="Administrador de Teste",
                    email=admin_email,
                    role="admin"
                )
                CompetitorRepository.create_profile(profile)
                print("✅ Perfil Admin registrado na tabela profiles.")
            else:
                print("ℹ️ Perfil Admin já existe na tabela profiles.")
        except Exception as e:
            print(f"❌ Erro ao criar perfil admin no banco (certifique-se de que rodou o schema.sql primeiro): {e}")

    print("-" * 40)

    # 2. Usuário Competidor de Teste
    comp_email = "competidor1@apostasn1.com"
    comp_pass = "competidor123"
    comp_auth_id = create_user(comp_email, comp_pass, "Competidor Um", "competidor")
    
    if comp_auth_id:
        try:
            # Verifica se já existe perfil
            existing_profile = CompetitorRepository.get_profile_by_auth_id(comp_auth_id)
            profile_id = None
            if not existing_profile:
                profile = Profile(
                    auth_user_id=comp_auth_id,
                    full_name="Competidor Um",
                    email=comp_email,
                    role="competidor"
                )
                created_profile = CompetitorRepository.create_profile(profile)
                profile_id = created_profile.id
                print("✅ Perfil Competidor registrado na tabela profiles.")
            else:
                profile_id = existing_profile.id
                print("ℹ️ Perfil Competidor já existe na tabela profiles.")
                
            # Verifica se já existe competitor lógico
            if profile_id:
                existing_comp = CompetitorRepository.get_competitor_by_profile(profile_id)
                if not existing_comp:
                    competitor = Competitor(
                        profile_id=profile_id,
                        display_name="Competidor Um"
                    )
                    CompetitorRepository.create_competitor(competitor)
                    print("✅ Competidor registrado na tabela competitors.")
                else:
                    print("ℹ️ Competidor já cadastrado na tabela competitors.")
        except Exception as e:
            print(f"❌ Erro ao criar competidor no banco (certifique-se de que rodou o schema.sql primeiro): {e}")

    print("\n=== Concluído ===")
    print("Credenciais criadas para teste:")
    print(f"🛡️ Admin: {admin_email} / Senha: {admin_pass}")
    print(f"🏆 Competidor: {comp_email} / Senha: {comp_pass}")

if __name__ == "__main__":
    main()
