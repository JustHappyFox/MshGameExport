#!/bin/bash
# Напоминание о правилах владельца - только после сжатия контекста (settings.json, SessionStart, matcher compact):
# не перед каждой задачей и не при возобновлении сессии после паузы (владелец 09.10).
# Текст правил не печатает: выжимок нет, правила читаются целиком инструментом Read (владелец 07.10; вывод хука больше
# ~2 КБ до ИИ не доходит). Печатает основные файлы «Сети правил» с числом строк (у GameExport RULES.md - раздел 1),
# справочные - строкой: их читать, когда задача до них дошла (владелец 25.10: перечитывать всё - перерасход), и журнал
# задачи в работе - по ветке ProjectVanguard task/NNN-... в клоне или в отдельной рабочей папке ветки.
# Само правило - GameExport docs/ai/RULES.md, раздел 1.
D="$(cd "$(dirname "$0")/../.." && pwd)"
GE=/home/user/gameexport
PV=/home/user/projectvanguard
echo "=== ПРАВИЛА ВЛАДЕЛЬЦА: прежде чем продолжать или отвечать - прочитать (Read) ЦЕЛИКОМ, до последней строки, КАЖДЫЙ"
echo "основной файл ниже (большой - страницами по подсказке offset). Не выборочно, не по памяти, без выжимок. ==="
# журнал задачи в работе: ветка task/NNN-... клона ProjectVanguard или его рабочих папок (git worktree)
JOURNAL=""
while read -r wt br; do
  case "$br" in refs/heads/task/[0-9][0-9][0-9]-*) N=${br#refs/heads/task/}; N=${N%%-*}
    f=$(ls "$wt"/docs/tasks/"$N"-*.md 2>/dev/null | head -1); [ -n "$f" ] && JOURNAL="$JOURNAL $f" ;; esac
done < <(git -C "$PV" worktree list --porcelain 2>/dev/null | awk '/^worktree /{w=$2} /^branch /{print w, $2}')
# строка на репо: путь клона, файлы (число строк); нет клона - подключить репо и склонировать
list() {
  local root=$1; shift; local out=""
  if [ ! -d "$root" ]; then
    echo "$root - НЕТ КЛОНА: add_repo и склонировать (GameExport - ветка main-copied), потом прочитать"; return
  fi
  for f in "$@"; do
    if [ -f "$root/$f" ]; then out="$out $f ($(wc -l < "$root/$f")),"; else out="$out $f (НЕТ в этой ветке - git pull / влить main),"; fi
  done
  echo "$root:${out%,}"
}
echo "Основные:"
list "$D" CLAUDE.md
list "$GE" CLAUDE.md
S2=$(grep -n '^## 2\.' "$GE/docs/ai/RULES.md" 2>/dev/null | head -1 | cut -d: -f1)
[ -n "$S2" ] && echo "$GE: docs/ai/RULES.md - раздел 1, строки 1-$((S2 - 1)) (Read offset 1, limit $((S2 - 1)))"
list "$PV" CLAUDE.md RULES.md docs/REVIEW.md docs/BRANCHES.md docs/tasks/README.md
if [ -n "$JOURNAL" ]; then echo "журнал задачи в работе:$JOURNAL"
else echo "Журнал задачи в работе (docs/tasks/NNN-*.md по ветке task/NNN-...) ещё не заведён."; fi
echo "Справочные - когда задача до них дошла (раздел, который правишь, - целиком; журнал опытов - Grep перед опытом):"
echo "  $PV: ARCHITECTURE.md, server/README.md, docs/EXPERIMENTS.md"
echo "  $GE: docs/ai/RULES.md разделы 2-6, docs/ai/EXPERIMENTS.md, docs/ai/ENGINE_NOTES.md, docs/ai/GAMEDATA.md"
for r in "$GE" "$PV"; do
  [ -d "$r/.git" ] && echo "$r - ветка $(git -C "$r" branch --show-current); правила читать свежие (git pull)"
done
echo "Затем - открытые PR."
