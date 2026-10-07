# Для ИИ

> **Сеть правил** (читать вместе: прочитал один - смотри остальные; сначала изучить все, потом делать - владелец 07.10).
> MshGameExport: `CLAUDE.md`, выжимка `.claude/rules/*.md` (её и карту разделов выводит хук после сжатия контекста).
> GameExport (`/home/user/gameexport`, ветка main-copied): `CLAUDE.md`, `docs/ai/RULES.md` - редакторы, земли.
> ProjectVanguard (`/home/user/projectvanguard`): `CLAUDE.md`, `RULES.md` - игра; `docs/REVIEW.md` - наблюдатель;
> `docs/BRANCHES.md` - ветки и выпуски; `docs/tasks/README.md` - журналы задач; `server/README.md` - тест-сервер.
> Новое правило - в полный файл своего репо, общее или частое - ещё и в выжимку MshGameExport `.claude/rules/`.

Отвечать владельцу **только на русском**.

## PlanetEditor (HeavyDuty, «Осада Онлайн»)

Основная работа идёт не в этом репозитории, а в **JustHappyFox/GameExport**, ветка `main-copied`
(клон `/home/user/gameexport`). Перед любой крупной задачей по редактору прочитай
`/home/user/gameexport/CLAUDE.md` и `/home/user/gameexport/docs/ai/RULES.md` и работай строго по ним.
Правила также выводит хук старта сессии (`.claude/hooks/planeteditor_rules.sh`) — при запуске
и после каждого сжатия контекста.

Если клона нет — подключить репо JustHappyFox/GameExport и склонировать ветку `main-copied` в
`/home/user/gameexport`.

## Игра «Замок на замок»

Отдельный репозиторий **JustHappyFox/ProjectVanguard** (клон `/home/user/projectvanguard`): прочитай его `CLAUDE.md`
и `RULES.md`. Редакторы и данные «Осады» остаются в GameExport.

**Игра работает на сервере владельца** (тест-сервер в WSL на его ПК, `server/README.md` в ProjectVanguard), а не на
странице claude.ai. Выкладка: сборка -> ветка `builds` -> workflow «Тест-сервер» -> метка `vXX.YY` workflow «Выпуск».
Страницу claude.ai не обновлять, её ограничения (511 файлов, только «веб»-типы файлов) не учитывать.

**Наблюдатель** (указание владельца 07.10): у проекта есть наблюдатель, он в любой момент пишет, если что-то надо
сделать иначе (комментарии в PR, Issues - `docs/REVIEW.md` в ProjectVanguard). **По его замечанию ничего не делать** - ни
кода, ни коммитов, ни новых задач, - **пока он прямо не скажет делать** («делай», «да, так», «исправь»). До вердикта -
только обсуждать с ним проблемы, которые он видит, и давать информацию о решениях (что, где, чем рискуем, варианты).
Замечание, которое расходится с указанием владельца, - вопрос владельцу.

## Этот репозиторий

autoedit.ink — Telegram Mini App и бот (см. README.md).
