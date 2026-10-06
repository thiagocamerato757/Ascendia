# Auditoria de front-end — Ascendia

> Fase 0 da `ASCENDIA_SPEC.md` (§10: "Primeiro audite o front-end atual"). Documenta o que existe hoje em `templates/` e `static/` e compara com as regras da seção 10. Nenhum código foi alterado.
> Data: 2026-10-06.

## 1. Abordagem atual

- **Server-rendered puro:** templates Django com `base.html` único e `{% block %}` (`title`, `extra_css`, `nav_links`, `content`, `footer`, `notifications`, `extra_js`, `body_class`). Toda página estende a base. ✔ compatível com §10.1.
- **Dupla camada de estilo (problema):** `base.html` carrega **Tailwind via CDN** (`<script src="https://cdn.tailwindcss.com">`) **e** um CSS de componentes próprio (`design.css`). Os templates usam **utilitárias Tailwind** (`flex`, `px-8`, `text-white/60`, `rounded-full`, `max-w-7xl`) **misturadas** com classes de componente próprias (`btn-primary`, `card-aurora`). §10.3 proíbe explicitamente misturar utilitárias com uma convenção de componentes.
- **JavaScript:** mínimo. **Sem HTMX, sem Alpine, sem framework** (grep por `htmx`/`hx-`/`x-data`/`alpine` não retorna nada). O único JS relevante é o recorte de avatar (Cropper, `cropper-custom.css`) e o toggle-favorite via `fetch` AJAX. §10.1 recomenda HTMX — ainda a adotar.
- **Sem SPA, sem build step.** Tailwind CDN (não adequado a produção) e CSS estático servidos direto.

## 2. CSS existente (`static/css/`)

| Arquivo | Linhas | Conteúdo |
|---|---|---|
| `design.css` | 426 | Paleta "aurora" em `:root`, tipografia (Inter + Space Grotesk via Google Fonts), e classes de componente: `.btn-*`, `.input-aurora`, `.card-aurora`, `.badge-aurora`, `.link-aurora`, `.navbar-aurora`, `.divider-aurora`, `.file-input-aurora`, color picker, checkbox, `.bg-aurora`, spinner, scrollbar, animações. |
| `notifications.css` | 172 | Toasts CSS-only para `messages` do Django (slide-in, hold 5s, fade-out), cores por tipo. |
| `profile.css` | 160 | Estilos da página de perfil. |
| `cropper-custom.css` | 162 | Customização do recorte de avatar (Cropper.js). |

### Tokens de design — parcial
- **Existe** em `:root` uma paleta de **cores** aurora (mint, cyan, blue, purple, light + variantes light/dark). ✔ ponto de partida.
- **Não existe `static/css/tokens.css`** (exigido por §10.2).
- **Faltam tokens** para: espaçamento (escala fixa), raios, sombras, tipografia (famílias/escala/pesos tokenizados). Hoje valores de padding, border-radius, font-size e box-shadow estão **soltos** dentro de cada classe de componente (ex.: `padding: 0.75rem 2rem; border-radius: 0.75rem;` repetidos). §10.2 proíbe valores soltos — tudo deveria referenciar um token.

### Tema
- **Apenas tema escuro** ("aurora"): fundo `.bg-aurora` com gradientes radiais, superfícies glass (`rgba(255,255,255,0.06)` + `backdrop-filter: blur`).
- **Não há tema claro**, nem `@media (prefers-color-scheme)`, nem alternância manual. §10.2 exige **claro e escuro**, definidos só nos tokens. Será o maior trabalho da Fase 1.
- Cores de texto são hardcoded como `text-white` / `text-white/60` (utilitárias Tailwind) em vez de tokens de texto — amarra tudo ao fundo escuro.

## 3. Componentes

- **Não existe `templates/components/`.** Nenhum partial reutilizável (`{% include %}`) nem template tag de componente.
- Os "componentes" existem só como **classes CSS** (`.btn-primary`, `.card-aurora`, `.input-aurora`, `.badge-aurora`, color picker, checkbox). Dá para reaproveitá-los como base visual, mas não há a camada de template reutilizável que §10.3 pede.
- **Estados de componente:** botões têm `:hover`/`:active`; inputs têm `:focus`. **Não há** estados padronizados de *desabilitado*, *carregando* (existe `.spinner-aurora` solto), *erro* em campo. Faltam `:focus-visible` (§10.6) — hoje usa `:focus`.

