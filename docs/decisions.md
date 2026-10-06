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

- **SQLite → Postgres + pgvector** (D1): migração planejada para a Fase 0/3. Motivo: vetores + full-text no mesmo banco.
- **Segredos fora do código**: `settings.py` hoje tem `SECRET_KEY`/`DEBUG` hardcoded e **não lê o `.env`** (apesar de `python-dotenv` ser dependência). Decisão: ligar `settings.py` ao ambiente e criar `.env.example`. Motivo: D6.
- **Idioma padrão pt-BR** (§6/§10.6): hoje `en-us`. Decisão: migrar para pt-BR com i18n na Fase 1.
