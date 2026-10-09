#!/bin/bash
# Напоминание о правилах владельца - только после сжатия контекста (settings.json, SessionStart, matcher compact):
# не перед каждой задачей и не при возобновлении сессии после паузы (владелец 09.10).
# Текст правил не печатает: выжимок нет, правила читаются целиком инструментом Read (владелец 07.10; вывод хука больше
# ~2 КБ до ИИ не доходит). Печатает только это требование и список файлов «Сети правил» с числом строк (и журнал
# задачи в работе - по ветке ProjectVanguard task/NNN-...).
# Само правило - GameExport docs/ai/RULES.md, раздел 1.
D="$(cd "$(dirname "$0")/../.." && pwd)"
GE=/home/user/gameexport
PV=/home/user/projectvanguard
echo "=== ПРАВИЛА ВЛАДЕЛЬЦА: прежде чем продолжать или отвечать - прочитать (Read) ЦЕЛИКОМ, до последней строки, КАЖДЫЙ"
echo "файл ниже (большой - страницами по подсказке offset). Не выборочно, не по памяти, без выжимок (владелец 07.10). ==="
# журнал задачи в работе - по ветке ProjectVanguard task/NNN-...
JOURNAL=""
B=$(git -C "$PV" branch --show-current 2>/dev/null)
case "$B" in task/[0-9][0-9][0-9]-*) N=${B#task/}; N=${N%%-*}
  JOURNAL=$(cd "$PV" 2>/dev/null && ls docs/tasks/"$N"-*.md 2>/dev/null | head -1) ;; esac
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
list "$D" CLAUDE.md
list "$GE" CLAUDE.md docs/ai/RULES.md docs/ai/EXPERIMENTS.md docs/ai/ENGINE_NOTES.md docs/ai/GAMEDATA.md
list "$PV" CLAUDE.md RULES.md docs/REVIEW.md docs/BRANCHES.md docs/tasks/README.md server/README.md \
  docs/EXPERIMENTS.md ARCHITECTURE.md $JOURNAL
for r in "$GE" "$PV"; do
  [ -d "$r/.git" ] && echo "$r - ветка $(git -C "$r" branch --show-current); правила читать свежие (git pull)"
done
[ -z "$JOURNAL" ] && echo "Журнал задачи в работе (docs/tasks/NNN-*.md по ветке task/NNN-...) ещё не заведён."
echo "Затем - открытые PR."
