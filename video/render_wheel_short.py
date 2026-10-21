#!/usr/bin/env python3
"""Render an original, silent 10-second prehistoric cartoon about a rolling wheel.

Install: python3 -m pip install -r video/requirements.txt
Run:     python3 video/render_wheel_short.py
Preview: python3 video/render_wheel_short.py --frame-at 6.5 --frame-output /tmp/wheel.png

The animation combines generated original illustration plates with hand-drawn,
procedurally animated props, particles, motion accents and timed subtitles.
It does not reuse frames from the reference fire video.
"""

from __future__ import annotations

import argparse
import math
import random
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
OUT = HERE / "Gol_Pahiye_Ka_Kamaal_10s_Silent.mp4"
W, H, FPS, SECONDS = 1280, 720, 24, 10
SCALE = Image.Resampling.LANCZOS


def smooth(a: float, b: float, x: float) -> float:
    p = max(0.0, min(1.0, (x - a) / (b - a)))
    return p * p * (3 - 2 * p)


def keyed_sprite(path: Path, height: int) -> Image.Image:
    """Turn a nearly-white generated sprite plate into a soft-edged RGBA layer."""
    src = Image.open(path).convert("RGB")
    r, g, b = src.split()
    low = ImageChops.darker(r, ImageChops.darker(g, b))
    high = ImageChops.lighter(r, ImageChops.lighter(g, b))
    darkness = ImageOps.invert(low)
    saturation = ImageChops.subtract(high, low)
    dark_lut = [max(0, min(255, round((v - 11) * 255 / 19))) for v in range(256)]
    sat_lut = [max(0, min(255, round((v - 8) * 255 / 15))) for v in range(256)]
    alpha = ImageChops.lighter(darkness.point(dark_lut), saturation.point(sat_lut))
    src.putalpha(alpha)
    box = alpha.getbbox()
    if box is None:
        raise ValueError(f"Empty character sprite: {path}")
    src = src.crop(box)
    return src.resize((round(src.width * height / src.height), height), SCALE)


