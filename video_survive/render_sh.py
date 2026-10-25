#!/usr/bin/env python3
"""
render_sh.py — "How Ancient Humans Survived" (9:16, 46 s, cinematic).

A new film, not a Law template: dark prehistory palette (charcoal night, ember,
bone, cold moonlight), procedural silhouettes (fire, cave, spear, mammoth,
hide, sprout), and the same camera/optics language the Law series earned —
whip transitions, punch blur on the picture only, anamorphic streak, light
leaks, weave, exposure breathe, grain.

Typography is drawn after every optic so the words never blur.

  python render_sh.py stills 0.5 6 12.4 ...   -> out/still_<t>.jpg
  python render_sh.py full                    -> out/survive_silent.mp4
"""
from __future__ import annotations

import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import vlib
from vlib import (F, H, N6, N7, N8, N9, S7, W, apply_camera, apply_grain,
                  apply_vignette, cl, eio, eo, ei, lerp, pill, put_text_scaled,
                  sg, transition, halo)
from render_v3 import (anamorphic, bloom, chroma, exposure_breathe, leak,
                       light_sweep, vignette_pulse, weave, whip_blur, zoom_blur)
from timeline_sh import BEATS, TOTAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)
FPS = vlib.FPS
FF = "/tmp/v/venv_ffmpeg"      # resolved below
TRANS_W = 0.34

# ------------------------------------------------------------------ palette
NIGHT = (9, 11, 15)
NIGHT2 = (18, 20, 26)
EMBER = (255, 122, 47)
GOLD = (255, 201, 113)
BONE = (232, 223, 203)
COLD = (108, 138, 168)
COLD_D = (28, 38, 52)
RED = (214, 48, 48)
WHITE = (255, 255, 255)


def ffmpeg() -> str:
    global FF
    if os.path.exists(FF):
        return FF
    import imageio_ffmpeg
    FF = imageio_ffmpeg.get_ffmpeg_exe()
    return FF


# ------------------------------------------------------------------ backdrops
_VG: dict = {}


def vgrad(top, bottom, curve=1.0) -> Image.Image:
    """Vertical gradient, cached — the cheap part of every frame."""
    key = (top, bottom, round(curve, 3))
    if key in _VG:
        return _VG[key].copy()
    y = np.linspace(0, 1, H, dtype=np.float32) ** curve
    a = np.array(top, dtype=np.float32)
    b = np.array(bottom, dtype=np.float32)
    col = (a[None, :] * (1 - y[:, None]) + b[None, :] * y[:, None]).astype(np.uint8)
    arr = np.repeat(col[:, None, :], W, axis=1)
    im = Image.fromarray(arr, "RGB")
    _VG[key] = im
    return im.copy()


def stars(img, n=90, seed=3, alpha=.55):
    rng = np.random.default_rng(seed)
    d = ImageDraw.Draw(img, "RGBA")
    xs = rng.integers(0, W, n)
    ys = rng.integers(0, int(H * .62), n)
    for x, y in zip(xs, ys):
        r = int(rng.integers(1, 3))
        a = int(255 * alpha * rng.uniform(.25, 1))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 252, 240, a))


def cave_arch(img, top_y=760, color=(6, 7, 10), jag=46, seed=7):
    """The mouth of the cave: a jagged black arch framing the whole frame."""
    rng = np.random.default_rng(seed)
    d = ImageDraw.Draw(img)
    pts = [(0, 0), (W, 0)]
    for i in range(13):
        x = W - i * (W / 12)
        pts.append((x, top_y + rng.integers(-jag, jag)))
    pts.append((0, top_y + rng.integers(-jag, jag)))
    d.polygon(pts, fill=color)
    for i in range(9):
        x = i * W / 8 + rng.integers(-30, 30)
        d.polygon([(x, top_y + 10), (x + 26, top_y + 10),
                   (x + 13, top_y - rng.integers(30, 110))], fill=color)


# ------------------------------------------------------------------ figures
def _limb(d, x0, y0, a1, l1, a2, l2, w, col):
    """Two-segment limb; angles in radians from straight down."""
    ex, ey = x0 + math.sin(a1) * l1, y0 + math.cos(a1) * l1
    hx, hy = ex + math.sin(a2) * l2, ey + math.cos(a2) * l2
    d.line([(x0, y0), (ex, ey)], fill=col, width=w)
    d.line([(ex, ey), (hx, hy)], fill=col, width=w)
    d.ellipse([hx - w * .55, hy - w * .55, hx + w * .55, hy + w * .55], fill=col)
    return hx, hy


