#!/usr/bin/env python3
"""
render_an2.py — "How Ancient Humans Survived", built from our own sprite kit.

Not a copy of Law 1, and no longer stick figures drawn in code: every element on
screen is a character/prop/environment from the sheet set in `sheet/`, cut into
83 transparent sprites by `extract_sheet.py` and staged here with its own timing.

What is kept from Law 1 (the *style*, not the content):
    cream paper · blue kinetic caption bar · the hooded host · pills and stamps
    · big display type · camera push/pull · punch optics on the picture only
    · light sweep / leak / anamorphic / weave / grain · hairline progress line

What is new and specific to this film:
    real sprite staging (parallax, pop-in, bob, flip, silhouette passes),
    fire that changes shape every frame from three separate flame sprites,
    a hide cloak that actually falls onto the character, a mammoth that walks,
    speed lines and dust from our own UI kit, and a sprite-based end card.

  python render_an2.py stills 2 12 26 44
  python render_an2.py full
"""
from __future__ import annotations

import glob
import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import vlib
from vlib import (BLUE, CREAM, F, GOLD, GOLD_L, H, INK, INK_SOFT, N6, N7, N8, N9,
                  NIGHT, RED, S7, S8, S9, W, WHITE, apply_camera, apply_grain,
                  apply_vignette, arrow, bubble, cl, draw_particles, eio, eo,
                  glow_ring, grade, halo, lerp, make_particles, paper_bg, pill,
                  put_text_scaled, sg, sparkle, stamp, star4, transition, tw)
from render_v3 import (anamorphic, bloom, chroma, draw_caption, draw_overlay,
                       exposure_breathe, leak, light_sweep, vignette_pulse,
                       weave, whip_blur, zoom_blur)
from timeline_an import BEATS, TOTAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
ASSETS = os.path.join(ROOT, "assets_an")
os.makedirs(OUT, exist_ok=True)
FPS = vlib.FPS
TRANS_W = 0.30


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


# =====================================================================
#  sprite library
# =====================================================================
_SPRITES: dict[str, Image.Image] = {}
_SCALED: dict[tuple[str, int], Image.Image] = {}
_INDEX: dict[str, str] = {}


def _index() -> dict[str, str]:
    """name -> path, from every sub-folder of assets_an/ (e.g. 'host_point')."""
    global _INDEX
    if not _INDEX:
        for p in glob.glob(os.path.join(ASSETS, "*", "*.png")):
            nm = os.path.splitext(os.path.basename(p))[0]
            _INDEX[nm.split("_", 1)[1] if nm[:2].isdigit() else nm] = p
    return _INDEX


def sprite(name: str) -> Image.Image:
    name = ALIAS.get(name, name)
    if name not in _SPRITES:
        idx = _index()
        if name not in idx:
            raise KeyError(f"no sprite '{name}' — have: {sorted(idx)[:12]}…")
        _SPRITES[name] = Image.open(idx[name]).convert("RGBA")
    return _SPRITES[name]


def sized(name: str, h: int) -> Image.Image:
    key = (name, h)
    if key not in _SCALED:
        im = sprite(name)
        w = max(1, int(round(im.width * h / im.height)))
        _SCALED[key] = im.resize((w, h), Image.LANCZOS)
    return _SCALED[key]


