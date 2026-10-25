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
from events_an import EVENTS, DUR as EV_DUR

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




# ------------------------------------------------------------------ premium fx
def motes(base, t, n=16, seed=5, area=(0, 300, W, 1500), color=(214, 200, 176),
          alpha=110, spread=1.0):
    """Dust in the light: slow specks at several depths, each on its own drift."""
    d = ImageDraw.Draw(base, "RGBA")
    rng = np.random.default_rng(seed)
    for i in range(n):
        x0, y0 = rng.uniform(area[0], area[2]), rng.uniform(area[1], area[3])
        sp = rng.uniform(.5, 1.7) * spread
        r = rng.uniform(1.6, 4.6)
        x = (x0 + t * 12 * sp + math.sin(t * .8 + i) * 14) % (area[2] - area[0]) + area[0]
        y = (y0 - t * 20 * sp + math.sin(t * .55 + i * 2) * 10) % (area[3] - area[1]) + area[1]
        a = int(alpha * (.35 + .65 * abs(math.sin(t * .6 + i))))
        d.ellipse([x - r, y - r, x + r, y + r], fill=color + (a,))


def birds(base, t, cx, cy, n=3, color=(48, 46, 50), scale=1.0, opacity=.55):
    """A few far birds circling — the cheapest way to make a sky feel alive."""
    if opacity <= .02:
        return
    d = ImageDraw.Draw(base, "RGBA")
    for i in range(n):
        a = t * (.45 + .07 * i) + i * 2.1
        rx, ry = 90 * scale + 26 * i, 34 * scale + 9 * i
        x = cx + math.cos(a) * rx
        y = cy + math.sin(a) * ry - i * 8
        flap = math.sin(t * 7 + i * 1.7)
        w, h = 17 * scale * (1 + .1 * i), 6 * scale
        wing = h * (.5 + .9 * flap)
        d.line([(x - w, y - wing), (x, y), (x + w, y - wing)],
               fill=color + (int(200 * opacity),), width=max(2, int(3 * scale)), joint="curve")


def fg_grass(base, t, color=(30, 42, 30), opacity=.85, y=H + 10, n=26, seed=9,
             hmin=60, hmax=150, sides=True):
    """Foreground reeds: a dark silhouette that gives the frame depth."""
    d = ImageDraw.Draw(base, "RGBA")
    rng = np.random.default_rng(seed)
    for i in range(n):
        if sides:
            x = rng.uniform(-20, W * .22) if i % 2 else rng.uniform(W * .78, W + 20)
        else:
            x = rng.uniform(-20, W + 20)
        h = rng.uniform(hmin, hmax)
        sway = math.sin(t * 1.5 + i * .7) * h * .10
        w = rng.uniform(5, 11)
        d.polygon([(x - w, y), (x + w, y),
                   (x + w * .25 + sway, y - h), (x - w * .5 + sway, y - h * .82)],
                  fill=color + (int(255 * opacity),))


