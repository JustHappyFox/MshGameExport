#!/bin/bash
# Напоминание о правилах владельца - при старте сессии и после каждого сжатия контекста (settings.json, SessionStart).
# Текст правил не печатает: выжимок нет, правила читаются целиком инструментом Read (владелец 07.10; вывод хука больше
# ~2 КБ до ИИ не доходит). Печатает только это требование и список файлов «Сети правил» с числом строк.
# Само правило - GameExport docs/ai/RULES.md, раздел 1.
D="$(cd "$(dirname "$0")/../.." && pwd)"
GE=/home/user/gameexport
PV=/home/user/projectvanguard
echo "=== ПРАВИЛА ВЛАДЕЛЬЦА: прежде чем продолжать или отвечать - прочитать (Read) ЦЕЛИКОМ, до последней строки, КАЖДЫЙ"
echo "файл ниже (большой - страницами по подсказке offset). Не выборочно, не по памяти, без выжимок (владелец 07.10). ==="
for f in "$D/CLAUDE.md" "$GE/CLAUDE.md" "$GE/docs/ai/RULES.md" "$PV/CLAUDE.md" "$PV/RULES.md" "$PV/docs/REVIEW.md" \
         "$PV/docs/BRANCHES.md" "$PV/docs/tasks/README.md" "$PV/server/README.md"; do
  if [ -f "$f" ]; then
    echo "- $f (строк: $(wc -l < "$f"))"
  else
    echo "- $f - НЕТ КЛОНА: подключить репо (add_repo) и склонировать (GameExport - ветка main-copied в $GE,"
    echo "  ProjectVanguard - в $PV), потом прочитать"
  fi
done
for r in "$GE" "$PV"; do
  [ -d "$r/.git" ] && echo "$r - ветка $(git -C "$r" branch --show-current); правила читать свежие (git pull)"
done
echo "Затем - журнал задачи в работе (ProjectVanguard docs/tasks/) и открытые PR."
