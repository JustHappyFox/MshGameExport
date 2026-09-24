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
