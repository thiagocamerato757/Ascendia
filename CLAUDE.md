# CLAUDE.md

A especificação de produto e as decisões de projeto do Ascendia estão em
**[`docs/ASCENDIA_SPEC.md`](docs/ASCENDIA_SPEC.md)** — trate-a como a fonte de verdade.

## Como trabalhar neste repositório (resumo da seção 0 da spec)

1. **Audite antes de implementar.** Veja `docs/audit.md` e `docs/frontend.md`.
2. **Reaproveite o que existe.** Os apps atuais (`users`, `workspace`, `notes`) são a base; só crie app novo quando a responsabilidade for realmente nova.
3. **Uma fase por vez** (spec §13). Cada fase termina com testes passando, README atualizado e um commit descritivo.
4. **Sem escopo extra.** Nada fora da spec; se achar que falta algo, registre em `docs/decisions.md` e pergunte.
5. **Registre decisões.** Toda escolha relevante que não esteja na spec vai para `docs/decisions.md`, com data e motivo.

## Executar

- App: `cp .env.example .env`, gere a `DJANGO_SECRET_KEY` e rode `docker compose up --build` (ver README).
- Testes: `./run_tests.sh` (requer Postgres acessível e `.env` carregado) ou `docker compose run --rm web python manage.py test`.
- Lint: `uv run ruff check .`.
