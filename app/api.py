"""HTTP-слой: приём видео из Mini App, статус задачи, выдача файла."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, db, security

log = logging.getLogger("autoedit.api")

USE_X_ACCEL = os.getenv("USE_X_ACCEL", "1").strip().lower() in ("1", "true", "yes", "on")
X_ACCEL_PREFIX = os.getenv("X_ACCEL_PREFIX", "/_files")

ALLOWED_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".3gp", ".mpeg", ".mpg"}
SAFE_NAME = re.compile(r"[^A-Za-z0-9._\-]+")

app = FastAPI(title="autoedit.ink", docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
def _startup() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    config.ensure_dirs()
    db.init()
    log.info("api запущен, данные в %s", config.DATA_DIR)


def current_user(x_telegram_init_data: str = Header(default="")) -> dict:
    try:
        return security.verify_init_data(x_telegram_init_data)
    except security.AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _job_view(job: dict, user_id: int) -> dict:
    if job["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    view = {
        "id": job["id"],
        "status": job["status"],
        "stage": job["stage"],
        "progress": job["progress"],
        "input_name": job["input_name"],
        "input_size": job["input_size"],
        "created_at": job["created_at"],
        "error": job["error"],
    }
    if job["status"] == "queued":
        view["queue_position"] = db.queue_position(job["id"])
    if job["status"] == "done":
        report = job.get("report") or {}
        plan = report.get("plan") or {}
        result = report.get("result") or {}
        view.update({
            "download_url": security.download_url(job["id"]),
            "output_size": job["output_size"],
            "can_send_to_chat": job["output_size"] <= config.TG_SEND_LIMIT_BYTES,
            "summary": {
                "output": plan.get("output"),
                "squeeze": plan.get("squeeze"),
                "coverage": plan.get("coverage"),
                "bars_removed": plan.get("bars_removed"),
                "insert": plan.get("insert"),
                "verified_coverage": result.get("coverage_min"),
                "warnings": plan.get("warnings") or [],
                "seconds": (report.get("timing") or {}).get("seconds"),
            },
        })
    return view


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/config")
def client_config(user: dict = Depends(current_user)) -> dict:
    return {
        "user": {"id": user["user_id"], "username": user["username"],
                 "first_name": user["first_name"]},
        "max_upload_bytes": config.MAX_UPLOAD_BYTES,
        "max_duration_seconds": config.MAX_INPUT_DURATION,
        "min_coverage": config.MIN_COVERAGE,
        "link_ttl_hours": config.LINK_TTL_HOURS,
        "retention_hours": config.RETENTION_HOURS,
        "allowed_suffixes": sorted(ALLOWED_SUFFIXES),
    }


@app.post("/api/jobs")
async def create_job(file: UploadFile,
                     user: dict = Depends(current_user)) -> JSONResponse:
    name = SAFE_NAME.sub("_", Path(file.filename or "video.mp4").name)[:120] or "video.mp4"
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"Формат {suffix or '?'} не поддерживается. "
                   f"Можно: {', '.join(sorted(ALLOWED_SUFFIXES))}",
        )

    config.ensure_dirs()
    # Имя финальное сразу: воркер может забрать задачу в ту же миллисекунду,
    # в которую она появилась в базе, поэтому переименований после вставки нет.
    tmp = config.UPLOAD_DIR / f"in-{os.urandom(12).hex()}{suffix}"
    written = 0
    try:
        with tmp.open("wb") as fh:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Файл больше "
                               f"{config.MAX_UPLOAD_BYTES // 1024 // 1024} МБ",
                    )
                fh.write(chunk)
    except HTTPException:
        tmp.unlink(missing_ok=True)
        raise
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        log.exception("загрузка не удалась")
        raise HTTPException(status_code=500, detail="Не удалось сохранить файл") from exc
    finally:
        await file.close()

    if written == 0:
        tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Пустой файл")

    job_id = db.create_job(user["user_id"], user["username"], tmp, name, written)
    log.info("задача %s создана (%s, %.1f МБ) пользователем %s",
             job_id, name, written / 1024 / 1024, user["user_id"])
    return JSONResponse({"id": job_id, "status": "queued"}, status_code=201)


@app.get("/api/jobs")
def list_jobs(user: dict = Depends(current_user)) -> dict:
    jobs = db.list_jobs(user["user_id"], limit=20)
    return {"jobs": [_job_view(j, user["user_id"]) for j in jobs]}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, user: dict = Depends(current_user)) -> dict:
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return _job_view(job, user["user_id"])


@app.post("/api/jobs/{job_id}/send")
async def send_to_chat(job_id: str, user: dict = Depends(current_user)) -> dict:
    job = db.get_job(job_id)
    if job is None or job["user_id"] != user["user_id"]:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if job["status"] != "done" or not job["output_path"]:
        raise HTTPException(status_code=409, detail="Файл ещё не готов")
    out = Path(job["output_path"])
    if not out.exists():
        raise HTTPException(status_code=410, detail="Файл уже удалён с сервера")
    if out.stat().st_size > config.TG_SEND_LIMIT_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Файл больше лимита Telegram — качай по ссылке",
        )
    if not config.BOT_TOKEN:
        raise HTTPException(status_code=503, detail="Бот не настроен")

    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/sendVideo"
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            with out.open("rb") as fh:
                resp = await client.post(
                    url,
                    data={"chat_id": str(user["user_id"]),
                          "caption": _caption(job), "supports_streaming": "true"},
                    files={"video": (f"autoedit-{job_id[:8]}.mp4", fh, "video/mp4")},
                )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Telegram недоступен: {exc}") from exc
    if resp.status_code != 200:
        log.error("sendVideo %s: %s", resp.status_code, resp.text[:300])
        raise HTTPException(status_code=502, detail="Telegram не принял файл")
    return {"ok": True}


def _caption(job: dict) -> str:
    report = job.get("report") or {}
    plan = report.get("plan") or {}
    out = plan.get("output") or {}
    cov = plan.get("coverage") or {}
    sq = plan.get("squeeze") or {}
    lines = [
        f"{out.get('width')}x{out.get('height')}, {out.get('duration')} с",
        f"панель занимает {float(cov.get('after', 0)) * 100:.2f}% кадра",
    ]
    lines.append(
        f"сжатие {sq.get('px')} px" if sq.get("applied") else "сжатие не потребовалось"
    )
    return "\n".join(lines)


@app.get("/d/{token}")
def download(token: str) -> Response:
    try:
        job_id = security.verify_download(token)
    except security.AuthError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    job = db.get_job(job_id)
    if job is None or job["status"] != "done" or not job["output_path"]:
        raise HTTPException(status_code=404, detail="Файл не найден")
    out = Path(job["output_path"])
    if not out.exists():
        raise HTTPException(status_code=410, detail="Файл удалён по сроку хранения")

    filename = f"autoedit-{job_id[:8]}.mp4"
    if USE_X_ACCEL:
        return Response(
            status_code=200,
            headers={
                "X-Accel-Redirect": f"{X_ACCEL_PREFIX}/{out.name}",
                "Content-Type": "video/mp4",
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    return FileResponse(out, media_type="video/mp4", filename=filename)


# Локальная отдача Mini App — в продакшене статику раздаёт nginx.
if config.WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(config.WEB_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse((config.WEB_DIR / "index.html").read_text(encoding="utf-8"))
