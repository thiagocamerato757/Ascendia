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

> **Status:** Fase 2 concluída (camada de provedores, credenciais e estilo por caderno).
> A ingestão/busca (RAG) e a avaliação são das fases seguintes.

## Stack

- Django 5.2 (server-rendered), Python 3.11+
- Postgres 16 + pgvector
- uv para dependências; gunicorn + uvicorn worker (ASGI) para servir; WhiteNoise para estáticos
- Front-end próprio com design tokens (CSS, tema claro/escuro) + HTMX; interface em pt-BR (i18n)

## Guia de estilo (styleguide)

Com `DEBUG=True`, a rota `/styleguide/` renderiza todos os componentes e estados nos
dois temas — a referência de consistência visual. Fica indisponível (404) em produção.

## Como rodar com Docker

Pré-requisitos: Docker e Docker Compose.

```bash
# 1. Crie o seu .env a partir do exemplo
cp .env.example .env

# 2. Gere uma SECRET_KEY e cole em DJANGO_SECRET_KEY no .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# 2b. Gere a chave de criptografia das chaves de API e cole em ASCENDIA_FERNET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 3. Suba o app (banco + web). Na primeira vez ele constrói a imagem,
#    aplica as migrations e coleta os arquivos estáticos.
docker compose up --build
```

O app fica em http://localhost:8000/.

### Desenvolvimento (recarga automática)

O `docker-compose.override.yml` é aplicado automaticamente pelo `docker compose up`
e monta o código-fonte no contêiner, rodando o `runserver` do Django. Assim,
edições em Python, templates, CSS e JS valem **na hora**, sem reconstruir a imagem
(o Python recarrega sozinho; os estáticos são servidos direto da fonte com
`DJANGO_DEBUG=True`). Reconstrua a imagem só quando mudar dependências
(`pyproject.toml`/`uv.lock`).

### Produção / CI

Use apenas o arquivo base (sem o override), que serve via gunicorn + uvicorn e
roda `collectstatic`:

```bash
docker compose -f docker-compose.yml up --build
```

> **Sem Django admin.** O Ascendia é auto-hospedável e toda a configuração é feita
> pelo próprio usuário dentro do app (perfil, cadernos, chaves de API e configurações
> por caderno). A rota `/admin/` não existe, nem em produção nem em desenvolvimento.
> Contas são criadas pelo cadastro normal (`/users/`).

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

As **chaves de API** são do usuário (criptografadas em repouso — Fernet, via
`ASCENDIA_FERNET_KEY`); o **provedor, o modelo e o estilo de resposta** são **por caderno**.

1. **Provedores** (`/llm/api-keys/`, link "Providers" no topo): um grid com todos os
   provedores. Em cada card você **cola a chave** (nuvem) ou define a **Base URL** (endpoints
   locais), clica **Atualizar modelos** para listar os modelos do provedor ao vivo e **Testar**
   (nuvem: chamada mínima; local: reachability do endpoint). A chave é somente escrita: fica
   criptografada e nunca volta a ser exibida. Provedores de nuvem: OpenAI, Anthropic (Claude),
   Google Gemini, DeepSeek, Mistral, Groq, xAI (Grok), Perplexity, Together AI, NVIDIA NIM e **OpenRouter**
   (gateway para 200+ modelos). Endpoints locais (com Base URL própria): **Ollama**, **LM
   Studio** e **llama.cpp**.
2. **Configurações do caderno** (botão **Settings** na página do caderno): selecione o
   **provedor** e os **modelos** (de chat e de embedding; a lista mostra os modelos
   carregados via "Atualizar modelos", senão a lista curada, ou texto livre para
   OpenRouter/endpoints locais sem lista) e ajuste o **estilo** (preset, tom, tamanho,
   idioma, formato, nível de detalhe e instruções extras). A página mostra a **instrução de
   sistema compilada** a partir desse estilo.

As regras de segurança (responder só pelas fontes, citar, admitir quando não encontrou)
são fixas e nunca são sobrescritas pelo estilo ou pelas instruções extras.

## Rodar a avaliação

_Em breve (Fase 4)._ Um comando `manage.py run_eval` medirá recall@k, MRR, validade das
citações, latência, tokens e custo, com resultados comparáveis entre provedores.

## Capturas de tela

_Em breve._