def smoke_plume(base, x, y, t, strength=1.0, seed=3, w=90, rise=420):
    """Soft smoke rising and widening — used at the fire and the cave mouth."""
    if strength <= .02:
        return
    lay = Image.new("RGBA", (w * 4, int(rise * 1.5)), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    rng = np.random.default_rng(seed)
    for i in range(7):
        u = ((t * .35 + i / 7) % 1.0)
        yy = lay.height - u * lay.height
        rr = w * (.22 + .5 * u) * strength
        xx = lay.width / 2 + math.sin(u * 6 + i) * w * .35 + rng.uniform(-6, 6)
        a = int(90 * (1 - u) * strength)
        d.ellipse([xx - rr, yy - rr, xx + rr, yy + rr], fill=(222, 214, 200, a))
    lay = lay.filter(ImageFilter.GaussianBlur(w * .10))
    base.paste(lay, (int(x - lay.width / 2), int(y - lay.height)), lay)


def annot_circle(base, cx, cy, rx, ry=None, p=1.0, color=RED, w=7, jitter=3.2):
    """A hand-drawn circle that draws itself on (chalk on paper)."""
    if p <= .02:
        return
    ry = rx * .78 if ry is None else ry
    d = ImageDraw.Draw(base, "RGBA")
    steps = max(8, int(72 * cl(p)))
    pts = []
    rng = np.random.default_rng(21)
    for i in range(steps):
        a = -math.pi * .62 + (i / 72) * math.tau * 1.03
        j = rng.uniform(-jitter, jitter)
        pts.append((cx + math.cos(a) * (rx + j), cy + math.sin(a) * (ry + j)))
    if len(pts) > 1:
        d.line(pts, fill=color + (235,), width=w, joint="curve")


def annot_arrow(base, x0, y0, x1, y1, p=1.0, color=RED, w=6, bow=60):
    """A drawn arrow with a bow in it; `p` is how much of it is on screen."""
    if p <= .02:
        return
    d = ImageDraw.Draw(base, "RGBA")
    mx, my = (x0 + x1) / 2 + bow * .35, (y0 + y1) / 2 - bow
    pts = []
    n = 26
    for i in range(n + 1):
        u = i / n * cl(p)
        pts.append(((1 - u) ** 2 * x0 + 2 * (1 - u) * u * mx + u ** 2 * x1,
                    (1 - u) ** 2 * y0 + 2 * (1 - u) * u * my + u ** 2 * y1))
    d.line(pts, fill=color + (230,), width=w, joint="curve")
    if p > .92:
        (ax, ay), (bx, by) = pts[-2], pts[-1]
        ang = math.atan2(by - ay, bx - ax)
        for side in (-1, 1):
            d.line([(bx, by), (bx - 34 * math.cos(ang + side * .48),
                               by - 34 * math.sin(ang + side * .48))],
                   fill=color + (230,), width=w)


def drift(base, dx, fn):
    """Run a drawing pass on a copy, then shift it — cheap parallax."""
    lay = Image.new("RGB", (W, H), WHITE)
    lay.paste(base, (0, 0))
    fn(lay)
    base.paste(lay, (int(dx), 0))


def ink_wipe(a, b, p):
    """A rough brush edge sweeps the old scene away (paper-tear feel)."""
    p = cl(p)
    if p <= 0:
        return a.copy()
    if p >= 1:
        return b.copy()
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    edge = int(-260 + p * (W + 520))
    rng = np.random.default_rng(12)
    pts = [(-40, -40)]
    x = -40
    while x < W + 40:
        pts.append((x, edge + rng.integers(-26, 26)))
        x += 26
    pts += [(W + 40, -40), (W + 40, H + 40), (-40, H + 40)]
    d.polygon(pts, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(9))
    out = b.copy()
    out.paste(a, (0, 0), m)
    return out





# ------------------------------------------------------------------ inserts
def _ins_base(dark=False):
    return Image.new("RGB", (W, H), NIGHT) if dark else paper_bg()


def crop_sprite(name, fx0, fy0, fx1, fy1, h):
    """A deliberate close crop of a sprite — how the inserts get their angle."""
    im = sprite(name)
    w0, h0 = im.size
    box = (int(fx0 * w0), int(fy0 * h0), int(fx1 * w0), int(fy1 * h0))
    sub = im.crop(box)
    k = h / max(1, sub.height)
    return sub.resize((max(1, int(sub.width * k)), int(h)), Image.LANCZOS)


def put_crop(base, name, box_frac, h, cx=None, bottom=None, cy=None, flip=False,
             silhouette=None):
    im = crop_sprite(name, *box_frac, h)
    if flip:
        im = im.transpose(Image.FLIP_LEFT_RIGHT)
    if silhouette:
        flat = Image.new("RGBA", im.size, tuple(silhouette) + (255,))
        flat.putalpha(im.getchannel("A"))
        im = flat
    x = int(cx - im.width / 2) if cx is not None else 0
    y = int(bottom - im.height) if bottom is not None else int(cy - im.height / 2)
    base.paste(im, (x, y), im)


def crop_zoom(base, cx, cy, zoom):
    """Re-frame an already-composed picture: a real camera move, not a sticker."""
    w, h = W / zoom, H / zoom
    x0 = max(0, min(W - w, cx - w / 2))
    y0 = max(0, min(H - h, cy - h / 2))
    return base.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((W, H), Image.LANCZOS)


def ins_moon(base, t):
    base.paste(Image.new("RGB", (W, H), (22, 24, 34)))
    d = ImageDraw.Draw(base, "RGBA")
    rng = np.random.default_rng(3)
    for i in range(90):
        x, y = rng.integers(0, W), rng.integers(0, 1300)
        r = rng.integers(1, 5)
        a = 255 * (.35 + .65 * abs(math.sin(t * 2.4 + i)))
        d.ellipse([x, y, x + r, y + r], fill=(226, 226, 234, int(a)))
    halo(base, 600, 820, 560, (170, 190, 230), .35, .95)
    put_s(base, "moon", cx=600, cy=820, w=760, shadow=False)
    # the hills, as a pure dark shape, only at the very bottom of the frame
    put_s(base, "env_hills", cx=540, bottom=2050, w=1600, opacity=.55,
          shadow=False, silhouette=(28, 30, 40))


def ins_teeth(base, t):
    base.paste(paper_bg())
    ImageDraw.Draw(base).rectangle([0, 1560, W, H], fill=(232, 228, 216))
    # the head sits at ~0.84 / 0.30 of the sprite box: place it, then push in
    put_s(base, "sabertooth", cx=-8, bottom=1720, h=900)
    d = ImageDraw.Draw(base, "RGBA")
    for i in range(3):
        a = .16 * (1 - (t * 2.4 + i * .3) % 1)
        d.rectangle([0, 0, W, H], fill=(198, 24, 44, int(46 * a)))
    base.paste(crop_zoom(base, 556, 1030, 2.15))


def ins_flame(base, t):
    base.paste(paper_bg())
    halo(base, 540, 1100, 700, (255, 180, 100), .40, .95)
    flame_stage(base, 540, 1720, 1500, t, 1.0, seed=77)


def ins_eyes(base, t):
    base.paste(Image.new("RGB", (W, H), (16, 16, 20)))
    # our own wolf head, as a flat silhouette — only the eyes catch light
    d0 = ImageDraw.Draw(base, "RGBA")
    head = [(540, 620), (462, 500), (418, 660), (368, 664), (330, 880),
            (368, 1092), (452, 1210), (540, 1244), (628, 1210), (712, 1092),
            (750, 880), (712, 664), (662, 660), (618, 500)]
    for off, col in ((30, (78, 84, 104, 255)), (0, (34, 36, 46, 255))):
        d0.polygon([(x + off * .5, y + off * .5) for x, y in head], fill=col)
    for sx in (-1, 1):                        # ears, catching a little light
        d0.polygon([(540 + sx * 112, 700), (540 + sx * 150, 566),
                    (540 + sx * 176, 706)],
                   fill=(92, 98, 118, 255) if sx > 0 else (70, 76, 94, 255))
    d = ImageDraw.Draw(base, "RGBA")
    blink = 1.0 if (t % 2.2) > .16 else .10
    for x, y, r in ((476, 880, 44), (606, 878, 42)):
        halo(base, x, y, 190, (255, 198, 110), .55, .95)
        d.ellipse([x - r, y - r * .62 * blink, x + r, y + r * .62 * blink],
                  fill=(255, 236, 168, 245))
        d.ellipse([x - r * .30, y - r * .40 * blink, x + r * .30, y + r * .40 * blink],
                  fill=(26, 18, 14, 252))


def ins_tusk(base, t):
    base.paste(paper_bg())
    ImageDraw.Draw(base).rectangle([0, 1600, W, H], fill=(226, 220, 206))
    put_s(base, "mammoth", cx=430, bottom=1780, h=1250)
    base.paste(crop_zoom(base, 430 + 1250 * 1.42 * .46, 1780 - 1250 * .70, 2.10))


def ins_words(base, t):
    """Three people, three bubbles, one idea travelling between them."""
    base.paste(paper_bg())
    halo(base, 540, 1200, 520, (255, 244, 222), .35, .95)
    for i, (cx, h, fl) in enumerate(((180, 600, False), (540, 660, True),
                                     (900, 590, False))):
        put_s(base, "human_idle", cx=cx, bottom=1790, h=h, flip=fl, opacity=.98)
        at = .05 + i * .16
        a = eo(sg(t, at, .16))
        if a > .02:
            bx, by = cx - 44 + i * 30, 1180 - i * 44
            w = 190
            own_bubble(base, bx, by, w, 112, tail=(cx, 1430), opacity=a)
            d = ImageDraw.Draw(base, "RGBA")
            rng = np.random.default_rng(i + 4)
            for k in range(3):
                yy = by - 26 + k * 26
                ww = w * rng.uniform(.35, .62)
                d.rounded_rectangle([bx - ww / 2, yy, bx + ww / 2, yy + 11], 5,
                                    fill=(32, 96, 176, int(220 * a)))


def ins_sprout(base, t):
    base.paste(paper_bg())
    halo(base, 540, 1080, 620, (255, 226, 150), .34, .95)
    put_s(base, "sprout", cx=540, bottom=1690, h=760 + 40 * math.sin(t * 3))
    d = ImageDraw.Draw(base, "RGBA")
    d.line([(40, 1692), (W - 40, 1692)], fill=(96, 78, 56, 90), width=6)
    for i, x in enumerate((110, 250, 830, 970)):
        put_s(base, "wheat", cx=x, bottom=1810, h=300, opacity=.55, shadow=False,
              rot=(i - 1.5) * 3)


INSERTS = {1: (ins_moon, 2.62, .34), 2: (ins_teeth, 2.05, .30),
           3: (ins_flame, 2.42, .30), 4: (ins_eyes, 3.05, .28),
           6: (ins_tusk, 2.62, .28), 8: (ins_words, 2.95, .30),
           9: (ins_sprout, 2.62, .32)}


def insert_frame(n, local_t):
    fn = INSERTS[n][0]
    base = _ins_base(n == 4)
    fn(base, local_t)
    if n == 4:
        return apply_vignette(base, .42)
    g = GRADE[n]
    base = grade(base, g["tint"], g["amt"], g["contrast"], 1.0, g["sat"])
    return apply_vignette(base, .30)


# ------------------------------------------------------------------ edit pulse
def snap_push(img, amp, p):
    """A four-frame push: the frame jumps closer, then settles."""
    if p <= 0 or p >= 1:
        return img
    k = math.exp(-p * 5.5) * amp
    z = 1.0 + .042 * k
    sh = (int(6 * k * math.sin(p * 24)), int(-3 * k))
    return apply_camera(img, z, .5, .47, sh)


def shock_ring(img, x, y, r, p, color=(198, 24, 44)):
    """Two rings racing outward from a point — the 'something just landed' cue."""
    if p <= 0 or p >= 1:
        return img
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for i, k in enumerate((1.0, .62)):
        rr = r * (0.35 + 1.15 * eo(p)) * k
        a = int(215 * (1 - p) ** 1.6 * (1.0 if i == 0 else .6))
        w = max(3, int(11 * (1 - p) * (1.0 if i == 0 else .7)))
        d.ellipse([x - rr, y - rr * .92, x + rr, y + rr * .92],
                  outline=tuple(color) + (a,), width=w)
    lay = lay.filter(ImageFilter.GaussianBlur(1.6))
    img.paste(lay, (0, 0), lay)
    return img


def spark_pop(img, x, y, n, p, color=(255, 206, 96)):
    """A quick hand-drawn sparkle: short rays, one soft core."""
    if p <= 0 or p >= 1:
        return img
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    grow = eo(p)
    fade = (1 - p) ** 1.3
    r0, r1 = 16 + 44 * grow, 54 + 150 * grow
    for i in range(n):
        a = (i / n) * math.tau + .35
        d.line([(x + math.cos(a) * r0, y + math.sin(a) * r0 * .9),
                (x + math.cos(a) * r1, y + math.sin(a) * r1 * .9)],
               fill=tuple(color) + (int(230 * fade),), width=max(2, int(7 * fade)))
    rr = 12 + 26 * grow
    d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(255, 252, 240, int(120 * fade)))
    lay = lay.filter(ImageFilter.GaussianBlur(1.2))
    img.paste(lay, (0, 0), lay)
    return img


