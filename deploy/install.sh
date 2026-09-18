#!/usr/bin/env bash
# Ставит autoedit в отдельную самодостаточную папку.
# Запускать от root из распакованного архива:
#
#     tar xzf autoedit-ГГГГММДД-ЧЧММ.tar.gz -C /tmp
#     bash /tmp/autoedit-ГГГГММДД-ЧЧММ/deploy/install.sh
#
# Повторный запуск = обновление: код заменяется, а whitelist.txt,
# autoedit.env, база и готовые файлы остаются на месте.
#
# На сервере могут работать другие боты и сервисы, поэтому:
#   - всё лежит внутри одной папки (по умолчанию /opt/autoedit);
#   - свободный порт подбирается сам;
#   - в системе появляются только три юнита autoedit-* и один сайт nginx.
set -euo pipefail

APP_ROOT=${AUTOEDIT_ROOT:-/opt/autoedit}
DOMAIN=${AUTOEDIT_DOMAIN:-autoedit.ink}
USER_NAME=${AUTOEDIT_USER:-autoedit}
PORT_FROM=${AUTOEDIT_PORT_FROM:-8081}
PORT_TO=${AUTOEDIT_PORT_TO:-8129}

ENV_FILE=$APP_ROOT/autoedit.env
WHITELIST=$APP_ROOT/whitelist.txt