def put_s(base, name, cx=None, cy=None, *, h=None, w=None, opacity=1.0, rot=0.0,
          flip=False, bottom=None, left=None, right=None, tint=None, silhouette=None,
          blur=0.0, shadow=True):
    """Stage one sprite. `h`/`w` give the drawn size; `bottom`/`cx` the anchor."""
    im = sprite(name)
    if h is None:
        h = int(w * im.height / im.width) if w else 400
    im = sized(name, int(h))
    if w is not None and h is None:
        im = sized(name, int(w * im.height / im.width))
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    if silhouette is not None:
        # paint the sprite as a flat silhouette (alpha kept) — used for the
        # figures that must read as shapes, not illustrations
        flat = Image.new("RGBA", im.size, tuple(silhouette) + (255,))
        flat.putalpha(im.getchannel("A"))
        im = flat
    elif tint is not None:
        ov = Image.new("RGBA", im.size, tuple(tint) + (255,))
        ov.putalpha(im.getchannel("A").point(lambda a: int(a * .35)))
        im = Image.alpha_composite(im, ov)
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    if opacity < .999:
        a = im.getchannel("A").point(lambda v: int(v * cl(opacity)))
        im = im.copy()
        im.putalpha(a)
    if opacity <= .01:
        return
    x = left if left is not None else (right - im.width if right is not None
                                      else int((cx if cx is not None else W / 2) - im.width / 2))
    y = (bottom - im.height) if bottom is not None else int((cy if cy is not None else H / 2) - im.height / 2)
    if shadow:
        sh = Image.new("RGBA", (im.width + 40, im.height // 3 + 40), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sh)
        ds.ellipse([20, 10, sh.width - 20, sh.height - 10], fill=(70, 60, 50, int(46 * opacity)))
        sh = sh.filter(ImageFilter.GaussianBlur(9))
        base.paste(sh, (int(x + im.width * .06), int(y + im.height * .92)), sh)
    base.paste(im, (int(x), int(y)), im)
    return im



# names the art changed under us -> what we actually draw
ALIAS = {"axe_hand": "hammer_stone", "human_walk_spear": "human_pair",
         "human_throw": "human_pair"}


def host_stage(base, pose, cx=232, bottom=1830, h=520, opacity=1.0, bob=0.0,
               scale=1.0, rot=0.0, glow=True):
    """The narrator, from our own character sheet: idle / point / think / cheer."""
    name = {"idle": "host_idle", "point": "host_point", "think": "host_think",
            "cheer": "host_cheer", "worried": "host_think", "happy": "host_cheer"}[pose]
    if opacity <= .01:
        return
    if glow:
        halo(base, cx, bottom - h * .30, h * .55, (255, 236, 200), .30 * opacity, .9)
    put_s(base, name, cx=cx, bottom=bottom + bob, h=int(h * scale), opacity=opacity,
          rot=rot, shadow=True)



# ------------------------------------------------------------------ staging
GL = 1700          # the ground line every scene stands on
HERO = 520         # a main subject's height
MID = 400
SMALL = 260


def speedlines(base, cx, cy, amount, w=700, h=520, n=9, color=(60, 58, 62)):
    """Hand-drawn motion streaks (the UI sprite read as a pale cloud)."""
    if amount <= .02:
        return
    d = ImageDraw.Draw(base, "RGBA")
    rng = np.random.default_rng(int(cx) + int(cy) + n)
    for i in range(n):
        a = (i / n) * math.tau + rng.uniform(-.1, .1)
        r0 = rng.uniform(.35, .55)
        r1 = rng.uniform(.85, 1.0)
        x0, y0 = cx + math.cos(a) * w * .5 * r0, cy + math.sin(a) * h * .5 * r0
        x1, y1 = cx + math.cos(a) * w * .5 * r1, cy + math.sin(a) * h * .5 * r1
        d.line([(x0, y0), (x1, y1)], fill=color + (int(150 * amount),), width=6)
        d.line([(x0, y0), (x1, y1)], fill=(255, 255, 255, int(90 * amount)), width=2)


def dust(base, cx, cy, amount, w=340):
    """A puff of dust: soft cream rings, nothing borrowed."""
    if amount <= .02:
        return
    lay = Image.new("RGBA", (int(w * 1.6), int(w * .9)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rng = np.random.default_rng(int(cx) + int(cy))
    for i in range(7):
        r = w * rng.uniform(.16, .30)
        x = lay.width / 2 + rng.uniform(-w * .45, w * .45)
        y = lay.height / 2 + rng.uniform(-w * .18, w * .18)
        d.ellipse([x - r, y - r, x + r, y + r],
                  fill=(226, 214, 192, int(120 * amount)))
    lay = lay.filter(ImageFilter.GaussianBlur(w * .045))
    base.paste(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)), lay)


def own_bubble(base, cx, cy, w, h, tail, opacity=1.0, lw=6,
               fill=(255, 253, 246), outline=(28, 28, 32)):
    """A paper speech bubble with an ink outline and a solid triangular tail."""
    if opacity <= .02:
        return
    lay = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x0, y0 = 40, 40
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], min(w, h) * .40, fill=fill, outline=outline,
                        width=lw)
    tx, ty = tail[0] - (cx - w / 2 - 40), tail[1] - (cy - h / 2 - 40)
    tip = (tx, ty)
    d.polygon([(x0 + w * .30, y0 + h - 4), (x0 + w * .46, y0 + h - 4), tip],
              fill=fill)
    d.line([(x0 + w * .30, y0 + h - 3), tip], fill=outline, width=lw)
    d.line([tip, (x0 + w * .46, y0 + h - 3)], fill=outline, width=lw)
    if opacity < .999:
        lay.putalpha(lay.getchannel("A").point(lambda v: int(v * cl(opacity))))
    base.paste(lay, (int(cx - w / 2 - 40), int(cy - h / 2 - 40)), lay)


