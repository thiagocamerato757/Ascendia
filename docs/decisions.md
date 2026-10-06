# Decisões de projeto — Ascendia

> Registro das decisões que não estão na `ASCENDIA_SPEC.md`, e das respostas aos `[VERIFICAR]` / "Decisões em aberto" (§14) levantadas na auditoria. Uma ou duas linhas por item, com data e motivo (§0, itens 4 e 5).

## Decididas na auditoria (2026-10-06)

- **`run_tests.sh` — como roda hoje** *(resolve §12 [VERIFICAR])*: ativa `.venv` e chama `python manage.py test --verbosity=1`; 110 testes passam. Decisão: **manter** e estender com os novos testes (estilo, chunking, RRF, citações).
- **Papel de cada app** *(resolve §3 [VERIFICAR])*: `users`=contas/perfil; `workspace`=`Notebook`; `notes`=`Note`/`Tag`; `core`=config. Decisão: **manter os três** como base; não recriar.

## Respondidas pelo autor (2026-10-06)

1. **`Note` vs. novos `Source`/`Chunk`** — **Decidido:** criar modelos **novos** (`Source`, `Chunk`) num app `sources`; `Note` segue como nota manual do usuário. Motivo: ingestão/vetor/página são responsabilidade nova e não cabem em `Note`.
2. **Front-end: abordagem** *(resolve §10.1 [VERIFICAR])* — **Decidido:** adotar **HTMX**, **remover o Tailwind CDN** e usar uma única camada de CSS própria com tokens (sem misturar utilitárias com BEM). Motivo: §10.1/10.3 e adequação a produção.
3. **Tarefa em segundo plano para ingestão** *(resolve §7.1 [VERIFICAR])* — **Decidido:** usar a **opção mais simples que atenda** (sem Celery+broker a menos que necessário). A escolha concreta (threads / `django-tasks` / RQ) fica definida no início da Fase 3, mas sem fila externa por padrão.
4. **Versão de Python** *(resolve §3/§14 [VERIFICAR])* — **Decidido:** **não fixar em 3.14**; tornar o projeto **compatível com várias versões** (alvo `requires-python = ">=3.11"`, cobrindo 3.11–3.14). Motivo: 3.14 não é exigido por nada no código e limita imagem Docker/portabilidade; Django 5.2 suporta 3.10+.
5. **Cross-encoder / reranking** *(§14)* — **Ainda a decidir** (Fase 5), conforme o ambiente de execução (CPU/GPU).

## Confirmadas pela spec (registradas para rastreio)

- **SQLite → Postgres + pgvector** (D1): migração planejada para a Fase 0/3. Motivo: vetores + full-text no mesmo banco. **✅ Postgres implementado na Fase 0** (campos vetoriais/`CREATE EXTENSION vector` ficam para a Fase 3).
- **Segredos fora do código**: `settings.py` tinha `SECRET_KEY`/`DEBUG` hardcoded e não lia o `.env`. Decisão: ligar `settings.py` ao ambiente e criar `.env.example`. Motivo: D6. **✅ implementado na Fase 0.**
- **Idioma padrão pt-BR** (§6/§10.6): hoje `en-us`. Decisão: migrar para pt-BR com i18n na Fase 1. **Pendente (Fase 1).**

## Implementadas na Fase 0 (2026-10-06)

Decisões de infra tomadas durante a implementação (não estavam na spec):

- **`settings.py` lê `.env`** via `python-dotenv` (`load_dotenv`); `SECRET_KEY`/`DEBUG`/`ALLOWED_HOSTS` vêm do ambiente, sem default inseguro.
- **Banco Postgres sempre** (sem fallback SQLite), via `psycopg`; config por `POSTGRES_*`. Motivo: fidelidade à produção (escolha do autor).
- **uv** no Dockerfile e no CI; **testes do CI** rodam contra Postgres+pgvector. Motivo: coerência com `uv.lock` e com o banco de produção.
- **Servir via ASGI**: gunicorn com `uvicorn.workers.UvicornWorker` apontando para `core.asgi:application` (preparado para streaming/SSE da Fase 3).
- **WhiteNoise** para estáticos sob gunicorn (`CompressedStaticFilesStorage`, sem manifesto para não quebrar `{% static %}` nos testes); `STATIC_ROOT=staticfiles/`. Motivo: o Django não serve `/static/` sob gunicorn mesmo com `DEBUG=True`.
- **Python `>=3.11`** aplicado no `pyproject.toml`; **ruff** adicionado como ferramenta de lint (grupo dev), config em `[tool.ruff]`.

