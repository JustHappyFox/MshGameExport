"""Обработчик очереди: берёт задачу, гонит конвейер, пишет результат."""
from __future__ import annotations

import logging
import os
import signal
import time
from pathlib import Path

from . import config, db
from .video import render as render_mod

log = logging.getLogger("autoedit.worker")
_stop = False


def _handle_signal(signum, _frame) -> None:
    global _stop
    _stop = True
    log.info("получен сигнал %s, доработаю текущую задачу и выйду", signum)


def cleanup_expired() -> int:
    """Удаляет файлы и записи старше срока хранения."""
    removed = 0
    for job in db.expired_jobs(config.RETENTION_HOURS):
        for key in ("input_path", "output_path"):
            p = job.get(key)
            if p:
                try:
                    Path(p).unlink(missing_ok=True)
                except OSError as exc:
                    log.warning("не удалить %s: %s", p, exc)
        db.delete_job(job["id"])
        removed += 1
    return removed


def process_job(job: dict) -> None:
    job_id = job["id"]
    src = Path(job["input_path"])
    if not src.exists():
        db.fail_job(job_id, "Загруженный файл не найден на диске")
        return

    out_path = config.OUTPUT_DIR / f"{job_id}.mp4"
    started = time.time()

    def progress(pct: int, stage: str) -> None:
        db.set_progress(job_id, pct, stage)

    try:
        report = render_mod.process(src, out_path, progress=progress)
    except render_mod.RenderError as exc:
        log.error("задача %s: %s", job_id, exc)
        db.fail_job(job_id, str(exc))
        out_path.unlink(missing_ok=True)
        return
    except Exception as exc:  # noqa: BLE001 — иначе воркер молча умрёт
        log.exception("задача %s упала", job_id)
        db.fail_job(job_id, f"Непредвиденная ошибка: {type(exc).__name__}: {exc}")
        out_path.unlink(missing_ok=True)
        return

    report["timing"] = {"seconds": round(time.time() - started, 1)}
    db.finish_job(job_id, out_path, out_path.stat().st_size, report)
    cov = report["result"]["coverage_min"]
    log.info(
        "задача %s готова за %.1fs, покрытие %.2f%%, сквиз=%s",
        job_id, time.time() - started, cov * 100,
        report["plan"]["squeeze"]["applied"],
    )
    # входной файл больше не нужен
    src.unlink(missing_ok=True)


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    config.ensure_dirs()
    db.init()
    back = db.requeue_stale()
    if back:
        log.info("вернул в очередь зависших задач: %d", back)

    log.info("воркер запущен, данные в %s", config.DATA_DIR)
    last_cleanup = 0.0
    while not _stop:
        if time.time() - last_cleanup > 3600:
            n = cleanup_expired()
            if n:
                log.info("удалено просроченных задач: %d", n)
            last_cleanup = time.time()

        job = db.claim_next()
        if job is None:
            time.sleep(config.WORKER_POLL_SECONDS)
            continue
        log.info("взял задачу %s (%s, %.1f МБ)", job["id"], job["input_name"],
                 job["input_size"] / 1024 / 1024)
        process_job(job)

    log.info("воркер остановлен")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
