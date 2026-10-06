# Ascendia

Alternativa open-source e auto-hospedável ao NotebookLM: organize **fontes** (PDFs,
texto, links) em **cadernos**, converse com elas e gere materiais de estudo, com
respostas baseadas apenas nas fontes e com citação.

Diferenciais planejados: provedor de LLM configurável por caderno (OpenAI, Gemini,
Claude, DeepSeek, modelos locais), estilo de resposta configurável, avaliação embutida
(qualidade, latência e custo) e uso da sua própria chave de API.

A especificação completa e as decisões de projeto estão em
[`docs/ASCENDIA_SPEC.md`](docs/ASCENDIA_SPEC.md). O estado atual e o planejamento por
fases estão em [`docs/audit.md`](docs/audit.md),
[`docs/frontend.md`](docs/frontend.md) e [`docs/decisions.md`](docs/decisions.md).

> **Status:** Fase 0 (fundação: auditoria, Docker, CI). As funcionalidades de RAG,
> provedores de LLM e avaliação são das fases seguintes.

## Stack

- Django 5.2 (server-rendered), Python 3.11+
- Postgres 16 + pgvector
- uv para dependências; gunicorn + uvicorn worker (ASGI) para servir; WhiteNoise para estáticos

## Como rodar com Docker

Pré-requisitos: Docker e Docker Compose.

```bash
# 1. Crie o seu .env a partir do exemplo
cp .env.example .env

# 2. Gere uma SECRET_KEY e cole em DJANGO_SECRET_KEY no .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 3. Suba o app (banco + web). Na primeira vez ele constrói a imagem,
#    aplica as migrations e coleta os arquivos estáticos.
docker compose up --build
```

O app fica em http://localhost:8000/.

Para criar um superusuário:

```bash
docker compose run --rm web python manage.py createsuperuser
```

## Rodar os testes

Os testes usam Postgres. Com o banco no ar via Docker (`docker compose up db`) e o
`POSTGRES_HOST=localhost` no `.env`:

```bash
./run_tests.sh
```

Alternativa, dentro do container (não exige Postgres no host):

```bash
docker compose run --rm web python manage.py test
```

## Lint

```bash
uv run ruff check .
```

## Configurar provedores de LLM

_Em breve (Fase 2)._ Cada caderno terá provedor, modelo e estilo configuráveis, com a
chave de API do próprio usuário armazenada criptografada.

## Rodar a avaliação

_Em breve (Fase 4)._ Um comando `manage.py run_eval` medirá recall@k, MRR, validade das
citações, latência, tokens e custo, com resultados comparáveis entre provedores.

## Capturas de tela

_Em breve._