def sliver_sweep(img, p, amp=.30):
    """A thin band of light crossing the frame on a diagonal."""
    if p <= 0 or p >= 1:
        return img
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    x = -300 + p * (W + 600)
    a = int(70 * math.sin(math.pi * p) * amp * 3)
    for i in range(6):
        o = i * 26
        d.polygon([(x + o, 0), (x + o + 90, 0), (x + o - 210, H), (x + o - 300, H)],
                  fill=(255, 250, 236, max(0, a - i * 9)))
    lay = lay.filter(ImageFilter.GaussianBlur(22))
    img.paste(lay, (0, 0), lay)
    return img


def lens(base, cx, cy, r, zoom, ring=INK):
    """A magnifier: re-crops the finished frame inside a circular glass."""
    if r < 12:
        return
    rr = int(max(20, min(r, cy - 6, H - cy - 6, cx - 6, W - cx - 6)))
    half = rr / max(zoom, .01)
    bx, by = max(0, min(W - 2 * half, cx - half)), max(0, min(H - 2 * half, cy - half))
    box = (int(bx), int(by), int(bx + 2 * half), int(by + 2 * half))
    crop = base.crop(box).resize((rr * 2, rr * 2), Image.LANCZOS)
    mask = Image.new("L", (rr * 2, rr * 2), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, rr * 2 - 1, rr * 2 - 1], fill=255)
    shadow = Image.new("RGBA", (rr * 2 + 60, rr * 2 + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([30, 34, rr * 2 + 30, rr * 2 + 30], fill=(40, 34, 30, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    base.paste(shadow, (int(cx - rr - 30), int(cy - rr - 30)), shadow)
    base.paste(crop, (int(cx - rr), int(cy - rr)), mask)
    d = ImageDraw.Draw(base, "RGBA")
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 253, 246, 245),
              width=max(6, int(rr * .10)))
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=ring + (248,),
              width=max(2, int(rr * .030)))
    # specular arc so the eye reads glass, not a hole
    for k, a in ((1, 150), (2, 70)):
        d.arc([cx - rr + 8 * k, cy - rr + 8 * k, cx + rr - 8 * k, cy + rr - 8 * k],
              200, 262, fill=(255, 255, 252, a), width=max(3, int(rr * .05)))


def slice_wipe(a, b, p, bands=5):
    """Vertical bands trade places in alternating directions — a real edit cut."""
    p = cl(p)
    if p <= 0:
        return a.copy()
    if p >= 1:
        return b.copy()
    out = a.copy()
    bw = W // bands + 1
    for i in range(bands):
        x0 = i * bw
        k = cl((p - i * .07) / (1 - (bands - 1) * .07))
        if k <= 0:
            continue
        hh = int(H * eo(k))
        y0 = 0 if i % 2 == 0 else H - hh
        out.paste(b.crop((x0, y0, min(W, x0 + bw), y0 + hh)),
                  (x0, y0), None)
    cut = int(W * p)
    d = ImageDraw.Draw(out, "RGBA")
    d.rectangle([cut - 5, 0, cut + 5, H], fill=(24, 24, 28, int(120 * (1 - p))))
    return out


def apply_events(img, n, tl):
    """Read the pulse sheet and stamp its picture half onto the frame."""
    for e in EVENTS:
        if e["beat"] != n:
            continue
        p = (tl - (e["t"] - BEATS[n - 1]["start"])) / EV_DUR[e["kind"]]
        if not (0 <= p <= 1):
            continue
        k = e["kind"]
        if k == "snap":
            img = snap_push(img, e.get("amp", 1.0), p)
        elif k == "ring":
            col = {"red": RED, "gold": (201, 155, 44)}.get(e.get("color", "red"), RED)
            img = shock_ring(img, e["x"], e["y"], e["r"], p, col)
        elif k == "spark":
            img = spark_pop(img, e["x"], e["y"], e.get("n", 6), p)
        elif k == "sweep":
            img = sliver_sweep(img, p)
        elif k == "pulse":
            img = grade(img, (255, 246, 232), .10 * math.sin(math.pi * p),
                        1.0 + .10 * math.sin(math.pi * p), 1.0, 1.0 + .18 * math.sin(math.pi * p))
    return img


def ribbon(img, t, n):
    """Segmented chapter line at the bottom: 10 ticks, the played part in gold."""
    d = ImageDraw.Draw(img)
    dark = n == 10
    y = H - 24
    x0, x1 = 54, W - 54
    span = x1 - x0
    d.rounded_rectangle([x0, y, x1, y + 3], 2, fill=(30, 32, 38) if dark else (223, 219, 211))
    prog = cl(t / max(TOTAL, .001))
    d.rounded_rectangle([x0, y, x0 + int(span * prog), y + 3], 2,
                        fill=GOLD_L if dark else GOLD)
    for i, b in enumerate(BEATS):
        bx = x0 + int(span * (b["start"] / TOTAL))
        live = t >= b["start"] - .01
        hh = 7 if live else 5
        d.rounded_rectangle([bx - 1, y - hh + 1, bx + 1, y + 3], 1,
                            fill=(255, 214, 112) if live and dark else
                            ((201, 155, 44) if live else (206, 202, 194)))


# ------------------------------------------------------------------ lens plan
# (cx, cy, r, zoom, in, out) — zoom stays >= 2.4 so the glass shows a *detail*
LENS = {5: (812, 1516, 138, 2.50, 2.10, 3.20),
        9: (330, 1580, 130, 2.45, 1.40, 2.42)}


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
             scale=1.08, ground_fill=True):
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
    top = int(bottom - h)
    base.paste(im, (int((W - w) / 2), top), im)
    # the band's own bottom edge would draw a hard line inside the frame: carry
    # the last ground row down to the canvas edge instead
    if ground_fill and bottom < H:
        a_last = np.asarray(im.getchannel("A")).astype(np.int16)
        rows = np.where((a_last > 200).mean(axis=1) > .55)[0]
        y_last = int(rows[-1]) if len(rows) else im.height - 1
        y0 = max(0, y_last - 10)
        src = im.crop((0, y0, im.width, max(y0 + 1, y_last - 1)))
        src.putalpha(Image.new("L", src.size, 255))      # opaque: no pale seam
        strip = src.resize((im.width, H - bottom + 10), Image.LANCZOS)
        base.paste(strip, (int((W - w) / 2), bottom - 10), strip)


