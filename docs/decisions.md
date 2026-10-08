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
- **Idioma padrão pt-BR** (§6/§10.6): hoje `en-us`. Decisão: migrar para pt-BR com i18n na Fase 1. **✅ implementado na Fase 1.**

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

## Planejadas para a Fase 2 (2026-10-07)

Decisões tomadas no planejamento da Fase 2 (camada de provedores, credenciais e estilo), confirmadas pelo autor:

- **App `llm` novo** (spec §3): concentra provedores, credenciais, estilo e chamadas. `ProviderCredential` e `NotebookSettings` moram nele.
- **`NotebookSettings` no app `llm`** (não em `workspace`): `OneToOne` cross-app para `workspace.Notebook`. Motivo: manter provedor/estilo/credenciais sob uma só responsabilidade (§3 lista "estilo" em `llm`).
- **Nome de modelo = lista fixa por provedor** (choices curados), em vez de texto livre. Motivo: experiência mais guiada. Exceção: provedor **local/Ollama** usa campo de texto (nomes de modelos locais são arbitrários). A lista curada será mantida em `llm/constants.py` e revisada quando necessário.
- **Demonstração de "muda o comportamento" = preview da instrução compilada + botão "Testar conexão"**: a tela de settings mostra o system prompt gerado por `compile_style` (read-only, atualiza ao trocar estilo) e um botão que faz uma chamada mínima ao provedor configurado (fake na suíte, real com a chave do usuário). Motivo: prova a camada ponta-a-ponta sem depender do chat da Fase 3.
- **Chave mestra de criptografia em `ASCENDIA_FERNET_KEY`** (novo no `.env.example`/`settings.py`), sem default inseguro; erro claro se faltar. Fernet (lib `cryptography`), D6.
- **Dependências novas**: `litellm` (D3, import lazy no provedor real) e `cryptography` (Fernet).

## Implementadas na Fase 2 (2026-10-07)

- **App `llm` criado** com: `constants.py` (choices de provedor/modelo/estilo), `crypto.py` (Fernet), `style.py` (`compile_style` puro + `StyleSpec`), `providers.py` (`BaseProvider`, `FakeProvider`, `LiteLLMProvider` com import lazy), `client.py` (`chat`/`embed`/`test_connection`, seleção por `NotebookSettings`, retry limitado + timeout, erros mapeados), `models.py`, `forms.py`, `views.py`, `urls.py`, `admin.py`.
- **`NotebookSettings`** (OneToOne → `workspace.Notebook`) com chat/embedding **provider+model separados** (embeddings podem usar outro provedor; D5 — trocar embedding exige reindexar, avisado na UI — aviso dinâmico ao trocar, ver ajustes abaixo). Criado sob demanda (`get_or_create`).
- **`ProviderCredential`** (`unique_together = user, provider`): guarda só `ciphertext` (Fernet) + `last_four`; `set_key`/`get_key`; nunca loga nem renderiza o plaintext. Admin exclui `ciphertext`/`last_four` e mostra só o mascarado.
- **`compile_style`** anexa as 3 regras fixas **por último**, declaradas com prioridade; `extra_instructions` entram antes, marcadas como subordinadas e como dado não confiável (defesa a injection, §8/§11). Testes cobrem cada preset/tom/tamanho/idioma/formato/detalhe e a inviolabilidade das regras.
- **Seleção de modelo**: lista curada por provedor em `constants.py`; provedor **local** usa campo de texto. Selects dependentes (provedor → modelos) via **HTMX** (`ModelOptionsView` → parcial `_model_field.html`), com fallback server-rendered correto no POST.
- **Demonstração de comportamento**: a tela de settings mostra a **instrução compilada** (atualiza ao salvar) e tem **"Testar conexão"** (`test_connection`), que usa `FakeProvider` nos testes e o provedor real com a chave do usuário fora deles.
- **`ASCENDIA_FERNET_KEY`** adicionada a `settings.py`/`.env.example`/`.env` e ao **CI** (chave descartável, só de teste). `UV_HTTP_TIMEOUT=300` no Dockerfile — o wheel do `litellm` (~35 MB) estourava o timeout padrão de 30 s do `uv` no build.
- **UI** reaproveitou os componentes da Fase 1 (`c-settings-panel`, `c-select`, `c-field`, `c-toast`, `c-source-item`, `c-empty-state`) — nenhum componente novo, styleguide não precisou mudar. Link **Settings** adicionado ao `notebook_detail`.
- **i18n pt-BR**: 64 strings novas traduzidas no catálogo; `.po`/`.mo` regenerados (gettext roda num container, ausente no host). Os testes de view afetados passaram a asseverar as strings em pt-BR (idioma padrão).
- **Testes**: 40 novos (crypto, style, models, client com fake, views com isolamento por dono §11). Suíte total: **154 testes** na entrega (**172** após os ajustes de 2026-10-07, abaixo), verdes.
- **Divisão final tela de APIs × caderno** (ajuste do autor em 2026-10-07, após iterar): separação por **responsabilidade**, não por entidade.
  - **Tela de APIs** (`/llm/api-keys/`, link "API keys" no navbar): uma **lista de todos os provedores**, cada um com campo de chave (write-only, mostra só os 4 últimos) e botão **Testar** por provedor. O teste usa um modelo curado representativo do provedor (`constants.representative_chat_model`); para os de texto livre (local/OpenRouter) não há modelo padrão, então o teste é feito a partir de um caderno.
  - **Configurações do caderno** (`/llm/notebook/<id>/settings/`): o usuário **seleciona o provedor + os modelos** (carregados conforme o provedor, via HTMX) **e** o estilo de resposta, com o preview da instrução compilada.
  - Isso **mantém a D4** (provedor/modelo por caderno) — o `UserLLMSettings` criado numa iteração anterior foi **removido**; provedor/modelo voltaram para `NotebookSettings`. O `client.chat/embed` recebe `NotebookSettings`; o teste por provedor usa `client.test_provider(user, provider)`. O tema claro/escuro ("estilo do site") segue global no navbar.
  - **Visual da tela de APIs** inspirado no OpenClaude (ref. do autor): **grid de cards** (`o-grid`), um por provedor, com **badge de status** (Configurado/Chave faltando/Sem chave necessária) + campo de chave + botões Salvar/Testar/Remover por card. Adicionadas as variantes `c-badge--success`/`c-badge--warning` (cor do token + `--surface-hover`, como `c-source-item__status`) e incluídas no styleguide. Seção Runtime/proxy/rate-limit do OpenClaude ficou de fora (não pedida).
