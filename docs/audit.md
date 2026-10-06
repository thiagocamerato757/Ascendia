# Auditoria do repositório — Ascendia

> Fase 0 da `ASCENDIA_SPEC.md` (seção 0, item 1). Levantamento do estado atual **antes** de implementar. Nenhum código foi alterado.
> Data: 2026-10-06.

## Resumo executivo

O repositório é um projeto Django 5.2.7 funcional, pequeno e bem testado (110 testes passando), focado em **autenticação de usuários e organização de cadernos/notas**. É uma base limpa para começar, mas **ainda não tem nada do núcleo de RAG** descrito na spec: sem fontes/chunks, sem camada de LLM, sem embeddings, sem busca, sem avaliação. O front-end usa Tailwind via CDN + classes utilitárias próprias, **não** o sistema de design tokens/componentes exigido pela spec. A infraestrutura da Fase 0 (Docker, CI, `.env.example`, README) ainda não existe.

Em termos de fases da spec (seção 13): **nada da Fase 0–7 está concluído**; o que existe é a camada de usuários/cadernos/notas que servirá de base.

---

## 1. Stack e configuração

| Item | Valor atual | Observação vs. spec |
|---|---|---|
| Python | 3.14.3 (`.python-version` = 3.14; `pyproject.toml` exige `>=3.14`) | **[VERIFICAR] da spec (§3/§14):** nada no código exige 3.14; é a versão mais recente e sem imagem Docker estável consolidada. Candidato a baixar para 3.12/3.13. |
| Django | 5.2.7 | OK. |
| Banco | **SQLite** (`db.sqlite3`, versionado no repo até o `.gitignore` recente) | Spec exige **Postgres + pgvector** (D1). Migração necessária. `db.sqlite3` está no `.gitignore` agora. |
| Servidor | `uvicorn`, `gunicorn` nas deps | OK, já previstos (§3). |
| Dependências | django, uvicorn, gunicorn, python-dotenv, pillow | **Faltam:** `psycopg`/pgvector, `litellm`, `pymupdf`, `cryptography` (Fernet), etc. |
| Gestão de deps | `pyproject.toml` + `uv.lock` (uv) | Sem `requirements.txt`. |

### Configuração sensível (`core/settings.py`)
- `SECRET_KEY` **hardcoded** (`django-insecure-...`) e `DEBUG = True` fixo; `ALLOWED_HOSTS = []`.
- Existe um `.env` no repo com `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_ADMIN_URL`, **mas `settings.py` não lê nenhuma dessas variáveis** — `python-dotenv` é dependência mas não é usado em `core/`. Desconexão a corrigir na Fase 0/2 (D6: segredos fora do repo).
- `LANGUAGE_CODE = 'en-us'`, `TIME_ZONE = 'UTC'`. Spec pede **pt-BR** por padrão (§6, §10.6) com i18n.
- Sem configuração de upload (limite de tamanho, tipos), rate limiting, ou logging — todos exigidos (§11).

---

## 2. Apps Django existentes

Instalados: `users`, `workspace`, `notes` (+ apps contrib, incluindo `humanize`). `core` é o projeto.

### `core/` — projeto/config
- `settings.py`, `urls.py`, `wsgi.py`, `asgi.py`, `views.py` (`HomeView` → `homepage.html`).
- URL raiz `''` → home; inclui `users/`, `workspace/`, `notes/`, `admin/`.

### `workspace/` — cadernos
- **Modelo `Notebook`**: `user` (FK), `title`, `description`, `color` (hex, default aurora), `created_at`, `updated_at`, `is_favorite`. Ordenação por `-updated_at`.
- Views CBV completas: list (home), detail, create, update, delete, toggle-favorite (com resposta JSON para AJAX). **Isolamento por usuário correto** (`filter(user=self.request.user)` em todos os querysets).
- **Mapeia para o `Notebook` da spec (§4).** Falta `NotebookSettings` (provedor, modelo, embedding, estilo). Serve de base — não precisa recriar.