def warn_badge(base, cx, cy, s, opacity=1.0, t=0):
    """Our own 'danger' badge — red triangle, ink outline, exclamation."""
    if opacity <= .02:
        return
    d = ImageDraw.Draw(base, "RGBA")
    h = s * .92
    p = [(cx, cy - h * .52), (cx + s * .52, cy + h * .40), (cx - s * .52, cy + h * .40)]
    d.polygon(p, fill=(198, 24, 44, int(255 * opacity)))
    d.line(p + [p[0]], fill=(24, 24, 28, int(255 * opacity)), width=max(4, int(s * .035)),
           joint="curve")
    d.line([(cx, cy - h * .16), (cx, cy + h * .10)],
           fill=(255, 250, 240, int(255 * opacity)), width=max(5, int(s * .055)))
    d.ellipse([cx - s * .028, cy + h * .19, cx + s * .028, cy + h * .245],
              fill=(255, 250, 240, int(255 * opacity)))

# ------------------------------------------------------------------ helpers
def flame_stage(base, cx, ground, h, t, hot=1.0, seed=0, ring=False):
    """A living fire assembled from three flame sprites, never the same frame."""
    if hot <= .02:
        return
    halo(base, cx, ground - h * .45, h * 1.5, (255, 190, 120), .40 * hot, .9)
    wob = math.sin(t * 6.1 + seed) * 3.2 + math.sin(t * 11.3) * 1.4
    beats = .82 + .18 * math.sin(t * 7.7 + seed)
    put_s(base, "fire_bonfire", cx=cx, bottom=ground, h=int(h * 1.02 * beats * hot),
          rot=wob, opacity=min(1.0, hot * 1.1), shadow=False)
    put_s(base, "fire_camp", cx=int(cx + h * .16), bottom=ground, h=int(h * .62 * beats),
          rot=-wob * 1.3, opacity=min(1.0, hot), shadow=False)
    put_s(base, "flame_core", cx=int(cx - h * .13), bottom=ground, h=int(h * .46 * hot),
          rot=wob * .7, opacity=min(1.0, hot * 1.2), shadow=False)
    if ring:
        put_s(base, "fire_ring", cx=cx, cy=ground - h * .34, w=int(h * 2.5),
              opacity=.55 * hot, rot=t * 8, shadow=False)
    rng = np.random.default_rng(seed + int(abs(t) * 7) + 1)
    d = ImageDraw.Draw(base, "RGBA")
    for _ in range(int(9 * hot)):
        u = rng.uniform(0, 1)
        ex = cx + rng.normal(0, h * .16)
        ey = ground - (h * .5 + u * h * 1.1)
        r = rng.uniform(2.5, 6) * (h / 400)
        d.ellipse([ex - r, ey - r, ex + r, ey + r],
                  fill=(232, 120, 40, int(220 * (1 - u) * hot)))


def env_band(base, name, bottom, opacity=1.0, feather=90, blur=0.0, flip=False,
             scale=1.08):
    """An environment sprite as a full-width band with a soft paper edge.

    Used bare, the sheet's environment art reads as a pasted rectangle; feathering
    the top and sides melts it into the paper so it feels drawn into the page.
    """
    im = sprite(name)
    w = int(W * scale)
    h = max(1, int(round(w * im.height / im.width)))
    im = im.resize((w, h), Image.LANCZOS)
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    a = np.asarray(im.getchannel("A")).astype(np.float32) / 255.0
    m = np.ones_like(a)
    f = max(1, int(feather))
    ramp = np.linspace(0, 1, f) ** 1.5
    m[:f, :] *= ramp[:, None]                      # soft top
    side = int(W * .16)
    ramp2 = np.linspace(0, 1, side) ** 1.2
    m[:, :side] *= ramp2[None, :]
    m[:, -side:] *= ramp2[None, ::-1]
    a = (a * m * cl(opacity) * 255).astype(np.uint8)
    im.putalpha(Image.fromarray(a))
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    base.paste(im, (int((W - w) / 2), int(bottom - h)), im)


def label(base, txt, cx, cy, fill=(38, 49, 66), size=26, at=None, t=0, track=3):
    if at is None or t > at:
        pill(base, cx, cy, txt, fill=fill, size=size, track=track,
             opacity=eo(sg(t, at if at is not None else 0, .4)))


# =====================================================================
#  scenes
# =====================================================================
def s1(base, t, dur):
    """20,000 years ago: stars, a moon, hills, a cave, one human, and the hook."""
    d = ImageDraw.Draw(base, "RGBA")
    rng = np.random.default_rng(7)
    for _ in range(54):
        sx, sy = rng.integers(40, W - 40), rng.integers(360, 1000)
        r = rng.integers(2, 6)
        d.ellipse([sx, sy, sx + r, sy + r], fill=(208, 202, 190, 200))
    put_s(base, "moon", cx=836, cy=760, w=250, shadow=False)
    env_band(base, "env_hills", bottom=1430, opacity=.95)
    put_s(base, "env_cave", cx=520, bottom=1750, w=800)
    put_s(base, "human_idle", cx=900, bottom=1706, h=430,
          opacity=eo(sg(t, .45, .8)))
    dust(base, 900, 1690, .5 * eo(sg(t, 2.2, .5)), 300)
    if t < 2.2:
        a = cl(sg(t, .02, .10)) * (1 - cl(sg(t, 1.9, .32)))
        if a > .02:
            for k in range(2):
                glow_ring(base, 552, 560, 150 + 300 * eo(sg(t, k * .12, .6)), 5, RED,
                          .30 * (1 - sg(t, k * .12, .6)) * a)
    host_stage(base, "think", cx=236, bottom=1868 + math.sin(t * 2.2) * 5, h=600,
               opacity=cl(sg(t, 0, .14)))
    if t > 1.2:
        pill(base, 236, 1500, "AAP", fill=(38, 49, 66), size=30,
             opacity=eo(sg(t, 1.2, .4)), track=2)
    if t > 2.4:
        pill(base, 560, 1755, "NA GHAR · NA KAPDE", fill=RED, size=26,
             opacity=eo(sg(t, 2.4, .4)), padx=22)