- **Endpoints locais separados + "Refresh models" dinâmico** (pedido do autor em 2026-10-07):
  - O provedor genérico `local` foi substituído por três endpoints — **Ollama, LM Studio, llama.cpp** — cada um com **Base URL** configurável (padrões `localhost:11434` / `:1234/v1` / `:8080/v1`). `LOCAL_PROVIDERS`/`DEFAULT_BASE_URLS` em `constants.py`.
  - Novo modelo **`ProviderConfig`** (único por `user`+`provider`): guarda `base_url` e a lista de modelos (`model_list`) carregada da API, com `models_updated_at`.
  - **"Refresh models"** por provedor: `providers.list_models(provider, api_key, base_url)` consulta a API ao vivo — Ollama `/api/tags`, Gemini `/models?key=`, Anthropic `/v1/models`, demais `GET /models` estilo OpenAI (Bearer). Usa `requests` (dep. explícita agora); `providers.set_model_lister` injeta um fake nos testes. Os modelos carregados aparecem nos selects do caderno (`client.available_models`: lista carregada ∪ curada; cai para texto livre só quando não há lista).
  - **Teste por provedor**: nuvem = chat mínimo com modelo representativo; local = reachability via `list_models`. `client.test_provider` retorna uma mensagem curta.
  - Base URLs resolvidas por `constants.base_url_for`; `PROVIDER_API_BASE`/`OPENAI_COMPATIBLE_PROVIDERS` mapeiam os endpoints de nuvem. **A rota de chat/embedding com modelos locais (prefixo LiteLLM + `api_base`) é da Fase 3** — aqui o caminho local exercitado é só a listagem/reachability.
- **Mais provedores de LLM** (pedido do autor em 2026-10-07, "como o openclaude tem"): além de OpenAI/Anthropic/Gemini/DeepSeek/local (spec §5), adicionados **Mistral, Groq, xAI (Grok), Perplexity, Together AI** (listas curadas em `constants.py`) e **OpenRouter** como *gateway* de texto livre (200+ modelos), junto do local. Todos suportados pelo LiteLLM; a chave por provedor e o roteamento por prefixo de modelo já eram genéricos, então não exigiu mudança na camada de client/credenciais. `FREE_TEXT_MODEL_PROVIDERS = {local, openrouter}`.
- **Django admin removido por completo** (não está na spec; decisão do autor em 2026-10-07): `django.contrib.admin` saiu de `INSTALLED_APPS`, a rota `/admin/` saiu de `core/urls.py` e os `admin.py` (`llm`, `users`) foram apagados. Motivo: o Ascendia é auto-hospedável e **toda configuração é do usuário final**, feita na própria UI (perfil, cadernos, notas, chaves de API em `/llm/credentials/`, settings por caderno). Admin não fica disponível nem em produção nem em dev. `createsuperuser` deixou de ser parte do fluxo (removido do README).

## Ajustes pós-auditoria da Fase 2 (2026-10-07)

Correções do que a auditoria da Fase 2 apontou como faltante ou divergente da spec:

- **Aviso de reindexação ao trocar o modelo de embedding** (spec §5, D5): ao salvar as configurações do caderno com `embedding_provider`/`embedding_model` diferentes dos salvos, a tela mostra um aviso (`messages.warning`). O texto estático de ajuda já existia; agora há o aviso no momento da troca. **O botão de reindexar fica para a Fase 3**, quando existirem fontes para reindexar.
- **Retry só em falhas transitórias**: `ProviderError` ganhou `retryable` (padrão `True`). Chave inválida (`AuthenticationError`) e modelo inexistente (`BadRequest`/`NotFound`) são marcados como `retryable=False` e não são repetidos. Motivo: repetir um erro que o retry não resolve só dobra a espera do usuário.
- **Dropdowns no tema escuro**: o popup nativo do `<select>` usava fundo branco, com o texto claro do tema, o que deixava as opções ilegíveis. Correção: `color-scheme` por tema em `tokens.css` (popup nativo escuro no escuro) e o token sólido `--surface-menu` para o fundo das opções (`--surface-raised` é translúcido, então não serve).
- **i18n consistente**: todo texto de interface passa por `{% trans %}` nos templates e por `gettext`/`gettext_lazy` no Python (labels, placeholders, `help_text`, nomes de cores, mensagens de view e de JSON de avatar, `alt` do avatar no JS). Não são traduzidos: nomes de marca (OpenAI, Ascendia, WhatsApp, provedores), exemplos de formato (`+55 11 98765-4321`, `sk-...`, `llama3.1, mistral, ...`) e URLs.
- **Catálogo pt_BR**: 58 traduções novas ou corrigidas (inclusive 17 entradas `fuzzy`, cujas sugestões automáticas estavam erradas, ex.: "Enter your username" → "Informe o nome do modelo."). Entradas obsoletas removidas. `.po` e `.mo` regenerados. `gettext` foi instalado temporariamente no container `web` para isso, sem alterar a imagem.
- **Testes** (primeira rodada): 172 passando (eram 168). Novos: retry de erro não transitório e transitório, aviso de reindexação (troca e não troca). O teste de avatar passou a asseverar a mensagem em pt-BR.

## Ajustes de front-end após teste do autor (2026-10-07)