def label(base, txt, cx, cy, fill=(38, 49, 66), size=26, at=None, t=0, track=3):
    if at is None or t > at:
        pill(base, cx, cy, txt, fill=fill, size=size, track=track,
             opacity=eo(sg(t, at if at is not None else 0, .4)))


# =====================================================================
#  scenes
# =====================================================================
def s1(base, t, dur):
    """20,000 years ago: a sky, a cave, one human — and the question."""
    d = ImageDraw.Draw(base, "RGBA")
    rng = np.random.default_rng(7)
    for i in range(58):
        sx, sy = rng.integers(40, W - 40), rng.integers(330, 1010)
        r = rng.integers(2, 6)
        tw_ = .45 + .55 * abs(math.sin(t * 2.1 + i))
        d.ellipse([sx, sy, sx + r, sy + r], fill=(206, 200, 188, int(210 * tw_)))
    put_s(base, "moon", cx=836, cy=706, w=256, shadow=False)
    halo(base, 836, 706, 300, (255, 246, 226), .20 + .05 * math.sin(t * 2.4), .95)
    birds(base, t + 2, 300, 560, 3, scale=.85, opacity=.42)
    env_band(base, "env_hills", bottom=1420, opacity=.95)
    # the cave breathes smoke, the human just stands there
    smoke_plume(base, 470, 1620, t, .55, seed=4, w=80, rise=300)
    put_s(base, "env_cave", cx=500, bottom=1752, w=820)
    bob = math.sin(t * 1.9) * 3
    put_s(base, "human_idle", cx=886, bottom=1706 + bob, h=446,
          opacity=eo(sg(t, .35, .7)))
    halo(base, 886, 1620, 300, (255, 248, 232), .18, .95)
    motes(base, t, 14, seed=5, area=(120, 900, 1000, 1700))
    annot_circle(base, 886, 1486, 196, 262, sg(t, .95, .55), RED, 6)
    if t > 1.9:
        annot_arrow(base, 700, 1300, 790, 1450, sg(t, 1.9, .35), RED, 5, bow=40)
    if t > 2.4:
        pill(base, 552, 1755, "NA GHAR · NA KAPDE", fill=RED, size=26,
             opacity=eo(sg(t, 2.4, .4)), padx=22)
    motes(base, t + 1, 8, seed=11, area=(300, 400, 1000, 1200), alpha=70)