### Componentes exigidos pela spec que **ainda não existem** (§10.3)
Botão com todos os estados (incl. desabilitado/carregando como componente), campo de formulário (rótulo/ajuda/erro padronizados), seletor, modal, aviso/toast *como componente* (hoje é CSS acoplado aos `messages`), cartão, **estado vazio**, **esqueleto de carregamento**, **bolha de mensagem** (usuário/assistente), **chip de citação `[n]`**, **item de fonte com status de ingestão**, **painel de configurações**. Todos os de RAG dependem das Fases 2–3.

## 4. Layout

- Layout atual: navbar fixa no topo + `main` com scroll + footer. Páginas usam containers centralizados (`max-w-7xl mx-auto`).
- **Não existe o layout de três painéis** do NotebookLM (fontes à esquerda / conversa ao centro / materiais à direita) exigido em §10.4 — a tela de caderno (`notebook_detail.html`) hoje mostra cabeçalho do caderno + lista de notas, não o workspace de RAG.
- Responsividade: usa utilitárias Tailwind pontuais; não há a estratégia de "colapsar painéis em abas" de §10.4.

## 5. Acessibilidade e idioma

- **Idioma:** `<html lang="en">` e **textos em inglês hardcoded** em todos os templates ("Welcome to Ascendia", "Log out", "Workspace"). Sem `{% trans %}` / i18n. §10.6 pede **pt-BR por padrão** via i18n do Django.
- **Semântica:** uso razoável de `<header>`, `<nav>`, `<main>`, `<footer>`. SVGs decorativos com `aria-hidden="true"` em parte dos casos.
- **Foco:** usa `:focus` (não `:focus-visible`). Falta revisão de navegação por teclado e contraste AA.
- **`aria-live`:** ausente (ainda não há área de resposta em streaming — §10.6 exigirá na Fase 3).

## 6. Segurança no front-end (§10.8)

- **CSRF:** `{% csrf_token %}` presente nos formulários (logout, etc.); testes de CSRF existem em `users/tests.py`. ✔
- **Escapamento:** autoescape padrão do Django ativo; testes de XSS passam. ✔ (Ainda não há Markdown renderizado — quando entrar conteúdo de fontes/modelo na Fase 3, precisará de sanitização explícita.)
- **Chaves:** nenhuma chave de API chega ao HTML/JS hoje (ainda não há provedores). A regra vale a partir da Fase 2.
- **Estilos inline:** há `style="..."` em vários templates. A maioria é **dinâmica legítima** (cor do caderno/tag vinda do modelo: `style="background: {{ notebook.color }}"`) — difícil tokenizar porque é dado do usuário. Mas há também valores **hardcoded** (ex.: no e-mail de reset: `style="background: #fff; padding: 10px"`, `color: #666`) que violam §10.2 e devem virar tokens/classe. Decidir na Fase 1 como tratar cor dinâmica (ex.: CSS var inline `style="--accent: {{ color }}"`).

## 7. Resumo: o que reaproveitar vs. refazer na Fase 1

**Reaproveitar:**
- Paleta aurora de `:root` como base das cores dos tokens.
- Estrutura de `base.html` com blocks (já boa).
- Toasts de `notifications.css` (adaptar a componente de aviso).
- Identidade visual (fontes Inter/Space Grotesk, cards glass) como ponto de partida do tema escuro.

**Refazer / criar:**
- `static/css/tokens.css` com a escala completa (cor, espaçamento, raio, sombra, tipografia) e **tema claro + escuro** via tokens.
- Eliminar a mistura **Tailwind CDN × classes próprias** — escolher uma única abordagem (ver decisão em `docs/decisions.md`).
- `templates/components/` com partials reais e estados documentados.
- Rota `/styleguide/` (ativa só com `DEBUG`) renderizando todos os componentes nos dois temas (§10.7).
- i18n pt-BR; trocar `:focus` por `:focus-visible`; revisar contraste/teclado.
- Layout de três painéis responsivo para a tela de caderno (quando a Fase 3 trouxer fontes/conversa/materiais).