- **Cache-busting dos estáticos**: o ajuste de cor dos dropdowns não aparecia porque o navegador reaproveitava o `tokens.css` antigo do cache (a URL `/static/css/tokens.css` nunca mudava, nem após rebuild). Criada a tag `{% asset %}` (`core/templatetags/assets.py`), que anexa `?v=<hash do conteúdo>` às URLs de CSS/JS. Em DEBUG o hash é recalculado a cada render; fora dele, uma vez por processo. Registrada em `TEMPLATES['OPTIONS']['libraries']`, porque `core` não é app instalado. Preferida ao `ManifestStaticFilesStorage`, que exige `collectstatic` nos testes e não versiona URLs em DEBUG.
- **Dropdown temático com `appearance: base-select`** (select customizável do Chromium 135+), dentro de `@supports`: o popup usa `--surface-menu`, borda, raio e sombra do tema, e a opção selecionada usa `--accent-strong`. Sem isso, a linha em foco usava o azul-claro fixo do Windows, com texto claro e pouco contraste. Navegadores sem suporte ficam com o popup nativo escurecido via `color-scheme`. O texto selecionado fica numa linha com reticências, como no nativo.
- **`components/field.html` envolve selects em `.c-select`** (detecta `widget.input_type == 'select'`): os campos de estilo do caderno não tinham a seta do componente.
- **Rótulos dos campos de `NotebookSettings`** via `verbose_name` traduzível (migração `llm/0002_field_labels`, só metadados, sem mudança no banco). Antes "Preset", "Tone", "Length", "Language", "Answer format" e "Detail level" apareciam em inglês. Também traduzidos: "Base URL" → "URL base", rótulos das notificações e título do guia de estilo.
- **"Workspace" → "Espaço de Trabalho"** em pt-BR (decisão do autor). No meio de frase fica em minúsculas ("Voltar para o espaço de trabalho").
- **Testes**: 175 passando (novos: tag `{% asset %}`).

## Idioma da interface segue o navegador (2026-10-07)

Regra do autor: **todo texto de interface é traduzido conforme o idioma do navegador**.

- **Mecanismo**: o `LocaleMiddleware` (já ativo desde a Fase 1) escolhe o idioma pelo `Accept-Language`, entre `LANGUAGES` (`pt-br`, `en`). Variantes caem no idioma-base (`pt-PT` → `pt-br`, `en-GB` → `en`). Idioma não suportado cai no `LANGUAGE_CODE` (`pt-br`). Os textos-fonte são em inglês e o catálogo `pt_BR` traz as traduções.
- **Regra para código novo**: nenhum texto visível escrito direto em português ou inglês. Nos templates use `{% trans %}`/`{% blocktrans %}`; no Python use `gettext`/`gettext_lazy`, com o texto-fonte em inglês. Depois, rode `makemessages` e traduza no `.po`.
- **Corrigido**: as mensagens de erro e status dos provedores (`llm/client.py`, `llm/providers.py`) estavam fixas em português e passaram para `gettext`. O `<html lang>` estava sempre `pt-br`, porque usava `LANGUAGE_CODE` sem o context processor de i18n. Agora usa `{% get_current_language %}`.
- **A instrução compilada (`compile_style`) também segue o idioma da interface** (decisão do autor, revendo a exceção inicial). Os textos são `gettext_lazy` com fonte em inglês. O português no catálogo é idêntico ao texto anterior, então a saída em pt-BR não mudou. A prévia continua mostrando exatamente o que o modelo recebe: a instrução sai no idioma de quem usa o app, e o **idioma da resposta** continua sendo a configuração "Idioma" do caderno, numa linha explícita (ex.: interface em inglês com "Answer in Brazilian Portuguese."). `compile_style(settings, ui_language=None)` usa o idioma ativo por padrão. **Na Fase 3**, se a instrução for compilada fora de uma requisição (tarefa em segundo plano), passe `ui_language` explicitamente; senão ela cai no `LANGUAGE_CODE`. `FIXED_RULES` virou tupla lazy; use `fixed_rules(ui_language)` para obter as regras como `str`.
- **Testes**: 185 passando. `core/tests.py::BrowserLanguageTests` cobre UI em inglês e em português, `<html lang>`, fallback de idioma não suportado e mensagens de provedor nos dois idiomas. `llm/tests/test_style.py` cobre a instrução em inglês e em português, a independência entre idioma da interface e idioma da resposta, e as regras fixas em inglês.

## Tela de provedores e refresh de modelos (2026-10-07)

O refresh é o que alimenta os dropdowns de modelo das configurações do caderno. Na revisão apareceram estes defeitos, agora corrigidos:

- **Ids sem prefixo do LiteLLM**: o refresh gravava `llama-3.3-70b`, mas o LiteLLM precisa de `groq/llama-3.3-70b` para rotear, e a lista curada já usava prefixo. Agora `llm/model_catalog.py` normaliza tudo para o id do LiteLLM (`LITELLM_PREFIX` por provedor; llama.cpp vira `openai/<modelo>`, por ser compatível com a API da OpenAI).
- **Chat e embedding misturados**: a mesma lista ia para os dois dropdowns, inclusive modelos de áudio e imagem. Agora cada modelo é gravado como `{"id", "kind"}`. O tipo vem dos metadados da API quando existem (Gemini `supportedGenerationMethods`, Together `type`, Mistral `capabilities`) e, se não, do nome. Áudio, imagem e moderação são descartados. Listas antigas (só strings) continuam sendo lidas.
- **Formato e paginação por provedor**: o Together devolve um array puro (antes caía no erro genérico). Anthropic (`limit=1000`) e Gemini (`pageSize=1000`) eram truncados na primeira página. Um 404 (provedor sem endpoint de listagem, como Perplexity) gera mensagem clara, e a lista embutida continua valendo.
- **Refresh e teste só depois da configuração** (decisão do autor): "Atualizar modelos" e "Testar conexão" ficam desabilitados, com uma linha explicando o que falta, até haver **chave salva** (nuvem, inclusive OpenRouter) ou **URL do servidor salva** (locais; a URL padrão vem pré-preenchida, basta salvar). O servidor aplica a mesma regra (`client.provider_ready`): chamar o endpoint direto devolve um aviso sem consultar o provedor.
- **Fallback por tipo**: se o refresh não trouxe modelos de um tipo, o dropdown daquele tipo usa a lista curada. Refresh com falha mantém a lista anterior.
- **Modelo já salvo continua válido**: se um refresh não lista mais o modelo salvo no caderno (renomeado, descontinuado), salvar o caderno não falha por isso.
- **Servidores locais dentro do Docker**: `localhost` no container é o próprio container, então o Ollama da máquina nunca era encontrado. Novo `ASCENDIA_LOCAL_LLM_HOST` (padrão `localhost`). O `docker-compose.yml` define `host.docker.internal` + `extra_hosts: host-gateway`, para funcionar também no Linux. URLs já salvas manualmente não mudam.
- **Erros com nível**: `ProviderError.level` é `'warning'` quando falta uma ação do usuário (salvar a chave) e `'error'` quando a chamada falhou. A UI mostra aviso amarelo ou erro vermelho conforme o nível.