def s2(base, t, dur):
    """The question every morning: a predator closes in."""
    env_band(base, "env_hills", bottom=1330, opacity=.60)
    d = ImageDraw.Draw(base, "RGBA")
    d.rectangle([0, 1240, W, H], fill=(234, 228, 214, 255))
    put_s(base, "human_crouch", cx=258, bottom=1706, h=420 - 18 * eio(sg(t, .2, 2.6)),
          opacity=eo(sg(t, .3, .6)))
    k = eio(sg(t, .2, 2.6))
    # it steps in: each step kicks dust
    for i, at in enumerate((.35, 1.05, 1.75, 2.45)):
        if t > at:
            dust(base, int(1050 - 250 * eio(sg(t, .2, 2.6))) - 90 + i * 10, 1706,
                 .30 * (1 - sg(t, at, .45)), 250 * (1 + .4 * k))
    x_in = int(1060 - 268 * k)
    put_s(base, "sabertooth", cx=x_in, bottom=int(1712 - 14 * k),
          h=int(392 + 246 * k), flip=True, opacity=eo(sg(t, .2, .7)))
    halo(base, x_in - 60, int(1560 - 40 * k), 240, (198, 24, 44), .16 * eo(sg(t, .6, 1.2)), .95)
    if t > 2.2:
        speedlines(base, 620, 1080, eo(sg(t, 2.2, .5)) * .8, 780, 640)
        dust(base, 700, 1700, .5 * eo(sg(t, 2.2, .5)), 470)
    if t > .18:
        a = eo(sg(t, .18, .40))
        warn_badge(base, 556, 946, 256, a * (1 + .04 * math.sin(t * 9)), t)
    if t > 2.35:
        a = eo(sg(t, 2.35, .45))
        stamp(base, 600, 640, "ZINDA?", ang=-8, color=RED, size=96, scale=.9 + .1 * a,
              opacity=a)
    fg_grass(base, t, (36, 46, 34), .55, n=22, hmin=70, hmax=170)


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
    env_band(base, "env_cave_inside", bottom=1860, opacity=.92, feather=150)
    ignite = eo(sg(t, .85, .7))
    halo(base, 690, 1420, 520, (255, 190, 110), .30 * ignite, .95)
    flame_stage(base, 690, GL, 620, t, hot=max(.05, ignite), seed=3)
    smoke_plume(base, 690, 1180, t, .75 * ignite, seed=8, w=110, rise=460)
    put_s(base, "human_kneel", cx=340, bottom=1712, h=436,
          opacity=eo(sg(t, .2, .6)))
    if t > .95:
        annot_arrow(base, 470, 1520, 610, 1460, sg(t, .95, .40), RED, 6, bow=52)
    motes(base, t, 12, seed=9, area=(80, 800, 1000, 1700), color=(240, 200, 150), alpha=120)
    if t > 1.5:
        pill(base, 350, 1240, "PEHLI AAG", fill=RED, size=30,
             opacity=eo(sg(t, 1.5, .4)), track=3)
    if t > 2.9:
        a = eo(sg(t, 2.9, .5))
        stamp(base, 545, 720, "DOST", ang=7, color=RED, size=96, scale=.9 + .1 * a, opacity=a)
    fg_grass(base, t, (28, 26, 26), .40, n=18, hmin=60, hmax=130)


