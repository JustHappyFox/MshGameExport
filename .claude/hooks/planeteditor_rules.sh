#!/bin/bash
# Правила владельца для ИИ - при старте сессии и после каждого сжатия контекста.
# Вывод хука больше ~10 КБ до ИИ не доходит целиком (только первые 2 КБ), поэтому полные файлы правил (сотни КБ) не
# печатаются: выводится выжимка .claude/rules/<часть>.md (у каждой части - свой вызов хука, settings.json) и карта
# разделов полных файлов; полный раздел ИИ читает сам перед работой по теме.
#   planeteditor_rules.sh 1|2|3 - часть выжимки; map-ge / map-pv - карта разделов полного файла правил GameExport / ProjectVanguard
D="$(cd "$(dirname "$0")/.." && pwd)"
GE=/home/user/gameexport
PV=/home/user/projectvanguard
case "$1" in
  1|2|3)
    cat "$D"/rules/"$1"_*.md
    ;;
  map-ge|map-pv)
    # заголовки разделов полного файла правил: где читать подробно
    if [ "$1" = map-ge ]; then f="$GE/docs/ai/RULES.md"; else f="$PV/RULES.md"; fi
    if [ -f "$f" ]; then
      echo "=== КАРТА РАЗДЕЛОВ $f (номер строки: раздел) - перед работой по теме прочитать раздел ==="
      python3 -c '
import re, sys
prev = False
for i, line in enumerate(open(sys.argv[1], encoding="utf-8"), 1):
    h = re.match(r"#{2,3} (.*)", line)
    if h and not prev:  # продолжение заголовка (следующая строка с #) - пропуск
        t = re.sub(r"\s*\((замечани[ея]|указание|передал|договорённость)[^:]*:?\s*", " (", h.group(1))
        print(f"{i}: {t[:46]}")
    prev = bool(h)
' "$f"
    else
      echo "$f: клона нет - подключить репо (add_repo) и склонировать: GameExport - ветка main-copied в $GE,"
      echo "ProjectVanguard - в $PV"
    fi
    [ "$1" = map-pv ] && echo "Прочие: $PV/CLAUDE.md, docs/REVIEW.md, docs/BRANCHES.md, docs/tasks/README.md, server/README.md; задачи - docs/tasks/, открытые PR."
    [ "$1" = map-ge ] && echo "Прочие: $GE/CLAUDE.md, docs/PlanetEditor_Manual.md, docs/ai/*.md (движок, каталог, MCP, видео)."
    ;;
esac