## Implementadas na Fase 1 (2026-10-06)

- **Arquitetura de CSS:** ITCSS-lite + BEM em `static/css/` — `tokens.css` (cor/espaço/raio/sombra/tipografia), `base.css` (reset, defaults, objetos de layout `.o-*` e shell `.l-*`), `components.css` (`.c-*`). `design.css`/`notifications.css` removidos; `profile.css`/`cropper-custom.css` mantidos como módulo da página de perfil, tokenizados (o JS do cropper depende dessas classes).
- **Tailwind CDN removido.** As 18 telas foram remarcadas para componentes + objetos de layout.
- **`style=""` inline eliminado das telas (§10.2 ao pé da letra).** Em vez de um framework de utilitárias atômicas (que violaria a §10.3, "sem misturar utilitárias com BEM"), os inline estáticos foram absorvidos em: (a) **classes de elemento de componente** (`.c-card__title`, `.c-card__footer`, `.c-callout__list`, `.c-settings-panel__title/__hint`, `.c-tag__remove`), (b) novos componentes pequenos (`.c-select`, `.c-icon` com tamanhos, `.c-dot`), (c) objetos de layout `.o-*` (`.o-grow`, `.o-min0`, `.o-form-actions`, `.o-cluster--center/--nowrap/--top`, `.o-grid--sm`) e (d) um grupo enxuto de **helpers semânticos** na camada ITCSS de helpers (`.text-muted/-subtle/-accent/-danger/-warning/-success`, escala `.text-xs…-4xl`, `.text-italic/-center/-pre/-truncate`, `.is-hidden`). Único `style=""` remanescente: **valores dinâmicos do modelo** (cor do caderno/tag) e o **template de e-mail** (`password_reset_email.html`), onde CSS externo não se aplica.
- **Dev com recarga automática via `docker-compose.override.yml`.** O serviço `web` passou a ter, no override (aplicado só em `docker compose up` local), bind-mount `.:/app` + `runserver`; edições de código/CSS/template valem na hora, sem rebuild. Produção/CI continuam no arquivo base (gunicorn + `collectstatic`), via `docker compose -f docker-compose.yml up`. Motivo: as dependências ficam em `/usr/local` (não em `/app`), então o mount não as oculta; resolve o atrito de precisar reconstruir a imagem a cada mudança.
- **Styleguide completado (§10.7).** Adicionadas as seções **select**, **modal** e **painel de configurações** que faltavam; o modal da página de perfil passou a alternar via classe `.is-hidden` (sem `display` inline). Teste novo em `core/tests.py` cobre `/styleguide/` (200 com `DEBUG`, 404 sem) e verifica a presença dos componentes.
- **Tema claro + escuro** só por tokens: claro no `:root`, escuro via `@media (prefers-color-scheme: dark)` e override manual `:root[data-theme=...]`. Alternância por um botão no navbar + snippet pré-paint lendo `localStorage['theme']`. A identidade "aurora" (acentos cyan/mint) é comum aos dois temas.
- **HTMX** auto-hospedado em `static/js/htmx.min.js` (v2.0.4), carregado na base. Ainda sem trocas parciais (entram na Fase 3).
- **i18n pt-BR completo:** `LANGUAGE_CODE='pt-br'`, `LocaleMiddleware`, `LANGUAGES`, `LOCALE_PATHS`; textos em `{% trans %}`/`{% blocktrans %}` e `gettext` nas views. Catálogo em `locale/pt_BR/LC_MESSAGES/`. **O `.mo` é commitado** (exceção no `.gitignore`) para servir pt-BR sem exigir GNU gettext em build/runtime; regerar com `makemessages`/`compilemessages` precisa de gettext instalado.
- **`/styleguide/`** só com `DEBUG` (`StyleguideView` → 404 fora de DEBUG), renderizando todos os componentes e estados; verificado nos dois temas.
- Cards clicáveis viraram `<a>` (acessibilidade; removido `onclick`/`window.location`); botões placeholder ("Upload file"/"Add link") viraram `c-button` desabilitados (sem `alert`).
