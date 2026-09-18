"""Телеграм-бот: кнопка Mini App плюс приём видео прямо в чат."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo,
)

from . import config, db, security

log = logging.getLogger("autoedit.bot")

# Через Bot API файл больше 20 МБ не скачать — это ограничение Telegram,
# а не нашего сервера. В Mini App загрузка идёт напрямую браузером и лимита нет.
BOT_API_DOWNLOAD_LIMIT = 20 * 1024 * 1024


def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Открыть autoedit",
                             web_app=WebAppInfo(url=config.PUBLIC_BASE_URL + "/"))
    ]])


async def cmd_start(message: Message) -> None:
    await message.answer(
        "Вставляю рекламную интеграцию ровно в центр видео.\n\n"
        "Кадр замирает, поверх него играет вставка, потом видео продолжается. "
        f"Перед сборкой замеряю, сколько кадра занимает раскрытая панель: если меньше "
        f"{config.MIN_COVERAGE * 100:.0f}%, слегка сжимаю кадр по вертикали, "
        "чтобы порог взялся. Если и так проходит — не трогаю.\n\n"
        "Открывай приложение и загружай видео — там нет лимита на размер. "
        "Можно и просто прислать видео в чат, но тогда Telegram отдаст мне "
        f"файл не больше {BOT_API_DOWNLOAD_LIMIT // 1024 // 1024} МБ.",
        reply_markup=keyboard(),
    )


async def cmd_status(message: Message) -> None:
    jobs = db.list_jobs(message.from_user.id, limit=5)
    if not jobs:
        await message.answer("Задач пока не было.", reply_markup=keyboard())
        return
    lines = []
    for j in jobs:
        if j["status"] == "done":
            cov = (((j.get("report") or {}).get("plan") or {}).get("coverage") or {})
            lines.append(
                f"✅ {j['input_name']} — готово, панель "
                f"{float(cov.get('after', 0)) * 100:.2f}%\n{security.download_url(j['id'])}"
            )
        elif j["status"] == "error":
            lines.append(f"❌ {j['input_name']} — {j['error']}")
        else:
            lines.append(f"⏳ {j['input_name']} — {j['stage']} {j['progress']}%")
    await message.answer("\n\n".join(lines), reply_markup=keyboard())


async def on_video(message: Message, bot: Bot) -> None:
    obj = message.video or message.document
    if obj is None:
        return
    if config.ALLOWED_USER_IDS and message.from_user.id not in config.ALLOWED_USER_IDS:
        await message.answer("Доступ закрыт.")
        return

    size = obj.file_size or 0
    if size > BOT_API_DOWNLOAD_LIMIT:
        await message.answer(
            f"Через чат Telegram отдаёт мне файлы только до "
            f"{BOT_API_DOWNLOAD_LIMIT // 1024 // 1024} МБ, а тут "
            f"{size / 1024 / 1024:.0f} МБ. Загрузи через приложение — там лимита нет.",
            reply_markup=keyboard(),
        )
        return

    name = obj.file_name or "video.mp4"
    suffix = Path(name).suffix.lower() or ".mp4"
    config.ensure_dirs()
    dest = config.UPLOAD_DIR / f"in-{os.urandom(12).hex()}{suffix}"

    note = await message.answer("Скачиваю…")
    try:
        tg_file = await bot.get_file(obj.file_id)
        await bot.download_file(tg_file.file_path, destination=dest)
    except Exception as exc:  # noqa: BLE001
        log.exception("не скачать файл")
        await note.edit_text(f"Не смог скачать файл: {exc}")
        return

    job_id = db.create_job(message.from_user.id, message.from_user.username,
                           dest, name, dest.stat().st_size)
    await note.edit_text(
        "Взял в работу. Прогресс видно в приложении, готовый файл пришлю сюда.",
        reply_markup=keyboard(),
    )
    asyncio.create_task(watch_job(bot, message.chat.id, job_id))


async def watch_job(bot: Bot, chat_id: int, job_id: str) -> None:
    """Дожидается задачу и присылает результат в чат."""
    while True:
        await asyncio.sleep(3)
        job = db.get_job(job_id)
        if job is None:
            return
        if job["status"] == "error":
            await bot.send_message(chat_id, f"Не получилось: {job['error']}")
            return
        if job["status"] != "done":
            continue

        plan = (job.get("report") or {}).get("plan") or {}
        cov, sq, out = (plan.get("coverage") or {}), (plan.get("squeeze") or {}), (plan.get("output") or {})
        text = [
            f"Готово: {out.get('width')}x{out.get('height')}, {out.get('duration')} с",
            f"Панель занимает {float(cov.get('after', 0)) * 100:.2f}% кадра "
            f"(порог {config.MIN_COVERAGE * 100:.0f}%)",
            ("Сжатие по вертикали: "
             f"{sq.get('px')} px ({float(sq.get('ratio', 0)) * 100:.1f}%)")
            if sq.get("applied") else "Сжатие не потребовалось — порог взялся и так",
            "",
            security.download_url(job_id),
        ]
        for w in plan.get("warnings") or []:
            text.insert(3, f"⚠️ {w}")
        await bot.send_message(chat_id, "\n".join(text), disable_web_page_preview=True)

        out_path = Path(job["output_path"])
        if out_path.exists() and out_path.stat().st_size <= config.TG_SEND_LIMIT_BYTES:
            try:
                from aiogram.types import FSInputFile
                await bot.send_video(chat_id, FSInputFile(out_path),
                                     supports_streaming=True)
            except Exception as exc:  # noqa: BLE001
                log.warning("не отправить видео в чат: %s", exc)
        return


async def run() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан")
    config.ensure_dirs()
    db.init()

    bot = Bot(config.BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.message.register(cmd_start, Command("start", "help"))
    dp.message.register(cmd_status, Command("status"))
    dp.message.register(on_video, F.video | F.document.mime_type.startswith("video/"))

    log.info("бот запущен, Mini App: %s", config.PUBLIC_BASE_URL)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


def main() -> int:
    asyncio.run(run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