def s2(base, t, dur):
    """The question every morning: a predator closes in."""
    env_band(base, "env_hills", bottom=1330, opacity=.60)
    d = ImageDraw.Draw(base, "RGBA")
    d.rectangle([0, 1240, W, H], fill=(234, 228, 214, 255))
    put_s(base, "human_crouch", cx=270, bottom=1706, h=420,
          opacity=eo(sg(t, .3, .6)))
    k = eio(sg(t, .2, 2.6))
    put_s(base, "sabertooth", cx=int(1050 - 250 * k), bottom=int(1712 - 14 * k),
          h=int(390 + 250 * k), flip=True, opacity=eo(sg(t, .2, .7)))
    if t > 2.2:
        speedlines(base, 640, 1080, eo(sg(t, 2.2, .5)) * .8, 760, 620)
        dust(base, 700, 1700, .55 * eo(sg(t, 2.2, .5)), 460)
    if t > .18:
        a = eo(sg(t, .18, .40))
        warn_badge(base, 560, 940, 250, a * (1 + .04 * math.sin(t * 9)), t)
    if t > 2.35:
        a = eo(sg(t, 2.35, .45))
        stamp(base, 600, 640, "ZINDA?", ang=-8, color=RED, size=96, scale=.9 + .1 * a,
              opacity=a)
    host_stage(base, "think", cx=252, bottom=1868, h=600, bob=math.sin(t * 2) * 4)
    if t > 1.3:
        pill(base, 252, 1470, "HAR SUBHA", fill=(38, 49, 66), size=28,
             opacity=eo(sg(t, 1.3, .4)), track=2)


def s3(base, t, dur):
    """Lightning, then the first controlled fire."""
    d = ImageDraw.Draw(base, "RGBA")
    if t < 1.05:
        k = 1 - abs(t - .22) / .32
        if k > 0:
            rng = np.random.default_rng(4)
            x = 720
            pts = [(x, 190)]
            for i in range(7):
                x += rng.integers(-48, 48)
                pts.append((x, 190 + (i + 1) * 122))
            d.line(pts, fill=(255, 236, 150, int(255 * k)), width=16)
            d.line(pts, fill=(255, 255, 240, int(255 * k)), width=6)
            b2 = Image.new("RGB", (W, H), WHITE)
            base.paste(Image.blend(base, b2, .46 * k))
    if t > .30:
        env_band(base, "env_cave_inside", bottom=1860, opacity=.92, feather=150)
    ignite = eo(sg(t, .85, .7))
    flame_stage(base, 690, GL, 620, t, hot=max(.05, ignite), seed=3)
    put_s(base, "human_kneel", cx=360, bottom=1712, h=430,
          opacity=eo(sg(t, .2, .6)))
    host_stage(base, "cheer", cx=1010, bottom=1860, h=520,
               opacity=eo(sg(t, 1.5, .5)), scale=.96 + .04 * eo(sg(t, 1.5, .5)))
    if t > 1.5:
        pill(base, 350, 1240, "PEHLI AAG", fill=RED, size=30,
             opacity=eo(sg(t, 1.5, .4)), track=3)
    if t > 2.9:
        a = eo(sg(t, 2.9, .5))
        stamp(base, 545, 720, "DOST", ang=7, color=RED, size=96, scale=.9 + .1 * a, opacity=a)