def s4(base, t, dur):
    """Warmth and light; the dark stays outside the circle."""
    d = ImageDraw.Draw(base, "RGBA")
    d.rectangle([0, 1180, W, H], fill=(232, 223, 206, 255))
    rng = np.random.default_rng(11)
    for i in range(34):
        sx, sy = rng.integers(20, W - 20), rng.integers(300, 1160)
        a = 150 * (.5 + .5 * abs(math.sin(t * 1.8 + i)))
        d.ellipse([sx, sy, sx + 4, sy + 4], fill=(176, 168, 156, int(a)))
    for r, op in ((700, .30), (500, .14)):
        halo(base, 540, 1400, r, (255, 190, 115), op, .95)
    flame_stage(base, 540, GL, 610, t, 1.0, seed=2)
    smoke_plume(base, 540, 1170, t, .5, seed=6, w=100, rise=380)
    put_s(base, "human_kneel", cx=206, bottom=1714, h=422, opacity=.98)
    put_s(base, "human_kneel2", cx=864, bottom=1714, h=422, opacity=.98, flip=True)
    put_s(base, "human_crouch", cx=692, bottom=1712, h=362, opacity=.94, flip=True,
          rot=2 * math.sin(t * 1.6))
    # something waiting just outside the light
    wx = int(1016 + 7 * math.sin(t * 2))
    put_s(base, "wolf", cx=wx, bottom=1660, h=252, silhouette=(24, 24, 28),
          opacity=.20 * eo(sg(t, 1.2, 1.0)))
    for i, (sx, sy) in enumerate(((wx - 26, 1530), (wx + 8, 1528))):
        d.ellipse([sx - 4, sy - 4, sx + 4, sy + 4],
                  fill=(255, 226, 130, int(200 * eo(sg(t, 1.4, 1.0)))))
    motes(base, t, 16, seed=13, area=(80, 900, 1000, 1700), color=(255, 214, 150), alpha=120)
    for i, (txt, col, at) in enumerate((("GARMI", RED, .35), ("ROSHNI", (201, 155, 44), .85),
                                        ("DARINDE DOOR", (38, 49, 66), 1.35))):
        if t > at:
            pill(base, 545, 402 + i * 62, txt, fill=col, size=27,
                 opacity=eo(sg(t, at, .35)), track=3)
    fg_grass(base, t, (26, 24, 24), .35, n=16, hmin=60, hmax=120)


