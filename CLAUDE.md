# Для ИИ

> **Сеть правил** (владелец 07.10: сначала изучить все правила, потом делать; каждое правило - в одном месте, копий нет).
> **После каждого сжатия контекста, и только тогда** - прочитать (Read) ЦЕЛИКОМ, до последней строки, основные файлы;
> справочные - когда задача до них дошла, нужную часть целиком, не по памяти; выжимок и пересказов правил нет (владелец
> 25.10: перечитывать всё - перерасход; правило - GameExport `docs/ai/RULES.md`, раздел 1; список печатает хук
> MshGameExport).
> Основные: GameExport (`/home/user/gameexport`, ветка main-copied) - `CLAUDE.md`, `docs/ai/RULES.md` раздел 1 (общее);
> ProjectVanguard (`/home/user/projectvanguard`) - `CLAUDE.md`, `RULES.md` (игра), `docs/REVIEW.md` (наблюдатель),
> `docs/BRANCHES.md` (ветки и выпуски), `docs/tasks/README.md` (журналы задач); журнал задачи в работе.
> Справочные: игра - `ARCHITECTURE.md` (устройство; раздел правимого модуля), `server/README.md` (сервер, панель),
> `docs/EXPERIMENTS.md` (опыты; перед опытом - поиск по нему); редакторы, земли, данные «Осады» - GameExport
> `docs/ai/RULES.md` разделы 2-6, `docs/ai/EXPERIMENTS.md`, `docs/ai/ENGINE_NOTES.md`, `docs/ai/GAMEDATA.md`.
> Новое правило - один раз, в полный файл своего репо: общее и редакторы - GameExport, игра - ProjectVanguard.

Отвечать владельцу **только на русском**.

Правил здесь нет - только вход (каждое правило - в одном месте, владелец 07.10):
- **PlanetEditor, WorldEditor, земли, общее** - JustHappyFox/GameExport, ветка `main-copied`, клон `/home/user/gameexport`.
  Клона нет - подключить репо и склонировать ветку в эту папку.
- **Игра «Замок на замок»** - JustHappyFox/ProjectVanguard, клон `/home/user/projectvanguard`.
- Хук `.claude/hooks/planeteditor_rules.sh` после каждого сжатия контекста (и только тогда) печатает список файлов
  правил - их прочитать целиком, прежде чем продолжать.

## Этот репозиторий

autoedit.ink — Telegram Mini App и бот (см. README.md).
