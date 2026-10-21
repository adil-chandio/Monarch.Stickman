#!/usr/bin/env python3
"""Render the 30-second, vertical Ancient Survival Easy Urdunglish reel.

This version animates real characters: an illustrated sprite rig supplies
walk-cycle poses, a berry-picking loop, a knapping strike, a pointing beat and
seated campfire poses, which the renderer times, bobs, leans and lights. The
backgrounds themselves are empty plates, so no character is ever a frozen part
of a painting. All illustrations, motion, music and SFX are generated for this
project; nothing is taken from the reference video.

    python3 -m pip install -r video/ancient_survival/requirements.txt
    python3 video/ancient_survival/render_reel.py

    # Art-direction check of a single frame:
    python3 video/ancient_survival/render_reel.py --frame-at 16 --frame-output /tmp/fire.png
"""

from __future__ import annotations

import argparse
import math
import random
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from compose_audio import create_mix
from sprites import ASSETS, load_rig, put, shaded, shadow

HERE = Path(__file__).resolve().parent
REPO_VIDEO = HERE.parent
FONTS = HERE / "fonts"
BUILD = HERE / "_build"
FINAL = REPO_VIDEO / "Ancient_Survival_Easy_Urdunglish_30s_Reel.mp4"
W, H, FPS, DURATION = 1080, 1920, 24, 30
PLATE = (1220, 2166)  # overscan used for background parallax and zooms
CREAM = (255, 246, 220)
GOLD = (255, 187, 93)
INK = (34, 29, 32)
CAPTION_Y = 1497


@dataclass(frozen=True)
class Scene:
    start: float
    end: float
    image: str
    zoom: float
    centre0: tuple[int, int]
    centre1: tuple[int, int]


SCENES = [
    Scene(0.00, 6.40, "night", 1.00, (604, 980), (620, 1030)),
    Scene(6.40, 11.50, "clearing", 1.00, (610, 1040), (596, 1080)),
    Scene(11.50, 13.35, "clearing", 1.42, (600, 1440), (612, 1470)),
    Scene(13.35, 14.92, "mudbank", 1.10, (610, 1300), (624, 1330)),
    Scene(14.92, 18.48, "camp", 1.62, (566, 1330), (566, 1306)),
    Scene(18.48, 22.67, "path", 1.12, (700, 1180), (612, 1200)),
    Scene(22.67, 25.50, "clearing", 1.12, (620, 1180), (600, 1216)),
    Scene(25.50, 27.65, "path", 1.22, (600, 1240), (648, 1232)),
    Scene(27.65, 30.00, "camp", 1.62, (566, 1326), (566, 1298)),
]
CUTS = [scene.start for scene in SCENES[1:]]

# Timings follow the chosen narrator's real pauses, measured in his WAV.
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
# Multiplane foreground: near-camera elements that create real parallax and
# depth-of-field. They sit below the captions and above the characters.
FOREGROUND = {
    "clearing": ("fg_grass", 0.08, 1.010, 0.62, 0.0, 1.45),
    "path": ("fg_grass", 0.94, 1.008, 0.56, 2.1, 1.45),
    "mudbank": ("fg_grass", 0.05, 1.012, 0.50, 4.2, 1.35),
    "night": ("fg_bush", 0.95, 1.006, 0.56, 1.3, 1.55),
    "camp": ("fg_bush", 0.04, 1.010, 0.52, 3.4, 1.45),
}

BERRY_BEATS = [8.4 + i * 0.62 for i in range(6)] + [23.5, 24.1, 24.7]
STRICKES = (11.63, 12.02, 12.55, 12.96, 13.18)


