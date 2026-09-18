"""Сквозной тест: подпись Mini App, загрузка, очередь, рендер, ссылка.

Запуск:  python3 tests/test_e2e.py путь/к/видео.mp4
Без аргумента генерирует тестовый ролик 9:16 сам.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TOKEN = "123456:TEST_TOKEN_FOR_LOCAL_E2E"
USER = {"id": 777000, "first_name": "Test", "username": "tester"}

FAILURES: list[str] = []


def check(cond: bool, label: str) -> bool:
    print(f"  {'OK  ' if cond else 'FAIL'}  {label}")
    if not cond:
        FAILURES.append(label)
    return cond


def make_init_data(token: str = TOKEN, user: dict | None = None) -> str:
    pairs = {"auth_date": str(int(time.time())), "user": json.dumps(user or USER),
             "query_id": "AAEtest"}
    check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def sample_video(dst: Path) -> Path:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=720x1280:r=30:d=6",
         "-f", "lavfi", "-i", "sine=f=440:r=48000:d=6", "-c:v", "libx264", "-crf", "26",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(dst), "-y"],
        check=True, capture_output=True,
    )
    return dst


def main() -> int:
    data_dir = Path(tempfile.mkdtemp(prefix="autoedit-e2e-"))
    os.environ.update({
        "AUTOEDIT_DATA_DIR": str(data_dir),
        "BOT_TOKEN": TOKEN,
        "SECRET_KEY": "e2e-secret",
        "PUBLIC_BASE_URL": "https://autoedit.ink",
        "USE_X_ACCEL": "0",
        "AUTOEDIT_BANNER": str(ROOT / "assets" / "banner.mp4"),
    })

    from fastapi.testclient import TestClient

    from app import config, db, security
    from app.api import app
    from app.worker import process_job

    config.ensure_dirs()
    db.init()
    client = TestClient(app)
    hdr = {"X-Telegram-Init-Data": make_init_data()}

    print("\n[1] подпись initData")
    check(client.get("/api/config").status_code == 401, "без initData — 401")
    bad = make_init_data("999:WRONG")
    check(client.get("/api/config", headers={"X-Telegram-Init-Data": bad}).status_code == 401,
          "чужая подпись — 401")
    r = client.get("/api/config", headers=hdr)
    check(r.status_code == 200 and r.json()["user"]["id"] == USER["id"],
          "верная подпись — 200 и наш пользователь")

    print("\n[2] отказы на входе")
    r = client.post("/api/jobs", headers=hdr,
                    files={"file": ("x.txt", b"nope", "text/plain")})
    check(r.status_code == 415, "неподдерживаемый формат — 415")
    r = client.post("/api/jobs", headers=hdr,
                    files={"file": ("x.mp4", b"", "video/mp4")})
    check(r.status_code == 400, "пустой файл — 400")

    print("\n[3] загрузка")
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else sample_video(data_dir / "src.mp4")
    with src.open("rb") as fh:
        r = client.post("/api/jobs", headers=hdr,
                        files={"file": (src.name, fh, "video/mp4")})
    ok = check(r.status_code == 201, f"загрузка принята ({r.status_code})")
    if not ok:
        print(r.text[:400])
        return 1
    job_id = r.json()["id"]

    r = client.get(f"/api/jobs/{job_id}", headers=hdr)
    check(r.status_code == 200 and r.json()["status"] == "queued", "задача в очереди")

    print("\n[4] чужой доступ к задаче")
    alien_hdr = {"X-Telegram-Init-Data": make_init_data(user=dict(USER, id=111222))}
    check(client.get(f"/api/jobs/{job_id}", headers=alien_hdr).status_code == 404,
          "другой пользователь задачу не видит")

    print("\n[5] обработка")
    job = db.claim_next()
    check(job is not None and job["id"] == job_id, "воркер забрал задачу")
    t0 = time.time()
    process_job(job)
    print(f"        рендер занял {time.time() - t0:.1f}s")

    r = client.get(f"/api/jobs/{job_id}", headers=hdr)
    body = r.json()
    ok = check(body["status"] == "done", f"задача готова (статус {body['status']})")
    if not ok:
        print("        ошибка:", body.get("error"))
        return 1

    s = body["summary"]
    cov = s["coverage"]
    print(f"        покрытие: до {cov['before'] * 100:.2f}% -> "
          f"после {cov['after'] * 100:.2f}% (проверено {s['verified_coverage'] * 100:.2f}%)")
    print(f"        сквиз: {s['squeeze']}")
    check(s["verified_coverage"] >= config.MIN_COVERAGE, "порог 25% выдержан")
    check(bool(body["download_url"]), "ссылка выдана")

    print("\n[6] ссылка на скачивание")
    token = body["download_url"].rsplit("/", 1)[-1]
    r = client.get(f"/d/{token}")
    check(r.status_code == 200 and r.headers["content-type"] == "video/mp4",
          f"файл отдаётся ({r.status_code})")
    check(len(r.content) == body["output_size"], "размер совпадает с отчётом")
    check(client.get("/d/подделка.подпись").status_code == 403, "битый токен — 403")
    expired = security.sign_download(job_id, ttl_hours=-1)
    check(client.get(f"/d/{expired}").status_code == 403, "просроченный токен — 403")

    print("\n[7] история")
    r = client.get("/api/jobs", headers=hdr)
    check(r.status_code == 200 and any(j["id"] == job_id for j in r.json()["jobs"]),
          "задача видна в истории")

    print("\n[8] уборка по сроку хранения")
    from app import worker
    with db.db() as conn:
        conn.execute("UPDATE jobs SET created_at=? WHERE id=?",
                     (time.time() - (config.RETENTION_HOURS + 1) * 3600, job_id))
    check(worker.cleanup_expired() == 1, "просроченная задача удалена")
    check(db.get_job(job_id) is None, "запись пропала из базы")

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
