#!/usr/bin/env bash
# Разведка сервера перед установкой autoedit. Только чтение, ничего не меняет.
h(){ printf '\n===== %s =====\n' "$1"; }
s(){ command -v "$1" >/dev/null 2>&1; }

h "СИСТЕМА"
. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME"
echo "ядро: $(uname -r)   аптайм: $(uptime -p 2>/dev/null)"
echo "CPU: $(nproc) ядер   RAM: $(free -h 2>/dev/null | awk '/Mem:/{print $2" всего, "$7" свободно"}')"
echo "root: $([ "$EUID" = 0 ] && echo да || echo "нет, пользователь $(whoami)")"

h "ДИСКИ"
df -hT -x tmpfs -x devtmpfs -x overlay 2>/dev/null | grep -vE '^Filesystem.*loop'

h "ЧТО УЖЕ СТОИТ"
for b in nginx apache2 caddy docker ffmpeg python3 certbot git node; do
  if s $b; then printf '  %-10s %s\n' "$b" "$($b --version 2>&1 | head -1 | cut -c1-60)"; else printf '  %-10s нет\n' "$b"; fi
done
s python3 && echo "  python venv: $(python3 -c 'import venv' 2>/dev/null && echo есть || echo 'НЕТ, нужен python3-venv')"

h "ЗАНЯТЫЕ ПОРТЫ (слушающие)"
if s ss; then ss -ltnp 2>/dev/null | awk 'NR>1{print $4"  "$6}' | sed 's/users:((//;s/))//' | sort -u
elif s netstat; then netstat -ltnp 2>/dev/null | awk 'NR>2{print $4"  "$7}' | sort -u
else
  echo "(ни ss, ни netstat — читаю /proc/net/tcp)"
  awk 'NR>1 && $4=="0A"{split($2,a,":"); print strtonum("0x"a[2])}' \
      /proc/net/tcp /proc/net/tcp6 2>/dev/null | sort -un | tr '\n' ' '
  echo
fi
echo "--- порты 8081-8129, куда встанет autoedit:"
for p in $(seq 8081 8129); do
  (exec 3<>/dev/tcp/127.0.0.1/$p) 2>/dev/null && { echo "  $p занят"; exec 3<&-; }
done
echo "  (что не перечислено — свободно)"

h "SYSTEMD-СЕРВИСЫ (не системные)"
systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null \
  | awk '{print $1}' \
  | grep -vE '^(systemd|dbus|cron|ssh|rsyslog|polkit|networkd|resolved|udev|getty|accounts|unattended|snapd|multipathd|irqbalance|user@|ModemManager|packagekit|thermald|chrony|ntp)' \
  | head -40

h "ГДЕ ЛЕЖАТ ЧУЖИЕ ПРОЕКТЫ"
for d in /opt /srv /var/www /home /root /apps /data; do
  [ -d "$d" ] || continue
  echo "--- $d"
  ls -la "$d" 2>/dev/null | awk 'NR>3{printf "    %-28s %s %s\n", $9, $3, $5}' | head -15
  echo "    (занято: $(du -sh "$d" 2>/dev/null | cut -f1))"
done

h "NGINX"
if s nginx; then
  echo "конфиг-тест: $(nginx -t 2>&1 | tail -1)"
  echo "пользователь: $(awk '$1=="user"{gsub(/;/,"",$2);print $2;exit}' /etc/nginx/nginx.conf 2>/dev/null)"
  echo "--- включённые сайты:"
  for f in /etc/nginx/sites-enabled/* /etc/nginx/conf.d/*.conf; do
    [ -e "$f" ] || continue
    names=$(grep -hoP 'server_name\s+\K[^;]+' "$f" 2>/dev/null | tr '\n' ' ')
    roots=$(grep -hoP '^\s*root\s+\K[^;]+' "$f" 2>/dev/null | sort -u | tr '\n' ' ')
    proxies=$(grep -hoP 'proxy_pass\s+\K[^;]+' "$f" 2>/dev/null | sort -u | tr '\n' ' ')
    printf '  %s\n    домены : %s\n    root   : %s\n    proxy  : %s\n' \
      "$(basename "$f")" "${names:-—}" "${roots:-—}" "${proxies:-—}"
  done
  echo "--- есть ли уже autoedit.ink:"
  grep -rl 'autoedit' /etc/nginx/ 2>/dev/null || echo "  упоминаний нет"
else echo "nginx не установлен"; fi

h "СЕРТИФИКАТЫ"
if [ -d /etc/letsencrypt/live ]; then ls /etc/letsencrypt/live 2>/dev/null | grep -v README
else echo "letsencrypt не настроен"; fi

h "DNS: КУДА СМОТРИТ ДОМЕН"
MYIP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || echo "не определить")
echo "внешний IP сервера: $MYIP"
for d in autoedit.ink www.autoedit.ink bot.autoedit.ink; do
  ip=$(getent ahostsv4 "$d" 2>/dev/null | awk 'NR==1{print $1}')
  echo "  $d -> ${ip:-нет A-записи}$([ -n "$ip" ] && [ "$ip" = "$MYIP" ] && echo '  (совпадает)')"
done

h "DOCKER"
s docker && docker ps --format '  {{.Names}}  {{.Image}}  {{.Ports}}' 2>/dev/null | head -20 || echo "docker не используется"

h "ИТОГ"
echo "готово — скопируй весь вывод целиком"