def ease(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def punch(x: float) -> float:
    """Fast-out, slow-settle easing for snappy character accents."""
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def back_out(x: float, overshoot: float = 1.9) -> float:
    """Small overshoot so kinetic type and punches feel physical, not linear."""
    x = min(1.0, max(0.0, x)) - 1
    return 1 + x * x * ((overshoot + 1) * x + overshoot)


def render_line(text: str, font: ImageFont.FreeTypeFont, fill: tuple[int, ...],
                stroke: int) -> Image.Image:
    """Draw one caption line with its ink shadow, tightly cropped for motion."""
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    width = probe.textlength(text, font=font)
    ascent, descent = font.getmetrics()
    layer = Image.new("RGBA", (round(width) + 44, ascent + descent + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.text((22 + 6, 14 + 8), text, font=font, fill=(20, 14, 16, 200),
           stroke_width=stroke + 5, stroke_fill=(20, 14, 16, 120))
    d.text((22, 14), text, font=font, fill=fill,
           stroke_width=stroke, stroke_fill=INK + (255,))
    box = layer.getchannel("A").getbbox()
    return layer.crop(box) if box else layer


def font_for(text: str, wanted: int, max_width: int, black: bool = True) -> ImageFont.FreeTypeFont:
    name = "BarlowCondensed-Black.ttf" if black else "BarlowCondensed-Bold.ttf"
    path = FONTS / name
    size = wanted
    while size > 55:
        f = ImageFont.truetype(str(path), size)
        if f.getlength(text) <= max_width:
            return f
        size -= 3
    return ImageFont.truetype(str(path), size)


def text_center(d: ImageDraw.ImageDraw, text: str, y: int,
                font: ImageFont.FreeTypeFont, fill: tuple[int, ...],
                stroke: int = 0) -> None:
    x = W // 2
    d.text((x + 6, y + 8), text, font=font, anchor="mt",
           fill=(20, 14, 16, 205), stroke_width=stroke + 5,
           stroke_fill=(20, 14, 16, 125))
    d.text((x, y), text, font=font, anchor="mt", fill=fill,
           stroke_width=stroke, stroke_fill=INK + (255,))


def caption_patch(first: str, second: str, final: bool = False) -> dict:
    """Two independently animated type layers, so each can fly in on its own."""
    f1 = font_for(first, 122 if not final else 128, 972)
    f2 = font_for(second, 118 if not final else 74, 964)
    art = {
        "first": render_line(first, f1, CREAM + (255,), 6),
        "second": render_line(second, f2, GOLD + (255,), 6 if not final else 4),
        "y1": 16,
        "y2": 128 if not final else 152,
    }
    return art


def vignette() -> Image.Image:
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for y in range(H):
        bottom = ease((y - 1150) / 600) * 186
        top = (1 - ease(y / 390)) * 96
        a = round(max(top, bottom))
        if a:
            d.line((0, y, W, y), fill=(18, 15, 21, a), width=1)
    return overlay


def film_grain() -> Image.Image:
    """A static, very low-contrast grain tile: analogue texture, cheap to paste."""
    rng = random.Random(1904)
    small = Image.new("L", (270, 480))
    small.putdata([rng.randint(104, 152) for _ in range(270 * 480)])
    tile = small.resize((W + 120, H + 120), Image.Resampling.BILINEAR)
    grain = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    grain.putalpha(tile.point(lambda v: max(0, abs(v - 128) - 2) // 3))
    return grain


def glow(size: int = 780) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for r in range(size // 2 - 8, 18, -4):
        a = round((1 - r / (size / 2)) ** 1.5 * 46)
        if a:
            d.ellipse((size // 2 - r, size // 2 - r,
                       size // 2 + r, size // 2 + r),
                      fill=(255, 146, 52, a))
    return layer


def flame_tongue(d: ImageDraw.ImageDraw, cx: float, base_y: float, width: float,
                 height: float, sway: float, colour: tuple[int, int, int]) -> None:
    """A solid teardrop flame built from stacked ellipses along a curved spine."""
    steps = 13
    for k in range(steps):
        u = k / (steps - 1)
        y = base_y - height * u
        x = cx + sway * (u ** 1.6)
        r = width * (1 - u) ** 0.72 * (0.55 + 0.45 * math.sin(math.pi * u) ** 0.4)
        if r < 0.8:
            continue
        d.ellipse((x - r, y - r * 1.35, x + r, y + r * 0.75), fill=colour + (255,))


def fire(im: Image.Image, cx: float, cy: float, t: float, scale: float = 1.0,
         glow_layer: Image.Image | None = None) -> None:
    """Stylised hand-drawn campfire: glow, crossed logs, layered flame, embers."""
    if glow_layer is not None:
        g = glow_layer.copy()
        pulse = 0.72 + 0.26 * math.sin(t * 9.3) + 0.09 * math.sin(t * 21)
        g.putalpha(g.getchannel("A").point(lambda a: min(255, round(a * pulse))))
        size = round(g.width * scale)
        g = g.resize((size, size), Image.Resampling.BILINEAR)
        im.paste(g, (round(cx - size / 2), round(cy - size / 2)), g.getchannel("A"))
    d = ImageDraw.Draw(im, "RGBA")
    # two crossed logs with rounded ends, drawn behind the flame
    for angle, colour, width in ((-0.13, (78, 49, 31), 26), (0.16, (108, 70, 43), 24)):
        dx, dy = math.cos(angle) * 104 * scale, math.sin(angle) * 104 * scale
        d.line((cx - dx, cy + 26 * scale - dy, cx + dx, cy + 26 * scale + dy),
               fill=colour + (255,), width=round(width * scale))
        for sign in (-1, 1):
            ex, ey = cx + sign * dx, cy + 26 * scale + sign * dy
            r = width * scale / 2
            d.ellipse((ex - r, ey - r, ex + r, ey + r), fill=colour + (255,))
    flame_tongue(d, cx, cy + 30 * scale, 42 * scale, 128 * scale,
                 -10 * scale, (206, 87, 32))
    outer = 5
    for i in range(outer):
        phase = t * (4.6 + i * 0.55) + i * 2.1
        flame_tongue(d, cx + (i - (outer - 1) / 2) * 15 * scale, cy + 26 * scale,
                     (21 + 6 * math.sin(phase)) * scale,
                     (104 + 30 * math.sin(phase * 0.9 + 1)) * scale,
                     14 * math.sin(phase * 0.8 + i) * scale, (243, 132, 40))
    for i in range(4):
        phase = t * (5.7 + i * 0.5) + i * 1.7
        flame_tongue(d, cx + (i - 1.5) * 12 * scale, cy + 24 * scale,
                     (13 + 4 * math.sin(phase)) * scale,
                     (70 + 22 * math.sin(phase * 1.1)) * scale,
                     10 * math.sin(phase + i) * scale, (255, 182, 64))
    for i in range(3):
        phase = t * (6.9 + i * 0.6) + i
        flame_tongue(d, cx + (i - 1) * 9 * scale, cy + 22 * scale,
                     (8 + 2.5 * math.sin(phase)) * scale,
                     (38 + 14 * math.sin(phase * 1.3)) * scale,
                     6 * math.sin(phase) * scale, (255, 238, 184))
    for j in range(14):
        drift = (t * (72 + j % 5 * 14) + j * 63) % (340 * scale)
        x = cx + sway_of(j, t) * (drift / (340 * scale))
        y = cy - 40 * scale - drift
        r = (1.8 + j % 3) * scale
        alpha = round(206 * (1 - drift / (340 * scale)) ** 1.5)
        d.ellipse((x - r, y - r, x + r, y + r),
                  fill=(255, 186 + j % 3 * 16, 92, alpha))
    for j in range(4):
        drift = (t * (42 + j * 8) + j * 137) % (430 * scale)
        r = (15 + drift * 0.07) * scale
        x = cx + 38 * math.sin(t * 0.7 + j) * scale
        y = cy - 110 * scale - drift
        d.ellipse((x - r, y - r * 0.8, x + r, y + r * 0.8),
                  fill=(104, 96, 104, round(46 * (1 - drift / (430 * scale)))))


def sway_of(j: int, t: float) -> float:
    return 60 * math.sin(t * 1.4 + j * 2.7)


class Reel:
    def __init__(self) -> None:
        self.plates = {
            key: ImageOps.fit(Image.open(ASSETS / f"{prefix}.png").convert("RGB"),
                              PLATE, method=Image.Resampling.LANCZOS)
            for key, prefix in (("night", "bg_night"), ("clearing", "bg_clearing"),
                                ("camp", "bg_camp"), ("path", "bg_path"),
                                ("mudbank", "bg_mudbank"))
        }
        from sprites import key_white

        self.fg = {
            name: Image.open(ASSETS / f"{name}.png").convert("RGB")
            for name in ("fg_grass", "fg_bush")
        }
        self.fg = {k: key_white(v) for k, v in self.fg.items()}
        self.fg = {
            k: ImageEnhance.Brightness(v).enhance(0.92 if k == "fg_bush" else 1.0)
            for k, v in self.fg.items()
        }
        rig = load_rig()
        self.lookout = rig["lookout"]
        self.woman = rig["woman"]
        self.pick = rig["pick"]
        self.elder = rig["elder"]
        self.sit = rig["lookout_sit"]
        self.woman_sit = rig["woman_sit"]

        runner = Image.open(REPO_VIDEO / "assets" / "caveperson_run.png").convert("RGB")
        from sprites import key_white

        runner = key_white(runner)
        height = 560
        runner = runner.resize((round(runner.width * height / runner.height), height),
                               Image.Resampling.LANCZOS)
        self.runner = shaded(runner, (52, 52, 74), 0.16)

        self.night_lookout = {k: shaded(v, (40, 42, 72), 0.34) for k, v in self.lookout.items()}
        self.night_woman = {k: shaded(v, (42, 42, 74), 0.35) for k, v in self.woman.items()}
        self.night_pick = {k: shaded(v, (42, 42, 74), 0.35) for k, v in self.pick.items()}
        self.night_elder = {k: shaded(v, (40, 42, 72), 0.33) for k, v in self.elder.items()}
        self.night_sit = {k: shaded(v, (62, 50, 64), 0.13, warm=0.30) for k, v in self.sit.items()}
        self.night_woman_sit = {k: shaded(v, (64, 51, 64), 0.12, warm=0.32)
                                for k, v in self.woman_sit.items()}

        self.captions = [caption_patch(a, b, i == len(CAPTIONS) - 1)
                         for i, (_, _, a, b) in enumerate(CAPTIONS)]
        self.vignette = vignette()
        self.fire_glow = glow()
        self.grain = film_grain()
        self.warm_grade = Image.new("RGB", (W, H), (255, 208, 150))
        self.cool_grade = Image.new("RGB", (W, H), (150, 175, 226))
        self.tag_font = ImageFont.truetype(str(FONTS / "BarlowCondensed-Bold.ttf"), 36)
        self.hook1 = ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), 157)
        self.hook2 = ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), 153)

    # ---------------------------------------------------------------- camera
    def scene(self, t: float) -> tuple[Image.Image, Scene, tuple[float, float]]:
        info = next((s for s in SCENES if s.start <= t < s.end), SCENES[-1])
        p = ease((t - info.start) / (info.end - info.start))
        cx = info.centre0[0] + (info.centre1[0] - info.centre0[0]) * p
        cy = info.centre0[1] + (info.centre1[1] - info.centre0[1]) * p
        # Every cut lands with a decaying punch-in, then breathes with a handheld
        # drift. Motion is always outward from the frame centre, never a lurch.
        since = t - info.start
        kick = math.exp(-since / 0.30)
        zoom = info.zoom * (1 + 0.075 * kick)
        shake = 9 * kick
        cx += shake * math.sin(46 * t) + 6 * math.sin(t * 0.63)
        cy += shake * 0.7 * math.cos(39 * t) + 4 * math.sin(t * 0.47 + 1.1)
        ww, wh = W / zoom, H / zoom
        x = round(min(PLATE[0] - ww, max(0.0, cx - ww / 2)))
        y = round(min(PLATE[1] - wh, max(0.0, cy - wh / 2)))
        plate = self.plates[info.image]
        crop = plate.crop((x, y, round(x + ww), round(y + wh)))
        im = crop.resize((W, H), Image.Resampling.LANCZOS)
        cam = (cx - info.centre0[0], cy - info.centre0[1])
        # A restrained grade separates the two "worlds" of the story.
        if info.image in ("night", "camp"):
            im = Image.blend(im, self.cool_grade, 0.050)
            im = ImageEnhance.Contrast(im).enhance(1.06)
        else:
            im = Image.blend(im, self.warm_grade, 0.070)
            im = ImageEnhance.Color(im).enhance(1.06)
            im = ImageEnhance.Contrast(im).enhance(1.04)
        return im, info, cam

    # ------------------------------------------------------------- animation
    def walk(self, rig: dict, x: float, foot_y: float, phase: float,
             scale: float = 1.0, angle: float = 0.0, step: float = 0.5) -> None:
        """Alternate the two painted stride poses with a weight-shift bob."""
        cycle = phase % 1.0
        pose = "walkB" if cycle >= step else "walkA"
        bob = 9 * abs(math.sin(math.pi * (cycle / step if cycle < step
                                          else (cycle - step) / (1 - step))))
        lean = angle + 2.2 * math.sin(2 * math.pi * phase)
        put(self.frame_im, rig[pose], x, foot_y - bob, angle=lean, scale=scale)

    def draw_clearing(self, t: float, callback: bool = False) -> None:
        im = self.frame_im
        if callback:
            shadow(im, 300, 1392, 215)
            shadow(im, 640, 1444, 225)
            shadow(im, 874, 1450, 195)
            sway = 1.5 * math.sin(t * 1.4)
            put(im, self.lookout["stand"], 300, 1392, angle=sway, scale=1.20)
            point = 1.0 + 0.03 * math.sin(t * 3.1)
            put(im, self.woman["point"], 640, 1444, angle=-1.2, scale=1.16 * point)
            # the elder has arrived with firewood; she shuffles a half-step on the spot
            phase = ((t - 22.67) * 1.35) % 1.0
            pose = "walkB" if phase >= 0.5 else "walkA"
            put(im, self.elder[pose], 874 + 8 * math.sin(t * 1.2),
                1450 - 5 * abs(math.sin(math.pi * phase)),
                angle=1.6 * math.sin(t * 1.7), scale=1.10)
            return
        shadow(im, 250, 1390, 215)
        shadow(im, 934, 1436, 225)
        shadow(im, 300, 1486, 200)
        # lookout scans the treeline, then takes one confident step forward
        step_out = punch((t - 9.55) / 0.55)
        lx = 250 + 36 * step_out
        if step_out <= 0:
            put(im, self.lookout["stand"], lx, 1390, angle=1.6 * math.sin(t * 1.25),
                scale=1.20)
        else:
            phase = ((t - 9.55) * 2.1) % 1.0
            pose = "walkB" if phase >= 0.5 else "walkA"
            put(im, self.lookout[pose], lx, 1390 - 6 * abs(math.sin(math.pi * phase)),
                angle=1.6 * math.sin(t * 1.25), scale=1.20)
        # berry picking loop: reach high, reach low, body sway, berries fall
        beat = (t - 6.4) % 1.24
        pose = "pickHigh" if beat < 0.62 else "pickLow"
        bend = 2.0 + 2.8 * math.sin(math.pi * min(1.0, beat / 0.62))
        put(im, self.pick[pose], 934, 1436, angle=bend, scale=1.16)
        d = ImageDraw.Draw(im, "RGBA")
        for i in range(3):
            age = ((t - 6.4) * 0.9 + i / 3) % 1.0
            bx = 934 + 92 + 10 * math.sin(t * 3 + i)
            by = 1300 + 140 * age
            d.ellipse((bx, by, bx + 7, by + 7), fill=(58, 40, 76, round(210 * (1 - age))))
        # the elder crosses the clearing carrying firewood
        if t >= 7.35:
            p = ease((t - 7.35) / 4.0)
            ex = 80 + 250 * p
            phase = ((t - 7.35) * 1.75) % 1.0
            if p < 1.0:
                pose_e = "walkB" if phase >= 0.5 else "walkA"
                put(im, self.elder[pose_e], ex,
                    1486 - 6 * abs(math.sin(math.pi * phase)), angle=1.2, scale=1.06)
            else:
                put(im, self.elder["walkA"], ex, 1486, angle=0.8, scale=1.06)

    def draw_tools(self, t: float) -> None:
        im = self.frame_im
        d = ImageDraw.Draw(im, "RGBA")
        # a hide spread of finished flakes and a fresh core beside the worker
        mat = [(300, 1352), (392, 1322), (506, 1316), (620, 1300), (724, 1302),
               (806, 1318), (846, 1362), (786, 1392), (662, 1400), (540, 1394),
               (412, 1398), (330, 1384)]
        d.polygon(mat, fill=(147, 111, 74, 236))
        d.line(mat + [mat[0]], fill=(66, 47, 33, 255), width=4, joint="curve")
        for fx, fy, sc in ((352, 1362, 1.05), (432, 1380, 0.9), (508, 1354, 0.95),
                           (700, 1352, 1.1), (766, 1378, 0.85)):
            d.polygon([(fx, fy - 20 * sc), (fx + 34 * sc, fy + 2 * sc),
                       (fx + 6 * sc, fy + 20 * sc), (fx - 26 * sc, fy + 4 * sc)],
                      fill=(176, 168, 152, 255), outline=(62, 54, 46, 255))
            d.line((fx - 4, fy - 10 * sc, fx + 16 * sc, fy + 8 * sc),
                   fill=(120, 113, 100, 255), width=2)
        strike = max((math.exp(-(t - s) / 0.085) for s in STRICKES if t >= s), default=0.0)
        shadow(im, 552, 1424, 330, alpha=90)
        put(im, self.lookout["work"], 552 - 6 * strike, 1424 - 8 * strike,
            angle=-2.0 * strike, scale=1.30)
        for j, beat in enumerate(STRICKES):
            age = t - beat
            if 0 < age < 0.34:
                for k in range(6):
                    angle = j * 0.9 + k * 1.45
                    dist = 22 + 250 * age * (0.45 + k / 6)
                    x = 626 + dist * math.cos(angle)
                    y = 1246 + dist * math.sin(angle) + 520 * age * age
                    r = max(1, round(7 - age * 12))
                    d.polygon([(x, y - r), (x + r, y + r), (x - r, y + r)],
                              fill=(255, 219, 150, round(190 * (1 - age / 0.34))))
        glint = 0.5 + 0.5 * math.sin(17 * t)
        d.line((620, 1216, 664, 1180), fill=(255, 240, 200, round(120 * glint)), width=4)

    def draw_mudbank(self, t: float) -> None:
        im = self.frame_im
        d = ImageDraw.Draw(im, "RGBA")
        # wet mud at the water's edge, with fresh cloven hoof tracks pressed in
        for mx, my, mrx, mry in ((566, 1340, 118, 44), (690, 1356, 104, 38),
                                 (792, 1330, 80, 32)):
            d.ellipse((mx - mrx, my - mry, mx + mrx, my + mry), fill=(98, 68, 47, 168))
        for hx, hy in ((556, 1332), (626, 1352), (700, 1336), (764, 1348), (808, 1318)):
            for side in (-1, 1):
                ox = hx + side * 10
                d.ellipse((ox - 8, hy - 14, ox + 8, hy + 14), fill=(54, 34, 24, 255))
                d.ellipse((ox - 5, hy - 9, ox + 5, hy + 9), fill=(80, 53, 36, 255))
            for side in (-1, 1):
                ox = hx + side * 13
                d.ellipse((ox - 4, hy + 18, ox + 4, hy + 25), fill=(54, 34, 24, 255))
        shadow(im, 286, 1442, 265)
        shadow(im, 886, 1430, 215)
        put(im, self.lookout["work"], 286, 1442, angle=1.0 * math.sin(t * 1.1), scale=1.22)
        reach = punch((t - 13.55) / 0.45)
        put(im, self.woman["point"], 886, 1430, angle=-1.6 - 2.6 * reach,
            scale=1.14 + 0.02 * reach)
        p = punch((t - 13.55) / 0.55)
        for i in range(7):
            a = p * (i / 7.0)
            x = 900 - 300 * a
            y = 1220 + 40 * a
            d.ellipse((x - 4, y - 4, x + 4, y + 4),
                      fill=(255, 196, 104, round(186 * p)))

    def draw_camp(self, t: float, ending: bool = False) -> None:
        im = self.frame_im
        # lookout sits behind the fire, occasionally poking the embers
        shadow(im, 552, 1144, 250, alpha=96)
        sitting = "tend" if 15.35 < t < 16.15 or 16.95 < t < 17.5 or t > 28.15 else "sit"
        put(im, self.night_sit[sitting], 552, 1148,
            angle=1.2 * math.sin(t * 1.6), scale=1.18)
        fire(im, 512, 1372, t, 1.34, self.fire_glow)
        # the woman kneels at the fire turning food on a stick
        turn = "turnB" if math.sin(t * 2.4) > 0 else "turnA"
        shadow(im, 846, 1420, 270, alpha=88)
        put(im, self.night_woman_sit[turn], 846, 1424, angle=1.0 * math.sin(t * 1.9),
            scale=1.18)
        # the elder warms her hands, both palms rubbing together slowly
        rub = 1.8 * math.sin(t * 5.2)
        shadow(im, 214, 1410, 255, alpha=88)
        put(im, self.night_elder["warm"], 214 + rub, 1414,
            angle=1.4 * math.sin(t * 1.35), scale=1.20)
        d = ImageDraw.Draw(im, "RGBA")
        flicker = 0.5 + 0.5 * math.sin(t * 7.4)
        # soft volumetric rays fanning up from the flames
        for k in range(7):
            angle = -1.9 + k * 0.30 + 0.05 * math.sin(t * 1.7 + k)
            length = 470 + 60 * math.sin(t * 2.1 + k)
            x2 = 512 + math.sin(angle) * length
            y2 = 1340 - math.cos(angle) * length
            d.polygon([(512 - 26, 1340), (512 + 26, 1340),
                       (x2 + 46, y2), (x2 - 46, y2)],
                      fill=(255, 172, 88, round(8 + 7 * flicker)))
        for box, base in (((356, 1016, 700, 1216), 26), ((700, 1190, 960, 1350), 22),
                          ((96, 1200, 350, 1360), 20)):
            d.ellipse(box, fill=(255, 154, 74, round(base + 12 * flicker)))
        if ending:
            for j in range(10):
                x = 110 + 96 * j + 14 * math.sin(t * 1.4 + j)
                y = 700 + (j * 137) % 470
                d.ellipse((x - 2, y - 2, x + 2, y + 2),
                          fill=(255, 217, 142, 128))

    def draw_path(self, t: float, tight: bool = False) -> None:
        im = self.frame_im
        base = 25.5 if tight else 18.48
        p = ease((t - base) / (2.15 if tight else 4.2))
        drift = (40 if tight else 66) * p
        trio = [
            (self.lookout, 452 + drift, 1362, 1.20, 0.0),
            (self.woman, 648 + drift, 1396, 1.16, 0.33),
            (self.elder, 822 + drift, 1434, 1.10, 0.62),
        ]
        d = ImageDraw.Draw(im, "RGBA")
        for rig, x, fy, sc, offset in trio:
            shadow(im, x, fy - 4, 196 * sc, alpha=58)
            phase = ((t - base) * 1.9 + offset) % 1.0
            pose = "walkB" if phase >= 0.5 else "walkA"
            bob = 10 * abs(math.sin(math.pi * (phase / 0.5 if phase < 0.5
                                               else (phase - 0.5) / 0.5)))
            put(im, rig[pose], x, fy - bob,
                angle=1.5 * math.sin(2 * math.pi * phase + offset), scale=sc)
            # dust kicked up right after each foot plants (contacts at 0 and 0.5)
            for contact in (0.0, 0.5):
                age = (phase - contact) % 1.0
                if age < 0.34:
                    r = 10 + 34 * age / 0.34
                    d.ellipse((x - 30 - r, fy - r * 0.45, x - 30 + r, fy + r * 0.45),
                              fill=(206, 174, 126, round(104 * (1 - age / 0.34))))
            if phase > 0.42:
                age = (phase - 0.42) / 0.3
                r = 8 + 24 * age
                d.ellipse((x - 66 - r, fy - r / 2, x - 66 + r, fy + r / 2),
                          fill=(196, 162, 114, round(88 * (1 - age))))

    # -------------------------------------------------------------- multiplane
    def dust_motes(self, t: float, key: str) -> None:
        """Lit particles drifting through the near plane: cheap, huge depth cue."""
        d = ImageDraw.Draw(self.frame_im, "RGBA")
        warm = key not in ("night", "camp")
        for i in range(22):
            speed = 11 + (i % 5) * 6
            x = (i * 197 + t * speed) % (W + 120) - 60
            y = (i * 331 + t * (6 + i % 4 * 4)) % (H - 420) + 240
            wobble = 14 * math.sin(t * 0.9 + i * 2.1)
            depth = 0.35 + 0.65 * ((i * 37) % 100) / 100
            r = 1.4 + 2.6 * depth
            alpha = round((30 + 46 * depth) * (0.7 + 0.3 * math.sin(t * 1.7 + i)))
            colour = (255, 232, 186) if warm else (206, 220, 244)
            d.ellipse((x + wobble - r, y - r, x + wobble + r, y + r),
                      fill=colour + (max(0, alpha),))

    def foreground(self, key: str, t: float, cam: tuple[float, float],
                   punch_in: float) -> None:
        """Near plane: larger, softly defocused, and parallaxing hardest."""
        spec = FOREGROUND.get(key)
        if not spec:
            return
        name, xf, yf, scale, phase, parallax = spec
        sprite = self.fg[name]
        wobble = 1.2 * math.sin(t * 0.85 + phase)
        grow = 1 + (punch_in - 1) * 0.65
        width = round(sprite.width * scale * grow)
        height = round(sprite.height * scale * grow)
        plane = sprite.resize((max(1, width), max(1, height)),
                              Image.Resampling.LANCZOS)
        # Depth of field: the near plane is out of focus while the cast stays sharp.
        plane = plane.filter(ImageFilter.GaussianBlur(radius=2.6))
        plane = ImageEnhance.Brightness(plane).enhance(0.86)
        alpha = plane.getchannel("A").point(lambda a: round(a * 0.92))
        plane.putalpha(alpha)
        x = W * xf - width / 2 + cam[0] * parallax + wobble
        y = H * yf - height + cam[1] * 0.35
        self.frame_im.paste(plane, (round(x), round(y)), plane.getchannel("A"))
        # A second, much closer silhouette clips the opposite corner so the
        # frame feels physically shot through foliage.
        corner = self.fg["fg_bush" if key not in ("night", "camp") else "fg_grass"]
        scale2 = 1.22
        cw, ch = round(corner.width * scale2), round(corner.height * scale2)
        near = corner.resize((cw, ch), Image.Resampling.LANCZOS)
        near = ImageEnhance.Brightness(near).enhance(0.50 if key in ("night", "camp") else 0.66)
        near = near.filter(ImageFilter.GaussianBlur(radius=5.0))
        near.putalpha(near.getchannel("A").point(lambda a: round(a * 0.72)))
        cx2 = W + 40 - cw * (0.58 if xf > 0.5 else 0.42) + cam[0] * 2.4
        cy2 = H + 150 - ch + cam[1] * 0.5
        self.frame_im.paste(near, (round(cx2 if xf > 0.5 else -40 - cw * 0.5),
                                  round(cy2)), near.getchannel("A"))

    # ---------------------------------------------------------------- plates
    def background_motion(self, im: Image.Image, key: str, t: float) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        if key == "camp":
            for i in range(6):
                x = ((i * 190 + t * (22 + i % 3 * 9)) % 1300) - 110
                y = 220 + (i * 143) % 300
                d.arc((x - 100, y - 10, x + 72, y + 18), 172, 344,
                      fill=(226, 220, 208, 30), width=2)
        if key == "clearing":
            for i in range(5):
                gx = 130 + i * 210 + 16 * math.sin(t * 0.8 + i)
                d.arc((gx - 26, 1580 - i * 12, gx + 30, 1602 - i * 12), 186, 352,
                      fill=(120, 96, 62, 66), width=3)
        if key == "path":
            for i in range(9):
                x = (i * 150 - t * 26) % 1240
                d.arc((x - 22, 1520 + (i * 47) % 260, x + 30, 1536 + (i * 47) % 260),
                      182, 352, fill=(150, 118, 78, 62), width=2)
        if key == "mudbank":
            shimmer = 0.5 + 0.5 * math.sin(t * 2.2)
            d.line((150, 1690, 640, 1666), fill=(196, 226, 236, round(48 + 40 * shimmer)),
                   width=3)

    # --------------------------------------------------------------- overlay
    def title(self, t: float) -> None:
        im = self.frame_im
        d = ImageDraw.Draw(im, "RGBA")
        d.text((60, 111), "MONARCHVOICE  /  SURVIVAL FILE 01",
               font=self.tag_font, fill=(255, 226, 171, 234),
               stroke_width=2, stroke_fill=(21, 20, 23, 190))
        d.rounded_rectangle((60, 178, 1018, 185), radius=3, fill=(255, 246, 220, 80))
        d.rounded_rectangle((60, 178, 60 + max(7, round(958 * t / DURATION)), 185),
                            radius=3, fill=GOLD + (235,))
        if t < 3.52:
            fade = min(1.0, t / 0.18, (3.52 - t) / 0.24)
            if fade > 0:
                layer = Image.new("RGBA", (W, 560), (0, 0, 0, 0))
                ld = ImageDraw.Draw(layer)
                text_center(ld, "KYA TUM", 12, self.hook1, CREAM + (255,), 6)
                text_center(ld, "BACH PATE?", 163, self.hook2, GOLD + (255,), 6)
                layer.putalpha(layer.getchannel("A").point(lambda a: round(a * fade)))
                im.paste(layer, (0, 318 + round(24 * (1 - fade))), layer.getchannel("A"))
        elif 6.40 <= t < 8.35:
            fade = min(1.0, (t - 6.40) / 0.22, (8.35 - t) / 0.20)
            if fade > 0:
                layer = Image.new("RGBA", (W, 210), (0, 0, 0, 0))
                text_center(ImageDraw.Draw(layer), "TEAMWORK", 0,
                            font_for("TEAMWORK", 185, 974), GOLD + (255,), 6)
                layer.putalpha(layer.getchannel("A").point(lambda a: round(a * fade)))
                im.paste(layer, (0, 294), layer.getchannel("A"))
        elif t >= 27.65:
            fade = ease((t - 27.65) / 0.36)
            layer = Image.new("RGBA", (W, 380), (0, 0, 0, 0))
            ld = ImageDraw.Draw(layer)
            text_center(ld, "SAATH HI", 5, font_for("SAATH HI", 157, 970),
                        CREAM + (255,), 6)
            text_center(ld, "SUPERPOWER HAI.", 150,
                        font_for("SUPERPOWER HAI.", 143, 970), GOLD + (255,), 6)
            layer.putalpha(layer.getchannel("A").point(lambda a: round(a * fade)))
            im.paste(layer, (0, 312), layer.getchannel("A"))

    def caption(self, t: float) -> None:
        """Word-level kinetic type: slide, overshoot, settle, then lift away."""
        im = self.frame_im
        for i, (start, end, _, _) in enumerate(CAPTIONS):
            if not start <= t < end:
                continue
            art = self.captions[i]
            enter = min(1.0, (t - start) / 0.24)
            leave = min(1.0, max(0.0, (end - t) / 0.17))
            if leave <= 0:
                return
            alpha = round(255 * min(1.0, enter * 1.5, leave * 1.25))
            pop = 1.0 + 0.06 * (1 - back_out(enter)) * (1 if enter < 1 else 0)
            for key, dx, delay in (("first", -84, 0.0), ("second", 84, 0.05)):
                layer = art[key]
                local = min(1.0, max(0.0, (t - start - delay) / 0.26))
                if local <= 0:
                    continue
                scale = (0.93 + 0.07 * back_out(local)) * pop
                wobble = 1.6 * math.sin(28 * t + i) * (1 - local)
                w = max(1, round(layer.width * scale))
                h = max(1, round(layer.height * scale))
                sprite = layer.resize((w, h), Image.Resampling.LANCZOS)
                if wobble:
                    sprite = sprite.rotate(wobble, resample=Image.Resampling.BICUBIC,
                                           expand=True)
                if alpha < 255:
                    sprite = sprite.copy()
                    sprite.putalpha(sprite.getchannel("A").point(
                        lambda a: round(a * alpha / 255)))
                offset = (1 - local) * dx
                lift = (1 - leave) * -26
                y = CAPTION_Y + art["y1" if key == "first" else "y2"] + lift
                im.paste(sprite, (round(W / 2 - sprite.width / 2 + offset), round(y)),
                         sprite.getchannel("A"))
            # A highlighter swipe under the second line lands with the beat.
            swipe = ease(min(1.0, max(0.0, (t - start - 0.08) / 0.26))) * leave
            if swipe > 0:
                d = ImageDraw.Draw(im, "RGBA")
                bar_w = 560 * swipe
                bar_y = CAPTION_Y + art["y2"] + art["second"].height - 6
                d.rounded_rectangle((W / 2 - bar_w / 2, bar_y, W / 2 + bar_w / 2,
                                     bar_y + 7), radius=4, fill=GOLD + (150,))
            return

    @staticmethod
    def transition(im: Image.Image, t: float) -> None:
        for cut in CUTS:
            distance = abs(t - cut)
            if distance < 0.115:
                power = (1 - distance / 0.115) ** 1.5
                d = ImageDraw.Draw(im, "RGBA")
                d.rectangle((0, 0, W, H), fill=(250, 222, 172, round(165 * power)))
                x = ((t - cut + 0.115) / 0.23) * (W + 400) - 220
                d.polygon([(x - 145, 0), (x - 102, 0), (x + 150, H),
                           (x + 106, H)], fill=(85, 62, 48, round(72 * power)))
                break

    def night_hook(self, t: float) -> None:
        im = self.frame_im
        d = ImageDraw.Draw(im, "RGBA")
        x = -520 + 250 * t
        if -self.runner.width < x < W:
            y = round(1520 + 8 * math.sin(14 * t))
            shadow(im, x + self.runner.width / 2, y, 230, alpha=70)
            put(im, self.runner, x + self.runner.width / 2, y,
                angle=2.4 * math.sin(13 * t))
        for i in range(4):
            age = ((t * 1.6 + i / 4) % 1.0)
            if age < 0.5:
                px = x + 40 - age * 120
                py = 1516 - age * 24
                r = 14 + 46 * age
                d.ellipse((px - r, py - r / 2, px + r, py + r / 2),
                          fill=(190, 182, 176, round(52 * (1 - age * 2))))
        # horizontal speed streaks sell the sprint without extra artwork
        for i in range(9):
            sy = 1240 + (i * 61) % 300
            age = (t * 2.6 + i * 0.17) % 1.0
            sx = x + 90 - age * 260
            length = 60 + 90 * (i % 3)
            d.line((sx, sy, sx + length, sy),
                   fill=(226, 222, 214, round(46 * (1 - age))), width=2)

    def frame(self, t: float) -> Image.Image:
        crop, info, cam = self.scene(t)
        self.frame_im = crop
        self.background_motion(crop, info.image, t)

        if info.image == "night":
            self.night_hook(t)
        elif info.image == "clearing":
            if 6.40 <= t < 11.50:
                self.draw_clearing(t)
            elif t < 13.35:
                self.draw_tools(t)
            else:
                self.draw_clearing(t, callback=True)
        elif info.image == "mudbank":
            self.draw_mudbank(t)
        elif info.image == "camp":
            self.draw_camp(t, ending=t >= 27.65)
        elif info.image == "path":
            self.draw_path(t, tight=t >= 25.5)

        punch_in = 1 + 0.075 * math.exp(-(t - info.start) / 0.30)
        self.foreground(info.image, t, cam, punch_in)
        self.dust_motes(t, info.image)
        crop.paste(self.vignette, (0, 0), self.vignette.getchannel("A"))
        gx = round((t * 7.3) % 60)
        gy = round((t * 11.7) % 60)
        crop.paste(self.grain.crop((gx, gy, gx + W, gy + H)), (0, 0),
                   self.grain.crop((gx, gy, gx + W, gy + H)).getchannel("A"))
        self.transition(crop, t)
        self.title(t)
        self.caption(t)
        return crop


def ffmpeg() -> str:
    result = shutil.which("ffmpeg")
    if result:
        return result
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise RuntimeError("Install video/ancient_survival/requirements.txt") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def render_video(reel: Reel, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        assert proc.stdin is not None
        for n in range(FPS * DURATION):
            proc.stdin.write(reel.frame(n / FPS).tobytes())
            if n % (FPS * 5) == 0:
                print(f"Visuals: {n // FPS:02d} / {DURATION}s", flush=True)
        proc.stdin.close()
        assert proc.stderr is not None
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg video encode failed: {err}")
    except BaseException:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        proc.kill()
        proc.wait()
        raise


def mux(video: Path, audio: Path, output: Path) -> None:
    cmd = [ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
           "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", "30", "-movflags", "+faststart", str(output)]
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-at", type=float, help="Render one frame as a preview PNG")
    parser.add_argument("--frame-output", type=Path)
    parser.add_argument("--output", type=Path, default=FINAL)
    parser.add_argument("--skip-visuals", action="store_true",
                        help="Reuse _build/visual.mp4 when only remixing audio")
    args = parser.parse_args()
    reel = Reel()
    if args.frame_at is not None:
        if not 0 <= args.frame_at < DURATION:
            parser.error("--frame-at must be within [0, 30)")
        out = args.frame_output or Path("/tmp/survival-preview.png")
        reel.frame(args.frame_at).save(out)
        print(f"Preview: {out}")
        return
    visual = BUILD / "visual.mp4"
    if not args.skip_visuals or not visual.exists():
        render_video(reel, visual)
    soundtrack = create_mix(BUILD / "final_mix.wav")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    mux(visual, soundtrack, args.output)
    print(f"Rendered {args.output}: 30s, 1080x1920, 24fps, narrated stereo audio")


if __name__ == "__main__":
    main()