def stick(d, x, y, h, color=BONE, lean=0.0, walk=0.0, arms=(.5, .5),
          alpha=255, spear=None, seated=False, hide=None, shadow=True):
    """An articulated figure: hips, knees, shoulders, elbows — not a pictogram.

    `y` is the ground line, `h` the full standing height. `arms` are 0..1
    (0 = hanging, 1 = raised). `spear=(dx, dy, ang, len)` in local offsets.
    """
    col = tuple(color) + (alpha,)
    w = max(4, int(h * .050))
    hip_y = y - h * .47
    sh_y = y - h * .80
    head_r = h * .072
    sw = math.sin(walk) * h * .22                      # stride
    bob = abs(math.sin(walk)) * h * .012
    dx = lean * h * .10

    if shadow:
        sh = Image.new("RGBA", (int(h), int(h * .3)), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sh)
        ds.ellipse([h * .10, h * .06, h * .90, h * .26], fill=(0, 0, 0, 110))
        sh = sh.filter(ImageFilter.GaussianBlur(h * .03))
        d._image.paste(sh, (int(x - h * .5), int(y - h * .12)), sh)

    # legs
    if seated:
        _limb(d, x, hip_y, math.pi / 2 * .92, h * .25, -.15, h * .24, w, col)
        _limb(d, x + 6, hip_y, math.pi / 2 - .05, h * .25, .05, h * .24, w, col)
    else:
        _limb(d, x, hip_y + bob * .3, .35 + sw / h * .9, h * .24, -sw / h * .5, h * .235, w, col)
        _limb(d, x + 4, hip_y + bob * .3, -.35 + sw / h * .9 * -1, h * .24,
              sw / h * .45, h * .235, w, col)
    # spine
    d.line([(x, hip_y), (x + dx, sh_y + bob)], fill=col, width=w)
    # head
    hx, hy = x + dx * 1.25, sh_y + bob - head_r * 1.5
    d.ellipse([hx - head_r, hy - head_r, hx + head_r, hy + head_r], fill=col)
    d.line([(x + dx, sh_y + bob), (hx, hy + head_r * .8)], fill=col, width=w)
    # arms: 0 hangs, 1 points up
    for i, a in enumerate(arms):
        sgn = -1 if i == 0 else 1
        a1 = sgn * (.03 + a * 1.42) + sw / h * .30 * sgn
        a2 = a1 * .55 + sgn * .12          # forearm drops back toward the body
        _limb(d, x + dx + sgn * h * .045, sh_y + bob + h * .02,
              a1, h * .165, a2, h * .155, w, col)
    if hide:
        top = sh_y + bob - head_r * .35
        wdt = h * .20
        pts = []
        for i in range(9):                       # shoulder line with fur bumps
            u = i / 8
            pts.append((x - wdt + 2 * wdt * u,
                        top + 10 * math.sin(u * 9) + h * .05 * (1 - abs(.5 - u) * 2)))
        for i in range(7):                       # ragged hem
            u = 1 - i / 6
            yy = y - h * .33 - (i % 2) * h * .05
            pts.append((x - wdt * .92 + 1.84 * wdt * u, yy))
        d.polygon(pts, fill=(128, 98, 70, int(238 * hide)))
        for k in range(7):                       # fur strokes
            fx = x - wdt * .8 + k * wdt * .27
            d.line([(fx, top + h * .09), (fx + 4, y - h * .34)],
                   fill=(100, 74, 52, int(210 * hide)), width=max(3, w // 2))
        # the head stays visible in the hood opening
        ox = x + dx * 1.25
        d.ellipse([ox - head_r * .92, hy - head_r * .92, ox + head_r * .92, hy + head_r * .92],
                  fill=col)
        d.arc([ox - head_r * 1.25, hy - head_r * 1.25, ox + head_r * 1.25, hy + head_r * 1.25],
              200, 340, fill=(96, 72, 52, int(230 * hide)), width=max(4, w // 2))
        for k in range(5):
            d.line([(x - wdt * .8 + k * wdt * .4, top + h * .20),
                    (x - wdt * .8 + k * wdt * .4, y - h * .12)],
                   fill=(96, 72, 52, int(190 * hide)), width=max(3, w // 2))
    if spear:
        ox, oy, ang, L = spear
        sx, sy = x + ox, y + oy
        d.line([(sx, sy), (sx + math.cos(ang) * L, sy - math.sin(ang) * L)],
               fill=col, width=max(3, int(w * .7)))
        tx, ty = sx + math.cos(ang) * L, sy - math.sin(ang) * L
        d.polygon([(tx, ty), (tx - 13, ty + 24), (tx + 9, ty + 22)], fill=col)


def rocks(img, y, n=7, color=(8, 9, 12), seed=5, hmin=60, hmax=190):
    """Foreground rock silhouettes — the cheapest way to get depth."""
    rng = np.random.default_rng(seed)
    d = ImageDraw.Draw(img)
    for i in range(n):
        x = i * (W / max(n - 1, 1)) + rng.integers(-40, 40)
        hh = int(rng.integers(hmin, hmax))
        ww = int(rng.integers(110, 260))
        d.polygon([(x - ww, y), (x - ww * .55, y - hh * .8), (x - ww * .1, y - hh),
                   (x + ww * .45, y - hh * .75), (x + ww, y)], fill=color)


def light_shafts(img, cx, cy, t, amt=.30, color=(255, 190, 120)):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for i in range(5):
        a = -0.9 + i * 0.45 + math.sin(t * .6 + i) * .05
        ln = 900
        d.polygon([(cx, cy), (cx + math.cos(a - .10) * ln, cy + math.sin(a - .10) * ln),
                   (cx + math.cos(a + .10) * ln, cy + math.sin(a + .10) * ln)],
                  fill=tuple(color) + (int(28 * amt * 100 / 30),))
    lay = lay.filter(ImageFilter.GaussianBlur(40))
    img.paste(lay, (0, 0), lay)


def mammoth(d, x, ground, w, color=(10, 11, 15), alpha=255, t=0.0):
    """Silhouette: body, hump, head, trunk, tusk, four legs. `w` = body width."""
    col = tuple(color) + (alpha,)
    h = w * .68
    body = [x - w * .5, ground - h * .82, x + w * .34, ground - h * .18]
    d.ellipse(body, fill=col)
    d.ellipse([x - w * .16, ground - h * 1.02, x + w * .18, ground - h * .52], fill=col)  # hump
    hx = x + w * .40
    d.ellipse([hx - w * .17, ground - h * .92, hx + w * .17, ground - h * .46], fill=col)
    sway = math.sin(t * .9) * w * .02
    d.line([(hx + w * .10, ground - h * .70),
            (hx + w * .17 + sway, ground - h * .34),
            (hx + w * .10 + sway, ground - h * .06)], fill=col, width=int(w * .055))
    d.line([(hx + w * .06, ground - h * .58), (hx + w * .22, ground - h * .30)],
           fill=(226, 216, 190, alpha), width=max(3, int(w * .018)))      # tusk
    for i, lx in enumerate((x - w * .40, x - w * .24, x + w * .06, x + w * .22)):
        d.line([(lx, ground - h * .28), (lx, ground)], fill=col, width=int(w * .075))


def _flame_pts(cx, base_y, w, h, t, ph=0.0, n=26):
    """Real flame outline: wide base, tapering tongues, animated wobble."""
    pts_r, pts_l = [], []
    for i in range(n + 1):
        u = i / n                                   # 0 at base -> 1 at tip
        y = base_y - h * u
        # width profile: fat near the bottom, pinch to a point at the top
        prof = (1 - u) ** .55 * (0.55 + 0.45 * math.sin(math.pi * min(1, u * 1.25)))
        wob = (math.sin(u * 7 + t * 8 + ph) * .12 +
               math.sin(u * 3.1 - t * 4.3 + ph) * .10) * u
        half = w * .5 * prof * (1 + wob)
        sway = math.sin(t * 3.2 + ph + u * 2) * w * .10 * u ** 1.5
        pts_r.append((cx + half + sway, y))
        pts_l.append((cx - half + sway, y))
    return pts_l[::-1] + pts_r


def fire(img, cx, base_y, scale, t, hot=1.0, seed=0):
    """Layered flame + glow + embers. Read as fire, not as a dome."""
    rng = np.random.default_rng(seed + int(t * 6))
    halo(img, cx, base_y - 90 * scale, 320 * scale, (255, 140, 60), .55 * hot, .85)
    halo(img, cx, base_y - 110 * scale, 160 * scale, (255, 205, 140), .45 * hot, .9)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    # three tongues of different heights so it never reads as one blob
    for li, (wf, hf, dxf, col) in enumerate((
            (1.00, 1.00, 0.00, (206, 58, 14, 205)),
            (0.62, 1.22, 0.10, (240, 96, 24, 205)),
            (0.72, 0.72, -0.16, (255, 130, 40, 195)),
            (0.44, 0.92, 0.02, (255, 186, 84, 225)),
            (0.24, 0.62, 0.01, (255, 240, 205, 240)))):
        pts = _flame_pts(cx + dxf * 80 * scale, base_y, 150 * scale * wf,
                         300 * scale * hf, t, ph=li * 1.7)
        d.polygon(pts, fill=col)
    layer = layer.filter(ImageFilter.GaussianBlur(5 * scale))
    img.paste(layer, (0, 0), layer)
    # rising licks: small flames that detach and shrink
    d2 = ImageDraw.Draw(img, "RGBA")
    for k in range(5):
        p = ((t * .8 + k / 5) % 1.0)
        lx = cx + math.sin(k * 2.3 + t) * 70 * scale
        ly = base_y - (240 + p * 320) * scale
        lw = 34 * scale * (1 - p) * hot
        if lw > 2:
            d2.polygon(_flame_pts(lx, ly, lw, 110 * scale * (1 - p), t, ph=k * 2.1),
                       fill=(255, 170 + int(60 * (1 - p)), 90, int(200 * (1 - p))))
    for _ in range(int(30 * hot)):
        u = rng.uniform(0, 1)
        ex = cx + rng.normal(0, 52 * scale)
        ey = base_y - (150 + u * 470) * scale
        r = rng.uniform(1.2, 3.4) * scale
        a = int(235 * (1 - u) * hot)
        d2.ellipse([ex - r, ey - r, ex + r, ey + r],
                   fill=(255, 176 + int(60 * u), 90, a))


def eyes(d, x, y, gap=44, r=13, glow=1.0, color=(255, 208, 92)):
    for i in (-1, 1):
        cx = x + i * gap / 2
        d.ellipse([cx - r * 2.2, y - r * 1.6, cx + r * 2.2, y + r * 1.6],
                  fill=tuple(color) + (int(38 * glow),))
        d.ellipse([cx - r, y - r * .62, cx + r, y + r * .62],
                  fill=tuple(color) + (int(240 * glow),))


def sprout(d, x, base_y, g, t=0.0, color=(132, 186, 92)):
    """g: 0..1 growth."""
    if g <= 0.01:
        return
    h = 150 * g
    sway = math.sin(t * 2.2) * 8 * g
    d.line([(x, base_y), (x + sway, base_y - h)], fill=tuple(color) + (255,),
           width=max(3, int(6 * g)))
    for s in (-1, 1):
        if g > .35:
            lw = 62 * g
            d.polygon([(x + sway * .5, base_y - h * .55),
                       (x + s * lw, base_y - h * .78),
                       (x + sway, base_y - h * .40)], fill=tuple(color) + (235,))


def wheat_row(d, y, t, count=9, color=(150, 132, 74)):
    for i in range(count):
        x = 80 + i * (W - 160) / (count - 1)
        sway = math.sin(t * 1.6 + i * .7) * 12
        h = 210 + (i % 3) * 26
        d.line([(x, y), (x + sway, y - h)], fill=tuple(color) + (230,), width=5)
        for k in range(4):
            yy = y - h * (.55 + .12 * k)
            d.line([(x + sway * .6, yy), (x + sway * .6 + 16, yy - 18)],
                   fill=tuple(color) + (200,), width=4)
            d.line([(x + sway * .6, yy), (x + sway * .6 - 16, yy - 18)],
                   fill=tuple(color) + (200,), width=4)
        d.ellipse([x + sway - 9, y - h - 26, x + sway + 9, y - h + 6],
                  fill=tuple(min(255, c + 26) for c in color) + (235,))


# ------------------------------------------------------------------ text
def headline(img, head, sub, tl, accent=EMBER, dur=1.0, y=250):
    """Kinetic title: pop-in with a bounce, hold, fade at the very end."""
    a = eo(sg(tl, .02, .34)) * (1 - cl(sg(tl, 4.05, .35)))
    if a <= .01:
        return
    sc = 1.14 - .14 * eob_local(sg(tl, .02, .30))
    y2 = y - 26 * eob_local(sg(tl, .02, .34)) + 26
    f = F(N9, 96)
    # fit long heads
    while vlib.tw(ImageDraw.Draw(img), head, f) > W - 190:
        f = F(N9, f.size - 4)
    put_text_scaled(img, head, f, WHITE, W // 2, int(y2), sc, a)
    if sub:
        sa = eo(sg(tl, .22, .38)) * (1 - cl(sg(tl, 4.05, .35)))
        fs = F(N6, 40)
        while vlib.tw(ImageDraw.Draw(img), sub, fs) > W - 210:
            fs = F(N6, fs.size - 2)
        put_text_scaled(img, sub, fs, (255, 255, 255), W // 2, int(y2 + 92 + 40 * sg(tl, .22, .3)),
                        .98, sa * .92)


def eob_local(t):
    t = cl(t)
    return 1 - (1 - t) ** 2.2


def tag(img, tl):
    a = eo(sg(tl, 1.2, .8))
    if a < .02:
        return
    put_text_scaled(img, "MONARCH · STICKMAN", F(N7, 26), (255, 255, 255), W // 2, H - 92,
                    .98, a * .5)


# ------------------------------------------------------------------ scenes
def sc1(b, t):
    """20,000 years ago — cave mouth, cold night, one silhouette."""
    b.paste(vgrad((10, 16, 26), (26, 30, 38)))
    stars(b, 110, 3)
    halo(b, W * .74, 300, 300, (150, 180, 210), .30, .95)          # moon
    d = ImageDraw.Draw(b, "RGBA")
    d.ellipse([W * .74 - 70, 300 - 70, W * .74 + 70, 300 + 70], fill=(226, 234, 246, 235))
    for i in range(6):                                              # far hills
        d.polygon([(i * 220 - 60, 1180), (i * 220 + 90, 1010), (i * 220 + 260, 1180)],
                  fill=(16, 20, 28, 255))
    d.rectangle([0, 1180, W, H], fill=(14, 17, 23, 255))
    rocks(b, 1250, 6, (12, 15, 21), 12, 70, 200)
    cave_arch(b, 700, (7, 8, 12), 60, 7)
    rocks(b, H, 5, (6, 7, 10), 31, 150, 340)
    # snow
    rng = np.random.default_rng(int(abs(t) * 30) + 1)
    for _ in range(70):
        x = rng.integers(0, W)
        y = int((rng.uniform(0, H) + t * 90) % H)
        r = rng.integers(1, 3)
        d.ellipse([x, y, x + r, y + r], fill=(230, 240, 255, 120))
    stick(d, W * .5 - 40, 1500, 300, BONE, lean=-.15, arms=(.10, .22),
          alpha=int(255 * eo(sg(t, .5, .9))))
    halo(b, W * .5 - 40, 1400, 260, (120, 155, 190), .22, .95)
    headline(b, "20,000 SAAL PEHLE", "na ghar · na kapde · na khana", t)
    tag(b, t)


def sc2(b, t):
    """The question every morning — predators in the dark."""
    b.paste(vgrad((6, 7, 11), (20, 15, 16)))
    d = ImageDraw.Draw(b, "RGBA")
    d.rectangle([0, 1250, W, H], fill=(9, 9, 12, 255))
    rocks(b, 1300, 6, (8, 8, 11), 22, 80, 220)
    cave_arch(b, 690, (4, 4, 6), 44, 11)
    # a big cat silhouette fading in behind the figure (stalking, not attacking)
    prowl = eo(sg(t, 1.1, 1.4))
    if prowl > .02:
        px, py = W * .62 + 40 * math.sin(t * .8), 1085
        body = (int(28 * prowl), int(24 * prowl), int(22 * prowl))
        d.ellipse([px - 210, py - 90, px + 150, py + 60], fill=body + (255,))
        d.ellipse([px + 90, py - 150, px + 250, py - 20], fill=body + (255,))    # head
        d.polygon([(px + 100, py - 140), (px + 130, py - 215), (px + 160, py - 130)],
                  fill=body + (255,))
        d.polygon([(px + 185, py - 140), (px + 215, py - 210), (px + 240, py - 125)],
                  fill=body + (255,))
        for k, lx in enumerate((px - 170, px - 60, px + 40, px + 110)):
            d.line([(lx, py + 30), (lx + (8 if k % 2 else -8), py + 150)], fill=body + (255,), width=16)
        d.line([(px - 210, py - 30), (px - 300, py - 120 + 20 * math.sin(t * 2))],
               fill=body + (255,), width=14)
        g = .55 + .45 * math.sin(t * 3)
        eyes(d, px + 170, py - 90, 46, 11, prowl * g, (255, 110, 80))
    for i, (x, y, s) in enumerate(((210, 780, .7), (830, 700, .55))):
        g = eo(sg(t, .5 + i * .6, .5)) * (.6 + .4 * math.sin(t * 3 + i))
        if g > .03:
            eyes(d, x, y, 40 * s, 9 * s, g, (255, 208, 92))
    stick(d, W * .5 + 30, 1560, 330, BONE, lean=.12, arms=(.2, .45),
          alpha=int(255 * eo(sg(t, 0, .6))))
    halo(b, W * .5 + 30, 1420, 300, (150, 130, 120), .20, .95)
    headline(b, "AAJ ZINDA RAHOGE?", "har subah ek hi sawal", t, accent=RED)


def sc3(b, t):
    """Lightning → the first controlled fire."""
    b.paste(vgrad((12, 14, 22), (30, 22, 20)))
    d = ImageDraw.Draw(b, "RGBA")
    d.rectangle([0, 1240, W, H], fill=(16, 14, 14, 255))
    cave_arch(b, 720, (6, 6, 9), 52, 5)
    if t < .9:                                  # the strike
        k = 1 - abs(t - .28) / .30
        if k > 0:
            rng = np.random.default_rng(4)
            x = W * .56
            xs = [x]
            for i in range(9):
                x += rng.integers(-40, 40)
                d.line([(xs[-1], 120 + i * 118), (x, 120 + (i + 1) * 118)],
                       fill=(235, 245, 255, int(255 * k)), width=7)
                xs.append(x)
            b2 = Image.new("RGB", (W, H), (255, 255, 255))
            b.paste(Image.blend(b, b2, .55 * k))
    rocks(b, 1330, 5, (10, 9, 9), 44, 60, 180)
    ignite = eo(sg(t, .9, .55))
    if ignite > .01:
        fire(b, W * .56, 1330, .55 + .75 * ignite, t, hot=ignite)
    stick(d, W * .30, 1470, 300, BONE, lean=.35, arms=(.12, 1.0),
          alpha=int(255 * eo(sg(t, .2, .5))))
    if ignite > .5:
        p = pill(b, W * .5, 560, "AAG", fill=EMBER, size=40,
                 opacity=eo(sg(t, 1.5, .4)), track=6)
    headline(b, "PHIR AAG MILI", "insaan ne aag ko dost banaya", t)


def sc4(b, t):
    """Fire = warmth, light, and the wild stays out."""
    b.paste(vgrad((18, 12, 12), (46, 24, 16)))
    d = ImageDraw.Draw(b, "RGBA")
    d.rectangle([0, 1300, W, H], fill=(22, 15, 12, 255))
    rocks(b, 1350, 6, (14, 10, 8), 55, 50, 150)
    fire(b, W * .5, 1330, 1.25, t, 1.0, seed=2)
    light_shafts(b, W * .5, 1200, t, .5, (255, 170, 100))
    for i, (x, lean) in enumerate(((W * .22, .18), (W * .78, -.18), (W * .5 + 4, .02))):
        seated = i == 2
        stick(d, x, 1560 if not seated else 1640, 280, BONE, lean=lean,
              arms=(.55, .55), alpha=250, seated=seated)
    draw_ring(d, W * .5, 1340, 300 + 40 * math.sin(t * 2), (255, 160, 80, 40))
    headline(b, "GARMI · ROSHNI", "aur darinde door", t)


def draw_ring(d, cx, cy, r, color):
    d.ellipse([cx - r, cy - r * .40, cx + r, cy + r * .40], outline=color, width=4)


def sc5(b, t):
    """Stone into tools — sparks on each strike."""
    b.paste(vgrad((14, 13, 12), (34, 28, 22)))
    d = ImageDraw.Draw(b, "RGBA")
    d.rectangle([0, 1290, W, H], fill=(20, 17, 14, 255))
    vlib.halo(b, W * .58, 1150, 260, (255, 170, 90), .30, .9)
    # anvil stone + knapped core
    rocks(b, 1300, 6, (13, 12, 11), 66, 40, 120)
    d.ellipse([W * .40, 1230, W * .74, 1380], fill=(62, 58, 54, 255))
    d.ellipse([W * .47, 1130, W * .66, 1260], fill=(78, 72, 64, 255))
    d.polygon([(W * .50, 1120), (W * .60, 1100), (W * .63, 1180), (W * .52, 1200)],
              fill=(96, 90, 82, 255))
    for i, at in enumerate((.75, 1.55, 2.35, 3.15)):
        p = sg(t, at, .30)
        if 0 < p < 1:
            cx, cy = W * .44, 1160
            for k in range(10):
                a = k / 10 * math.tau
                r = 30 + 120 * p
                d.line([(cx + math.cos(a) * r * .5, cy + math.sin(a) * r * .4),
                        (cx + math.cos(a) * r, cy + math.sin(a) * r * .8)],
                       fill=(255, 210, 130, int(255 * (1 - p))), width=4)
            vlib.halo(b, cx, cy, 150, (255, 220, 150), .5 * (1 - p), .95)
    stick(d, W * .32, 1470, 320, BONE, lean=.45, arms=(.9, .25))
    pill(b, W * .5, 620, "PATTHAR", fill=(88, 80, 70), size=34, opacity=eo(sg(t, 1.2, .4)))
    pill(b, W * .5, 700, "HATHIYAR", fill=EMBER, size=34, opacity=eo(sg(t, 2.0, .4)))
    headline(b, "HATHIYAR", "pathar tod ke bana", t)


def sc6(b, t):
    """Alone weak, together lethal — hunters vs mammoth."""
    b.paste(vgrad((10, 14, 22), (34, 26, 22)))
    d = ImageDraw.Draw(b, "RGBA")
    d.rectangle([0, 1260, W, H], fill=(24, 20, 18, 255))
    rocks(b, 1300, 5, (15, 13, 12), 77, 50, 150)
    for i in range(5):
        d.polygon([(i * 260 - 80, 1260), (i * 260 + 70, 1080), (i * 260 + 240, 1260)],
                  fill=(18, 20, 26, 255))
    mammoth(d, W * .72, 1290, 520, (8, 9, 12), 255, t)
    for i, (x, ph) in enumerate(((150, 0), (285, .6), (400, 1.2), (520, 1.8))):
        walk = t * 5 + ph * 3
        stick(d, x, 1400, 250, BONE, lean=.22, walk=walk, arms=(.75, .45),
              spear=(86, -196, .30, 300), alpha=250)
    if t > .8:
        k = 1 - abs(t - 1.0) / .45
        if k > 0:
            vlib.halo(b, W * .45, 1240, 380, (220, 60, 60), .35 * k, .95)
    headline(b, "JHUND MEIN", "akela kamzor · saath mein khatarnaak", t, accent=GOLD)


def sc7(b, t):
    """Hide and cave — clothing and shelter."""
    b.paste(vgrad((16, 15, 14), (40, 32, 26)))
    d = ImageDraw.Draw(b, "RGBA")
    d.rectangle([0, 1260, W, H], fill=(28, 23, 20, 255))
    d.polygon([(0, 560), (W, 500), (W, H), (0, H)], fill=(15, 13, 12, 255))     # cave wall
    d.polygon([(0, 560), (W, 500), (W, 640), (0, 700)], fill=(10, 9, 9, 255))
    fire(b, W * .70, 1420, .55, t, .95, seed=5)
    light_shafts(b, W * .70, 1300, t, .35, (255, 160, 90))
    # the cloak drops onto the figure
    drop = eo(sg(t, .55, .7))
    stick(d, W * .34, 1560, 320, BONE, lean=-.05, arms=(.5, .5))
    if drop > .02:
        top = 1180 - 40 * drop
        d.polygon([(W * .34 - 118, top + 210), (W * .34 - 52, top),
                   (W * .34 + 52, top), (W * .34 + 118, top + 210),
                   (W * .34 + 86, top + 360), (W * .34 - 86, top + 360)],
                  fill=(120, 92, 66, int(235 * drop)))
        for k in range(6):
            d.line([(W * .34 - 110 + k * 44, top + 230), (W * .34 - 104 + k * 44, top + 350)],
                   fill=(94, 70, 50, int(200 * drop)), width=5)
    # sleeping family by the fire
    for i, x in enumerate((W * .58, W * .76)):
        d.ellipse([x - 96, 1548, x + 96, 1604], fill=(122, 94, 68, 240))     # fur roll
        for k in range(4):
            d.arc([x - 96 + k * 6, 1548 + k * 4, x + 96 - k * 6, 1604 - k * 3],
                  200, 340, fill=(100, 76, 54, 220), width=3)
        d.ellipse([x - 104, 1552, x - 78, 1590], fill=(232, 223, 203, 240))   # head
        d.line([(x + 70, 1592), (x + 132, 1602)], fill=(232, 223, 203, 210), width=9)
    headline(b, "KHAAL · GUFA", "jacket aur ghar", t)


def sc8(b, t):
    """Language — the weapon that is not a weapon."""
    b.paste(vgrad((14, 13, 18), (44, 30, 24)))
    d = ImageDraw.Draw(b, "RGBA")
    d.rectangle([0, 1280, W, H], fill=(24, 19, 18, 255))
    fire(b, W * .5, 1470, .5, t, .8, seed=9)
    light_shafts(b, W * .5, 1330, t, .4, (255, 170, 110))
    stick(d, W * .30, 1420, 330, BONE, lean=.10, arms=(.72, .18))
    stick(d, W * .70, 1420, 330, BONE, lean=-.10, arms=(.18, .72))
    for k in range(4):                                   # speech rings
        p = (t * .55 + k / 4) % 1.0
        r = 40 + 240 * p
        a = int(150 * (1 - p) * eo(sg(t, .35, .5)))
        d.ellipse([W * .5 - r, 1190 - r * .55, W * .5 + r, 1190 + r * .55],
                  outline=(255, 205, 130, a), width=4)
    for i, (x, y, s) in enumerate(((W * .5, 860, "aa"), (W * .34, 940, "oh"),
                                   (W * .66, 950, "hm"))):
        p = eo(sg(t, .7 + i * .5, .5))
        if p > .05:
            put_text_scaled(b, s, F(S7, 60), (255, 232, 196), x, y, .9 + .2 * p, p * .85)
    headline(b, "ZUBAAN", "sabse bada hathiyaar", t)


def sc9(b, t):
    """Seeds to harvest — sunrise over the first field."""
    b.paste(vgrad((34, 26, 46), (196, 122, 62), .8))
    d = ImageDraw.Draw(b, "RGBA")
    halo(b, W * .5, 1080, 620, (255, 186, 104), .62, .9)
    d.ellipse([W * .5 - 190, 940, W * .5 + 190, 1320], fill=(255, 216, 142, 255))
    for k in range(14):                                   # sun rays
        a = k / 14 * math.tau + 0.2
        d.line([(W * .5 + math.cos(a) * 210, 1130 + math.sin(a) * 210),
                (W * .5 + math.cos(a) * 470, 1130 + math.sin(a) * 470)],
               fill=(255, 200, 130, 26), width=26)
    for i in range(5):
        d.polygon([(i * 260 - 80, 1300), (i * 260 + 80, 1150), (i * 260 + 250, 1300)],
                  fill=(64, 48, 42, 255))
    d.rectangle([0, 1300, W, H], fill=(52, 42, 30, 255))
    rocks(b, 1330, 4, (44, 35, 26), 88, 40, 110)
    wheat_row(d, 1440, t, 13, (196, 166, 96))
    wheat_row(d, 1520, t * 1.3, 9, (216, 184, 110))
    g = eo(sg(t, .45, 2.2))
    sprout(d, W * .26, 1580, g * 1.25, t)
    for k in range(7):                                    # falling seeds
        p = sg(t, .2 + k * .12, 1.2)
        if 0 < p < 1:
            sx = W * .30 + (k - 3) * 26
            d.ellipse([sx - 5, 980 + p * 560, sx + 5, 990 + p * 560],
                      fill=(226, 196, 130, int(200 * (1 - p * .5))))
    stick(d, W * .22, 1560, 280, BONE, lean=.35, arms=(.85, .3), alpha=235)
    headline(b, "BEEJ BOYA", "khana khud ugaya", t, accent=GOLD)


def sc10(b, t):
    """Same human, new tools — the phone glow at night."""
    b.paste(vgrad((6, 8, 14), (14, 16, 26)))
    d = ImageDraw.Draw(b, "RGBA")
    rng = np.random.default_rng(21)
    for i in range(11):                                   # skyline
        x = i * 104 - 20
        hh = int(rng.integers(220, 620))
        d.rectangle([x, 1320 - hh, x + 88, 1320], fill=(19, 22, 31, 255))
        d.rectangle([x, 1320 - hh, x + 88, 1320 - hh + 8], fill=(30, 34, 46, 255))
        for r in range(int(hh / 62)):
            for c in range(3):
                if rng.random() > .55:
                    yy = 1320 - hh + 18 + r * 60
                    d.rectangle([x + 12 + c * 24, yy, x + 26 + c * 24, yy + 18],
                                fill=(255, 208, 130, int(rng.integers(90, 210))))
    d.rectangle([0, 1320, W, H], fill=(9, 10, 15, 255))
    glow = .55 + .25 * math.sin(t * 2.4)
    halo(b, W * .5 + 60, 1330, 420, (150, 195, 255), glow * .62, .95)
    halo(b, W * .5 + 60, 1240, 190, (190, 220, 255), glow * .55, .9)
    d.rectangle([0, 1300, W, 1400], fill=(14, 16, 24, 90))
    stick(d, W * .5, 1560, 380, BONE, lean=-.06, arms=(.42, .78))
    px, py = W * .5 + 78, 1290
    d.rounded_rectangle([px - 26, py - 44, px + 26, py + 44], 8, fill=(220, 236, 255, 245))
    d.rounded_rectangle([px - 20, py - 36, px + 20, py + 34], 5, fill=(120, 180, 255, 255))
    # the payoff lines
    a1 = eo(sg(t, .9, .6))
    if a1 > .02:
        put_text_scaled(b, "hum wahi insaan hain", F(N6, 54), (255, 255, 255), W // 2, 980,
                        .98, a1)
    a2 = eo(sg(t, 1.9, .7))
    if a2 > .02:
        put_text_scaled(b, "SIRF TOOLS BADLE", F(N9, 92), GOLD, W // 2, 720, .99, a2)
    a3 = eo(sg(t, 2.9, .8))
    if a3 > .02:
        put_text_scaled(b, "MONARCH · STICKMAN", F(N7, 28), (255, 255, 255), W // 2,
                        H - 120, .98, a3 * .55)


SCENES = {1: sc1, 2: sc2, 3: sc3, 4: sc4, 5: sc5, 6: sc6, 7: sc7, 8: sc8,
          9: sc9, 10: sc10}

CAM = {1: ((1.12, 1.02), "out"), 2: ((1.02, 1.12), "in"), 3: ((1.01, 1.13), "in"),
       4: ((1.10, 1.01), "out"), 5: ((1.03, 1.12), "in"), 6: ((1.13, 1.02), "out"),
       7: ((1.08, 1.00), "out"), 8: ((1.01, 1.09), "in"), 9: ((1.02, 1.10), "in"),
       10: ((1.00, 1.14), "in")}

SHAKE = {1: [(0.05, 20, 12)], 2: [(0.10, 16, 14)], 3: [(0.95, 22, 10), (2.2, 9, 14)],
         4: [(0.20, 8, 16)], 5: [(0.75, 14, 11), (1.55, 12, 11), (2.35, 10, 11)],
         6: [(0.00, 24, 12), (1.00, 10, 14)], 7: [(0.60, 9, 15)],
         8: [(0.70, 7, 16)], 9: [(0.45, 8, 15)], 10: [(0.90, 14, 13), (1.90, 10, 15)]}

GRADE = {1: dict(tint=(150, 180, 220), amt=.10, contrast=1.06, sat=.92, vig=.34),
         2: dict(tint=(200, 120, 110), amt=.08, contrast=1.10, sat=.86, vig=.40),
         3: dict(tint=(255, 190, 140), amt=.10, contrast=1.06, sat=1.04, vig=.34),
         4: dict(tint=(255, 170, 110), amt=.12, contrast=1.04, sat=1.06, vig=.30),
         5: dict(tint=(255, 200, 150), amt=.08, contrast=1.06, sat=1.02, vig=.34),
         6: dict(tint=(180, 190, 220), amt=.10, contrast=1.10, sat=.90, vig=.38),
         7: dict(tint=(255, 190, 140), amt=.09, contrast=1.05, sat=1.02, vig=.35),
         8: dict(tint=(255, 180, 130), amt=.10, contrast=1.04, sat=1.04, vig=.33),
         9: dict(tint=(255, 205, 150), amt=.10, contrast=1.04, sat=1.06, vig=.28),
         10: dict(tint=(120, 160, 230), amt=.08, contrast=1.08, sat=.95, vig=.40)}


def cam_for(n, tl, dur):
    (z0, z1), e = CAM[n]
    p = cl(tl / max(dur, 1e-6))
    z = lerp(z0, z1, eio(p)) if e == "in" else lerp(z0, z1, eio(p))
    sh = (0, 0)
    for at, amp, dec in SHAKE.get(n, []):
        k = (tl - at)
        if 0 <= k < dec / 30:
            sh = (int(amp * math.exp(-k * 22) * math.sin(k * 90)),
                  int(amp * .6 * math.exp(-k * 22) * math.cos(k * 70)))
    return z, sh


def scene_frame(n, tl, dur):
    b = vgrad((10, 11, 15), (20, 18, 20))
    SCENES[n](b, tl)
    z, sh = cam_for(n, tl, dur)
    b = apply_camera(b, z, .5, .5, sh)
    g = GRADE[n]
    b = vlib.grade(b, g["tint"], g["amt"], g["contrast"], 1.0, g["sat"])
    b = apply_vignette(b, g["vig"])
    return b


def compose(t: float) -> Image.Image:
    idx = 0
    for i, bt in enumerate(BEATS):
        if t >= bt["start"] - 1e-6:
            idx = i
    bt = BEATS[idx]
    tl = t - bt["start"]
    img = scene_frame(bt["n"], tl, bt["dur"])

    if idx > 0:
        prev = BEATS[idx - 1]
        p = (t - (bt["start"] - TRANS_W * .5)) / TRANS_W
        if 0 <= p <= 1:
            a = scene_frame(prev["n"], prev["dur"] + (t - bt["start"]) + .05, prev["dur"])
            img = transition(a, img, bt["trans"], p)
            if bt["trans"] in ("slide", "whoosh"):
                img = whip_blur(img, math.sin(math.pi * cl(p)) * .55)
            if bt["trans"] == "slam":
                img = zoom_blur(img, math.sin(math.pi * cl(p)) * .75)
            if bt["trans"] in ("flash", "punch"):
                img = vlib.flash(img, WHITE, .32 * math.sin(math.pi * cl(p)))

    # optics on the picture, then the text on top (never both)
    punch = 0.0
    for at, amp, dec in SHAKE.get(bt["n"], []):
        k = tl - at
        if 0 <= k < .30:
            punch = max(punch, math.exp(-k * 14) * amp / 24)
    if punch > .01:
        img = chroma(img, int(round(1 + 3 * punch)))
        img = zoom_blur(img, .40 * punch)

    if tl < .66:
        img = light_sweep(img, eo(cl(tl / .66)), .30 if bt["n"] != 10 else .14)
    if tl < .85:
        img = leak(img, .20 * math.sin(math.pi * cl(tl / .85)) ** 1.4, seed=bt["n"] * .37)
    img = anamorphic(img, .55 if bt["n"] == 10 else .28)
    if bt["n"] in (3, 4, 7, 8):
        img = bloom(img, .42, 205)
    if punch > .01:
        img = vignette_pulse(img, min(1.0, punch) * .8)
    img = weave(img, t, .8 if bt["n"] != 10 else 1.1)
    img = exposure_breathe(img, t)
    img = apply_grain(img, int(t * FPS), .05)
    return img


def render_full():
    silent = os.path.join(OUT, "survive_silent.mp4")
    nframes = int(round(TOTAL * FPS))
    cmd = [ffmpeg(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
           "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", silent]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    import time
    t0 = time.time()
    for i in range(nframes):
        img = compose(i / FPS)
        p.stdin.write(img.tobytes())
        if i % 60 == 0:
            el = time.time() - t0
            print(f"  {i}/{nframes}  {i/max(el,1e-6):.1f} fps  eta {(nframes-i)/max(i/max(el,1e-6),1e-6):.0f}s",
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
            im = compose(t)
            p = os.path.join(OUT, f"still_{t:05.2f}.jpg")
            im.save(p, quality=90)
            print(p)
    else:
        render_full()
