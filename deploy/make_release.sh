#!/usr/bin/env bash
# Собирает архив для переноса на сервер.
#   bash deploy/make_release.sh            -> autoedit-ГГГГММДД-ЧЧММ.tar.gz
#   bash deploy/make_release.sh /куда/положить
set -euo pipefail

SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT_DIR=${1:-$SRC/dist}
STAMP=$(date +%Y%m%d-%H%M)
NAME=autoedit-$STAMP
ARCHIVE=$OUT_DIR/$NAME.tar.gz

cd "$SRC"
[[ -f assets/banner.mp4 ]] || { echo "Нет assets/banner.mp4 — без вставки смысла нет"; exit 1; }

mkdir -p "$OUT_DIR"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
DEST=$STAGE/$NAME
mkdir -p "$DEST"

# Кладём только то, что нужно для работы. Ни данных, ни venv, ни .git.
for item in app web assets tools deploy requirements.txt .env.example README.md; do
    [[ -e $item ]] || { echo "Нет $item"; exit 1; }
    cp -r "$item" "$DEST/"
done

find "$DEST" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$DEST" -name '*.py[co]' -delete 2>/dev/null || true

echo "$STAMP" > "$DEST/VERSION"
tar -czf "$ARCHIVE" -C "$STAGE" "$NAME"

echo
echo "Архив: $ARCHIVE  ($(du -h "$ARCHIVE" | cut -f1))"
echo "$(cd "$OUT_DIR" && sha256sum "$NAME.tar.gz")"
cat <<MSG

Дальше на сервере:

    scp $ARCHIVE root@СЕРВЕР:/tmp/
    ssh root@СЕРВЕР
    tar xzf /tmp/$NAME.tar.gz -C /tmp
    bash /tmp/$NAME/deploy/install.sh

Повторная установка тем же способом обновляет код и не трогает
whitelist.txt, autoedit.env и уже обработанные файлы.
MSG