### `notes/` — notas e tags
- **Modelos:** `Note` (notebook FK, user FK, title, content, created/updated, is_pinned, order), `Tag` (name, user, color, unique por usuário), `NoteTag` (M2M note↔tag).
- Views CBV: CRUD de nota, toggle-pin, lista/criação de tags, add/remove tag.
- `Note` é conceitualmente próximo mas **não** é `Source`/`Chunk`. Na spec, `Source` tem tipo (pdf/texto/link), status de ingestão e arquivo; `Chunk` tem embedding/página. **Decisão em aberto (§14):** reaproveitar `Note` como base de `Source` ou criar modelos novos no app `sources`. Recomendação preliminar: criar `sources`/`Chunk` novos (responsabilidade nova: ingestão/vetor), mantendo `Note` como "nota manual" do usuário.

### `users/` — contas e perfil
- **Modelo `Profile`** (OneToOne com `User`): avatar (ImageField), whatsapp; criado por signal `post_save`. Properties `avatar_url`, `whatsapp_link`.
- Fluxos: signup, login customizado (`CustomLoginView` com "remember me"), logout, reset de senha completo (4 telas), perfil, upload/recorte de avatar.
- Comando de gestão `create_profiles` (backfill de perfis).
- Tipagem presente (type hints), bom padrão de referência.

**Não existem** os apps previstos na spec: `sources`, `llm`, `rag`, `evals`. Nenhum é necessário ainda — só após as fases correspondentes.

---

## 3. URLs

| Prefixo | App | Rotas-chave |
|---|---|---|
| `/` | core | `home` |
| `/admin/` | admin | — |
| `/users/` | users | signup, login, logout, password-reset (×4), profile, update-avatar |
| `/workspace/` | workspace | home, notebook detail/create/edit/delete/toggle-favorite |
| `/notes/` | notes | note create/detail/edit/delete/toggle-pin, tags, add/remove tag |

Padrão: CBVs com `app_name` + namespaces (`workspace:home`, `notes:note_detail`). `LOGIN_REDIRECT_URL='workspace:home'`. **Não há** rota `/styleguide/` (§10.7) nem rotas de chat/fontes/eval.

---

## 4. Front-end e templates

- **`base.html` único** com blocks: `title`, `extra_css`, `nav_links`, `content`, `footer`, `notifications`, `extra_js`, `body_class`. Todas as páginas estendem a base. ✔ alinhado com §10.1.
- **Carrega Tailwind via CDN** (`<script src="https://cdn.tailwindcss.com">`) **+** CSS próprio. Ou seja: **mistura utilitárias (Tailwind) com classes de componente próprias** (`.btn-primary`, `.card-aurora`, `.navbar-aurora`, `.glow-aurora`) — exatamente o que §10.3 proíbe ("sem misturar utilitárias com BEM"). Tailwind CDN também não é adequado a produção.
- **`static/css/`**: `design.css` (426 l — paleta aurora em `:root`, tipografia Inter/Space Grotesk via Google Fonts, botões, cards), `notifications.css`, `profile.css`, `cropper-custom.css` (recorte de avatar). **Não existe `tokens.css`.**
- **Tema:** só **escuro** ("aurora"), gradientes/glass. **Não há tema claro** nem `prefers-color-scheme`/alternância (§10.2 exige ambos).
- **Design tokens:** há variáveis de **cor** em `:root`, mas não a escala completa exigida (espaçamento fixo, raios, sombras, tipografia tokenizada). Cores/espaços/tamanhos soltos e `style=""` inline aparecem nos templates (ex.: `style="background: {{ notebook.color }}"`) — §10.2 proíbe valores soltos.
- **Componentes:** **não existe `templates/components/`**. Nenhum partial reutilizável; nada de bolha de mensagem, chip de citação, lista de fontes, painel de config (todos exigidos em §10.3).
- **JS:** mínimo. **Sem HTMX, sem Alpine** (grep vazio). §10.1 recomenda HTMX — decisão em aberto (§14).
- **i18n:** textos em **inglês** hardcoded nos templates; sem uso de `{% trans %}`. Spec pede pt-BR centralizado.
- **Layout:** não há o layout de três painéis do NotebookLM (§10.4) — ainda não há tela de caderno com fontes/conversa/materiais.