Visual e textos:

- **Página em duas seções**: "Provedores na nuvem" (chave) e "Servidores locais" (URL), cada uma com uma linha explicando o que é preciso.
- **Card `c-provider`**: nome + selo ("Chave salva" / "Sem chave" / "Local"), campo **com rótulo visível** ("Chave de API" / "URL do servidor") e ajuda ("A chave salva termina em ••••abcd" / "Padrão: …"), linha de modelos ("12 modelos de chat, 2 de embedding. Atualizado em …" ou "Lista embutida: 5 modelos de chat."), grade de ações e área de resultado.
- **Objeto `o-button-grid`**: 2 colunas de largura igual. Os botões preenchem a célula e quebram o texto dentro dela, então as fileiras se alinham entre cards independentemente do tamanho do rótulo. Formulários HTMX dentro dele usam `display: contents`. "Remover chave" aparece desabilitado quando não há chave, para todos os cards de nuvem terem o mesmo desenho. Nova variante `c-button--danger-outline`.
- **Componente `c-notice`** (`templates/components/notice.html`): mensagem em linha, de largura total, com título e texto que quebra linha. Variantes success/warning/danger/info, mesma linguagem de cor dos toasts. Usado pelo refresh e pelo teste. Substitui o selo apertado e o toast estático. Está no guia de estilo.
- **Cards com altura própria** (`align-self: start`): um aviso num card não abre vão nos vizinhos. Como os cards têm a mesma estrutura, os botões já se alinham.
- **Grade mais larga** (`o-grid--wide`, mínimo 21rem): 3 colunas em telas comuns, sem quebrar nomes de provedor nem rótulos de botão.
- **Carregando**: botão que dispara HTMX mostra spinner enquanto a requisição roda.
- **Vocabulário único**: a página, o link do menu e o botão nas configurações do caderno se chamam "Provedores" (antes "Chaves de API" num lugar e "Provedores" em outro). Botões dizem a ação: "Salvar chave", "Remover chave", "Atualizar modelos", "Testar conexão". O rótulo do OpenRouter virou só "OpenRouter" (migração `llm/0003`, só metadados).
- **Testes**: 205 passando. `llm/tests/test_model_catalog.py` cobre o bloqueio de refresh/teste antes de chave/URL, prefixo, classificação, normalização, formatos de Together/Gemini/Anthropic, 404, refresh sem chave, OpenRouter sem chave, separação chat/embedding, fallback, refresh com falha mantendo a lista, modelo salvo continuando válido e agrupamento da página.

## Provedores NVIDIA NIM e Hugging Face (2026-10-07)

Pedido do autor.

- **NVIDIA NIM** (`nvidia_nim`): API do catálogo da NVIDIA (`https://integrate.api.nvidia.com/v1`), compatível com OpenAI, com o prefixo LiteLLM `nvidia_nim/`. A listagem mistura chat, embedding e rerank; a classificação por nome separa os tipos (em 2026-10-07: 80 modelos, que viram 69 de chat e 7 de embedding). NIM auto-hospedado (container local) não foi incluído; dá para usar via llama.cpp/LM Studio ou como provedor novo, se for pedido.
- **Hugging Face** (`huggingface`): Inference Providers via router (`https://router.huggingface.co/v1`), com o prefixo `huggingface/`. O `/models` do router lista **só modelos de chat** (134). Os de embedding (`BAAI/bge-m3`, `all-MiniLM-L6-v2`, via HF Inference) ficam **na lista embutida**, e o dropdown de embedding usa essa lista mesmo depois do refresh.
- Listas embutidas escolhidas entre ids que existiam na listagem real na data. Migração `llm/0004` (só choices).
- **Invariante testada** (`ProviderRegistryTests`): todo provedor precisa ter prefixo LiteLLM, URL de listagem/padrão e entrada nas listas embutidas, e todo id embutido já precisa estar com prefixo. Um provedor novo incompleto quebra a suíte.

## Chave de API nunca exibida, nem parcialmente (2026-10-07)

**Diverge da spec §5** ("na interface, mostrar só os quatro últimos caracteres"), por decisão do autor: nenhum caractere da chave aparece depois de salva.

- O campo `ProviderCredential.last_four` foi **removido** (migração `llm/0005`, que apaga os valores já guardados) e `crypto.last_four` deixou de existir. Como o dado não é exibido, também não é guardado: o banco fica só com o ciphertext.
- O card mostra "Há uma chave salva e criptografada." e o selo "Chave salva". A mensagem ao salvar diz só "Chave de <provedor> salva." `__str__` não inclui nada da chave.
- Isso substitui as menções a `last_four`/"4 últimos caracteres" nas seções anteriores deste arquivo.
- Testes garantem que a página não mostra nem os últimos caracteres depois de salvar.

## Teste de conexão resistente a modelos indisponíveis (2026-10-07)

Bug relatado pelo autor: o teste da NVIDIA NIM falhava com uma chave válida.

