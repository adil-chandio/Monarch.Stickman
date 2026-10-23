#!/usr/bin/env python3
"""Render the stickman cut of the reel: 5 shots x exactly 2.0 s = 10 s.

Same skeleton, same motion module, same motion-blur / grain / caption pipeline
as the other cuts, but the cast is drawn as stick figures on a black field
(Style 1 dark), so the pre-viz reads instantly.

    python3 render_stick.py                       # whole 10 s
    python3 render_stick.py --start 0 --end 120   # a slice, for parallel runs
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from rasterlib import Raster
from scenes3d import apply_env
from scenes_stick import SHOTS

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

RW, RH = 810, 1440
W, H, FPS, DURATION = 1080, 1920, 24, 10.0
FONTS = REPO / "video" / "ancient_survival" / "fonts"
BUILD = HERE / "_build"
OUT = REPO / "video" / "Ancient_Survival_Stickman_10s.mp4"

CREAM = (255, 246, 220)
GOLD = (255, 187, 93)

# one caption per shot, cut on the shot boundary
CAPTIONS = [
    (0.00, 2.00, "RAAT KA", "JUNGLE..."),
    (2.00, 4.00, "NA PHONE.", "NA SAFE GHAR."),
    (4.00, 6.00, "PEHLE", "CHALNA SEEKHO"),
    (6.00, 8.00, "AAG =", "PEHLA GHAR"),
    (8.00, 10.00, "PEHRA", "+ TEAMWORK"),
]


def font_for(text: str, size: int, max_width: int) -> ImageFont.FreeTypeFont:
    while size > 40:
        f = ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), size)
        if f.getlength(text) <= max_width:
            return f
        size -= 6
    return ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), size)


def render_line(text: str, colour) -> Image.Image:
    f = font_for(text, 116, 940)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    box = tmp.textbbox((0, 0), text, font=f)
    w, h = box[2] - box[0], box[3] - box[1]
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((20 - box[0], 20 - box[1]), text, font=f,
                            fill=colour + (255,))
    return im


class Reel:
    def __init__(self) -> None:
        self.r = Raster(RW, RH, fov=0.8)
        self.captions = [{k: render_line(t, c) for k, (t, c) in
                          (("first", (a, CREAM)), ("second", (b, GOLD)))}
                         for _, _, a, b in CAPTIONS]
        self.tag_font = ImageFont.truetype(str(FONTS / "BarlowCondensed-Bold.ttf"), 30)
        rng = np.random.default_rng(5)
        self.grain = rng.normal(0, 3.0, (H, W, 1)).repeat(3, axis=2).astype(np.int16)

    def shot_for(self, t: float):
        for start, end, fn in SHOTS:
            if start <= t < end:
                return fn, start, end
        start, end, fn = SHOTS[-1]
        return fn, start, end

    def frame(self, t: float) -> Image.Image:
        fn, start, end = self.shot_for(t)
        p = (t - start) / (end - start)
        meshes, opts = fn(t, p)
        env = opts["env"]
        self.r.camera(*opts["cam"], fov=env["fov"])
        apply_env(self.r, env)
        small = Image.fromarray(self.r.render(meshes))
        im = small.resize((W, H), Image.Resampling.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=42, threshold=2))
        arr = np.clip(np.asarray(im).astype(np.int16) + self.grain, 0, 255).astype(np.uint8)
        im = Image.fromarray(arr)
        self.overlay(im, t)
        return im

    def overlay(self, im: Image.Image, t: float) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        d.text((54, 104), "MONARCHVOICE  /  SURVIVAL FILE 01  /  PRE-VIZ",
               font=self.tag_font, fill=(255, 226, 171, 236),
               stroke_width=2, stroke_fill=(21, 20, 23, 190))
        d.rounded_rectangle((54, 166, 1026, 173), radius=3, fill=(255, 246, 220, 70))
        d.rounded_rectangle((54, 166, 54 + max(7, round(972 * t / DURATION)), 173),
                            radius=3, fill=GOLD + (235,))
        # shot ticks: five equal beats
        for i in range(1, 5):
            x = 54 + round(972 * i / 5)
            d.rounded_rectangle((x - 1, 160, x + 1, 179), radius=1,
                                fill=(12, 12, 16, 220))
        for i, (start, end, _, _) in enumerate(CAPTIONS):
            if not start <= t < end:
                continue
            art = self.captions[i]
            enter = min(1.0, (t - start) / 0.18)
            leave = min(1.0, max(0.0, (end - t) / 0.14))
            if leave <= 0:
                break
            alpha = round(255 * min(1.0, enter * 1.8, leave * 1.5))
            y = 1470
            for key in ("first", "second"):
                layer = art[key]
                if alpha < 255:
                    layer = layer.copy()
                    layer.putalpha(layer.getchannel("A").point(
                        lambda a: round(a * alpha / 255)))
                im.paste(layer, (54 - 20, y - 20), layer.getchannel("A"))
                y += layer.height - 24
            break


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=round(FPS * DURATION))
    ap.add_argument("--segment", type=Path)
    args = ap.parse_args()

    import shutil
    ff = shutil.which("ffmpeg")
    if not ff:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()

    seg = args.segment or (BUILD / f"stick_{args.start:04d}.mp4")
    seg.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", str(seg)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    reel = Reel()
    try:
        assert proc.stdin is not None
        for n in range(args.start, args.end):
            proc.stdin.write(reel.frame(n / FPS).tobytes())
            if (n - args.start) % 24 == 0:
                print(f"frame {n}/{args.end}", flush=True)
        proc.stdin.close()
        assert proc.stderr is not None
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError(err)
    except BaseException:
        proc.kill()
        raise
    print(f"wrote {seg}")


if __name__ == "__main__":
    main()
