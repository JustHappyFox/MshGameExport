"""Планирование и сборка ролика со вставкой.

Порядок строго такой:
  1. найти и срезать чёрные поля — их площадь не должна попадать в знаменатель;
  2. замерить, сколько кадра занимает раскрытая панель на этой геометрии;
  3. если уже >= порога — ничего не сжимать;
  4. если меньше — уменьшить высоту кадра ровно настолько, чтобы порог взялся;
  5. собрать: пауза в центре -> вставка поверх замершего кадра -> продолжение;
  6. проверить результат на реальной геометрии и только потом отдавать файл.
"""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from .. import config
from . import banner as banner_mod
from .probe import Crop, VideoInfo, output_fps, probe

ProgressCb = Callable[[int, str], None]


class RenderError(RuntimeError):
    pass


@dataclass
class RenderPlan:
    info: VideoInfo
    crop: Crop
    out_w: int
    out_h: int
    fps: int
    insert_at: float
    insert_duration: float
    measure: banner_mod.BannerMeasure
    coverage_before: float          # на кадре видео после срезания полей
    coverage_after: float           # на итоговой геометрии
    bars_removed: bool
    squeeze: bool
    squeeze_px: int
    squeeze_ratio: float
    warnings: list[str] = field(default_factory=list)

    @property
    def content_w(self) -> int:
        return self.crop.w

    @property
    def content_h(self) -> int:
        return self.crop.h

    @property
    def total_duration(self) -> float:
        return self.info.duration + self.insert_duration

    def as_dict(self) -> dict:
        return {
            "input": {
                "width": self.info.width, "height": self.info.height,
                "duration": round(self.info.duration, 3), "fps": round(self.info.fps, 3),
                "has_audio": self.info.has_audio, "rotation": self.info.rotation,
            },
            "bars_removed": self.bars_removed,
            "content": {"width": self.content_w, "height": self.content_h},
            "output": {"width": self.out_w, "height": self.out_h, "fps": self.fps,
                       "duration": round(self.total_duration, 3)},
            "insert": {"at": round(self.insert_at, 3),
                       "duration": round(self.insert_duration, 3)},
            "squeeze": {"applied": self.squeeze, "px": self.squeeze_px,
                        "ratio": round(self.squeeze_ratio, 5)},
            "coverage": {
                "threshold": config.MIN_COVERAGE,
                "target": config.TARGET_COVERAGE,
                "before": round(self.coverage_before, 5),
                "after": round(self.coverage_after, 5),
                "panel_px": self.measure.solid_min,
                "panel_height": self.measure.height,
                "open_phase": [round(self.measure.open_from, 3),
                               round(self.measure.open_to, 3)],
            },
            "warnings": self.warnings,
        }


def _even(v: int) -> int:
    return v - (v % 2)


def make_plan(path: Path, banner_path: Path | None = None) -> RenderPlan:
    from .probe import detect_content_crop

    info = probe(path)
    if info.duration > config.MAX_INPUT_DURATION:
        raise RenderError(
            f"Ролик длиннее {config.MAX_INPUT_DURATION / 60:.0f} мин "
            f"({info.duration / 60:.1f} мин)"
        )

    crop = detect_content_crop(info)
    bars_removed = (crop.w, crop.h) != (info.width, info.height)
    content_w, content_h = _even(crop.w), _even(crop.h)
    if content_w < 16 or content_h < 16:
        raise RenderError("Слишком маленький кадр после обработки")
    crop = Crop(content_w, content_h, crop.x, crop.y)

    fps = output_fps(info)
    bm = banner_mod.measure(content_w, banner_path)

    warnings: list[str] = []
    coverage_before = bm.coverage(content_h)

    if coverage_before >= config.MIN_COVERAGE:
        out_h, squeeze = content_h, False
    else:
        needed = bm.max_frame_height(config.TARGET_COVERAGE)
        out_h = max(16, min(content_h, needed))
        squeeze = out_h != content_h
        if not squeeze:
            warnings.append(
                "Порог не берётся даже без сжатия — геометрия вставки не подходит кадру"
            )

    squeeze_px = content_h - out_h
    squeeze_ratio = squeeze_px / content_h if content_h else 0.0
    if squeeze_ratio > 0.06:
        warnings.append(
            f"Сжатие {squeeze_ratio * 100:.1f}% — заметно на глаз. "
            f"Кадр {content_w}x{content_h} сильно выше, чем 9:16"
        )
    if bars_removed:
        warnings.append(
            f"Срезаны чёрные поля: {info.width}x{info.height} -> {content_w}x{content_h}"
        )

    coverage_after = bm.coverage(out_h)
    insert_frames = max(1, int(round(bm.duration * fps)))
    insert_duration = insert_frames / fps
    insert_at = round(info.duration / 2 * fps) / fps

    return RenderPlan(
        info=info, crop=crop, out_w=content_w, out_h=out_h, fps=fps,
        insert_at=insert_at, insert_duration=insert_duration, measure=bm,
        coverage_before=coverage_before, coverage_after=coverage_after,
        bars_removed=bars_removed, squeeze=squeeze, squeeze_px=squeeze_px,
        squeeze_ratio=squeeze_ratio, warnings=warnings,
    )


