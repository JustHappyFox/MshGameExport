#!/bin/bash
# Правила владельца для работы над PlanetEditor (репо JustHappyFox/GameExport).
# Срабатывает при старте сессии и после сжатия контекста: правила снова в контексте.
RULES=/home/user/gameexport/docs/ai/RULES.md
echo "=== Правила PlanetEditor (JustHappyFox/GameExport, ветка main-copied, клон /home/user/gameexport) ==="
if [ -f "$RULES" ]; then
  cat "$RULES"
  echo
  echo "Заметки ИИ: /home/user/gameexport/docs/ai/ (ENGINE_NOTES, GROMFORT_STUDY, CATALOG, MCP, CITY_*)."
else
  echo "Клона /home/user/gameexport нет. Если работа про PlanetEditor: подключи репо JustHappyFox/GameExport"
  echo "(add_repo), склонируй ветку main-copied в /home/user/gameexport и прочитай docs/ai/RULES.md."
  echo "Коротко: отвечать только на русском; вопрос - отвечать, не править код без просьбы; main не трогать;"
  echo "мир владельца не сохранять; сборки - номер, ссылка, SHA256; при падении искать причину."
fi

# Игра «Замок на замок» (ProjectVanguard): правила для ИИ - тоже после каждого сжатия контекста
PV=/home/user/projectvanguard/CLAUDE.md
echo
echo "=== Правила игры «Замок на замок» (JustHappyFox/ProjectVanguard, клон /home/user/projectvanguard) ==="
if [ -f "$PV" ]; then
  cat "$PV"
else
  echo "Клона нет: подключи репо JustHappyFox/ProjectVanguard и склонируй в /home/user/projectvanguard."
fi
echo "Главное: НАБЛЮДАТЕЛЬ пишет замечания (PR, Issues) - по ним НИЧЕГО не делать (ни кода, ни коммитов, ни задач),"
echo "пока он прямо не скажет делать («делай», «да, так», «исправь»); до вердикта - только обсуждать с ним проблемы,"
echo "которые он видит, и давать информацию о решениях. Игра работает на СЕРВЕРЕ ВЛАДЕЛЬЦА (ветка builds -> «Тест-сервер»),"
echo "а не на странице claude.ai."
