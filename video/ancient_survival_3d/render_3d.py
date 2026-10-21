#!/usr/bin/env python3
"""Render the Ancient Survival reel as true 3D.

Every frame is geometry: procedural terrain, rocks, trees, a rigged humanoid cast
with per-frame skeletal poses, an emissive fire, a perspective camera that moves
in 3D, a sun with a real shadow map, and cel-shaded lighting with ink outlines.
No photographs, no painted plates, no sprite sheets.

Frames are rasterised by `raster.c` (C, via ctypes), captions are composited with
Pillow, and ffmpeg encodes. Audio comes from the existing narration + score mix.

    python3 video/ancient_survival_3d/render_3d.py --start 0 --end 300
"""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "video" / "ancient_survival"))

from rasterlib import Raster          # noqa: E402
from scenes3d import SHOTS            # noqa: E402

RW, RH = 720, 1280                    # raster size (upscaled to 1080x1920)
W, H, FPS, DURATION = 1080, 1920, 24, 30
FONTS = REPO / "video" / "ancient_survival" / "fonts"
OUT = REPO / "video" / "Ancient_Survival_3D_30s_Reel.mp4"
BUILD = HERE / "_build"

CAPTIONS = [
    (0.00, 1.73, "RAAT KA", "JUNGLE..."),
    (1.73, 3.58, "NA PHONE.", "NA SAFE GHAR."),
    (3.58, 6.40, "ANCIENT LOG", "KAISE BACHE?"),
    (6.40, 8.24, "JAWAB?", "TEAMWORK."),
    (8.24, 11.50, "PEHRA + BERRIES", "+ ROOTS"),
    (11.50, 13.35, "SHARP PATHAR", "SE TOOLS"),
    (13.35, 14.92, "MIL KAR", "SHIKAR"),
    (14.92, 18.48, "AAG: ROSHNI,", "GARAMI + KHANA"),
    (18.48, 21.37, "SAB CAVES MEIN", "NAHI REHTE THE!"),
    (21.37, 22.67, "CAMPS BHI", "BADALTE THE"),
    (22.67, 25.50, "ASLI POWER?", "STRENGTH NAHI"),
    (25.50, 27.65, "PLANNING", "+ EK DOOSRE KA SAATH"),
    (27.65, 30.00, "SAATH = SURVIVAL", "MONARCHVOICE"),
]
CREAM = (255, 246, 220)
GOLD = (255, 187, 93)
INK = (34, 29, 32)


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def back_out(x: float, overshoot: float = 1.9) -> float:
    x = min(1.0, max(0.0, x)) - 1
    return 1 + x * x * ((overshoot + 1) * x + overshoot)


def font_for(text: str, wanted: int, max_width: int) -> ImageFont.FreeTypeFont:
    path = FONTS / "BarlowCondensed-Black.ttf"
    size = wanted
    while size > 48:
        f = ImageFont.truetype(str(path), size)
        if f.getlength(text) <= max_width:
            return f
        size -= 3
    return ImageFont.truetype(str(path), size)


