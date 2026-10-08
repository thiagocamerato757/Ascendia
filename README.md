# Ascendia

Alternativa open-source e auto-hospedável ao NotebookLM: organize **fontes** (PDFs e
texto) em **cadernos**, converse com elas e gere materiais de estudo, com respostas
baseadas apenas nas fontes e com citação.

Diferenciais planejados: provedor de LLM configurável por caderno (OpenAI, Gemini,
Claude, DeepSeek, modelos locais), estilo de resposta configurável, avaliação embutida
(qualidade, latência e custo) e uso da sua própria chave de API.

A especificação completa e as decisões de projeto estão em
[`docs/ASCENDIA_SPEC.md`](docs/ASCENDIA_SPEC.md). O estado atual e o planejamento por
fases estão em [`docs/audit.md`](docs/audit.md),
[`docs/frontend.md`](docs/frontend.md) e [`docs/decisions.md`](docs/decisions.md).

> **Status:** Fase 3 concluída: ingestão de PDF e texto, busca híbrida (full-text +
> vetorial com RRF), respostas em streaming com citações validadas e clicáveis, e
> "não encontrei" quando as fontes não cobrem a pergunta. Avaliação (Fase 4),
> reranking/CRAG (Fase 5) e materiais gerados (Fase 6) vêm a seguir.

## Stack

- Django 5.2 (server-rendered), Python 3.11+
- Postgres 16 + pgvector (vetores e busca textual no mesmo banco)
- LiteLLM (provedores de LLM e embeddings), PyMuPDF (PDF)
- Fila de tarefas no Postgres (`django-tasks` + `django-tasks-db`), sem broker
- uv para dependências; gunicorn + uvicorn worker (ASGI) para servir; WhiteNoise para estáticos
- Front-end próprio com design tokens (CSS, tema claro/escuro) + HTMX; interface no idioma do navegador (pt-BR/en)

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

# 3. Suba o app (banco + web + worker). Na primeira vez ele constrói a imagem,
#    aplica as migrations e coleta os arquivos estáticos.
docker compose up --build
```

O app fica em http://localhost:8000/. São três serviços:

- **db**: Postgres com pgvector;
- **web**: a aplicação;
- **worker**: processa as fontes enviadas (leitura do PDF, divisão em trechos e embeddings)
  a partir da fila no banco (`python manage.py db_worker`).

Os arquivos das fontes ficam no volume `sources`, compartilhado por `web` e `worker` e nunca
servido por URL pública. Se o `worker` estiver parado, as fontes ficam "Na fila" até ele subir.

### Desenvolvimento (recarga automática)

O `docker-compose.override.yml` é aplicado automaticamente pelo `docker compose up`
e monta o código-fonte no contêiner, rodando o `uvicorn --reload` (ASGI, o mesmo servidor da produção). Assim,
edições em Python, templates, CSS e JS valem **na hora**, sem reconstruir a imagem
(o Python recarrega sozinho, inclusive no `worker`; os estáticos são servidos direto da
fonte com `DJANGO_DEBUG=True`). Reconstrua a imagem só quando mudar dependências
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

## Usar um caderno

A página do caderno tem três painéis: **Fontes**, **Conversa** e **Notas**. Em telas estreitas
eles viram abas.

1. **Fontes**: arraste PDFs ou arquivos Markdown (`.md`) para a área de envio, ou escolha vários de uma vez (até
   `ASCENDIA_UPLOAD_MAX_FILES`, padrão 10, com `ASCENDIA_SOURCE_MAX_MB`, padrão 25 MB, cada), ou cole um texto.
   Cada arquivo é conferido sozinho: um PDF inválido não impede os outros, e o aviso diz o que ficou de fora. A
   fonte passa por "Na fila" → "Processando" → "Pronta" (ou "Falhou", com o motivo e
   "Tentar de novo"). Só fontes prontas e marcadas entram nas respostas. PDFs escaneados
   (só imagem) precisam de OCR antes.
2. **Conversa**: pergunte. Fórmulas em LaTeX (`$…$`, `$$…$$`, `\(…\)`, `\[…\]`) aparecem formatadas (KaTeX, servido pelo próprio app) e blocos de código vêm com realce de sintaxe e botão "Copiar código". A resposta chega em streaming e cita os trechos como `[n]`.
   Clicar num número abre o trecho (fonte, página e seção) e destaca a fonte. Se as fontes
   não respondem, o app diz que não encontrou. O botão **Parar** interrompe a resposta.
3. **Trocar o modelo de embedding** do caderno deixa as fontes antigas de fora até você
   clicar em **Reindexar fontes** (vetores de modelos diferentes nunca são misturados).

Parâmetros de ingestão e busca (todos opcionais, ver `.env.example`):
`ASCENDIA_CHUNK_SIZE`/`ASCENDIA_CHUNK_OVERLAP` (tamanho e sobreposição dos trechos, em
caracteres), `ASCENDIA_RAG_TOP_K`, `ASCENDIA_RAG_CANDIDATES`, `ASCENDIA_RAG_RRF_K` e os limites
`ASCENDIA_RATE_ASK_PER_MIN`/`ASCENDIA_RATE_UPLOAD_PER_MIN`.

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

1. **Provedores** (`/llm/api-keys/`, link "Provedores" no topo), em duas seções:
   - **Na nuvem**: OpenAI, Anthropic (Claude), Google Gemini, DeepSeek, Mistral, Groq,
     xAI (Grok), Perplexity, Together AI, NVIDIA NIM e **OpenRouter** (gateway). Cole a
     **chave de API** e salve. A chave fica criptografada e nunca volta a ser exibida,
     nem parcialmente.
   - **Servidores locais**: **Ollama**, **LM Studio** e **llama.cpp**. Salve a **URL do
     servidor**. O campo já vem com o padrão; no Docker o padrão aponta para a sua máquina
     (`host.docker.internal`, via `ASCENDIA_LOCAL_LLM_HOST`). Por segurança, só são aceitos
     os hosts de `ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS` (padrão: `localhost`, `127.0.0.1`, `::1`,
     `host.docker.internal`). Para um servidor de modelos em outra máquina da rede,
     adicione o endereço dela nessa variável (ver `.env.example`).

   Depois de salvar a chave ou a URL, ficam liberados **Atualizar modelos** (busca a lista
   ao vivo e separa modelos de chat e de embedding) e **Testar conexão** (nuvem: chamada
   mínima, pulando modelos que o provedor lista mas não atende; local: alcance do servidor).
2. **Configurações do caderno** (botão **Configurações** na página do caderno): selecione o
   **provedor** e os **modelos** de chat e de embedding. A lista mostra os modelos carregados
   pelo "Atualizar modelos"; se não houver, a lista embutida, ou texto livre quando não há
   nenhuma. Ajuste também o **estilo** (predefinição, tom, tamanho, idioma, formato, nível de
   detalhe e instruções extras). A página mostra a **instrução de sistema compilada**, no
   idioma da interface.

As regras de segurança (responder só pelas fontes, citar, admitir quando não encontrou)
são fixas e nunca são sobrescritas pelo estilo ou pelas instruções extras.

## Rodar a avaliação

_Em breve (Fase 4)._ Um comando `manage.py run_eval` medirá recall@k, MRR, validade das
citações, latência, tokens e custo, com resultados comparáveis entre provedores.

## Capturas de tela

_Em breve._
