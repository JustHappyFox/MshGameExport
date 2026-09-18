#!/usr/bin/env python3
"""Замер: сколько процентов кадра занимает раскрытая панель.

  python3 tools/measure.py video.mp4            # что увидит бот рекламодателя
  python3 tools/measure.py --plan video.mp4     # + какой будет план обработки
  python3 tools/measure.py --geometry 720x1240  # только по геометрии, без файла
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config
from app.video import banner as banner_mod
from app.video import render as render_mod
from app.video.probe import detect_content_crop, output_fps, probe


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", nargs="?")
    ap.add_argument("--geometry", help="WxH вместо файла")
    ap.add_argument("--plan", action="store_true", help="показать план обработки")
    ap.add_argument("--banner", default=str(config.BANNER_PATH))
    args = ap.parse_args()

    config.ensure_dirs()
    banner = Path(args.banner)

    if args.geometry:
        w, h = (int(x) for x in args.geometry.lower().split("x"))
        bm = banner_mod.measure(w, banner)
        cov = bm.coverage(h)
        print(f"кадр {w}x{h}")
        print(f"панель {bm.width}x{bm.shelf_height}, {bm.solid_min} залитых пикселей")
        print(f"покрытие {cov * 100:.2f}%  порог {config.MIN_COVERAGE * 100:.0f}%  "
              f"-> {'OK' if cov >= config.MIN_COVERAGE else 'НИЖЕ ПОРОГА'}")
        print(f"максимальная высота кадра под порог: {bm.max_frame_height(config.MIN_COVERAGE)} px")
        return 0

    if not args.video:
        ap.error("нужен файл или --geometry")

    src = Path(args.video)
    info = probe(src)
    crop = detect_content_crop(info)
    bars = (crop.w, crop.h) != (info.width, info.height)
    bm = banner_mod.measure(crop.w - crop.w % 2, banner)

    print(f"вход:      {info.width}x{info.height}, {info.duration:.2f}s, "
          f"{info.fps:.2f} fps, звук: {'есть' if info.has_audio else 'нет'}")
    print(f"поля:      {'срезаны -> ' + str(crop.w) + 'x' + str(crop.h) if bars else 'нет'}")
    print(f"панель:    {bm.width}x{bm.shelf_height}, {bm.solid_min} залитых пикселей "
          f"(раскрыта {bm.open_from:.2f}-{bm.open_to:.2f}s)")
    cov = bm.coverage(crop.h - crop.h % 2)
    print(f"покрытие:  {cov * 100:.2f}% на кадре видео -> "
          f"{'порог взят, сквиз не нужен' if cov >= config.MIN_COVERAGE else 'ниже порога, нужен сквиз'}")

    if args.plan:
        plan = render_mod.make_plan(src, banner)
        print()
        print(json.dumps(plan.as_dict(), ensure_ascii=False, indent=2))
        geo = render_mod.verify_geometry(plan.out_w, plan.out_h, output_fps(info), banner)
        print()
        print(f"проверка на {plan.out_w}x{plan.out_h}: "
              f"min={geo['coverage_min'] * 100:.2f}% mean={geo['coverage_mean'] * 100:.2f}% "
              f"max={geo['coverage_max'] * 100:.2f}% -> {'OK' if geo['passed'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
