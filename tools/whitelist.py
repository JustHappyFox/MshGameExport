#!/usr/bin/env python3
"""Управление вайтлистом из консоли сервера.

    python3 tools/whitelist.py list
    python3 tools/whitelist.py add @nickname другой_ник
    python3 tools/whitelist.py add id:123456789
    python3 tools/whitelist.py remove @nickname
    python3 tools/whitelist.py check @nickname

Файл можно править и руками — приложение перечитывает его само.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import access, config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="показать список")
    p_add = sub.add_parser("add", help="добавить ники или id:...")
    p_add.add_argument("entries", nargs="+")
    p_rm = sub.add_parser("remove", help="убрать ники или id:...")
    p_rm.add_argument("entries", nargs="+")
    p_ck = sub.add_parser("check", help="проверить, пустит ли")
    p_ck.add_argument("entry")
    args = ap.parse_args()

    path = access.ensure_file()

    if args.cmd == "list":
        wl = access.load(force=True)
        print(f"файл: {path}")
        if wl.is_empty:
            print("пусто — доступа нет ни у кого")
            return 0
        for n in sorted(wl.usernames):
            print(f"  @{n}")
        for i in sorted(wl.user_ids):
            print(f"  id:{i}")
        print(f"всего: {len(wl.usernames) + len(wl.user_ids)}")
        return 0

    if args.cmd == "check":
        entry = args.entry
        if entry.lower().startswith("id:"):
            ok = access.is_allowed(int(entry[3:]), None)
        else:
            ok = access.is_allowed(None, entry)
        print("пустит" if ok else "не пустит")
        return 0 if ok else 1

    changed = 0
    for entry in args.entries:
        try:
            ok = access.add(entry) if args.cmd == "add" else access.remove(entry)
        except ValueError as exc:
            print(f"  {entry}: {exc}", file=sys.stderr)
            return 2
        if ok:
            changed += 1
            print(f"  {entry}: {'добавлен' if args.cmd == 'add' else 'убран'}")
        else:
            print(f"  {entry}: {'уже был' if args.cmd == 'add' else 'не было в списке'}")
    print(f"изменений: {changed} (файл {path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