Detalhe completo irá para `docs/frontend.md` (Fase 0).

---

## 5. Testes

- **110 testes, todos passando** (`python manage.py test` → OK em ~29 s).
- Distribuição: `users/tests.py` (969 l — o grosso), `notes/tests.py` (379 l), `workspace/tests.py` (233 l).
- Cobrem: modelos, forms, views, signals, **CSRF**, **SQL injection**, **XSS**, remember-me, reset de senha, upload de avatar.
- **`run_tests.sh`**: ativa `.venv` (aborta se não existir) e roda `python manage.py test --verbosity=1`. Simples e reutilizável (§12 **[VERIFICAR]** respondido: é assim que roda hoje).
- **Lacunas vs. spec (§12):** nenhum teste de `compile_style`, chunking, RRF, validação de citações, ingestão/busca, isolamento entre cadernos de usuários diferentes (há isolamento no código, mas não há teste que tente acessar caderno alheio), nem PDFs adversariais. Esperado — essas features ainda não existem.

---

## 6. Infraestrutura / qualidade (Fase 0)

| Exigido pela spec (§3, §12, §13) | Estado |
|---|---|
| `docker-compose` (web + db pgvector) | **Ausente** |
| `Dockerfile` | **Ausente** |
| `.env.example` completo | **Ausente** (existe um `.env` real, não exemplo, e não lido pelo settings) |
| CI GitHub Actions (ruff + testes + build) | **Ausente** (`.github/` não existe) |
| README (o que é, screenshots, como rodar, provedores, eval) | **Vazio** (0 bytes) |
| `CLAUDE.md` referenciando a spec | **Ausente** (a spec pede, seção de cabeçalho) |
| Lint ruff | Não configurado |

---

## 7. Lacunas por fase (visão rápida)

- **Fase 0 (infra/docs):** falta Docker, CI, `.env.example`, README, `CLAUDE.md`; `docs/` já tem `audit.md`, `frontend.md` e `decisions.md`. Migrar SQLite→Postgres+pgvector. Reduzir piso do Python.
- **Fase 1 (front-end):** criar `tokens.css`, refatizar base/templates para tokens + componentes, tema claro/escuro, `/styleguide/`, resolver mistura Tailwind×classes próprias, i18n pt-BR.
- **Fase 2 (provedores/estilo):** apps `llm`; `NotebookSettings`, `ProviderCredential` (Fernet), `compile_style`, cliente LiteLLM, fake provider para testes.
- **Fase 3 (RAG):** apps `sources`, `rag`; `Source`/`Chunk`, ingestão PyMuPDF, busca híbrida RRF, chat com citação validada, streaming.
- **Fase 4 (evals):** app `evals`; `run_eval`, métricas, página de comparação.
- **Fases 5–7:** reranking/CRAG, saídas com LangGraph, servidor MCP.

---

## 8. Pontos fortes a preservar

- Isolamento por usuário já aplicado consistentemente nos querysets de `workspace`/`notes`.
- Suíte de testes sólida (incl. segurança) e `run_tests.sh` reutilizável.
- Padrão CBV + namespaces de URL + `base.html` com blocks, limpo e consistente.
- Tipagem e docstrings em `users/` servem de referência de estilo para o código novo.
- Paleta/identidade visual "aurora" definida — pode virar a base dos tokens em vez de ser descartada.

---

## 9. Decisões em aberto levantadas (para `docs/decisions.md`)

1. Python: reduzir piso para suportar várias versões (3.11–3.14), não fixar em 3.14.
2. `Note` vs. novos modelos `Source`/`Chunk` (recomendação: modelos novos em `sources`, manter `Note`).
3. SQLite → Postgres+pgvector (confirmado pela spec; planejar migração).
4. Front-end: adotar HTMX e eliminar a mistura Tailwind-CDN × classes próprias (§10.1/§10.3).
5. Conectar `settings.py` ao `.env` (python-dotenv já é dependência) e tirar `SECRET_KEY`/`DEBUG` do código.
6. Idioma padrão → pt-BR com i18n.