def s4(base, t, dur):
    """Warmth and light; the dark stays outside the circle."""
    d = ImageDraw.Draw(base, "RGBA")
    d.rectangle([0, 1180, W, H], fill=(232, 223, 206, 255))
    rng = np.random.default_rng(11)
    for _ in range(30):
        sx, sy = rng.integers(20, W - 20), rng.integers(300, 1160)
        d.ellipse([sx, sy, sx + 4, sy + 4], fill=(176, 168, 156, 150))
    halo(base, 540, 1360, 700, (255, 184, 110), .34, .95)
    for r, op in ((640, .10), (470, .13)):
        halo(base, 540, 1400, r, (255, 206, 140), op, .9)
    flame_stage(base, 540, GL, 600, t, 1.0, seed=2)
    put_s(base, "human_kneel", cx=210, bottom=1714, h=420, opacity=.98)
    put_s(base, "human_kneel2", cx=862, bottom=1714, h=420, opacity=.98, flip=True)
    put_s(base, "human_crouch", cx=690, bottom=1712, h=360, opacity=.94, flip=True)
    put_s(base, "wolf", cx=int(1016 + 6 * math.sin(t * 2)), bottom=1660, h=250,
          silhouette=(26, 26, 30), opacity=.20 * eo(sg(t, 1.2, 1.0)))
    for i, (txt, col, at) in enumerate((("GARMI", RED, .35), ("ROSHNI", (201, 155, 44), .85),
                                        ("DARINDE DOOR", (38, 49, 66), 1.35))):
        if t > at:
            pill(base, 545, 402 + i * 62, txt, fill=col, size=27,
                 opacity=eo(sg(t, at, .35)), track=3)
    host_stage(base, "think", cx=1004, bottom=1868, h=470,
               opacity=.92 * eo(sg(t, .2, .6)))


def s5(base, t, dur):
    """Stone into tools — four strikes, each one lands on its sound cue."""
    strikes = (.75, 1.55, 2.35, 3.15)
    hit = max([-1] + [i for i, at in enumerate(strikes) if t > at - .26])
    put_s(base, "boulder", cx=430, bottom=1760, w=560)
    put_s(base, "rocks_small", cx=180, bottom=1760, w=250, opacity=.95)
    put_s(base, "human_kneel2", cx=165, bottom=1740, h=450)
    # the hammer swings down and lands on the stone, once per strike
    if hit < 0:
        swing = 0.0
    else:
        swing = eio(cl((t - (strikes[hit] - .26)) / .26))
    rot = -58 + 44 * swing
    # held in the kneeling figure's hands, head landing on the stone's face
    put_s(base, "hammer_stone", cx=310 + 46 * swing, cy=int(1330 + 55 * swing),
          h=240, rot=rot, opacity=eo(sg(t, .30, .40)))
    d = ImageDraw.Draw(base, "RGBA")
    for at in strikes:
        p = sg(t, at, .30)
        if 0 < p < 1:
            cx, cy = 428, 1330
            halo(base, cx, cy, 300, (255, 226, 150), .70 * (1 - p), .95)
            put_s(base, "ui_sparkle", cx=cx, cy=cy, w=int(360 * (0.5 + p)),
                  opacity=(1 - p), rot=t * 60, shadow=False)
            for k in range(10):
                a = k / 10 * math.tau
                r = 60 + 200 * p
                d.line([(cx + math.cos(a) * r * .45, cy + math.sin(a) * r * .40),
                        (cx + math.cos(a) * r, cy + math.sin(a) * r * .82)],
                       fill=(232, 150, 40, int(255 * (1 - p))), width=6)
            dust(base, 430, 1740, (1 - p) * .8, 400)
    # ...and what comes out of it
    put_s(base, "spear", cx=858, bottom=1758, h=430, rot=-10,
          opacity=eo(sg(t, 1.85, .5)))
    if t > 1.25:
        a = eo(sg(t, 1.25, .45))
        stamp(base, 540, 690, "HATHIYAR", ang=-7, color=RED, size=84,
              scale=.9 + .1 * a, opacity=a)
    if t > 3.0:
        pill(base, 300, 1180, "SHIKAAR", fill=(38, 49, 66), size=28,
             opacity=eo(sg(t, 3.0, .4)), track=3)


def s6(base, t, dur):
    """Alone weak, together lethal."""
    env_band(base, "env_plain", bottom=1560, opacity=.92, feather=70, blur=2)
    wx = int(1090 - 400 * eio(sg(t, .1, 3.6)))
    put_s(base, "mammoth", cx=wx, bottom=int(1730 + 5 * math.sin(t * 4)),
          h=530, flip=True, opacity=1.0)
    dust(base, wx - 200, 1710, .55, 420)
    for i, (x, hh, fl) in enumerate(((170, 400, False), (330, 430, True), (80, 350, False))):
        put_s(base, "human_pair", cx=x, bottom=1720 + int(3 * math.sin(t * 6 + i)),
              h=hh, opacity=eo(sg(t, .7 + i * .1, .5)), flip=fl)
    if t > 1.1:
        speedlines(base, 700, 1280, eo(sg(t, 1.1, .5)) * .95, 820, 640)
    if t > 1.3:
        a = eo(sg(t, 1.3, .45))
        stamp(base, 600, 620, "JHUND", ang=-6, color=RED, size=96, scale=.9 + .1 * a,
              opacity=a)
    if t > 2.7:
        put_text_scaled(base, "KHATARNAAK", F(N9, 82), RED, 546, 1040, .98,
                        eo(sg(t, 2.7, .45)))


