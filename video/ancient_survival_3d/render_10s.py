#!/usr/bin/env python3
"""Render the first 10 seconds of the reel with photoreal AI people in 3D.

Same pipeline as `render_3d.py` (CPU rasteriser -> 1080x1920 frames -> ffmpeg),
but the cast is the AI-generated photo cards from `photopeople.py`, placed as
3D geometry, and the shots come from `scenes_photo.py`.

    python3 render_10s.py                       # whole 10 s clip
    python3 render_10s.py --start 0 --end 120   # a slice, runs in parallel
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import photopeople as PP
import stage as STAGE
from rasterlib import Raster
from scenes3d import apply_env
from scenes_stage import SHOTS as SHOTS10

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

RW, RH = 960, 1707                     # raster size, upscaled to 1080x1920
W, H, FPS, DURATION = 1080, 1920, 24, 10.0
FONTS = REPO / "video" / "ancient_survival" / "fonts"
BUILD = HERE / "_build"
OUT = REPO / "video" / "Ancient_Survival_3D_10s_Photoreal.mp4"

CREAM = (255, 246, 220)
GOLD = (255, 187, 93)
INK = (34, 29, 32)

# Only the two photoreal shots, with captions that match what is on screen.
CAPTIONS = [
    (0.00, 2.55, "RAAT KA", "JUNGLE..."),
    (2.55, 4.80, "NA PHONE.", "NA SAFE GHAR."),
    (4.80, 7.30, "AAG =", "PEHLA GHAR"),
    (7.30, 10.00, "PEHRA", "+ TEAMWORK"),
]


def font_for(text: str, size: int, max_width: int) -> ImageFont.FreeTypeFont:
    """Shrink the font until the line fits inside the safe width."""
    size = size
    while size > 40:
        f = ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), size)
        if f.getlength(text) <= max_width:
            return f
        size -= 6
    return ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), size)


def render_line(text: str, font, colour):
    width = max(40, round(font.getlength(text)) + 80)
    height = font.size + 44
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text((width / 2 + 5, 26), text, font=font, anchor="ma",
           fill=(20, 14, 16, 210), stroke_width=10,
           stroke_fill=(20, 14, 16, 140))
    d.text((width / 2, 21), text, font=font, anchor="ma", fill=colour,
           stroke_width=6, stroke_fill=INK + (255,))
    return layer


def back_out(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2


def ease(x: float) -> float:
    return x * x * (3 - 2 * x)


class Reel:
    def __init__(self) -> None:
        self.r = Raster(RW, RH, fov=0.8)
        self.r.set_texture(PP.atlas())
        self.r.set_texture2(STAGE.atlas())
        self.captions = []
        for _, _, first, second in CAPTIONS:
            self.captions.append({
                "first": render_line(first, font_for(first, 118, 940), CREAM),
                "second": render_line(second, font_for(second, 114, 940), GOLD),
            })
        self.tag_font = ImageFont.truetype(str(FONTS / "BarlowCondensed-Bold.ttf"), 30)
        rng = np.random.default_rng(3)
        self.grain = rng.normal(0, 4.6, (H, W, 1)).repeat(3, axis=2).astype(np.int16)

    def shot_for(self, t: float):
        for start, end, fn in SHOTS10:
            if start <= t < end:
                return fn, start, end
        start, end, fn = SHOTS10[-1]
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
        im = im.filter(ImageFilter.UnsharpMask(radius=1.3, percent=38, threshold=2))
        arr = np.asarray(im).astype(np.int16)
        arr = np.clip(arr + self.grain, 0, 255).astype(np.uint8)
        im = Image.fromarray(arr)
        self.overlay(im, t)
        return im

    # ------------------------------------------------------------------ overlay
    def overlay(self, im: Image.Image, t: float) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        d.text((54, 104), "MONARCHVOICE  /  SURVIVAL FILE 01  /  PHOTOREAL",
               font=self.tag_font, fill=(255, 226, 171, 236),
               stroke_width=2, stroke_fill=(21, 20, 23, 190))
        d.rounded_rectangle((54, 166, 1026, 173), radius=3, fill=(255, 246, 220, 76))
        d.rounded_rectangle((54, 166, 54 + max(7, round(972 * t / DURATION)), 173),
                            radius=3, fill=GOLD + (235,))

        for i, (start, end, _, _) in enumerate(CAPTIONS):
            if not start <= t < end:
                continue
            art = self.captions[i]
            enter = min(1.0, (t - start) / 0.24)
            leave = min(1.0, max(0.0, (end - t) / 0.17))
            if leave <= 0:
                break
            alpha = round(255 * min(1.0, enter * 1.5, leave * 1.25))
            pop = 1.0 + 0.06 * (1 - back_out(enter))
            for key, dx, delay, ybase in (("first", -84, 0.0, 1478),
                                          ("second", 84, 0.05, 1590)):
                local = min(1.0, max(0.0, (t - start - delay) / 0.26))
                if local <= 0:
                    continue
                layer = art[key]
                scale = (0.93 + 0.07 * back_out(local)) * pop
                w = max(1, round(layer.width * scale))
                h = max(1, round(layer.height * scale))
                sprite = layer.resize((w, h), Image.Resampling.LANCZOS)
                if alpha < 255:
                    sprite = sprite.copy()
                    sprite.putalpha(sprite.getchannel("A").point(
                        lambda a: round(a * alpha / 255)))
                im.paste(sprite, (round(W / 2 - w / 2 + (1 - local) * dx),
                                  round(ybase + (1 - leave) * -26)),
                         sprite.getchannel("A"))
            swipe = ease(min(1.0, max(0.0, (t - start - 0.08) / 0.26))) * leave
            if swipe > 0:
                dd = ImageDraw.Draw(im, "RGBA")
                bar_w = 520 * swipe
                bar_y = 1590 + art["second"].height - 4
                dd.rounded_rectangle((W / 2 - bar_w / 2, bar_y,
                                      W / 2 + bar_w / 2, bar_y + 7),
                                     radius=4, fill=GOLD + (150,))
            break


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=round(FPS * DURATION))
    ap.add_argument("--segment", type=Path)
    args = ap.parse_args()

    reel = Reel()
    seg = args.segment or (BUILD / f"p10_{args.start:04d}.mp4")
    seg.parent.mkdir(parents=True, exist_ok=True)

    import shutil
    ff = shutil.which("ffmpeg")
    if not ff:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", str(seg)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
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
