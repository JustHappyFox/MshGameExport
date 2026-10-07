# Для ИИ

> **Сеть правил** (владелец 07.10: сначала изучить все правила, потом делать; каждое правило - в одном месте, копий нет).
> При старте сессии и **после каждого сжатия контекста** - прежде чем продолжать, прочитать (Read) ЦЕЛИКОМ, до последней
> строки, все файлы ниже; выжимок и пересказов правил нет (список печатает хук MshGameExport, правило - GameExport
> `docs/ai/RULES.md`, раздел 1).
> GameExport (`/home/user/gameexport`, ветка main-copied): `CLAUDE.md`, `docs/ai/RULES.md` - общее, редакторы, земли;
> `docs/ai/EXPERIMENTS.md` - опыты и выводы; `docs/ai/ENGINE_NOTES.md` - движок; `docs/ai/GAMEDATA.md` - файлы игры.
> ProjectVanguard (`/home/user/projectvanguard`): `CLAUDE.md`, `RULES.md` - игра; `docs/REVIEW.md` - наблюдатель;
> `docs/BRANCHES.md` - ветки и выпуски; `docs/tasks/README.md` - журналы задач; `server/README.md` - тест-сервер;
> `docs/EXPERIMENTS.md` - опыты и выводы; `ARCHITECTURE.md` - устройство игры; журнал задачи в работе.
> Новое правило - один раз, в полный файл своего репо: общее и редакторы - GameExport, игра - ProjectVanguard.
> Каждое указание владельца - сразу в файл правил своего репо; итог каждого опыта - в `EXPERIMENTS.md` своего репо.

Отвечать владельцу **только на русском**.

Правил здесь нет - только вход (каждое правило - в одном месте, владелец 07.10):
- **PlanetEditor, WorldEditor, земли, общее** - JustHappyFox/GameExport, ветка `main-copied`, клон `/home/user/gameexport`.
  Клона нет - подключить репо и склонировать ветку в эту папку.
- **Игра «Замок на замок»** - JustHappyFox/ProjectVanguard, клон `/home/user/projectvanguard`.
- Хук `.claude/hooks/planeteditor_rules.sh` при старте и после каждого сжатия контекста печатает список файлов правил -
  их прочитать целиком, прежде чем продолжать.

## Этот репозиторий

autoedit.ink — Telegram Mini App и бот (см. README.md).