def s7(base, t, dur):
    """Hide and cave — the cloak falls onto the character."""
    env_band(base, "env_cave_inside", bottom=1860, opacity=.95, feather=150)
    put_s(base, "human_idle", cx=320, bottom=1718, h=480)
    fall = eio(sg(t, .45, .75))
    if t > .45:
        if fall < .97:
            cy = int(700 + 340 * fall)
            put_s(base, "hide_cloak", cx=336, cy=cy, h=int(420 - 70 * fall),
                  rot=(1 - fall) * 6, opacity=min(1.0, fall * 1.8), shadow=False)
        else:
            # worn: the vest lands on the torso and stays there
            put_s(base, "hide_cloak", cx=336, cy=1400, h=248, rot=-2, opacity=.98,
                  shadow=False)

    dust(base, 330, 1460, .5 * eo(sg(t, 1.05, .5)), 300)
    if t > 1.5:
        a = eo(sg(t, 1.5, .42))
        stamp(base, 540, 700, "JACKET", ang=-7, color=RED, size=82,
              scale=.9 + .1 * a, opacity=a)
    if t > 2.4:
        pill(base, 830, 1180, "GUFA = GHAR", fill=(38, 49, 66), size=28,
             opacity=eo(sg(t, 2.4, .4)), track=3)
    put_s(base, "human_kneel", cx=1000, bottom=1690, h=280,
          opacity=.60 * eo(sg(t, 2.2, .8)))


def s8(base, t, dur):
    """Language — the weapon that is not a weapon."""
    put_s(base, "human_pair", cx=250, bottom=1716, h=470, flip=True)
    put_s(base, "human_idle", cx=830, bottom=1714, h=470, flip=False)
    for k in range(3):
        p = (t * .55 + k / 3) % 1.0
        halo(base, 540, 1080, int(120 + 300 * p), (255, 236, 214),
             (1 - p) * .22 * eo(sg(t, .3, .5)), .95)
    if t > .6:
        a = eo(sg(t, .6, .4))
        own_bubble(base, 560, 950, 380, 190, tail=(430, 1090), opacity=a)
        if t > .8:
            put_text_scaled(base, "aa · oh · hm", F(S8, 56), INK, 560, 948, .98,
                            eo(sg(t, .8, .4)))
    if t > 1.5:
        a = eo(sg(t, 1.5, .45))
        stamp(base, 540, 640, "ZUBAAN", ang=-5, color=RED, size=96,
              scale=.9 + .1 * a, opacity=a)
    if t > 3.0:
        pill(base, 540, 760, "SIKHANA", fill=(38, 49, 66), size=28,
             opacity=eo(sg(t, 3.0, .4)), track=3)


def s9(base, t, dur):
    """Seeds to the first harvest — sunrise over a field."""
    put_s(base, "sun", cx=540, cy=720, w=300, shadow=False)
    for r, op in ((420, .12), (600, .08)):
        halo(base, 540, 720, r, (255, 214, 130), op, .95)
    env_band(base, "env_field", bottom=1870, opacity=.95, feather=110)
    for i in range(5):
        x = 128 + i * 208
        put_s(base, "wheat", cx=x, bottom=1806 + (i % 2) * 10, h=380 + (i % 3) * 40,
              rot=math.sin(t * 1.6 + i) * 3, opacity=.97, shadow=False)
    put_s(base, "sprout", cx=330, bottom=1716, h=int(90 + 150 * eo(sg(t, .5, 1.8))),
          opacity=eo(sg(t, .45, .5)))
    put_s(base, "seeds", cx=620, cy=1120, w=210, rot=-8 + 6 * math.sin(t * 2.2),
          opacity=eo(sg(t, .9, .6)), shadow=False)
    if t > 1.05:
        put_s(base, "ui_arrow_curve", cx=452, cy=1310, w=190, rot=146,
              opacity=.85 * eo(sg(t, 1.05, .5)), shadow=False)
    put_s(base, "deer", cx=900, bottom=1620, h=230, opacity=.50 * eo(sg(t, 1.6, 1.0)))
    d = ImageDraw.Draw(base, "RGBA")
    for k in range(8):
        p = sg(t, .2 + k * .1, 1.2)
        if 0 < p < 1:
            sx = 330 + (k - 4) * 26
            d.ellipse([sx - 6, 1080 + p * 480, sx + 6, 1092 + p * 480],
                      fill=(196, 150, 60, int(220 * (1 - p * .4))))
    if t > 1.35:
        a = eo(sg(t, 1.35, .45))
        stamp(base, 690, 560, "BEEJ", ang=8, color=RED, size=88,
              scale=.9 + .1 * a, opacity=a)
    if t > 2.9:
        pill(base, 700, 790, "BHOOKH KAM", fill=(38, 49, 66), size=26,
             opacity=eo(sg(t, 2.9, .4)), track=3)