- **Causa**: o teste usava só o 1º modelo da lista embutida (`nvidia/llama-3.1-nemotron-70b-instruct`). O catálogo público da NVIDIA o lista, mas a API responde **404 "Function not found for account"**. Testado com a chave real do autor: dos 10 modelos de chat, só 2 responderam; os outros deram 404 ou **410 Gone** (descontinuados). Dos 10 de embedding, só 2.
- **Teste com fallback**: `client.test_provider` tenta os candidatos em ordem (lista embutida; sem ela, os 3 primeiros do refresh, como no OpenRouter) e pula os que dão 404/410 (`ProviderError.code == MODEL_UNAVAILABLE`). Chave inválida, limite ou timeout encerram na hora. Se nenhum responder, o aviso diz que a chave funciona mas nenhum modelo de teste está disponível.
- **410 reconhecido**: o LiteLLM levanta 410 como `APIError` genérico. `_map_error` agora olha `status_code` 404/410 e devolve "modelo indisponível" (sem retry), em vez de "falha ao falar com o provedor" com retry.
- **Lista embutida da NVIDIA reduzida ao que responde** (verificado em 2026-10-07): chat `nemotron-3-super-120b-a12b` e `openai/gpt-oss-20b`; embedding `nemotron-3-embed-1b`.
- **Limitação conhecida**: o refresh da NVIDIA continua trazendo os modelos que o catálogo lista, inclusive os que não respondem, porque a API de listagem não diz quais funcionam. Escolher um desses no caderno resulta em "modelo indisponível" na hora do uso. Verificar cada modelo no refresh exigiria uma chamada por modelo (80+).
- **Para a Fase 3**: modelos de embedding **assimétricos** da NVIDIA (ex.: `llama-nemotron-embed-vl-1b-v2`) exigem `input_type` (`passage` ao indexar, `query` ao buscar). `client.embed` ainda não envia esse parâmetro e precisa enviar quando a ingestão/busca for implementada.

## Hugging Face removido (2026-10-07)

Decisão do autor, após análise: o roteador da HF repassa as chamadas para parceiros (Together, Groq, Fireworks…) cujos modelos abertos já estão acessíveis pelo OpenRouter, pelo Together e pelo Groq. Além disso, o caminho de chat e embedding nunca foi verificado com um token real, e cada provedor traz uma lista embutida que envelhece (ver o caso da NVIDIA). Removido de `constants`, `model_catalog`, testes e README. Migração `llm/0006` (só choices). Não havia chaves, listas nem cadernos com HF no banco, então não foi preciso limpar dados. A migração `0004` mantém o nome `nvidia_huggingface` por histórico. Readicionar exige: verificar chat/embedding com token real e preencher prefixo, URL e listas embutidas (o `ProviderRegistryTests` cobra isso).

## Auditoria pós-Fase 2 (2026-10-07)

Validação do commit `1d62795` antes da Fase 3: 211 testes, ruff, `makemigrations --check` e `manage.py check` limpos; CI no GitHub verde (lint, testes em Postgres+pgvector, build da imagem) a partir de um checkout limpo.

Corrigido na auditoria:
- `users/views.update_avatar` devolvia `str(e)` ao navegador (viola §10.5). Agora loga a exceção e devolve uma mensagem genérica traduzida.
- Código morto removido de `llm` (`representative_chat_model`, `chat_model_choices`, `embedding_model_choices`, `all_*_models`, `OPENAI_COMPATIBLE_PROVIDERS`, `NotebookSettings.credential_for_chat`).
- README (seção de provedores) atualizado; `docs/audit.md` e `docs/frontend.md` marcados como retrato da Fase 0.

Pendências registradas (não bloqueiam a Fase 3, mas precisam de decisão):
- ~~**Python**~~: resolvido abaixo (CI na versão de produção).
- ~~**SSRF**~~: resolvido abaixo (allowlist de hosts locais).
- **HTTPS em produção**: `check --deploy` aponta HSTS, `SECURE_SSL_REDIRECT` e cookies `Secure` não configurados.

## CI na versão de Python de produção (2026-10-07)

- O CI lê a versão do `FROM python:X.Y-slim` do **Dockerfile** (fonte única de verdade) e define `UV_PYTHON`, que tem prioridade sobre o `.python-version` (3.14, que segue como padrão local). Um passo confere que o interpretador em uso é mesmo essa versão. Trocar a versão de produção = editar só o Dockerfile.
- Verificado: simulação dos passos do CI numa cópia isolada (uv escolhe 3.12 apesar do `.python-version`) e a suíte inteira rodando em 3.12 dentro do container de produção.

## URLs de servidores locais: allowlist (2026-10-07)

O app faz GET na URL que o usuário salva para um servidor local. Numa instância compartilhada, isso permitiria sondar a rede interna (SSRF). Regras (`llm/local_urls.py`):

- Só `http`/`https` com host e porta válidos; sem usuário/senha, query ou fragmento. A URL é normalizada.
- O host precisa estar em **`ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS`** (env, separado por vírgula), controlado por quem administra o servidor. Padrão: `localhost`, `127.0.0.1`, `::1`, `host.docker.internal` e o valor de `ASCENDIA_LOCAL_LLM_HOST`. Isso cobre o caso comum sem configuração e bloqueia por padrão `db`, `web` e IPs da rede. Um servidor na LAN é adicionado explicitamente; `*` libera qualquer host.
- **Sempre recusados**, mesmo com `*` e após resolução DNS: link-local (169.254.0.0/16, `fe80::/10`, o que inclui o metadata de nuvem), multicast, não especificado e reservados. Loopback é explicitamente permitido: o Python classifica `::1` como "reservado", e os testes pegaram esse bug.
- A validação roda **ao salvar** (a mensagem chega ao usuário no aviso, já que a página redireciona) e **antes de cada uso**, porque a allowlist pode mudar depois de salva.
- **Sem seguir redirecionamentos** nos servidores locais (um 3xx poderia levar a um host proibido); a resposta 3xx vira uma mensagem clara.
- Testes: `llm/tests/test_local_urls.py`.

## HTTPS em produção (2026-10-07) — em aberto

Os avisos do `check --deploy` (HSTS, `SECURE_SSL_REDIRECT`, cookies `Secure`) dependem de como cada pessoa hospeda: atrás de proxy com TLS, só na rede de casa por HTTP, ou só em `localhost`. Ativar fixo quebraria o uso por HTTP. **Pendente de decisão do autor**; a opção proposta é uma flag de ambiente opt-in (`DJANGO_SECURE_HTTPS`), desligada por padrão.

