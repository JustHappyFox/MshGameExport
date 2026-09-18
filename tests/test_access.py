"""Проверки вайтлиста: разбор файла, отказы, перечитывание на лету."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []


def check(cond: bool, label: str) -> None:
    print(f"  {'OK  ' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILURES.append(label)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="autoedit-wl-"))
    os.environ.update({
        "AUTOEDIT_ROOT": str(tmp),
        "AUTOEDIT_DATA_DIR": str(tmp / "data"),
        "AUTOEDIT_WHITELIST": str(tmp / "whitelist.txt"),
        "BOT_TOKEN": "123:TEST",
        "SECRET_KEY": "wl-secret",
        "OWNER": "bossnick",
    })

    from app import access

    wl_path = tmp / "whitelist.txt"

    print("\n[1] пустой список никого не пускает")
    access.ensure_file()
    access.load(force=True)
    check(not access.is_allowed(1, "someone"), "по нику не пускает")
    check(not access.is_allowed(1, None), "без ника не пускает")
    check("Вайтлист пуст" in access.denial_reason(1, "someone"), "объясняет, что список пуст")

    print("\n[2] разбор файла")
    wl_path.write_text(
        "# комментарий\n"
        "\n"
        "JustHappyFox\n"
        "@Another_User   # с собакой и хвостом-комментарием\n"
        "t.me/third_one\n"
        "id:555111\n"
        "  \n",
        encoding="utf-8",
    )
    time.sleep(0.01)
    wl = access.load(force=True)
    check(wl.usernames == frozenset({"justhappyfox", "another_user", "third_one"}),
          f"ники разобраны: {sorted(wl.usernames)}")
    check(wl.user_ids == frozenset({555111}), "id разобран")

    print("\n[3] кого пускает")
    check(access.is_allowed(42, "justhappyfox"), "ник из списка")
    check(access.is_allowed(42, "JUSTHAPPYFOX"), "регистр не важен")
    check(access.is_allowed(42, "@JustHappyFox"), "собака не мешает")
    check(access.is_allowed(555111, None), "по id без ника")
    check(not access.is_allowed(42, "stranger"), "чужого не пускает")
    check(not access.is_allowed(42, None), "без ника и без id не пускает")
    check("stranger" in access.denial_reason(42, "stranger"), "в отказе виден ник")
    check("id: 42" in access.denial_reason(42, None), "без ника отказ подсказывает id")

    print("\n[4] перечитывание без перезапуска")
    check(not access.is_allowed(42, "latecomer"), "пока не в списке")
    wl_path.write_text(wl_path.read_text(encoding="utf-8") + "latecomer\n", encoding="utf-8")
    os.utime(wl_path, (time.time() + 1, time.time() + 1))
    check(access.is_allowed(42, "latecomer"), "после правки файла пускает сам")

    print("\n[5] add и remove")
    check(access.add("@NewGuy") is True, "add добавил")
    check(access.add("newguy") is False, "повторный add не дублирует")
    check(access.is_allowed(42, "newguy"), "добавленный проходит")
    check(access.remove("NEWGUY") is True, "remove убрал")
    check(not access.is_allowed(42, "newguy"), "убранный больше не проходит")
    check(access.remove("never_existed") is False, "remove о несуществующем честен")
    check(access.add("id:777") is True and access.is_allowed(777, None), "add по id")
    check(access.remove("id:777") is True and not access.is_allowed(777, None), "remove по id")
    check("JustHappyFox" in wl_path.read_text(encoding="utf-8"),
          "правки не затирают исходные строки файла")
    check("# комментарий" in wl_path.read_text(encoding="utf-8"),
          "комментарии в файле сохраняются")

    print("\n[6] владелец")
    check(access.is_owner(1, "bossnick"), "владелец по нику")
    check(access.is_owner(1, "BossNick"), "регистр владельца не важен")
    check(not access.is_owner(1, "justhappyfox"), "обычный пользователь не владелец")

    print("\n[7] связка с подписью Mini App")
    import hashlib
    import hmac
    import json
    from urllib.parse import urlencode

    from app import security

    def init_data(user: dict) -> str:
        pairs = {"auth_date": str(int(time.time())), "user": json.dumps(user)}
        cs = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret = hmac.new(b"WebAppData", b"123:TEST", hashlib.sha256).digest()
        pairs["hash"] = hmac.new(secret, cs.encode(), hashlib.sha256).hexdigest()
        return urlencode(pairs)

    ok = security.verify_init_data(init_data({"id": 9, "username": "justhappyfox"}))
    check(ok["user_id"] == 9, "свой проходит проверку подписи")
    try:
        security.verify_init_data(init_data({"id": 9, "username": "stranger"}))
        check(False, "чужой не должен проходить")
    except security.AuthError as exc:
        check("stranger" in str(exc), f"чужой отбит: {exc}")

    print()
    if FAILURES:
        print(f"ПРОВАЛЕНО {len(FAILURES)}:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("Все проверки прошли.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