def s5(base, t, dur):
    """Stone into tools — four strikes, each one lands on its sound cue."""
    strikes = (.75, 1.55, 2.35, 3.15)
    hit = max([-1] + [i for i, at in enumerate(strikes) if t > at - .26])
    put_s(base, "boulder", cx=430, bottom=1760, w=560)
    put_s(base, "rocks_small", cx=180, bottom=1760, w=250, opacity=.95)
    put_s(base, "human_kneel2", cx=165, bottom=1740, h=450)
    if hit < 0:
        swing = 0.0
    else:
        swing = eio(cl((t - (strikes[hit] - .26)) / .26))
    rot = -58 + 44 * swing
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
            dust(base, 428, 1740, (1 - p) * .8, 400)
    put_s(base, "spear", cx=806, bottom=1758, h=430, rot=-10,
          opacity=eo(sg(t, 1.85, .5)))
    if t > 2.15:
        annot_circle(base, 812, 1560, 132, 196, sg(t, 2.15, .5), RED, 6)
    if t > 1.25:
        a = eo(sg(t, 1.25, .45))
        stamp(base, 540, 690, "HATHIYAR", ang=-7, color=RED, size=84,
              scale=.9 + .1 * a, opacity=a)
    if t > 3.0:
        pill(base, 300, 1180, "SHIKAAR", fill=(38, 49, 66), size=28,
             opacity=eo(sg(t, 3.0, .4)), track=3)
    motes(base, t, 10, seed=17, area=(120, 900, 1000, 1600), color=(220, 200, 160), alpha=90)


def s6(base, t, dur):
    """Alone weak, together lethal."""
    env_band(base, "env_plain", bottom=1560, opacity=.92, feather=70, blur=2)
    wx = int(1090 - 400 * eio(sg(t, .1, 3.6)))
    step = math.sin(t * 5.4)
    put_s(base, "mammoth", cx=wx, bottom=int(1730 + 4 * step),
          h=530, rot=1.2 * step, flip=True, opacity=1.0)
    dust(base, wx - 210, 1712, .45 + .12 * abs(step), 420)
    for i, (x, hh, fl) in enumerate(((170, 400, False), (330, 430, True), (80, 350, False))):
        put_s(base, "human_pair", cx=x, bottom=1720 + int(3 * math.sin(t * 6 + i)),
              h=hh, opacity=eo(sg(t, .7 + i * .1, .5)), flip=fl)
    # the spear leaves the hunters' hands and crosses the frame
    if .95 < t < 1.85:
        u = cl((t - .95) / .9)
        sx = 470 + 190 * u
        sy = 1560 - 250 * math.sin(math.pi * u) - 30 * u
        put_s(base, "spear", cx=int(sx), cy=int(sy), h=310, rot=-62 + 40 * u,
              opacity=1.0, shadow=False)
        for k in range(3):
            lay_u = max(0, u - .04 * (k + 1))
            d2 = ImageDraw.Draw(base, "RGBA")
            d2.line([(470 + 190 * lay_u, 1560 - 210 * math.sin(math.pi * lay_u) - 40 * lay_u),
                     (sx - 30, sy + 10)],
                    fill=(180, 170, 156, int(110 - k * 30)), width=5 - k)
    if 1.78 < t < 2.30:                      # the spear lands
        p = sg(t, 1.78, .30)
        halo(base, 672, 1480, 230, (255, 220, 170), .55 * (1 - p), .95)
        dust(base, 668, 1700, (1 - p) * .75, 400)
    if t > 1.1:
        speedlines(base, 760, 1320, eo(sg(t, 1.1, .5)) * .85, 820, 620)
    if t > 1.3:
        a = eo(sg(t, 1.3, .45))
        stamp(base, 600, 620, "JHUND", ang=-6, color=RED, size=96, scale=.9 + .1 * a,
              opacity=a)
    if t > 2.7:
        put_text_scaled(base, "KHATARNAAK", F(N9, 82), RED, 546, 1040, .98,
                        eo(sg(t, 2.7, .45)))
    motes(base, t, 12, seed=19, area=(60, 800, 1020, 1650))
    fg_grass(base, t, (34, 44, 32), .5, n=20, hmin=70, hmax=160)


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
            put_s(base, "hide_cloak", cx=336, cy=1400, h=248, rot=-2, opacity=.98,
                  shadow=False)
            put_s(base, "ui_sparkle", cx=336, cy=1300, w=150, opacity=.55,
                  rot=t * 30, shadow=False)
    dust(base, 330, 1460, .5 * eo(sg(t, 1.05, .5)), 300)
    halo(base, 640, 1500, 300, (255, 190, 120), .16 + .04 * math.sin(t * 3), .95)
    motes(base, t + 2, 10, seed=12, area=(480, 1250, 900, 1700), color=(255, 200, 150),
          alpha=140, spread=.7)
    put_s(base, "human_kneel", cx=980, bottom=1690, h=280,
          opacity=.60 * eo(sg(t, 2.2, .8)))
    if t > 1.5:
        a = eo(sg(t, 1.5, .42))
        stamp(base, 540, 700, "JACKET", ang=-7, color=RED, size=82,
              scale=.9 + .1 * a, opacity=a)
    if t > 2.4:
        pill(base, 830, 1180, "GUFA = GHAR", fill=(38, 49, 66), size=28,
             opacity=eo(sg(t, 2.4, .4)), track=3)
    motes(base, t, 10, seed=23, area=(200, 900, 900, 1650), color=(240, 210, 170), alpha=100)


