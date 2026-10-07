# Для ИИ

> **Сеть правил** (читать вместе: прочитал один - смотри остальные; сначала изучить все, потом делать - владелец 07.10).
> Главное (выжимка; её выводит хук MshGameExport при старте и после сжатия контекста): общее и редакторы - GameExport
> `CLAUDE.md`, игра - ProjectVanguard `CLAUDE.md`. Полностью: GameExport (`/home/user/gameexport`, ветка main-copied)
> `docs/ai/RULES.md`; ProjectVanguard (`/home/user/projectvanguard`) `RULES.md`, `docs/REVIEW.md` - наблюдатель,
> `docs/BRANCHES.md` - ветки и выпуски, `docs/tasks/README.md` - журналы, `server/README.md` - тест-сервер.
> **Каждое правило - в одном месте, копий нет** (владелец 07.10): игра - ProjectVanguard, общее и редакторы -
> GameExport. Частое правило - строкой в «Главное» `CLAUDE.md` своего репо, подробности - в его полном файле.

Отвечать владельцу **только на русском**.

Правил здесь нет - только вход (каждое правило - в одном месте, владелец 07.10):
- **PlanetEditor, WorldEditor, земли, общее** - JustHappyFox/GameExport, ветка `main-copied`, клон `/home/user/gameexport`:
  `CLAUDE.md` (главное), `docs/ai/RULES.md` (полностью). Клона нет - подключить репо и склонировать ветку в эту папку.
- **Игра «Замок на замок»** - JustHappyFox/ProjectVanguard, клон `/home/user/projectvanguard`: `CLAUDE.md` (главное, в т.ч.
  наблюдатель и выкладка на сервер владельца), `RULES.md` (полностью).
- Хук `.claude/hooks/planeteditor_rules.sh` выводит их разделы «Главное» и карту разделов при старте и после каждого
  сжатия контекста.

## Этот репозиторий

autoedit.ink — Telegram Mini App и бот (см. README.md).
