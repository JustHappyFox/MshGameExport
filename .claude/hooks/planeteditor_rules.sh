#!/bin/bash
# Правила владельца для ИИ - при старте сессии и после каждого сжатия контекста.
# Правила живут только в своих репозиториях (копий здесь нет - владелец 07.10): общее и редакторы - GameExport
# CLAUDE.md, игра - ProjectVanguard CLAUDE.md. Хук печатает их разделы «Главное» (между <!-- выжимка:имя --> и
# <!-- /выжимка -->, у игры - до конца файла) и карту разделов полных RULES.md. Вывод одного вызова больше ~10 КБ до ИИ
# не доходит целиком - поэтому каждая часть - свой вызов (settings.json).
#   planeteditor_rules.sh общее|редактор|игра - раздел «Главное»; map-ge / map-pv - карта разделов полного файла правил
D="$(cd "$(dirname "$0")/.." && pwd)"
GE=/home/user/gameexport
PV=/home/user/projectvanguard
case "$1" in
  общее|редактор|игра)
    if [ "$1" = игра ]; then f="$PV/CLAUDE.md"; else f="$GE/CLAUDE.md"; fi
    if [ -f "$f" ]; then
      echo "=== ГЛАВНОЕ: $1 ($f; полностью - его RULES.md, карта ниже) ==="
      awk -v m="<!-- выжимка:$1" 'index($0, m) == 1 {on = 1; next} on && index($0, "<!-- /выжимка") == 1 {exit} on' "$f"
    else
      echo "$f: клона нет - подключить репо (add_repo) и склонировать: GameExport - ветка main-copied в $GE,"
      echo "ProjectVanguard - в $PV"
    fi
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