say()  { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
note() { printf '    %s\n' "$1"; }
die()  { printf '\033[31mОшибка: %s\033[0m\n' "$1" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "нужен root"
SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
[[ -f "$SRC/app/api.py" ]] || die "запускай из распакованного архива"
[[ -f "$SRC/assets/banner.mp4" ]] || die "в архиве нет assets/banner.mp4"

FRESH=1
[[ -f $ENV_FILE ]] && FRESH=0

say "Пакеты"
MISSING=()
for bin in ffmpeg python3; do command -v $bin >/dev/null || MISSING+=("$bin"); done
if ((${#MISSING[@]})) || ! python3 -c 'import venv' 2>/dev/null; then
    if command -v apt-get >/dev/null; then
        apt-get update -qq
        apt-get install -y --no-install-recommends python3 python3-venv python3-pip ffmpeg
    else
        die "поставь вручную: ${MISSING[*]:-python3-venv}"
    fi
fi
note "$(ffmpeg -version | head -1)"
note "$(python3 --version)"
command -v nginx >/dev/null || note "nginx не найден — конфиг положу, но включать будет нечего"

say "Пользователь и папка $APP_ROOT"
id -u "$USER_NAME" >/dev/null 2>&1 || \
    useradd --system --home "$APP_ROOT" --shell /usr/sbin/nologin "$USER_NAME"
mkdir -p "$APP_ROOT"/{data/{uploads,outputs,cache,tmp},bin}

say "Код"
# Меняем только код. data/, autoedit.env и whitelist.txt не трогаем.
for item in app web assets tools requirements.txt; do
    rm -rf "${APP_ROOT:?}/$item"
    cp -r "$SRC/$item" "$APP_ROOT/$item"
done
[[ -f $SRC/VERSION ]] && cp "$SRC/VERSION" "$APP_ROOT/VERSION"
note "версия $(cat "$APP_ROOT/VERSION" 2>/dev/null || echo 'без метки')"

say "venv"
[[ -d $APP_ROOT/venv ]] || python3 -m venv "$APP_ROOT/venv"
"$APP_ROOT/venv/bin/pip" install --quiet --upgrade pip
"$APP_ROOT/venv/bin/pip" install --quiet -r "$APP_ROOT/requirements.txt"
note "зависимости на месте"

say "Порт"
if [[ $FRESH -eq 0 ]] && grep -q '^API_PORT=' "$ENV_FILE"; then
    API_PORT=$(grep '^API_PORT=' "$ENV_FILE" | cut -d= -f2)
    note "оставляю прежний $API_PORT"
else
    # ss есть не везде, поэтому просто пробуем занять порт сами.
    API_PORT=$(python3 - "$PORT_FROM" "$PORT_TO" <<'PY'
import socket, sys
for port in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
    s = socket.socket()
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
    except OSError:
        continue
    finally:
        s.close()
    print(port)
    break
PY
)
    [[ -n $API_PORT ]] || die "нет свободного порта в диапазоне $PORT_FROM-$PORT_TO"
    note "выбран свободный $API_PORT"
fi

say "Конфиг"
if [[ $FRESH -eq 1 ]]; then
    cp "$SRC/.env.example" "$ENV_FILE"
    sed -i \
        -e "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" \
        -e "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://$DOMAIN|" \
        -e "s|^AUTOEDIT_ROOT=.*|AUTOEDIT_ROOT=$APP_ROOT|" \
        -e "s|^API_PORT=.*|API_PORT=$API_PORT|" \
        "$ENV_FILE"
    note "создан $ENV_FILE"
else
    note "$ENV_FILE уже есть, не трогаю"
fi
grep -q '^AUTOEDIT_ROOT=' "$ENV_FILE" || echo "AUTOEDIT_ROOT=$APP_ROOT" >> "$ENV_FILE"
grep -q '^API_PORT=' "$ENV_FILE" || echo "API_PORT=$API_PORT" >> "$ENV_FILE"

if [[ ! -f $WHITELIST ]]; then
    cat > "$WHITELIST" <<'WL'
# Кому можно пользоваться ботом. По одной записи в строке.
# Ник Telegram: собака необязательна, регистр не важен.
# Если ника нет — можно по id, строкой вида id:123456789
# Файл перечитывается сам, перезапускать сервисы не нужно.
#
# Пустой список = доступа нет ни у кого.
WL
    note "создан $WHITELIST (пустой — доступа пока нет ни у кого)"
else
    ENTRIES=$(grep -vE '^\s*(#|$)' "$WHITELIST" | wc -l)
    note "$WHITELIST уже есть, записей: $ENTRIES"
fi

say "Обёртка для команд"
cat > "$APP_ROOT/bin/autoedit" <<WRAP
#!/usr/bin/env bash
# Короткие команды: autoedit whitelist list | measure --plan файл.mp4
set -euo pipefail
set -a; . "$ENV_FILE"; set +a
cmd=\${1:-help}; shift || true
case "\$cmd" in
    whitelist) exec "$APP_ROOT/venv/bin/python" "$APP_ROOT/tools/whitelist.py" "\$@" ;;
    measure)   exec "$APP_ROOT/venv/bin/python" "$APP_ROOT/tools/measure.py" "\$@" ;;
    *) echo "autoedit whitelist list|add|remove|check"; echo "autoedit measure [--plan] файл.mp4"; exit 1 ;;
esac
WRAP
chmod 755 "$APP_ROOT/bin/autoedit"
ln -sfn "$APP_ROOT/bin/autoedit" /usr/local/bin/autoedit

say "Права"
NGINX_USER=$(awk '$1=="user"{gsub(/;/,"",$2); print $2; exit}' /etc/nginx/nginx.conf 2>/dev/null || true)
[[ -n ${NGINX_USER:-} ]] || NGINX_USER=www-data
id -u "$NGINX_USER" >/dev/null 2>&1 || NGINX_USER=$USER_NAME
note "nginx работает от $NGINX_USER"

chown -R "$USER_NAME":"$USER_NAME" "$APP_ROOT"
chmod 750 "$APP_ROOT"
chown root:"$USER_NAME" "$ENV_FILE"
chmod 640 "$ENV_FILE"
chown "$USER_NAME":"$USER_NAME" "$WHITELIST"
chmod 664 "$WHITELIST"
# nginx должен дойти до web/ и data/outputs/, но не дальше
if [[ $NGINX_USER != "$USER_NAME" ]]; then
    chown "$USER_NAME":"$NGINX_USER" "$APP_ROOT" "$APP_ROOT/data" "$APP_ROOT/data/outputs"
    chmod 710 "$APP_ROOT" "$APP_ROOT/data"
    chmod 750 "$APP_ROOT/data/outputs"
    chmod -R a+rX "$APP_ROOT/web"
fi

say "Прогрев кеша замеров"
for geom in 720x1280 1080x1920 1920x1080; do
    sudo -u "$USER_NAME" env AUTOEDIT_ROOT="$APP_ROOT" \
        "$APP_ROOT/venv/bin/python" "$APP_ROOT/tools/measure.py" --geometry "$geom" \
        | sed 's/^/    /'
done

say "systemd"
for unit in api worker bot; do
    sed -e "s|__APP_ROOT__|$APP_ROOT|g" \
        -e "s|__USER__|$USER_NAME|g" \
        "$SRC/deploy/autoedit-$unit.service" > "/etc/systemd/system/autoedit-$unit.service"
done
systemctl daemon-reload
systemctl enable autoedit-api autoedit-worker autoedit-bot >/dev/null
note "юниты autoedit-api, autoedit-worker, autoedit-bot"

say "nginx"
SITE=/etc/nginx/sites-available/autoedit
if [[ -d /etc/nginx/sites-available ]]; then
    if [[ -f $SITE ]]; then
        note "$SITE уже есть, не трогаю"
    else
        sed -e "s|__APP_ROOT__|$APP_ROOT|g" \
            -e "s|__API_PORT__|$API_PORT|g" \
            -e "s|__DOMAIN__|$DOMAIN|g" \
            "$SRC/deploy/nginx.conf" > "$SITE"
        note "создан $SITE"
        if grep -rlq "server_name.*\b$DOMAIN\b" /etc/nginx/sites-enabled/ 2>/dev/null; then
            note "ВНИМАНИЕ: $DOMAIN уже встречается в другом конфиге — сайт не включаю,"
            note "разберись вручную, чтобы не сломать соседний сервис"
        elif [[ -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]]; then
            ln -sfn "$SITE" /etc/nginx/sites-enabled/autoedit
            nginx -t && systemctl reload nginx && note "сайт включён"
        else
            note "сертификата нет — сайт пока не включаю (см. подсказку ниже)"
        fi
    fi
else
    note "нет /etc/nginx/sites-available — подключи $SRC/deploy/nginx.conf по-своему"
fi

say "Запуск"
if [[ $FRESH -eq 1 ]]; then
    note "пока не запускаю: нет токена бота"
else
    systemctl restart autoedit-api autoedit-worker autoedit-bot
    sleep 2
    for unit in api worker bot; do
        printf '    %-18s %s\n' "autoedit-$unit" \
            "$(systemctl is-active "autoedit-$unit")"
    done
fi

say "Готово"
cat <<MSG
Папка:      $APP_ROOT   (всё внутри: код, venv, данные, конфиг)
Конфиг:     $ENV_FILE
Вайтлист:   $WHITELIST
Порт API:   127.0.0.1:$API_PORT
MSG

if [[ $FRESH -eq 1 ]]; then
cat <<MSG

Осталось сделать:

 1. Токен бота в $ENV_FILE:
        BOT_TOKEN=...
        OWNER=твой_ник      # он сможет править вайтлист командами бота

 2. Себя в вайтлист:
        autoedit whitelist add твой_ник

 3. Сертификат, если его ещё нет:
        certbot certonly --nginx -d $DOMAIN -d www.$DOMAIN
        ln -sfn $SITE /etc/nginx/sites-enabled/autoedit
        nginx -t && systemctl reload nginx

 4. В @BotFather: /setmenubutton -> бот -> https://$DOMAIN/

 5. systemctl restart autoedit-api autoedit-worker autoedit-bot
MSG
fi

cat <<MSG

Полезное:
    autoedit whitelist list
    autoedit whitelist add @nickname
    autoedit whitelist remove @nickname
    autoedit measure --plan видео.mp4
    journalctl -u autoedit-worker -f
    curl -s localhost:$API_PORT/api/health
MSG
