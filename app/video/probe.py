"""Разбор входного видео: геометрия, поворот, звук, чёрные поля."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .. import config


class ProbeError(RuntimeError):
    pass


def _run(cmd: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout or config.FFMPEG_TIMEOUT
    )


@dataclass(frozen=True)
class Crop:
    w: int
    h: int
    x: int
    y: int

    @property
    def is_noop_for(self) -> bool:  # pragma: no cover - удобство отладки
        return self.x == 0 and self.y == 0

    def filter_str(self) -> str:
        return f"crop={self.w}:{self.h}:{self.x}:{self.y}"


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    width: int          # уже с учётом поворота
    height: int
    duration: float
    fps: float
    has_audio: bool
    rotation: int
    raw_width: int
    raw_height: int

    @property
    def aspect(self) -> float:
        return self.width / self.height


def _stream_rotation(stream: dict) -> int:
    """Угол из display matrix. ffmpeg по умолчанию доворачивает кадр сам,
    поэтому нам нужно только знать, меняются ли местами ширина и высота."""
    for sd in stream.get("side_data_list") or []:
        if "rotation" in sd:
            try:
                return int(round(float(sd["rotation"]))) % 360
            except (TypeError, ValueError):
                pass
    tags = stream.get("tags") or {}
    if "rotate" in tags:
        try:
            return int(round(float(tags["rotate"]))) % 360
        except (TypeError, ValueError):
            pass
    return 0


def _parse_fps(stream: dict) -> float:
    for key in ("avg_frame_rate", "r_frame_rate"):
        val = stream.get(key)
        if not val or val == "0/0":
            continue
        try:
            num, den = val.split("/")
            num, den = float(num), float(den)
            if den > 0 and num > 0:
                return num / den
        except ValueError:
            continue
    return 30.0


def probe(path: Path) -> VideoInfo:
    res = _run([
        config.FFPROBE, "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path),
    ], timeout=120)
    if res.returncode != 0:
        raise ProbeError(f"ffprobe не смог прочитать файл: {res.stderr.strip()[:400]}")
    try:
        data = json.loads(res.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"ffprobe вернул мусор: {exc}") from exc

    streams = data.get("streams") or []
    vstreams = [s for s in streams if s.get("codec_type") == "video"]
    if not vstreams:
        raise ProbeError("В файле нет видеодорожки")
    v = vstreams[0]

    raw_w, raw_h = int(v["width"]), int(v["height"])
    rotation = _stream_rotation(v)
    width, height = (raw_h, raw_w) if rotation in (90, 270) else (raw_w, raw_h)

    duration = 0.0
    for candidate in (v.get("duration"), (data.get("format") or {}).get("duration")):
        try:
            duration = float(candidate)
            if duration > 0:
                break
        except (TypeError, ValueError):
            continue
    if duration <= 0:
        raise ProbeError("Не удалось определить длительность видео")

    return VideoInfo(
        path=path,
        width=width,
        height=height,
        duration=duration,
        fps=_parse_fps(v),
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        rotation=rotation,
        raw_width=raw_w,
        raw_height=raw_h,
    )


def output_fps(info: VideoInfo) -> int:
    """Приводим к целому кадровому ряду в разумных границах."""
    return max(config.FPS_MIN, min(config.FPS_MAX, int(round(info.fps)) or 30))


_CROP_RE = re.compile(r"crop=(\d+):(\d+):(\d+):(\d+)")


def detect_content_crop(info: VideoInfo, samples: int = 9) -> Crop:
    """Ищет чёрные поля и возвращает область реального изображения.

    Замер берётся в нескольких точках ролика, результаты объединяются
    по максимуму — иначе одна тёмная сцена «съест» часть кадра.
    """
    full = Crop(info.width, info.height, 0, 0)
    if not config.CROP_BLACK_BARS:
        return full

    x1, y1 = info.width, info.height
    x2, y2 = 0, 0
    found = False

    for i in range(1, samples + 1):
        ts = info.duration * i / (samples + 1)
        res = _run([
            config.FFMPEG, "-hide_banner", "-nostdin",
            "-ss", f"{ts:.3f}", "-i", str(info.path),
            "-frames:v", "8",
            "-vf", "cropdetect=limit=24:round=2:reset=1",
            "-f", "null", "-",
        ], timeout=120)
        for m in _CROP_RE.finditer(res.stderr):
            w, h, x, y = (int(g) for g in m.groups())
            if w <= 0 or h <= 0:
                continue
            found = True
            x1, y1 = min(x1, x), min(y1, y)
            x2, y2 = max(x2, x + w), max(y2, y + h)

    if not found:
        return full

    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(info.width, x2), min(info.height, y2)
    w, h = x2 - x1, y2 - y1

    # чётные размеры для h264 и центрирование остатка
    w -= w % 2
    h -= h % 2
    x1 += x1 % 2
    y1 += y1 % 2
    if x1 + w > info.width:
        w = (info.width - x1) - ((info.width - x1) % 2)
    if y1 + h > info.height:
        h = (info.height - y1) - ((info.height - y1) % 2)

    if w < 64 or h < 64:
        return full
    # меньше процента площади — считаем, что полей нет
    if w * h >= 0.99 * info.width * info.height:
        return full
    return Crop(w, h, x1, y1)
