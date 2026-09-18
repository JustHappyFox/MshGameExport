"""Вайтлист: кто вообще имеет право пользоваться ботом.

Список лежит в обычном текстовом файле рядом с приложением, по строке на
запись. Файл перечитывается сам, как только меняется — перезапускать сервисы
после правки не нужно.

    # комментарии и пустые строки игнорируются
    justhappyfox        # ник, собака необязательна, регистр не важен
    @another_user
    id:123456789        # если у человека нет ника

Пустой список никого не пускает. Это осознанно: забытый пустой файл не должен
открывать доступ всему интернету.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass(frozen=True)
class Whitelist:
    usernames: frozenset[str]
    user_ids: frozenset[int]

    @property
    def is_empty(self) -> bool:
        return not self.usernames and not self.user_ids

    def allows(self, user_id: int | None, username: str | None) -> bool:
        if user_id is not None and user_id in self.user_ids:
            return True
        return bool(username) and normalize(username) in self.usernames


_lock = threading.Lock()
_cache: tuple[float, int, Whitelist] | None = None  # (mtime, size, список)


def normalize(nick: str) -> str:
    """@JustHappyFox, t.me/justhappyfox и JUSTHAPPYFOX — это одно и то же."""
    nick = nick.strip().lower()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "@"):
        if nick.startswith(prefix):
            nick = nick[len(prefix):]
    return nick.strip()


def parse(text: str) -> Whitelist:
    usernames: set[str] = set()
    user_ids: set[int] = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.lower().startswith("id:"):
            try:
                user_ids.add(int(line[3:].strip()))
            except ValueError:
                continue
            continue
        nick = normalize(line)
        if nick:
            usernames.add(nick)
    return Whitelist(frozenset(usernames), frozenset(user_ids))


def load(force: bool = False) -> Whitelist:
    """Читает файл, если он изменился с прошлого раза."""
    global _cache
    path = config.WHITELIST_PATH
    try:
        st = path.stat()
        stamp = (st.st_mtime, st.st_size)
    except OSError:
        stamp = (0.0, -1)

    with _lock:
        if not force and _cache is not None and _cache[:2] == stamp:
            return _cache[2]
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        # из окружения — дополнение к файлу, удобно для одноразовых правок
        text += "\n" + "\n".join(config.EXTRA_ALLOWED)
        wl = parse(text)
        _cache = (stamp[0], stamp[1], wl)
        return wl


def is_allowed(user_id: int | None, username: str | None) -> bool:
    return load().allows(user_id, username)


def denial_reason(user_id: int | None, username: str | None) -> str:
    """Текст отказа — такой, чтобы человек понял, что делать дальше."""
    wl = load()
    if wl.is_empty:
        return ("Вайтлист пуст, доступа нет ни у кого. "
                "Владельцу: добавь ник в whitelist.txt")
    if not username:
        return (f"У тебя не задан ник в Telegram, пускать некого. "
                f"Поставь ник в настройках или попроси добавить тебя по id: {user_id}")
    return f"Доступ закрыт. Попроси владельца добавить @{username} в вайтлист"


def is_owner(user_id: int | None, username: str | None) -> bool:
    """Владелец правит вайтлист командами бота. Задаётся OWNER в окружении."""
    owner = config.OWNER
    if not owner:
        return False
    if owner.lower().startswith("id:"):
        try:
            return user_id == int(owner[3:].strip())
        except ValueError:
            return False
    return bool(username) and normalize(username) == normalize(owner)


def ensure_file() -> Path:
    """Создаёт файл-заготовку, если его ещё нет."""
    path = config.WHITELIST_PATH
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Кому можно пользоваться ботом. По одной записи в строке.\n"
        "# Ник Telegram: собака необязательна, регистр не важен.\n"
        "# Если ника нет — можно по id, строкой вида id:123456789\n"
        "# Файл перечитывается сам, перезапускать сервисы не нужно.\n"
        "#\n"
        "# Пустой список = доступа нет ни у кого.\n",
        encoding="utf-8",
    )
    return path


def add(entry: str) -> bool:
    """Дописывает запись. Возвращает False, если она уже была."""
    ensure_file()
    path = config.WHITELIST_PATH
    wl = load(force=True)
    if entry.lower().startswith("id:"):
        try:
            if int(entry[3:].strip()) in wl.user_ids:
                return False
        except ValueError as exc:
            raise ValueError(f"Не похоже на id: {entry}") from exc
        line = f"id:{entry[3:].strip()}"
    else:
        nick = normalize(entry)
        if not nick:
            raise ValueError("Пустая запись")
        if nick in wl.usernames:
            return False
        line = nick

    text = path.read_text(encoding="utf-8")
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + line + "\n", encoding="utf-8")
    load(force=True)
    return True


def remove(entry: str) -> bool:
    """Убирает запись. Возвращает False, если её и не было."""
    path = config.WHITELIST_PATH
    if not path.exists():
        return False
    target_id = None
    target_nick = None
    if entry.lower().startswith("id:"):
        try:
            target_id = int(entry[3:].strip())
        except ValueError as exc:
            raise ValueError(f"Не похоже на id: {entry}") from exc
    else:
        target_nick = normalize(entry)

    kept, dropped = [], False
    for raw in path.read_text(encoding="utf-8").splitlines():
        body = raw.split("#", 1)[0].strip()
        if body:
            if target_id is not None and body.lower().startswith("id:"):
                try:
                    if int(body[3:].strip()) == target_id:
                        dropped = True
                        continue
                except ValueError:
                    pass
            elif target_nick is not None and normalize(body) == target_nick:
                dropped = True
                continue
        kept.append(raw)

    if dropped:
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        load(force=True)
    return dropped