def s10(base, t, dur):
    """The payoff card: same human, new tools."""
    base.paste(Image.new("RGB", (W, H), NIGHT))
    put_s(base, "env_night", cx=540, cy=430, w=1500, opacity=.55, shadow=False)
    halo(base, 700, 1300, 560, (110, 170, 240), .48 + .16 * math.sin(t * 2.4), .95)
    put_s(base, "human_idle", cx=520, bottom=1700, h=560, silhouette=(10, 12, 18),
          opacity=1.0)
    d = ImageDraw.Draw(base, "RGBA")
    d.rounded_rectangle([646, 1236, 712, 1352], 12, fill=(226, 240, 255, 250))
    d.rounded_rectangle([654, 1248, 704, 1340], 8, fill=(120, 180, 250, 255))
    halo(base, 679, 1294, 210, (180, 215, 255), .80, .9)
    if t > .5:
        put_text_scaled(base, "hum wahi insaan hain", F(S7, 58), WHITE, 540, 1010, .98,
                        eo(sg(t, .5, .5)))
    a2 = eo(sg(t, 1.35, .5))
    if a2 > .02:
        put_text_scaled(base, "SIRF TOOLS", F(N9, 96), GOLD_L, 540, 780, .98, a2)
        put_text_scaled(base, "BADLE HAIN", F(N9, 96), GOLD_L, 540, 892, .98, a2)
    if t > 3.1:
        pill(base, 540, 1730, "FOLLOW · MONARCH STICKMAN", fill=(232, 223, 203),
             fg=(20, 22, 28), size=26, opacity=eo(sg(t, 3.1, .5)), track=2)


SCENES = {1: s1, 2: s2, 3: s3, 4: s4, 5: s5, 6: s6, 7: s7, 8: s8, 9: s9, 10: s10}

CAM = {1: ((1.11, 1.005), "out"), 2: ((1.01, 1.10), "in"), 3: ((1.00, 1.09), "in"),
       4: ((1.07, 1.00), "out"), 5: ((1.02, 1.11), "in"), 6: ((1.13, 1.04), "out"),
       7: ((1.09, 1.01), "out"), 8: ((1.01, 1.07), "in"), 9: ((1.02, 1.09), "in"),
       10: ((1.00, 1.13), "in")}

SHAKE = {1: [(0.02, 24, 14), (1.35, 10, 16)],
         2: [(0.02, 26, 12), (0.50, 9, 14)],
         3: [(0.18, 20, 12), (0.85, 12, 16)],
         4: [(0.50, 8, 16)],
         5: [(0.75, 14, 11), (1.55, 12, 11), (2.35, 10, 11), (3.15, 9, 11)],
         6: [(0.00, 26, 12), (1.30, 12, 14)],
         7: [(0.55, 10, 15)],
         8: [(1.35, 10, 14)],
         9: [(1.40, 9, 15)],
         10: [(0.00, 22, 13), (1.35, 10, 15)]}

GRADE = {1: dict(tint=(255, 243, 232), amt=.05, contrast=1.05, sat=1.02),
         2: dict(tint=(255, 235, 230), amt=.06, contrast=1.07, sat=.96),
         3: dict(tint=(255, 240, 214), amt=.10, contrast=1.04, sat=1.04),
         4: dict(tint=(255, 232, 200), amt=.11, contrast=1.03, sat=1.05),
         5: dict(tint=(255, 240, 220), amt=.07, contrast=1.05, sat=1.02),
         6: dict(tint=(236, 240, 246), amt=.07, contrast=1.08, sat=.92),
         7: dict(tint=(255, 238, 214), amt=.09, contrast=1.04, sat=1.02),
         8: dict(tint=(252, 244, 240), amt=.05, contrast=1.04, sat=1.0),
         9: dict(tint=(255, 244, 214), amt=.09, contrast=1.03, sat=1.06),
         10: dict(tint=(40, 52, 74), amt=.03, contrast=1.06, sat=1.0)}

PARTS = {1: ("dust", 20, 11), 2: ("dust", 16, 12), 3: ("ember", 42, 13),
         4: ("ember", 50, 14), 5: ("spark", 28, 15), 6: ("dust", 22, 16),
         7: ("ember", 24, 17), 8: ("dust", 16, 18), 9: ("confetti", 30, 19),
         10: ("ember", 20, 20)}
_parts = {k: make_particles(v[0], v[1], v[2]) for k, v in PARTS.items()}