def _main_chain(plan: RenderPlan, with_fps: bool = True) -> str:
    parts = []
    if with_fps:
        parts.append(f"fps={plan.fps}")
    parts.append(plan.crop.filter_str())
    if plan.out_h != plan.content_h:
        parts.append(f"scale={plan.out_w}:{plan.out_h}:flags=lanczos")
    parts.append("setsar=1")
    return ",".join(parts)


_PROGRESS_RE = re.compile(r"out_time_us=(\d+)")


def _run_ffmpeg(cmd: list[str], total: float, progress: ProgressCb | None,
                lo: int, hi: int, stage: str) -> None:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    tail: list[str] = []
    try:
        for line in proc.stdout or []:
            m = _PROGRESS_RE.search(line)
            if m and progress and total > 0:
                done = int(m.group(1)) / 1_000_000 / total
                progress(lo + int(max(0.0, min(1.0, done)) * (hi - lo)), stage)
    finally:
        if proc.stdout:
            proc.stdout.close()
        if proc.stderr:
            tail = proc.stderr.read().splitlines()[-25:]
        proc.wait(timeout=config.FFMPEG_TIMEOUT)
    if proc.returncode != 0:
        raise RenderError("ffmpeg упал:\n" + "\n".join(tail))


def render(plan: RenderPlan, out_path: Path, banner_path: Path | None = None,
           progress: ProgressCb | None = None) -> Path:
    banner_path = Path(banner_path or config.BANNER_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    T = plan.insert_at
    D = plan.insert_duration
    has_banner_audio = probe(banner_path).has_audio

    with tempfile.TemporaryDirectory(dir=str(config.TMP_DIR)) as tmp:
        tmpdir = Path(tmp)
        freeze = tmpdir / "freeze.png"

        # 1. кадр, на котором видео замирает
        if progress:
            progress(5, "замер и подготовка")
        res = subprocess.run(
            [config.FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin",
             "-ss", f"{T:.6f}", "-i", str(plan.info.path), "-frames:v", "1",
             str(freeze), "-y"],
            capture_output=True, text=True, timeout=300,
        )
        if res.returncode != 0 or not freeze.exists():
            raise RenderError(f"Не удалось снять кадр для паузы: {res.stderr.strip()[:300]}")

        # 2. сборка
        inputs = [
            "-i", str(plan.info.path),
            "-i", str(banner_path),
            "-loop", "1", "-framerate", str(plan.fps), "-t", f"{D + 0.5:.3f}",
            "-i", str(freeze),
        ]
        next_idx = 3
        silence_idx = None
        if not plan.info.has_audio or not has_banner_audio:
            inputs += ["-f", "lavfi", "-t", f"{plan.total_duration + 1:.3f}",
                       "-i", f"anullsrc=channel_layout=stereo:sample_rate={config.AUDIO_RATE}"]
            silence_idx = next_idx
            next_idx += 1

        chain = _main_chain(plan)
        bg_chain = _main_chain(plan, with_fps=False)
        afmt = (f"aresample={config.AUDIO_RATE},"
                "aformat=sample_fmts=fltp:channel_layouts=stereo")

        g = [
            f"[0:v]{chain},split=2[m1][m2]",
            f"[m1]trim=end={T:.6f},setpts=PTS-STARTPTS[v0]",
            f"[m2]trim=start={T:.6f},setpts=PTS-STARTPTS[v2]",
            f"[1:v]{banner_mod.keyed_filter(plan.out_w, plan.fps)},"
            f"trim=end={D:.6f},setpts=PTS-STARTPTS[ad]",
            f"[2:v]{bg_chain}[bg]",
            "[bg][ad]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p[v1]",
        ]

        if plan.info.has_audio:
            g += [
                f"[0:a]{afmt},asplit=2[ma1][ma2]",
                f"[ma1]atrim=end={T:.6f},asetpts=PTS-STARTPTS[a0]",
                f"[ma2]atrim=start={T:.6f},asetpts=PTS-STARTPTS[a2]",
            ]
        else:
            g += [
                f"[{silence_idx}:a]{afmt},asplit=2[ms1][ms2]",
                f"[ms1]atrim=end={T:.6f},asetpts=PTS-STARTPTS[a0]",
                f"[ms2]atrim=end={plan.info.duration - T:.6f},asetpts=PTS-STARTPTS[a2]",
            ]

        if has_banner_audio:
            g.append(f"[1:a]{afmt},apad,atrim=end={D:.6f},asetpts=PTS-STARTPTS[a1]")
        else:
            g.append(f"[{silence_idx}:a]{afmt},atrim=end={D:.6f},asetpts=PTS-STARTPTS[a1]")

        g.append("[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]")

        cmd = [
            config.FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-progress", "pipe:1", *inputs,
            "-filter_complex", ";".join(g),
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", config.X264_PRESET, "-crf", str(config.X264_CRF),
            "-pix_fmt", "yuv420p", "-fps_mode", "cfr", "-r", str(plan.fps),
            "-c:a", "aac", "-b:a", config.AUDIO_BITRATE, "-ar", str(config.AUDIO_RATE),
            "-movflags", "+faststart", str(out_path), "-y",
        ]
        _run_ffmpeg(cmd, plan.total_duration, progress, 8, 92, "рендер")

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RenderError("Рендер не дал файла")
    return out_path


def verify_geometry(out_w: int, out_h: int, fps: int,
                    banner_path: Path | None = None) -> dict:
    """Проверка на реальной геометрии кадра.

    Кладём вставку на чистую магенту тем же конвейером, что и в рендере, и
    считаем всё, что не магента. Так проверяется и масштаб, и позиция, и кей —
    а не только арифметика плана.
    """
    banner_path = Path(banner_path or config.BANNER_PATH)
    proc = subprocess.Popen(
        [
            config.FFMPEG, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "lavfi", "-i", f"color=0xFF00FF:s={out_w}x{out_h}:r={fps}:d=600",
            "-i", str(banner_path),
            "-filter_complex",
            f"[1:v]{banner_mod.keyed_filter(out_w, fps)}[ad];[0:v]setsar=1[bg];"
            "[bg][ad]overlay=(W-w)/2:(H-h)/2:shortest=1,format=rgb24[out]",
            "-map", "[out]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    frame_bytes = out_w * out_h * 3
    screen = out_w * out_h
    magenta = np.array([255, 0, 255], dtype=np.int16)
    rows: list[tuple[int, int]] = []  # (solid, bbox_h)
    try:
        while True:
            buf = proc.stdout.read(frame_bytes)
            if len(buf) < frame_bytes:
                break
            fr = np.frombuffer(buf, dtype=np.uint8).reshape(out_h, out_w, 3).astype(np.int16)
            mask = np.abs(fr - magenta).max(axis=2) > 24
            ys = np.nonzero(mask.any(axis=1))[0]
            rows.append((int(mask.sum()), int(ys[-1] - ys[0] + 1) if ys.size else 0))
    finally:
        if proc.stdout:
            proc.stdout.close()
        err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
        proc.wait()

    if not rows:
        raise RenderError(f"Проверка не смогла раскадрировать вставку: {err.strip()[:300]}")

    heights = [h for _, h in rows if h > 0]
    shelf = max(set(heights), key=heights.count)
    open_rows = [(s, h) for s, h in rows if h >= shelf]
    cov = [s / screen for s, _ in open_rows]
    return {
        "frames": len(rows),
        "open_frames": len(open_rows),
        "shelf_height": shelf,
        "coverage_min": min(cov),
        "coverage_mean": sum(cov) / len(cov),
        "coverage_max": max(cov),
        "passed": min(cov) >= config.MIN_COVERAGE,
    }


def verify_output(out_path: Path, plan: RenderPlan) -> dict:
    """Сверяет готовый файл с планом и проверяет порог на его геометрии."""
    info = probe(out_path)
    problems = []
    if (info.width, info.height) != (plan.out_w, plan.out_h):
        problems.append(
            f"геометрия файла {info.width}x{info.height} вместо "
            f"{plan.out_w}x{plan.out_h}"
        )
    expected = plan.total_duration
    if abs(info.duration - expected) > 0.5:
        problems.append(f"длительность {info.duration:.2f}s вместо {expected:.2f}s")

    geo = verify_geometry(plan.out_w, plan.out_h, plan.fps)
    if not geo["passed"]:
        problems.append(
            f"панель занимает {geo['coverage_min'] * 100:.2f}% — ниже порога "
            f"{config.MIN_COVERAGE * 100:.0f}%"
        )
    if problems:
        raise RenderError("Проверка результата не прошла: " + "; ".join(problems))

    return {
        "width": info.width, "height": info.height,
        "duration": round(info.duration, 3),
        "size_bytes": out_path.stat().st_size,
        "coverage_min": round(geo["coverage_min"], 5),
        "coverage_mean": round(geo["coverage_mean"], 5),
        "coverage_max": round(geo["coverage_max"], 5),
        "open_frames": geo["open_frames"],
        "threshold": config.MIN_COVERAGE,
        "passed": True,
    }


def process(src: Path, out_path: Path, banner_path: Path | None = None,
            progress: ProgressCb | None = None) -> dict:
    """Весь путь: план -> рендер -> проверка. Возвращает отчёт для клиента."""
    plan = make_plan(src, banner_path)
    render(plan, out_path, banner_path, progress)
    if progress:
        progress(94, "проверка порога")
    report = verify_output(out_path, plan)
    if progress:
        progress(100, "готово")
    return {"plan": plan.as_dict(), "result": report}