def s8(base, t, dur):
    """Language — the weapon that is not a weapon."""
    put_s(base, "human_pair", cx=230, bottom=1716, h=470, flip=True)
    put_s(base, "human_idle", cx=846, bottom=1714, h=474, flip=False)
    for k in range(3):
        p = (t * .55 + k / 3) % 1.0
        halo(base, 545, 1090, int(130 + 300 * p), (255, 236, 214),
             (1 - p) * .22 * eo(sg(t, .3, .5)), .95)
    if t > .55:
        annot_arrow(base, 620, 1180, 470, 1240, sg(t, .55, .40), (32, 96, 176), 6, bow=34)
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
    motes(base, t, 12, seed=29, area=(80, 700, 1000, 1650))


def s9(base, t, dur):
    """Seeds to the first harvest — sunrise over a field."""
    suna = t * 1.3
    put_s(base, "sun", cx=540, cy=720, w=300, rot=math.sin(suna) * 3, shadow=False)
    for r, op in ((420, .12), (600, .08)):
        halo(base, 540, 720, r, (255, 214, 130), op, .95)
    birds(base, t + 4, 300, 560, 2, scale=.7, opacity=.38)
    env_band(base, "env_field", bottom=1870, opacity=.95, feather=110)
    for i in range(5):
        x = 128 + i * 208
        put_s(base, "wheat", cx=x, bottom=1806 + (i % 2) * 10, h=380 + (i % 3) * 40,
              rot=math.sin(t * 1.6 + i) * 3, opacity=.97, shadow=False)
    put_s(base, "sprout", cx=330, bottom=1716, h=int(90 + 150 * eo(sg(t, .5, 1.8))),
          opacity=eo(sg(t, .45, .5)))
    put_s(base, "seeds", cx=620, cy=1120, w=210, rot=-8 + 6 * math.sin(t * 2.2),
          opacity=eo(sg(t, .9, .6)), shadow=False)
    if t > .95:
        annot_arrow(base, 560, 1210, 400, 1420, sg(t, .95, .45), (32, 96, 176), 6, bow=46)
    # the deer crosses without noticing us
    dcx = int(980 - 70 * eio(sg(t, .8, 3.6)))
    put_s(base, "deer", cx=dcx, bottom=1620 + int(3 * math.sin(t * 4)),
          h=230, opacity=.50 * eo(sg(t, 1.6, 1.0)), flip=True)
    d = ImageDraw.Draw(base, "RGBA")
    for k in range(8):
        p = sg(t, .2 + k * .1, 1.2)
        if 0 < p < 1:
            sx = 620 + (k - 4) * 18
            d.ellipse([sx - 6, 1000 + p * 420, sx + 6, 1012 + p * 420],
                      fill=(196, 150, 60, int(220 * (1 - p * .4))))
    if t > 1.35:
        a = eo(sg(t, 1.35, .45))
        stamp(base, 690, 560, "BEEJ", ang=8, color=RED, size=88,
              scale=.9 + .1 * a, opacity=a)
    if t > 2.9:
        pill(base, 700, 790, "BHOOKH KAM", fill=(38, 49, 66), size=26,
             opacity=eo(sg(t, 2.9, .4)), track=3)
    motes(base, t, 14, seed=31, area=(60, 700, 1020, 1750), color=(255, 226, 160), alpha=95)


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
    motes(base, t, 16, seed=37, area=(100, 900, 1000, 1750), color=(150, 195, 255), alpha=80)
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

    # hit-stop: on every impact the picture holds two frames while the edit
    # keeps breathing — the cheapest way to make a hit feel expensive
    tl_scene = tl
    for at, _amp, _dec in SHAKE.get(b["n"], []):
        if 0 <= tl - at < 2.0 / FPS:
            tl_scene = at
    img = scene_frame(b["n"], tl_scene)

    if idx > 0:
        prev = BEATS[idx - 1]
        p = (t - (b["start"] - TRANS_W * .5)) / TRANS_W
        if 0 <= p <= 1:
            a = scene_frame(prev["n"], prev["dur"] + (t - b["start"]) + .05)
            if b["n"] in (3, 7):
                img = ink_wipe(a, img, p)
            elif b["n"] in (4, 9):
                img = slice_wipe(a, img, p)
            else:
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

    in_insert = False
    if b["n"] in INSERTS:
        _fn, at, ln = INSERTS[b["n"]]
        if at <= tl <= at + ln:
            in_insert = True
            u = (tl - at) / ln
            ins = insert_frame(b["n"], tl)
            if u < .22:                      # whip into the insert
                img = zoom_blur(vlib.flash(ins, WHITE, .22 * (1 - u / .22)), .55 * (1 - u / .22))
            elif u > .80:                    # and whip back out
                k = (u - .80) / .20
                img = zoom_blur(vlib.flash(ins, WHITE, .18 * k), .65 * k)
            else:
                img = ins

    if not in_insert:
        img = apply_events(img, b["n"], tl)

    # the magnifier: a detail reveal, so the eye has something new to find
    if b["n"] in LENS:
        cx, cy, r, zoom, t_in, t_out = LENS[b["n"]]
        if t_in <= tl <= t_out:
            grow = eo(sg(tl, t_in, .34)) * (1 - eo(sg(tl, t_out - .28, .28)))
            rr = r * (grow * 1.04 + .02) * (1 + .05 * math.sin((tl - t_in) * 9))
            zz = 1.0 + (zoom - 1.0) * min(1.0, grow * 1.3)
            lens(img, cx, cy, rr, zz)

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
    ribbon(img, t, b["n"])
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