def draw_stone() -> Image.Image:
    im = Image.new("RGBA", (188, 170), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    d.ellipse((12, 151, 181, 169), fill=(48, 40, 37, 64))
    points = [(24, 41), (69, 17), (144, 21), (173, 55), (167, 142),
              (132, 155), (32, 152), (12, 115)]
    d.polygon(points, fill=(172, 140, 103, 255))
    d.polygon([(24, 41), (69, 17), (144, 21), (119, 47), (45, 58)], fill=(210, 181, 138, 255))
    d.polygon([(144, 21), (173, 55), (167, 142), (132, 155), (125, 52)], fill=(126, 100, 81, 255))
    d.polygon([(45, 58), (119, 47), (125, 52), (132, 155), (32, 152), (12, 115), (24, 41)],
              fill=(185, 151, 113, 255))
    d.line(points + [points[0]], fill=(42, 36, 33, 255), width=4, joint="curve")
    for path in ([(45, 58), (119, 47), (144, 21)], [(119, 47), (132, 155)],
                 [(43, 82), (37, 103), (47, 116)], [(77, 58), (74, 88), (86, 103)],
                 [(94, 118), (99, 140)], [(141, 66), (147, 96), (142, 110)]):
        d.line(path, fill=(73, 59, 48, 195), width=2, joint="curve")
    rng = random.Random(99)
    for _ in range(72):
        x = rng.randrange(36, 155)
        y = rng.randrange(64, 139)
        d.line((x, y, x + rng.randrange(2, 8), y - 1),
               fill=(91, 72, 54, rng.randrange(30, 80)), width=1)
    return im


def draw_wheel() -> Image.Image:
    """Wooden disc with inked rings. Rotation is animated in the main loop."""
    im = Image.new("RGBA", (192, 192), (0, 0, 0, 0))
    d = ImageDraw.Draw(im, "RGBA")
    cx = cy = 96
    rng = random.Random(4)
    coords = []
    for i in range(90):
        a = 2 * math.pi * i / 90
        r = 70 + 2.4 * math.sin(5 * a + 0.2) + 1.4 * math.sin(13 * a)
        coords.append((round(cx + r * math.cos(a)), round(cy + r * math.sin(a))))
    d.polygon(coords, fill=(151, 95, 51, 255))
    d.line(coords + [coords[0]], fill=(39, 32, 27, 255), width=5, joint="curve")
    d.ellipse((36, 36, 156, 156), fill=(196, 134, 76, 255), outline=(55, 39, 29, 255), width=3)
    d.arc((45, 42, 148, 151), 35, 281, fill=(237, 181, 105, 235), width=7)
    for radius, start, end in ((51, 13, 232), (43, 192, 451), (32, 35, 246)):
        box = (cx - radius, cy - radius, cx + radius, cy + radius)
        d.arc(box, start, end, fill=(106, 65, 41, 178), width=3)
    for a in (0.12, 2.23, 4.36):
        d.line((cx, cy, cx + 55 * math.cos(a), cy + 55 * math.sin(a)),
               fill=(93, 56, 36, 115), width=4)
    d.ellipse((84, 84, 108, 108), fill=(102, 65, 43, 255), outline=(40, 33, 26, 255), width=3)
    d.ellipse((91, 89, 97, 95), fill=(235, 189, 118, 160))
    for _ in range(60):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(18, 57)
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        d.line((x, y, x + 3, y - 2), fill=(83, 56, 40, rng.randrange(35, 95)), width=1)
    return im


CUES = [
    (0.0, 2.8, "A square stone won't budge.", "Chaukora pathar hilta hi nahi!"),
    (2.8, 5.1, "Then a round piece of wood rolls by...", "Phir gol lakri nazar aayi..."),
    (5.1, 7.6, "One push, and away it goes!", "Ek dhakka... aur chal pari!"),
    (7.6, 10.0, "Wait! Who's going to stop it?", "Ab isay rokay ga kaun?!"),
]


def caption_layers() -> list[Image.Image]:
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    en = ImageFont.truetype(font, 21)
    ur = ImageFont.truetype(font.replace(".ttf", "-Bold.ttf"), 29)
    layers = []
    for _, _, english, roman_urdu in CUES:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for text, fnt, y, sw in ((english, en, 618, 2), (roman_urdu, ur, 651, 3)):
            d.text((W // 2 + 2, y + 2), text, anchor="ma", font=fnt,
                   fill=(31, 23, 20, 115), stroke_width=sw + 2,
                   stroke_fill=(31, 23, 20, 75))
            d.text((W // 2, y), text, anchor="ma", font=fnt,
                   fill=(252, 245, 225, 255), stroke_width=sw,
                   stroke_fill=(28, 26, 27, 255))
        layers.append(layer)
    return layers


class Animation:
    def __init__(self):
        def plate(name: str) -> Image.Image:
            bg = Image.open(ASSETS / name).convert("RGB")
            bg = ImageOps.fit(bg, (W - 32, H - 30), method=SCALE)
            canvas = Image.new("RGB", (W, H), (232, 217, 190))
            mask = Image.new("L", bg.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, bg.width - 1, bg.height - 1),
                                                    radius=11, fill=255)
            canvas.paste(bg, (16, 14), mask)
            ImageDraw.Draw(canvas).rounded_rectangle((15, 13, W - 16, H - 16),
                                                     radius=12, outline=(55, 49, 47), width=2)
            return canvas

        self.background_a = plate("wheel_landscape.png")
        self.background_b = plate("wheel_path.png")
        self.push = keyed_sprite(ASSETS / "caveperson_push.png", 277)
        self.notice = keyed_sprite(ASSETS / "caveperson_notice.png", 289)
        self.run = keyed_sprite(ASSETS / "caveperson_run.png", 273)
        self.stone = draw_stone()
        self.wheel = draw_wheel()
        self.captions = caption_layers()

    @staticmethod
    def paste_at(im: Image.Image, sprite: Image.Image, x: float, foot_y: float,
                 opacity: float = 1.0) -> None:
        if opacity <= 0:
            return
        if opacity < 0.999:
            sprite = sprite.copy()
            sprite.putalpha(sprite.getchannel("A").point(lambda a: round(a * opacity)))
        im.paste(sprite, (round(x), round(foot_y - sprite.height)), sprite.getchannel("A"))

    @staticmethod
    def wheel_x(t: float) -> float:
        if t < 3.04:
            return 1500
        if t < 5.08:
            return 1370 - 525 * smooth(3.04, 5.08, t)
        if t < 7.45:
            p = (t - 5.08) / (7.45 - 5.08)
            return 845 + 266 * p * p
        return 1111 + 130 * (t - 7.45)

    def frame(self, t: float) -> Image.Image:
        # A motivated cut follows the rolling disc farther down the same path.
        im = (self.background_a if t < 5.12 else self.background_b).copy()
        d = ImageDraw.Draw(im, "RGBA")

        # The stubborn angular stone stays behind in the establishing shot.
        shake = 3 * math.sin(25 * t) * (1 - smooth(2.35, 2.9, t)) if t < 2.9 else 0
        rock_x = 648 + (9 * smooth(0.4, 2.25, t)) + shake
        if t < 5.12:
            im.paste(self.stone, (round(rock_x), 419), self.stone.getchannel("A"))
        if t < 2.8:
            # Impact/huff marks and sweat emphasize the futile physical effort.
            for j in range(3):
                yy = 463 + j * 18 + 3 * math.sin(9 * t + j)
                d.arc((rock_x + 171 + j * 12, yy - 11, rock_x + 192 + j * 12, yy + 11),
                      110, 245, fill=(58, 50, 46, 200), width=2)
            if t > 0.6:
                for j in range(3):
                    p = (t * 1.4 + j / 3) % 1
                    x = 536 + 22 * p + j * 8
                    y = 343 + 33 * p - 19 * math.sin(p * math.pi)
                    d.ellipse((x, y, x + 5, y + 9), fill=(227, 230, 216, 200),
                              outline=(57, 63, 61, 180), width=1)

        # A small stationary contact shadow keeps the cut-out character grounded.
        if t < 2.75:
            x = 225 + 2.8 * math.sin(t * 12)
            d.ellipse((x + 38, 571, x + 323, 595), fill=(47, 35, 31, 45))
            bob = 3 * math.sin(17 * t) * (1 - smooth(2.2, 2.7, t))
            self.paste_at(im, self.push, x, 590 + bob)
        elif t < 5.12:
            x = 474 + 6 * smooth(3.7, 4.6, t)
            d.ellipse((x + 12, 573, x + 152, 593), fill=(47, 35, 31, 44))
            self.paste_at(im, self.notice, x, 589 + 1.5 * math.sin(t * 4.7))
            if 3.9 < t < 5.04:
                p = min(1.0, (t - 3.9) * 4)
                # Hand-drawn idea spark, not a misleading historical claim.
                sx, sy = x + 162, 287
                for a in (0, 0.8, 1.7, 2.5, 3.55, 4.45, 5.2):
                    dx, dy = math.cos(a), math.sin(a)
                    d.line((sx + 15 * dx, sy + 15 * dy,
                            sx + (20 + 7 * p) * dx, sy + (20 + 7 * p) * dy),
                           fill=(255, 219, 122, round(205 * p)), width=3)
                d.ellipse((sx - 5, sy - 5, sx + 5, sy + 5), fill=(255, 219, 122, round(225 * p)))
        elif t < 7.45:
            x = self.wheel_x(t) - 498
            d.ellipse((x + 40, 576, x + 336, 594), fill=(47, 35, 31, 40))
            self.paste_at(im, self.push, x, 592 + 3 * math.sin(16 * t))
        else:
            x = self.wheel_x(t) - 505
            bob = 6 * math.sin(17 * t)
            d.ellipse((x + 48, 576, x + 328, 593), fill=(47, 35, 31, 39))
            self.paste_at(im, self.run, x, 590 + bob)
            for j in range(2):
                q = (t * 3 + j / 2) % 1
                xx, yy = x + 70 - q * 45, 569 - q * 9
                d.arc((xx - 18, yy - 9, xx + 18, yy + 9), 160, 352,
                      fill=(74, 64, 54, 195), width=2)

        if 3.04 <= t < 10:
            cx = self.wheel_x(t)
            # Irregular ring rotates at a speed proportional to its travel.
            travel = (1370 - cx) if t < 5.08 else (1370 - 845) - (cx - 845)
            angle = travel / 70 * 180 / math.pi
            wheel = self.wheel.rotate(angle, resample=Image.Resampling.BICUBIC)
            wheel_y = 523 + 2 * math.sin(angle * math.pi / 90)
            d.ellipse((cx - 70, 575, cx + 66, 593), fill=(55, 39, 30, 51))
            im.paste(wheel, (round(cx - 96), round(wheel_y - 96)), wheel.getchannel("A"))
            if t > 5.4:
                for j in range(3):
                    trail = (t * 2.7 + j * 0.38) % 1
                    px = cx - 104 - 30 * trail
                    py = 514 - 24 * j + 2 * math.sin(12 * t)
                    d.arc((px - 16, py - 9, px + 15, py + 9), 145, 346,
                          fill=(43, 39, 35, round(195 * (1 - trail))), width=2)
            if t > 6.2:
                for j in range(11):
                    age = (t * 3.8 + j * 0.37) % 1
                    dx = 82 + (j % 5) * 12 + age * 40
                    dy = (j % 4) * 8 + 22 * age
                    r = 3 + (j % 3) * 3 + 9 * age
                    d.ellipse((cx - dx - r, 583 - dy - r, cx - dx + r, 583 - dy + r),
                              fill=(202, 168, 124, round(115 * (1 - age))))

        for index, (start, end, _, _) in enumerate(CUES):
            if start <= t < end:
                fade = min(1.0, (t - start) / 0.13, (end - t) / 0.13)
                cap = self.captions[index]
                if fade < 0.999:
                    cap = cap.copy()
                    cap.putalpha(cap.getchannel("A").point(lambda a: round(a * max(0, fade))))
                im.paste(cap, (0, 0), cap.getchannel("A"))
                break
        return im


def ffmpeg_binary() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError("Install video/requirements.txt for the bundled ffmpeg") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--frame-at", type=float, help="Render only this timestamp to a PNG")
    parser.add_argument("--frame-output", type=Path, help="PNG path for --frame-at")
    args = parser.parse_args()
    animation = Animation()
    if args.frame_at is not None:
        if not 0 <= args.frame_at < SECONDS:
            parser.error("--frame-at must be in [0, 10)")
        path = args.frame_output or Path("/tmp/wheel-preview.png")
        animation.frame(args.frame_at).save(path)
        print(path)
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg_binary(), "-hide_banner", "-loglevel", "error", "-y",
               "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-an",
               "-c:v", "libx264", "-preset", "medium", "-crf", "19",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(args.output)]
    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert proc.stdin is not None
        for n in range(FPS * SECONDS):
            proc.stdin.write(animation.frame(n / FPS).tobytes())
        proc.stdin.close()
        assert proc.stderr is not None
        stderr = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr}")
    except BaseException:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.kill()
        proc.wait()
        raise
    print(f"Rendered {args.output} ({SECONDS}s, {W}x{H}, {FPS} fps, no audio)")


if __name__ == "__main__":
    main()