def camera_for(n, tl):
    (z0, z1), e = CAM[n]
    p = cl(tl / max(BEATS[n - 1]["dur"], 1e-6))
    z = lerp(z0, z1, eio(p))
    sh = (0, 0)
    for at, amp, dec in SHAKE.get(n, []):
        k = tl - at
        if 0 <= k < dec / 30:
            sh = (int(amp * math.exp(-k * 22) * math.sin(k * 90)),
                  int(amp * .6 * math.exp(-k * 22) * math.cos(k * 70)))
    return z, sh


def impact_curve(n, tl):
    v = 0.0
    for at, amp, dec in SHAKE.get(n, []):
        k = tl - at
        if 0 <= k < dec / 30:
            v = max(v, amp * math.exp(-k * 14) / 24)
    return v


def scene_frame(n, tl):
    base = Image.new("RGB", (W, H), NIGHT) if n == 10 else paper_bg()
    SCENES[n](base, tl, BEATS[n - 1]["dur"])
    z, sh = camera_for(n, tl)
    base = apply_camera(base, z, .5, .5, sh)
    kind, cnt, seed = PARTS[n]
    if n != 10:
        draw_particles(base, _parts[n], tl, kind, .85)
    g = GRADE[n]
    base = grade(base, g["tint"], g["amt"], g["contrast"], 1.0, g["sat"])
    base = apply_vignette(base, .30 if n == 10 else .15)
    return base


def compose(t: float) -> Image.Image:
    idx = 0
    for i, b in enumerate(BEATS):
        if t >= b["start"] - 1e-6:
            idx = i
    b = BEATS[idx]
    tl = t - b["start"]
    img = scene_frame(b["n"], tl)

    if idx > 0:
        prev = BEATS[idx - 1]
        p = (t - (b["start"] - TRANS_W * .5)) / TRANS_W
        if 0 <= p <= 1:
            a = scene_frame(prev["n"], prev["dur"] + (t - b["start"]) + .05)
            img = transition(a, img, b["trans"], p)
            if b["trans"] in ("slide", "whoosh"):
                img = whip_blur(img, math.sin(math.pi * cl(p)) * .55)
            if b["trans"] == "slam":
                img = zoom_blur(img, math.sin(math.pi * cl(p)) * .80)
            if b["trans"] in ("flash", "punch"):
                img = vlib.flash(img, WHITE, .32 * math.sin(math.pi * cl(p)))

    ic = impact_curve(b["n"], tl)
    if ic > .006:
        k = min(1.0, ic / .030)
        img = chroma(img, int(round(1 + 3 * k)))
        img = zoom_blur(img, .42 * k)

    if b["n"] != 10:
        draw_caption(img, b, tl)

    if b["n"] == 1:
        img = vlib.flash(img, (255, 246, 236), .45 * max(0, 1 - tl / .16))
    if b["n"] == 3 and .12 < tl < .40:
        img = vlib.flash(img, (255, 252, 220), .30 * (1 - abs(tl - .26) / .14))
    if b["n"] == 6 and tl < .28:
        img = vlib.flash(img, WHITE, .35 * max(0, 1 - tl / .28))

    if tl < .66:
        img = light_sweep(img, eo(cl(tl / .66)), .34 if b["n"] != 10 else .12)
    if tl < .85:
        img = leak(img, .22 * math.sin(math.pi * cl(tl / .85)) ** 1.4, seed=b["n"] * .37)
    img = anamorphic(img, .40 if b["n"] == 10 else .16)
    if b["n"] == 10:
        img = bloom(img, .50, 205)
    if ic > .008:
        img = vignette_pulse(img, min(1.0, ic / .030) * .7)
    img = weave(img, t, .8 if b["n"] != 10 else 1.2)
    img = exposure_breathe(img, t)
    draw_overlay(img, t, TOTAL, b["n"])
    img = apply_grain(img, int(t * FPS), .05)
    return img


def render_full():
    silent = os.path.join(OUT, "ancient2_silent.mp4")
    nframes = int(round(TOTAL * FPS))
    cmd = [ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
           "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-x264-params", "keyint=48:min-keyint=24", "-movflags", "+faststart", silent]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    import time
    t0 = time.time()
    for i in range(nframes):
        p.stdin.write(compose(i / FPS).tobytes())
        if i % 60 == 0:
            el = max(time.time() - t0, 1e-6)
            print(f"  {i}/{nframes}  {i/el:.1f} fps  eta {(nframes-i)/max(i/el,1e-6):.0f}s",
                  flush=True)
    p.stdin.close()
    p.wait()
    print(f"FINAL: {silent}  {os.path.getsize(silent)/1048576:.1f} MB")
    return silent


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    if mode == "stills":
        for a in sys.argv[2:]:
            t = float(a)
            compose(t).save(os.path.join(OUT, f"s2_{t:05.2f}.jpg"), quality=90)
            print(os.path.join(OUT, f"s2_{t:05.2f}.jpg"))
    else:
        render_full()
