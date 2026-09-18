"""Анализ рекламной вставки: сколько кадра реально закрывает раскрытая панель.

Замер идёт по альфа-маске после хромакея, а не по габаритам файла: зелёный
фон в площадь не входит, скругления углов тоже вычитаются. Результат
кешируется по (файл, параметры кея, целевая ширина).
"""
from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

from .. import config


class BannerError(RuntimeError):
    pass


@dataclass(frozen=True)
class FrameStat:
    index: int
    time: float
    solid: int
    bbox_h: int


@dataclass(frozen=True)
class BannerMeasure:
    """Замер баннера, отмасштабированного под ширину кадра `width`."""
    width: int
    height: int
    fps: float
    duration: float
    frames: int
    # раскрытая панель = кадры, где высота следа не меньше самой частой (полка)
    open_from: float
    open_to: float
    open_frames: int
    solid_min: int      # худший кадр раскрытой фазы — по нему и судим
    solid_mean: float
    solid_max: int
    shelf_height: int

    def coverage(self, frame_height: int) -> float:
        return self.solid_min / (self.width * frame_height)

    def coverage_mean(self, frame_height: int) -> float:
        return self.solid_mean / (self.width * frame_height)

    def max_frame_height(self, target: float) -> int:
        """Самая большая высота кадра, при которой порог ещё держится."""
        h = int(self.solid_min // (self.width * target))
        return h - (h % 2)


def scaled_height(native_w: int, native_h: int, width: int) -> int:
    """Так же, как это делает ffmpeg через scale=W:-2."""
    return int(round(native_h * width / native_w / 2)) * 2


def _cache_key(banner: Path, width: int) -> str:
    st = banner.stat()
    raw = "|".join([
        str(banner.resolve()), str(st.st_size), str(int(st.st_mtime)), str(width),
        config.CHROMAKEY_COLOR, f"{config.CHROMAKEY_SIMILARITY:.4f}",
        f"{config.CHROMAKEY_BLEND:.4f}", str(config.ALPHA_THRESHOLD), "v2",
    ])
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def keyed_filter(width: int, fps: int | None = None) -> str:
    """Цепочка фильтров вставки: кей → добивка перелива → масштаб под ширину кадра."""
    parts = []
    if fps:
        parts.append(f"fps={fps}")
    parts += [
        "format=yuva420p",
        f"chromakey={config.CHROMAKEY_COLOR}:{config.CHROMAKEY_SIMILARITY}:{config.CHROMAKEY_BLEND}",
        "despill=type=green",
        f"scale={width}:-2",
        "setsar=1",
    ]
    return ",".join(parts)


def _native_dims(banner: Path) -> tuple[int, int, float, float]:
    from .probe import probe  # локальный импорт, чтобы не было цикла
    info = probe(banner)
    return info.width, info.height, info.fps, info.duration


def measure(width: int, banner: Path | None = None, use_cache: bool = True) -> BannerMeasure:
    """Считает след баннера покадрово при заданной ширине кадра."""
    banner = Path(banner or config.BANNER_PATH)
    if not banner.exists():
        raise BannerError(f"Файл вставки не найден: {banner}")
    if width < 16 or width % 2:
        raise BannerError(f"Ширина кадра должна быть чётной и не меньше 16, получено {width}")

    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = config.CACHE_DIR / f"banner-{_cache_key(banner, width)}.json"
    if use_cache and cache_file.exists():
        try:
            return BannerMeasure(**json.loads(cache_file.read_text()))
        except (json.JSONDecodeError, TypeError):
            cache_file.unlink(missing_ok=True)

    nat_w, nat_h, nat_fps, nat_dur = _native_dims(banner)
    height = scaled_height(nat_w, nat_h, width)

    proc = subprocess.Popen(
        [
            config.FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-i", str(banner),
            "-filter_complex", f"[0:v]{keyed_filter(width)},format=rgba[out]",
            "-map", "[out]", "-f", "rawvideo", "-pix_fmt", "rgba", "-",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    frame_bytes = width * height * 4
    stats: list[FrameStat] = []
    try:
        idx = 0
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            alpha = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 4)[:, :, 3]
            mask = alpha > config.ALPHA_THRESHOLD
            solid = int(mask.sum())
            rows = np.nonzero(mask.any(axis=1))[0]
            bbox_h = int(rows[-1] - rows[0] + 1) if rows.size else 0
            stats.append(FrameStat(idx, idx / nat_fps, solid, bbox_h))
            idx += 1
    finally:
        if proc.stdout:
            proc.stdout.close()
        err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        proc.wait()

    if not stats:
        raise BannerError(f"Не удалось раскадрировать вставку: {err.strip()[:400]}")

    # Полка = самая частая высота следа. Раскрытая панель — всё, что не ниже неё
    # (сюда же попадает «подскок» при выпадении предметов).
    heights = [s.bbox_h for s in stats if s.bbox_h > 0]
    shelf = statistics.mode(heights)
    open_frames = [s for s in stats if s.bbox_h >= shelf]
    if not open_frames:
        raise BannerError("Не нашлась фаза раскрытой панели")

    result = BannerMeasure(
        width=width,
        height=height,
        fps=nat_fps,
        duration=nat_dur,
        frames=len(stats),
        open_from=open_frames[0].time,
        open_to=open_frames[-1].time,
        open_frames=len(open_frames),
        solid_min=min(s.solid for s in open_frames),
        solid_mean=statistics.mean(s.solid for s in open_frames),
        solid_max=max(s.solid for s in open_frames),
        shelf_height=shelf,
    )
    cache_file.write_text(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return result
