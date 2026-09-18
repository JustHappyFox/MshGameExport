"""Проверка подписи Telegram Mini App и подпись ссылок на скачивание."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from . import config


class AuthError(RuntimeError):
    pass


def verify_init_data(init_data: str) -> dict:
    """Проверяет initData из Telegram.WebApp по алгоритму Telegram.

    Ключ = HMAC-SHA256("WebAppData", bot_token), затем сверяется хеш строки
    из отсортированных пар ключ=значение без самого hash.
    """
    if not config.BOT_TOKEN:
        raise AuthError("BOT_TOKEN не задан на сервере")
    if not init_data:
        raise AuthError("Нет initData — открой приложение через Telegram")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        raise AuthError("В initData нет hash")

    check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise AuthError("Подпись initData не сходится")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        auth_date = 0
    if config.INIT_DATA_MAX_AGE and (time.time() - auth_date) > config.INIT_DATA_MAX_AGE:
        raise AuthError("Сессия устарела, переоткрой приложение")

    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError as exc:
        raise AuthError("Не разобрать данные пользователя") from exc
    user_id = user.get("id")
    if not isinstance(user_id, int):
        raise AuthError("В initData нет пользователя")

    if config.ALLOWED_USER_IDS and user_id not in config.ALLOWED_USER_IDS:
        raise AuthError("Доступ закрыт")

    return {
        "user_id": user_id,
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "auth_date": auth_date,
    }


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sign_download(job_id: str, ttl_hours: int | None = None) -> str:
    exp = int(time.time()) + (ttl_hours or config.LINK_TTL_HOURS) * 3600
    payload = f"{job_id}.{exp}"
    sig = hmac.new(config.signing_key(), payload.encode(), hashlib.sha256).digest()[:16]
    return f"{_b64e(payload.encode())}.{_b64e(sig)}"


def verify_download(token: str) -> str:
    try:
        raw, sig_part = token.split(".", 1)
        payload = _b64d(raw).decode()
        job_id, exp_str = payload.rsplit(".", 1)
        exp = int(exp_str)
    except (ValueError, UnicodeDecodeError, base64.binascii.Error) as exc:
        raise AuthError("Битая ссылка") from exc

    expected = hmac.new(config.signing_key(), payload.encode(), hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(_b64e(expected), sig_part):
        raise AuthError("Подпись ссылки не сходится")
    if time.time() > exp:
        raise AuthError("Срок ссылки истёк")
    return job_id


def download_url(job_id: str) -> str:
    return f"{config.PUBLIC_BASE_URL}/d/{sign_download(job_id)}"
