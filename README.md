# Web App Controle de Apostas N1

Sistema de controle de apostas para competição interna, construído com **FastAPI + HTML/CSS/JS + Supabase + Gemini Vision**.

---

## 🚀 Setup Inicial

### 1. Pré-requisitos
- Python 3.11+
- Conta no [Supabase](https://supabase.com)
- Chave de API do [Google Gemini](https://aistudio.google.com/app/apikey)

### 2. Instalação
```bash
pip install -r requirements.txt
```

### 3. Configuração de ambiente
```bash
# Copie o template e preencha os valores
copy .env.example .env
```

Variáveis obrigatórias no `.env`:
```
SUPABASE_URL=https://SEU_PROJETO.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
GEMINI_API_KEY=...
```

### 4. Configurar o Supabase

Execute os scripts SQL **nesta ordem** no SQL Editor do Supabase:

```bash
# 1. Criar as tabelas
supabase/schema.sql

# 2. Criar as políticas RLS
supabase/rls_policies.sql

# 3. Inserir dados iniciais
supabase/seed.sql
```

**Crie o bucket de Storage:**
- Dashboard → Storage → New Bucket
- Nome: `bet-images`
- Acesso: **Private**

**Crie o usuário admin:**
- Dashboard → Authentication → Users → Invite User
- Após criação, copie o UUID e execute:
```sql
INSERT INTO public.profiles (auth_user_id, full_name, email, role)
VALUES ('UUID-AQUI', 'Administrador', 'admin@email.com', 'admin');
```

### 5. Executar a aplicação
```bash
uvicorn backend.main:app --reload
```

Acesse em: `http://localhost:8000`

---

## 🧪 Testes

```bash
# Rodar todos os testes
pytest tests/ -v

# Com cobertura
pytest tests/ --cov=. --cov-report=term-missing
```

---

## 🏗️ Estrutura do Projeto

```
backend/                  ← API FastAPI (ponto de entrada: backend/main.py)
  main.py                 ← Monta rotas /api/* e serve frontend/ como estático
  security.py             ← Validação do Bearer token (Supabase JWT)
  routers/
    auth.py / competitors.py / rounds.py / bets.py / admin.py
frontend/                 ← SPA em HTML/CSS/JS puro
  index.html
  css/                    ← theme.css / components.css
  js/
    api.js / router.js / sidebar.js / format.js / app.js
    pages/
      login.js / competidores.js / apostas.js / admin.js
.env.example              ← Template de configuração
requirements.txt
pyproject.toml            ← Configuração do pytest
supabase/
  schema.sql              ← DDL do banco
  rls_policies.sql        ← Políticas de segurança
  seed.sql                ← Dados iniciais
config/
  settings.py             ← Constantes e env vars
  supabase_client.py      ← Cliente Supabase (singleton)
agents/
  leitura_imagem.py       ← AgentLeituraImagem (Gemini Vision)
  normalizacao_aposta.py  ← AgentNormalizacaoAposta
  validador_regras.py     ← AgentValidadorRegras
  persistencia.py         ← AgentPersistencia
  ranking.py              ← AgentRanking
  auditoria.py            ← AgentAuditoria
services/
  auth_service.py         ← Autenticação Supabase
  bet_service.py          ← Regras de apostas
  upload_service.py       ← Upload Storage
  ranking_service.py      ← Cálculo de ranking
  round_service.py        ← Ciclo de rodadas
models/
  bet.py / competitor.py / round.py / audit.py
repositories/
  bet_repository.py / image_repository.py
  round_repository.py / competitor_repository.py
  audit_repository.py / settlement_repository.py
tests/
  test_bet_service.py / test_upload_service.py
  test_validators.py / test_ranking_service.py / test_round_service.py
```

---

## 📋 Regras de Negócio

| Regra | Valor |
|---|---|
| Apostas por dia | Máximo **2** |
| Odd mínima | **1.50** por seleção |
| Seleções por aposta | Máximo **3** (combinadas) |
| Prazo de upload | Até **23:59 do dia anterior** |
| Rodada semanal | **Domingo 00:00 → Sábado 23:59** |
| Confiança mínima da IA | **75%** (configurável) |

---

## 🔐 Segurança

- Autenticação via **Supabase Auth**
- **RLS** habilitado em todas as tabelas sensíveis
- Competidor acessa **apenas suas próprias apostas**
- Admin tem acesso irrestrito via service role
- Validação de prazo em **duas camadas** (front + backend)
- Upload protegido por MIME type e magic bytes

---

## 🤖 Pipeline de IA

```
Upload → Storage → AgentLeituraImagem (Gemini Vision)
       → AgentNormalizacaoAposta
       → AgentValidadorRegras
       → AgentPersistencia (Supabase)
```

Se confiança < 75%: aposta vai para **revisão manual** (admin).

---

## 🌐 Deploy em Produção

### Opção 1: Render / Railway / Heroku (via Procfile)
1. Conecte seu repositório no [Render](https://render.com) ou [Railway](https://railway.app).
2. Escolha o ambiente **Python 3.11+**.
3. O serviço detectará automaticamente o arquivo `Procfile`:
   ```bash
   web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```
4. Configure as variáveis de ambiente no painel:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `GEMINI_API_KEY`
   - `GEMINI_MODEL=gemini-2.5-flash`
   - `TIMEZONE=America/Sao_Paulo`

### Opção 2: Docker / Container
```bash
# Build da imagem
docker build -t campeonato-n1 .

# Execução do container
docker run -d -p 8000:8000 --env-file .env campeonato-n1
```
Acesse em: `http://localhost:8000`