## Implementadas na Fase 3 (2026-10-07/08)

Escolhas do autor no planejamento: fila no Postgres + worker; fontes PDF + texto colado (links depois); notas no painel direito; uma conversa por caderno.

**Infraestrutura**
- **Fila de tarefas**: `django-tasks` 0.12 + `django-tasks-db` (a partir da 0.12 o backend de banco é um pacote separado). Serviço `worker` (`manage.py db_worker`) no compose, mesma imagem, com autoreload em dev. A tarefa é enfileirada com `transaction.on_commit`, para o worker nunca pegar uma fonte ainda não gravada.
- **Arquivos das fontes**: storage privado em `ASCENDIA_SOURCES_ROOT`, fora de `MEDIA_ROOT`, sem URL e com nome UUID; no Docker é o volume `sources`, compartilhado entre web e worker. Um sinal `post_delete` apaga o arquivo junto com a fonte, inclusive em cascata.
- **Cache compartilhado** (`DatabaseCache`) para o rate limit valer entre os workers do gunicorn; `createcachetable` roda no comando de subida.
- **pgvector**: a extensão é criada na migração `sources/0001` (`VectorExtension`). A coluna `embedding` é `vector` **sem dimensão fixa** (cada caderno usa um modelo) e toda consulta filtra por `embedding_model` e `embedding_dim`.

**Ingestão**
- PyMuPDF; a seção vem do sumário do PDF. Validação real: assinatura `%PDF-`, abertura pelo parser, PDF com senha, limite de páginas e de tamanho.
- Chunking em caracteres (1200/200 por padrão), por parágrafo, **sem cruzar página nem seção**, para que toda citação aponte para uma página exata.
- **Reindexar = reingerir**: o arquivo original continua guardado, então reindexar (novo modelo de embedding ou novo idioma) é a mesma rotina da ingestão. Essa versão é mais simples que re-embedar os chunks guardados, como estava no plano, e também recalcula o full-text.
- `search_vector` usa a config do idioma de resposta do caderno (`portuguese`/`english`/`spanish`), guardada por chunk.

**Busca**
- Full-text (`websearch_to_tsquery`, que exige todos os termos) + vetorial exata (`CosineDistance`), fundidas por RRF (k=60, 40 candidatos por método, top 8). Sem índice ANN até a Fase 4 medir.
- **Bug encontrado nos testes**: `DISTINCT` em `search_config` herdava o `Meta.ordering` de `Chunk` e repetia a busca uma vez por chunk; corrigido com `order_by()`, com teste de regressão.
- O embedder falso usa 512 dimensões; com 64, as colisões de hash invertiam rankings nos testes.

**Geração e chat**
- ~~**Streaming com gerador síncrono** + `StreamingHttpResponse` (SSE): funciona igual com runserver (dev) e com uvicorn (prod).~~ **Errado, corrigido em 2026-10-08** (ver "Resposta em segundo plano" abaixo): em ASGI o Django consome um iterador síncrono inteiro antes de enviar, ou seja, não havia streaming em produção. O retry só acontece **antes** do primeiro token. Uma reconexão do `EventSource` reapresenta a resposta, sem gerar de novo (a mensagem é "reivindicada" de forma atômica). Se o cliente se desconecta, o parcial é salvo como interrompido.
- **Citações com snapshot** (texto, fonte, página e seção em `MessageCitation`): continuam válidas depois de reindexar, porque reindexar recria os chunks.
- **Gate**: números inválidos são removidos. Sem nenhuma citação válida, há uma nova tentativa (sem streaming); se ainda faltar, a resposta é o "não encontrei" padrão. Busca vazia responde sem chamar o LLM.
- **Prompt**: estilo compilado + regras fixas + regras de entrega das fontes; os trechos vão em `<sources>` como dado não confiável, e o texto do PDF tem os delimitadores neutralizados para não poder fechar o bloco.
- **Render**: Markdown sem HTML cru (`markdown-it-py`, links e imagens desligados) → `nh3` → chips `[n]` gerados por nós **depois** de sanitizar.
- **Rate limit** por usuário em pergunta (20/min) e envio de fontes (10/min); no HTMX, o aviso aparece no lugar certo via `HX-Retarget`.
- **`client` LLM**: `api_base` dos servidores locais agora chega a chat e embed (antes só listagem e teste); `input_type` (`passage`/`query`) para NVIDIA; embeddings em lote.

**Interface**
- Três painéis (Fontes | Conversa | Notas). Abaixo de 75rem viram abas WAI-ARIA (`notebook.js`); sem JS, as colunas empilham. `chat.js` em JS puro, sem dependências.

**Verificação ponta a ponta (com a chave NVIDIA real do autor)**
- PDF de 3 páginas com sumário → worker → 3 chunks com página e seção corretas, 2048 dimensões.
- Pergunta coberta → resposta correta com chip `[1]`; o chip abre o trecho da página 3 e destaca a fonte.
- Streaming confirmado por leitura byte a byte: 55 leituras com um token cada, sem buffer no servidor.
- **Observação: o tempo até o primeiro token é alto** (~10 s com `nemotron-3-super`): embedding da pergunta + busca + o raciocínio oculto do modelo. É característica do modelo de raciocínio; um modelo sem raciocínio responde mais rápido.
- Pergunta fora das fontes → o modelo diz que não encontrou, **mas cita os trechos para justificar**, e o gate as aceita por serem válidas. A busca vetorial sempre devolve os "mais próximos", mesmo irrelevantes; julgar relevância é papel do CRAG (Fase 5).
- **Não verificado visualmente: layout em largura de celular.** A janela do Chrome não redimensionou e o `X-Frame-Options: DENY` (proteção contra clickjacking) bloqueia testar num iframe. A estrutura está coberta por teste, e a regra de CSS foi revisada.

