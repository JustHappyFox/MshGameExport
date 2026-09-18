#!/usr/bin/env bash
# Разворачивает autoedit на сервере. Запускать от root из корня репозитория.
#   sudo bash deploy/install.sh
# Повторный запуск безопасен — это же и обновление.
set -euo pipefail

APP_DIR=/opt/autoedit
DATA_DIR=/var/lib/autoedit
ENV_DIR=/etc/autoedit
ENV_FILE=$ENV_DIR/autoedit.env
USER_NAME=autoedit
DOMAIN=autoedit.ink

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
die() { printf '\033[31mОшибка: %s\033[0m\n' "$1" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "нужен root"
SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
[[ -f "$SRC/app/api.py" ]] || die "запускай из корня репозитория"

say "Пакеты"
if command -v apt-get >/dev/null; then
    apt-get update -qq
    apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip ffmpeg nginx ca-certificates
else
    command -v ffmpeg >/dev/null || die "поставь ffmpeg вручную"
    command -v python3 >/dev/null || die "поставь python3 вручную"
fi
ffmpeg -version | head -1

say "Пользователь и каталоги"
id -u "$USER_NAME" >/dev/null 2>&1 || \
    useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$USER_NAME"
mkdir -p "$APP_DIR" "$DATA_DIR"/{uploads,outputs,cache,tmp} "$ENV_DIR"

say "Код в $APP_DIR"
for item in app web assets tools requirements.txt; do
    [[ -e "$SRC/$item" ]] || die "в репозитории нет $item"
    rm -rf "$APP_DIR/$item"
    cp -r "$SRC/$item" "$APP_DIR/$item"
done
[[ -f "$APP_DIR/assets/banner.mp4" ]] || die "нет assets/banner.mp4 — положи файл вставки"

say "venv и зависимости"
[[ -d $APP_DIR/venv ]] || python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

say "Конфиг"
if [[ ! -f $ENV_FILE ]]; then
    cp "$SRC/.env.example" "$ENV_FILE"
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -hex 32)|" "$ENV_FILE"
    sed -i "s|^AUTOEDIT_BANNER=.*|AUTOEDIT_BANNER=$APP_DIR/assets/banner.mp4|" "$ENV_FILE"
    NEW_ENV=1
else
    echo "$ENV_FILE уже есть, не трогаю"
    NEW_ENV=0
fi
chmod 640 "$ENV_FILE"
chown root:"$USER_NAME" "$ENV_FILE"
chown -R "$USER_NAME":"$USER_NAME" "$APP_DIR" "$DATA_DIR"

say "Прогрев кеша замеров"
# Считаем след баннера для частых ширин заранее, чтобы первая задача не ждала.
for w in 720 1080 1920; do
    sudo -u "$USER_NAME" env \
        AUTOEDIT_DATA_DIR="$DATA_DIR" \
        AUTOEDIT_BANNER="$APP_DIR/assets/banner.mp4" \
        "$APP_DIR/venv/bin/python" "$APP_DIR/tools/measure.py" --geometry "${w}x$((w * 16 / 9))" \
        | sed 's/^/    /'
done

say "systemd"
cp "$SRC/deploy/autoedit-api.service" "$SRC/deploy/autoedit-worker.service" \
   "$SRC/deploy/autoedit-bot.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable autoedit-api autoedit-worker autoedit-bot >/dev/null

say "nginx"
if [[ ! -f /etc/nginx/sites-available/$DOMAIN ]]; then
    cp "$SRC/deploy/nginx.conf" /etc/nginx/sites-available/$DOMAIN
    ln -sfn /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
    echo "конфиг положен в /etc/nginx/sites-available/$DOMAIN"
else
    echo "конфиг nginx уже есть, не трогаю"
fi

if [[ ! -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]]; then
    cat <<MSG

Сертификата для $DOMAIN пока нет, поэтому nginx с этим конфигом не поднимется.
Получи его и вернись к этому шагу:

    apt-get install -y certbot python3-certbot-nginx
    certbot certonly --nginx -d $DOMAIN -d www.$DOMAIN
    nginx -t && systemctl reload nginx
MSG
else
    nginx -t && systemctl reload nginx
fi

if [[ $NEW_ENV -eq 1 ]]; then
    cat <<MSG

Осталось одно: вписать токен бота в $ENV_FILE

    BOT_TOKEN=...      # @BotFather -> /newbot
    PUBLIC_BASE_URL=https://$DOMAIN

Потом в @BotFather: /setmenubutton -> выбрать бота -> URL https://$DOMAIN/
И запустить:

    systemctl restart autoedit-api autoedit-worker autoedit-bot
MSG
else
    say "Перезапуск"
    systemctl restart autoedit-api autoedit-worker autoedit-bot
    sleep 2
    systemctl --no-pager --lines=0 status autoedit-api autoedit-worker autoedit-bot || true
fi

say "Готово"
cat <<MSG
Проверить:
    curl -s localhost:8081/api/health
    journalctl -u autoedit-worker -f
    journalctl -u autoedit-api -f
Замер вручную:
    sudo -u $USER_NAME $APP_DIR/venv/bin/python $APP_DIR/tools/measure.py --plan видео.mp4
MSG