def render_line(text: str, font: ImageFont.FreeTypeFont, fill) -> Image.Image:
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    width = probe.textlength(text, font=font)
    ascent, descent = font.getmetrics()
    layer = Image.new("RGBA", (round(width) + 44, ascent + descent + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text((28, 22), text, font=font, fill=(20, 14, 16, 200),
           stroke_width=11, stroke_fill=(20, 14, 16, 120))
    d.text((22, 14), text, font=font, fill=fill, stroke_width=6, stroke_fill=INK + (255,))
    box = layer.getchannel("A").getbbox()
    return layer.crop(box) if box else layer


def build_captions() -> list[dict]:
    out = []
    for i, (a, b, first, second) in enumerate(CAPTIONS):
        final = i == len(CAPTIONS) - 1
        out.append({
            "first": render_line(first, font_for(first, 122, 972), CREAM + (255,)),
            "second": render_line(second, font_for(second, 118 if not final else 74,
                                                   964), GOLD + (255,)),
        })
    return out


def shot_for(t: float):
    for start, end, fn in SHOTS:
        if start <= t < end:
            return fn, start, end
    start, end, fn = SHOTS[-1]
    return fn, start, end


class Reel3D:
    def __init__(self) -> None:
        self.r = Raster(RW, RH, fov=0.8)
        self.captions = build_captions()
        self.tag_font = ImageFont.truetype(
            str(FONTS / "BarlowCondensed-Bold.ttf"), 30)
        self.title1 = ImageFont.truetype(
            str(FONTS / "BarlowCondensed-Black.ttf"), 132)
        self.title2 = ImageFont.truetype(
            str(FONTS / "BarlowCondensed-Black.ttf"), 128)
        rng = np.random.default_rng(11)
        self.grain = rng.normal(0, 5.2, (H, W, 1)).repeat(3, axis=2).astype(np.int16)

    def frame(self, t: float) -> Image.Image:
        fn, start, end = shot_for(t)
        p = (t - start) / (end - start)
        meshes, opts = fn(t, p)
        env = opts["env"]
        self.r.camera(*opts["cam"], fov=env["fov"])
        self.r.environment(env["sun"], env["sun_colour"], env["ambient"], env["ground"],
                           env["fog"], env["fog_density"], env["exposure"],
                           env["night"], env["moon"], env["shadow"])
        small = Image.fromarray(self.r.render(meshes))
        im = small.resize((W, H), Image.Resampling.BICUBIC)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.4, percent=42, threshold=2))
        arr = np.asarray(im).astype(np.int16)
        arr = np.clip(arr + self.grain, 0, 255).astype(np.uint8)
        im = Image.fromarray(arr)
        self.overlay(im, t)
        return im

    # ------------------------------------------------------------------ 2D layer
    def overlay(self, im: Image.Image, t: float) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        d.text((54, 104), "MONARCHVOICE  /  SURVIVAL FILE 01  /  3D",
               font=self.tag_font, fill=(255, 226, 171, 236),
               stroke_width=2, stroke_fill=(21, 20, 23, 190))
        d.rounded_rectangle((54, 166, 1026, 173), radius=3, fill=(255, 246, 220, 76))
        d.rounded_rectangle((54, 166, 54 + max(7, round(972 * t / DURATION)), 173),
                            radius=3, fill=GOLD + (235,))

        if t < 3.52:
            fade = min(1.0, t / 0.18, (3.52 - t) / 0.24)
            if fade > 0:
                layer = Image.new("RGBA", (W, 520), (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                for text, y, font, col in (("KYA TUM", 10, self.title1, CREAM),
                                           ("BACH PATE?", 148, self.title2, GOLD)):
                    w = ld.textlength(text, font=font)
                    ld.text((W / 2 - w / 2 + 6, y + 8), text, font=font,
                            fill=(20, 14, 16, 200), stroke_width=11,
                            stroke_fill=(20, 14, 16, 120))
                    ld.text((W / 2 - w / 2, y), text, font=font, fill=col + (255,),
                            stroke_width=6, stroke_fill=INK + (255,))
                layer.putalpha(layer.getchannel("A").point(lambda a: round(a * fade)))
                im.paste(layer, (0, 322 + round(26 * (1 - fade))), layer.getchannel("A"))
        elif 6.40 <= t < 8.35:
            fade = min(1.0, (t - 6.40) / 0.22, (8.35 - t) / 0.20)
            if fade > 0:
                text = "TEAMWORK"
                font = font_for(text, 178, 974)
                layer = Image.new("RGBA", (W, 210), (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                w = ld.textlength(text, font=font)
                ld.text((W / 2 - w / 2 + 6, 8), text, font=font, fill=(20, 14, 16, 200),
                        stroke_width=11, stroke_fill=(20, 14, 16, 120))
                ld.text((W / 2 - w / 2, 0), text, font=font, fill=GOLD + (255,),
                        stroke_width=6, stroke_fill=INK + (255,))
                layer.putalpha(layer.getchannel("A").point(lambda a: round(a * fade)))
                im.paste(layer, (0, 292), layer.getchannel("A"))

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
                d = ImageDraw.Draw(im, "RGBA")
                bar_w = 560 * swipe
                bar_y = 1590 + art["second"].height - 6
                d.rounded_rectangle((W / 2 - bar_w / 2, bar_y,
                                     W / 2 + bar_w / 2, bar_y + 7),
                                    radius=4, fill=GOLD + (150,))
            break


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0, help="first frame index")
    ap.add_argument("--end", type=int, default=FPS * DURATION)
    ap.add_argument("--segment", type=Path, help="write this frame range to a segment mp4")
    args = ap.parse_args()
    reel = Reel3D()
    seg = args.segment
    if seg is None:
        BUILD.mkdir(parents=True, exist_ok=True)
        seg = BUILD / f"seg_{args.start:04d}.mp4"
    import shutil
    ff = shutil.which("ffmpeg")
    if not ff:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    seg.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
           "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", str(seg)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert proc.stdin is not None
        for n in range(args.start, args.end):
            proc.stdin.write(reel.frame(n / FPS).tobytes())
            if (n - args.start) % 48 == 0:
                print(f"3D frame {n}/{args.end}", flush=True)
        proc.stdin.close()
        assert proc.stderr is not None
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError(err)
    except BaseException:
        proc.kill()
        raise
    print(f"Wrote {seg}")


if __name__ == "__main__":
    main()