**Fica para depois**
- Links como fonte (exigem regras de SSRF próprias) e várias conversas por caderno.
- OCR de PDFs escaneados.
- Índice ANN por modelo (quando a Fase 4 medir).
- Avaliação (Fase 4), reranking/CRAG (Fase 5).

## Chat: Markdown no streaming, copiar resposta, rolagem (2026-10-08)

Pedido do autor depois de usar a Fase 3.

- **Markdown durante a escrita**: o servidor renderiza o texto parcial (mesmo caminho seguro: markdown-it sem HTML → nh3) e envia eventos `html` em vez de `token`. Há um *throttle* (no máximo a cada 8 tokens ou 120 ms, e sempre no 1º), porque cada evento reenvia o texto todo. O cliente não interpreta Markdown. Os `[n]` aparecem como chips inertes até passar pelo gate. Tabelas e tachado foram habilitados.
- **Copiar**: "Copiar Markdown" (texto cru) e "Copiar formatado" (`text/html` + `text/plain`, cola formatado no Docs/Word/Notion). Os dois terminam com a lista das fontes **citadas** (título, página, seção), porque fora do app um `[1]` sozinho não diz nada. Os conteúdos vão em `<template>` na bolha (`rag/export.py`). Há fallback `execCommand('copy')` para auto-hospedagem por HTTP, onde a Clipboard API não existe. Respostas interrompidas também podem ser copiadas; "não encontrei" e erros não.
- **`done` traz a bolha inteira** (mesmo template do histórico), então a resposta nova e o histórico são idênticos.
- **Idioma no streaming (bug latente corrigido)**: o gerador roda depois que a view retorna e, sob ASGI, cada passo pode cair em outra thread. A view passa o idioma da requisição e o idioma é reativado **a cada passo** do gerador (um `override` só em volta do gerador não basta, porque é *thread-local*).
- **Rolagem**:
  - a página do caderno virou um espaço de trabalho de altura fixa (`l-app--workspace`, sem rodapé, cabeçalho compacto) e cada coluna rola sozinha;
  - o log de mensagens ocupa o resto do painel, e o campo de pergunta fica sempre visível, com 1 linha que cresce até ~6;
  - a rolagem automática só acompanha quem já está no fim; quem subiu para reler não é puxado de volta e vê "Ir para o fim";
  - em telas com menos de 34rem de altura, a página volta a rolar normalmente.
- **Verificado no navegador** (caderno temporário, removido depois): formatação durante o streaming, conteúdo copiado nos dois formatos (com a lista de fontes), leitor no topo sem ser puxado, sem rolagem dupla, campo crescendo, temas claro e escuro. Numa janela de 671 px de altura, o log foi de 192 → 327 px.
- **Bug achado na medição**: `textarea.c-field__input { min-height: 7rem }` vencia `.c-chat__input` por especificidade; resolvido com `textarea.c-chat__input`.

## Envio de vários PDFs e caderno de borda a borda (2026-10-08)

Pedido do autor. Direção de layout escolhida entre três propostas: **"Só fluido"** (descartadas: painéis recolhíveis e modo foco).

- **Borda a borda**: o caderno usa `o-container--fluid` (sem `max-width`, só o gutter). Grid com áreas:
  - largo: Fontes | (barra do caderno + conversa) | Notas. A barra fica só em cima da conversa, então os painéis laterais ganham a altura toda;
  - estreito: barra, abas e o painel ativo;
  - sem JS: colunas empilhadas.
- **Larguras**: laterais `minmax(16rem, 18rem)` / `minmax(14rem, 16rem)`, que viram 20/18rem acima de 120rem. A conversa fica com o resto.
- **Medida de leitura** (princípio da skill frontend-design: a conversa é a superfície de leitura). O texto fica em ~46rem (~72 caracteres por linha), centralizado por `padding-inline`, para a barra de rolagem continuar na borda do painel. O campo de pergunta, a área de erro e o cartão de citação seguem a mesma medida. A resposta do assistente ocupa a medida inteira, com entrelinha 1.65.
- **Cabeçalho do caderno** virou a barra fina `c-notebook-bar` (cor, título, datas, ações). A descrição foi para o `title`.
- **Envio múltiplo**:
  - zona `c-dropzone` (arrastar e soltar, ou escolher vários) no lugar do input nativo, que aparecia cortado;
  - o envio começa ao escolher ou soltar, com barra de progresso (`htmx:xhr:progress`);
  - no servidor, cada arquivo é validado e criado de forma independente (`validate_pdf_upload`), com teto `ASCENDIA_UPLOAD_MAX_FILES` (10) por envio;
  - o aviso resume o resultado: verde se tudo entrou; amarelo se algo ficou de fora mas nada quebrou (inclusive só duplicatas); vermelho se nada entrou por erro. A lista "arquivo: motivo" usa o novo `items` de `components/notice.html`.
- **Estado vazio da conversa sempre atual**: respostas do painel de fontes emitem `HX-Trigger: sources-updated`, e o estado vazio da conversa se recarrega sozinho (só ele, via `hx-select`, sem apagar o que estiver digitado). Antes ficava "Adicione uma fonte" mesmo com fontes prontas.
- **Verificado no navegador a 1920 px**: gutters de 24 px, laterais 320/288 px, conversa 1232 px, campo de pergunta 736 px centralizado, sem rolagem da página. O arrastar e soltar de 3 PDFs + 1 falso deu 3 adicionados e o falso listado com o motivo; o worker deixou os 3 prontos. O estado vazio atualizou nos dois sentidos. Tema claro OK.

## Resposta em segundo plano e streaming real em ASGI (2026-10-08)

**Bug relatado**: "This answer is already being written in another tab." numa resposta que foi gerada inteira. Pelos logs: o autor perguntou, abriu uma nota 2 s depois e voltou. O stream da volta tentou reivindicar uma resposta que ainda estava sendo escrita pelo primeiro stream (já sem ninguém ouvindo) e virou erro permanente. Investigando, apareceram problemas mais sérios:

- **Não havia streaming em produção.** Em ASGI, `StreamingHttpResponse` consome um iterador **síncrono** inteiro (`sync_to_async(list)`) antes de enviar; o inverso vale em WSGI. O dev rodava runserver (WSGI) e a produção roda uvicorn (ASGI), por isso o problema passou despercebido.
- **A resposta dependia da conexão**: em dev continuava sem ninguém ouvindo; em produção, sair a cortaria.
- **Órfãs**: um restart no meio deixava a resposta em `streaming` para sempre.

**Desenho novo** (o autor escolheu que a resposta **continua sendo escrita** ao sair da página):
- `rag/generation.py`: o `ask` dispara a geração, depois do commit, numa **thread** (`ThreadPoolExecutor`, `ASCENDIA_ANSWER_THREADS=4`; 0 roda inline nos testes). A thread salva o parcial e o **batimento** (`Message.updated_at`, definido explicitamente porque `update()` ignora `auto_now`) a cada ~0,3 s, num único `UPDATE ... WHERE status='streaming'`; se nenhuma linha muda, alguém pediu "Parar". O fim também é condicional, para nunca sobrescrever um "parado". Thread em vez da fila `django-tasks`: a resposta é interativa, e a fila (polling de ~1 s, uma tarefa por vez) faria a ingestão de PDFs atrasar as respostas.
- `rag/answer.py`: o stream é um **gerador assíncrono** que só **acompanha** a mensagem no banco (a cada 0,25 s envia `html` quando o texto muda, `done` no fim, e `: keepalive` a cada 15 s). Desconectar não altera nada; várias abas acompanham a mesma resposta. Sem batimento há mais de `ASCENDIA_ANSWER_STALE_SECONDS` (60), a resposta vira "interrompida" com o parcial salvo; `pending` que nunca começou (3× o prazo) vira erro "pergunte de novo".
- **Dev igual a produção**: o override do compose usa `uvicorn --reload` (ASGI). Os estáticos de dev vêm da fonte via `WHITENOISE_USE_FINDERS/AUTOREFRESH = DEBUG`.
- **Segundo bug achado na verificação**: com a geração em thread, o **primeiro** `import litellm` (que era preguiçoso) passou a acontecer dentro da thread e deu `_DeadlockError` no lock de import do Python. Agora o LiteLLM é carregado no `ready()` do app `llm`, na thread principal (~2 s por processo), com teste de regressão.

**Verificado contra o uvicorn real (cliente HTTP e navegador)**:
- sair 1 s depois de perguntar e voltar → o texto já escrito aparece na hora e o resto chega ao vivo (13 eventos `html` em 3,6 s), sem erro;
- reiniciar o `web` no meio de uma resposta → depois de 60 s sem batimento, quem volta vê "Interrompida antes do fim" com os 150 caracteres preservados;
- nenhum erro no log depois da correção do import.

## LaTeX, blocos de código e fontes Markdown (2026-10-08)

**Diagnóstico** (o render aplicado a uma resposta típica): além de não formatar, o código era **corrompido**:
- o gate de citações tratava todo `[n]` como citação, inclusive em código: `dp = [0]` virava `dp = +`, `dp[3]` virava `dp`, `moedas[1, 2]` virava chip;
- a limpeza de espaços do gate colapsava a indentação no texto inteiro;
- `\(…\)` perdia a barra (escape do Markdown) e `$…$` ficava cru.

**Decisões**:
- **`rag/segments.py`** divide o Markdown em prosa / código / matemática:
  - cercas com e sem fechamento (streaming), crases de N caracteres;
  - `$$`, `\[`, `\(`, e `$` com a regra do Pandoc, para "R$ 10 e R$ 20" não virar fórmula.
  - Gate, chips e normalização de matemática atuam **só na prosa**; código e fórmulas passam byte a byte.
- **Gate sem limpeza global de espaços**: um marcador removido leva o espaço antes dele, e nada mais é mexido (preserva indentação de listas e quebras forçadas do Markdown).
- **Chips por sentinela**: citações válidas viram caracteres de uso privado **antes** do Markdown e viram botões **depois** do nh3, então um `[1]` dentro de código nunca vira chip.
- **Matemática**: `mdit-py-plugins` `dollarmath` (`allow_space=False, allow_digits=False`) marca `.math.inline`/`.math.block` com o TeX escapado. O **KaTeX 0.16.11** fica em `static/vendor/katex/` (MIT; integridade sha512 conferida no registro do npm; só JS, CSS e fontes woff2; ~600 KB), sem CDN. Renderiza com `trust: false`, `throwOnError: false` e limites de `maxSize`/`maxExpand`; saída `htmlAndMathml` (MathML para leitores de tela).
- **Código**: realce no servidor com **Pygments** (`classprefix='tok-'`). O nh3 só aceita `class` em `span`/`div`/`code` quando os valores são `tok-*`, `math`/`inline`/`block` ou `language-*` (`attribute_filter`). As cores vêm de tokens `--code-*` por tema: no claro o número tinha contraste **1.52** e agora todos passam de AA (4.58 a 6.12). Botão "Copiar código" e nome da linguagem por bloco (`static/js/richtext.js`, compartilhado com `chat.js`).
- **Fontes `.md`** (`Source.KIND_MARKDOWN`, migração `sources/0002`):
  - validação UTF-8, aceitando BOM;
  - seções pelos títulos, ignorando `#` dentro de código ("Grafos › Dijkstra");
  - **chunking por blocos** usando o mapa de linhas do markdown-it: texto original, sem refluir, e bloco de código/tabela/fórmula nunca cortado (código grande é dividido por linhas, refazendo as cercas);
  - o arquivo guardado leva a extensão do tipo (`.md`), nunca o nome enviado;
  - o cartão de citação de fonte `.md` mostra o trecho renderizado.
  - Texto colado segue o chunking antigo (fora do pedido).
- **Verificado no navegador** (caderno temporário, removido):
  - `.md` enviado por arrastar e soltar ficou pronto;
  - na resposta real, 5 fórmulas inline + 1 em bloco pelo KaTeX (0 erros, já durante o streaming) e código Python realçado e indentado;
  - "Copiar código" copiou o texto exato;
  - o cartão de citação `.md` veio renderizado com fórmulas e código.
