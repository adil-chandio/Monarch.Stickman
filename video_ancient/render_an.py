#!/usr/bin/env python3
"""
render_an.py — "How Ancient Humans Survived", drawn in the **Law 1 style**.

Same visual grammar as `video_law1/render_v3.py`, because that is the style the
channel is built on:

    cream paper background · ink line art · blue/red/gold accents
    the hooded host character · pills and stamps · big display words
    kinetic caption bar at the top (blue, word-by-word reveal, gold keywords)
    camera push/pull per beat, punch blur on the picture only, whip transitions,
    light sweep, light leak, anamorphic streak, weave, exposure breathe, grain

Only the subject matter changes: fire, stone, hide, mammoth, wheat and language
instead of courtrooms and crowns.

  python render_an.py stills 2 12.5 26      -> out/still_<t>.jpg
  python render_an.py full                  -> out/ancient_silent.mp4
"""
from __future__ import annotations

import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

import vlib
from vlib import (BLUE, BLUE_DEEP, CREAM, F, GOLD, GOLD_L, H, INK, INK_SOFT,
                  N6, N7, N8, N9, NIGHT, RED, RED_DEEP, S7, S8, S9, W, WHITE,
                  apply_camera, apply_grain, apply_vignette, arrow, bubble, cl,
                  draw_particles, eio, eo, glow_ring, grade, halo, lerp,
                  make_particles, paper_bg, pill, put_text_scaled, sg, sparkle,
                  stamp, star4, transition, underline, wrap, tw)
from render_v3 import (anamorphic, bloom, chroma, draw_caption, draw_overlay,
                       exposure_breathe, leak, light_sweep, put_host,
                       vignette_pulse, weave, whip_blur, zoom_blur)
from timeline_an import BEATS, TOTAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)
FPS = vlib.FPS
TRANS_W = 0.30


def ffmpeg() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


# =====================================================================
#  ink line art (Law-1 palette, drawn on the paper)
# =====================================================================
def figure(base, cx, bottom, h, color=INK, lean=0.0, walk=0.0, arms=(.5, .5),
           alpha=1.0, spear=None, cloak=None, glow=True):
    """Ink stick figure with joints; `bottom` is the ground line."""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    col = tuple(color) + (int(255 * alpha),)
    w = max(6, int(h * .052))
    hip, sh = bottom - h * .47, bottom - h * .80
    hr = h * .075
    sw = math.sin(walk) * h * .22
    dx = lean * h * .10

    if glow:
        sh_l = Image.new("RGBA", (int(h * 1.1), int(h * .3)), (0, 0, 0, 0))
        ds = ImageDraw.Draw(sh_l)
        ds.ellipse([h * .12, h * .07, h * .98, h * .25], fill=(60, 52, 44, int(52 * alpha)))
        lay.paste(sh_l, (int(cx - h * .55), int(bottom - h * .10)), sh_l)

    def limb(x0, y0, a1, l1, a2, l2):
        ex, ey = x0 + math.sin(a1) * l1, y0 + math.cos(a1) * l1
        hx, hy = ex + math.sin(a2) * l2, ey + math.cos(a2) * l2
        d.line([(x0, y0), (ex, ey)], fill=col, width=w)
        d.line([(ex, ey), (hx, hy)], fill=col, width=w)
        d.ellipse([hx - w * .55, hy - w * .55, hx + w * .55, hy + w * .55], fill=col)

    limb(cx, hip, .30 + sw / h, h * .24, -sw / h * .5, h * .235)
    limb(cx + 5, hip, -.30 - sw / h, h * .24, sw / h * .45, h * .235)
    d.line([(cx, hip), (cx + dx, sh)], fill=col, width=w)
    hx, hy = cx + dx * 1.25, sh - hr * 1.55
    d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=col)
    d.line([(cx + dx, sh), (hx, hy + hr * .8)], fill=col, width=w)
    for i, a in enumerate(arms):
        sgn = -1 if i == 0 else 1
        a1 = sgn * (.03 + a * 1.42) + sw / h * .30 * sgn
        limb(cx + dx + sgn * h * .045, sh + h * .02, a1, h * .165,
             a1 * .55 + sgn * .12, h * .155)
    if cloak:
        top = sh - hr * .35
        wd = h * .20
        pts = [(cx - wd + 2 * wd * (i / 8),
                top + 9 * math.sin(i / 8 * 9) + h * .05 * (1 - abs(.5 - i / 8) * 2))
               for i in range(9)]
        pts += [(cx - wd * .92 + 1.84 * wd * (1 - i / 6),
                 bottom - h * .33 - (i % 2) * h * .05) for i in range(7)]
        d.polygon(pts, fill=(196, 158, 92, int(240 * alpha)))
        for k in range(6):
            fx = cx - wd * .8 + k * wd * .32
            d.line([(fx, top + h * .10), (fx + 4, bottom - h * .34)],
                   fill=(168, 130, 70, int(220 * alpha)), width=max(3, w // 2))
        d.ellipse([hx - hr * .9, hy - hr * .9, hx + hr * .9, hy + hr * .9], fill=col)
    if spear:
        ox, oy, ang, L = spear
        sx, sy = cx + ox, bottom + oy
        d.line([(sx, sy), (sx + math.cos(ang) * L, sy - math.sin(ang) * L)],
               fill=col, width=max(4, int(w * .7)))
        tx, ty = sx + math.cos(ang) * L, sy - math.sin(ang) * L
        d.polygon([(tx, ty), (tx - 15, ty + 26), (tx + 10, ty + 24)], fill=col)
    base.paste(lay, (0, 0), lay)


def flame(base, cx, ground, scale, t, hot=1.0, seed=0):
    """Paper-style fire: red/gold tongues + glow rings, no black."""
    rng = np.random.default_rng(seed + int(abs(t) * 6) + 1)
    halo(base, cx, ground - 90 * scale, 330 * scale, (255, 196, 120), .55 * hot, .9)
    for k in range(3):
        p = (t * .55 + k / 3) % 1.0
        glow_ring(base, cx, ground - 40 * scale, (90 + 190 * p) * scale, 4, RED,
                  .22 * (1 - p) * hot)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for wf, hf, dxf, colr in ((1.00, 1.00, 0.00, RED + (205,)),
                              (0.66, 1.24, 0.10, (232, 96, 32, 215)),
                              (0.76, 0.72, -0.15, (245, 152, 40, 205)),
                              (0.44, 0.94, 0.02, GOLD + (228,)),
                              (0.26, 0.62, 0.01, (255, 236, 170, 245))):
        n = 22
        ptsr, ptsl = [], []
        for i in range(n + 1):
            u = i / n
            y = ground - 300 * scale * hf * u
            prof = (1 - u) ** .55 * (.55 + .45 * math.sin(math.pi * min(1, u * 1.25)))
            wob = (math.sin(u * 7 + t * 8 + dxf * 9) * .12 +
                   math.sin(u * 3.1 - t * 4.3) * .10) * u
            half = 150 * scale * wf * .5 * prof * (1 + wob)
            sway = math.sin(t * 3.2 + u * 2 + dxf * 5) * 150 * scale * wf * .10 * u ** 1.5
            ptsr.append((cx + dxf * 80 * scale + half + sway, y))
            ptsl.append((cx + dxf * 80 * scale - half + sway, y))
        d.polygon(ptsl[::-1] + ptsr, fill=colr)
    from PIL import ImageFilter
    lay = lay.filter(ImageFilter.GaussianBlur(1.4))
    base.paste(lay, (0, 0), lay)
    d2 = ImageDraw.Draw(base, "RGBA")
    for _ in range(int(24 * hot)):
        u = rng.uniform(0, 1)
        ex = cx + rng.normal(0, 46 * scale)
        ey = ground - (150 + u * 430) * scale
        r = rng.uniform(2, 4.5) * scale
        d2.ellipse([ex - r, ey - r, ex + r, ey + r],
                   fill=(230, 120, 40, int(230 * (1 - u) * hot)))



def cave(base, cx, ground, w=300, h=260, rock=(206, 198, 184), dark=(84, 80, 74)):
    """A jagged rock massif with a small dark mouth — not a circle, not a tent."""
    import math as _m
    d = ImageDraw.Draw(base, "RGBA")
    pts = []
    n = 13
    for i in range(n + 1):
        u = i / n
        a = _m.pi * u
        bump = 1 + .16 * _m.sin(u * 11) + .08 * _m.sin(u * 23 + 1.3)
        pts.append((cx + _m.cos(a) * -1 * w * bump, ground - _m.sin(a) * h * bump))
    pts += [(cx + w * .92, ground + 8), (cx - w * .92, ground + 8)]
    d.polygon(pts, fill=rock + (255,))
    # a lighter ridge line for depth
    d.line([(p[0], p[1] + 16) for p in pts[:len(pts) // 2]], fill=(174, 166, 152, 255), width=5)
    aw, ah = w * .26, h * .52
    d.polygon([(cx - aw, ground), (cx - aw * .92, ground - ah * .55),
               (cx - aw * .40, ground - ah * .95), (cx + aw * .44, ground - ah * .92),
               (cx + aw * .95, ground - ah * .50), (cx + aw, ground)],
              fill=dark + (255,))
    d.ellipse([cx - aw * .60, ground - ah * .34, cx + aw * .20, ground + ah * .10],
              fill=(60, 58, 54, 255))
    return


def mammoth(base, cx, ground, width, color=INK, alpha=.92, t=0.0):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    col = tuple(color) + (int(255 * alpha),)
    h = width * .68
    d.ellipse([cx - width * .5, ground - h * .82, cx + width * .34, ground - h * .18], fill=col)
    d.ellipse([cx - width * .16, ground - h * 1.02, cx + width * .18, ground - h * .52], fill=col)
    hx = cx + width * .40
    d.ellipse([hx - width * .17, ground - h * .92, hx + width * .17, ground - h * .46], fill=col)
    sway = math.sin(t * .9) * width * .02
    d.line([(hx + width * .10, ground - h * .70), (hx + width * .17 + sway, ground - h * .34),
            (hx + width * .10 + sway, ground - h * .07)], fill=col, width=int(width * .055))
    d.line([(hx + width * .05, ground - h * .58), (hx + width * .22, ground - h * .30)],
           fill=(255, 255, 255, int(230 * alpha)), width=max(4, int(width * .020)))
    for lx in (cx - width * .40, cx - width * .24, cx + width * .06, cx + width * .22):
        d.line([(lx, ground - h * .28), (lx, ground)], fill=col, width=int(width * .075))
    base.paste(lay, (0, 0), lay)


def wheat(base, y, t, count=9, color=(178, 138, 58)):
    d = ImageDraw.Draw(base, "RGBA")
    for i in range(count):
        x = 90 + i * (W - 180) / (count - 1)
        sway = math.sin(t * 1.6 + i * .7) * 11
        h = 200 + (i % 3) * 24
        d.line([(x, y), (x + sway, y - h)], fill=tuple(color) + (235,), width=6)
        for k in range(4):
            yy = y - h * (.55 + .12 * k)
            d.line([(x + sway * .6, yy), (x + sway * .6 + 17, yy - 19)],
                   fill=tuple(color) + (215,), width=5)
            d.line([(x + sway * .6, yy), (x + sway * .6 - 17, yy - 19)],
                   fill=tuple(color) + (215,), width=5)
        d.ellipse([x + sway - 10, y - h - 27, x + sway + 10, y - h + 5],
                  fill=(206, 164, 74, 240))


def sprout(base, cx, ground, g, t):
    if g <= .02:
        return
    d = ImageDraw.Draw(base, "RGBA")
    h = 165 * g
    sway = math.sin(t * 2.2) * 9 * g
    d.line([(cx, ground), (cx + sway, ground - h)], fill=(72, 140, 78, 255),
           width=max(4, int(7 * g)))
    if g > .35:
        for s in (-1, 1):
            lw = 64 * g
            d.polygon([(cx + sway * .5, ground - h * .55),
                       (cx + s * lw, ground - h * .80), (cx + sway, ground - h * .40)],
                      fill=(96, 164, 92, 240))


def stone_stack(base, cx, ground, t):
    d = ImageDraw.Draw(base, "RGBA")
    halo(base, cx, ground - 60, 240, (255, 226, 170), .40, .9)
    d.ellipse([cx - 190, ground - 60, cx + 150, ground + 40], fill=(214, 202, 180, 255))
    d.polygon([(cx - 120, ground - 60), (cx - 40, ground - 190), (cx + 50, ground - 130),
               (cx + 70, ground - 60)], fill=(186, 174, 154, 255))
    d.polygon([(cx - 40, ground - 190), (cx + 6, ground - 226), (cx + 50, ground - 130)],
              fill=(206, 194, 172, 255))
    d.line([(cx - 40, ground - 190), (cx + 50, ground - 130)], fill=INK_SOFT + (200,), width=5)


def ink_sun(base, cx, cy, r, t):
    halo(base, cx, cy, r * 2.4, (255, 214, 150), .55, .9)
    d = ImageDraw.Draw(base, "RGBA")
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(244, 196, 92, 252))
    d.ellipse([cx - r * .74, cy - r * .74, cx + r * .74, cy + r * .74],
              fill=(252, 222, 138, 252))
    for k in range(14):
        a = k / 14 * math.tau + .2
        d.line([(cx + math.cos(a) * r * 1.18, cy + math.sin(a) * r * 1.18),
                (cx + math.cos(a) * r * 1.62, cy + math.sin(a) * r * 1.62)],
               fill=(200, 148, 44, 190), width=9)


# =====================================================================
#  scenes — beat by beat
# =====================================================================
def s1(base, t, dur):
    """20,000 years ago — cold, no roof, no clothes."""
    halo(base, 800, 700, 520, (222, 232, 240), .85, .8)
    put_host(base, "host_worried", cx=235, bottom=1830 + math.sin(t * 2.2) * 5, max_h=690,
             scale=.97 + .03 * eo(sg(t, 0, .5)), opacity=cl(sg(t, 0, .14)))
    if t > 1.2:
        pill(base, 235, 1470, "AAP", fill=(38, 49, 66), size=30,
             opacity=eo(sg(t, 1.2, .4)), track=2)
    # the hook word slams
    if t < 2.2:
        a = cl(sg(t, .02, .10)) * (1 - cl(sg(t, 1.85, .35)))
        if a > .02:
            sc = 1.06 - .06 * eo(sg(t, 0, .3))
            put_text_scaled(base, "20,000 SAAL", F(N9, 112), RED, 560, 470, sc, a)
            put_text_scaled(base, "PEHLE", F(N9, 112), RED, 560, 588, sc, a)
            for k in range(2):
                glow_ring(base, 560, 520, 130 + 250 * eo(sg(t, k * .12, .6)), 5, RED,
                          .28 * (1 - sg(t, k * .12, .6)) * a)
    # drawn cave mouth + a lonely ink figure
    # distant hills + moon: the paper is cream, so they are ink-soft, not black
    d0 = ImageDraw.Draw(base, "RGBA")
    for i in range(5):
        d0.polygon([(i * 260 - 80, 1160), (i * 260 + 90, 1010), (i * 260 + 270, 1160)],
                   fill=(226, 220, 208, 255))
    d0.rectangle([0, 1156, W, 1172], fill=(214, 208, 196, 255))
    halo(base, 860, 800, 260, (255, 244, 214), .85, .9)
    d0.ellipse([860 - 96, 800 - 96, 860 + 96, 800 + 96], fill=(240, 232, 210, 255))
    d0.ellipse([860 - 52, 800 - 60, 860 + 34, 800 + 26], fill=(228, 220, 198, 255))
    rng0 = np.random.default_rng(7)
    for _ in range(46):
        sx, sy = rng0.integers(60, W - 60), rng0.integers(300, 1000)
        r0 = rng0.integers(2, 5)
        d0.ellipse([sx, sy, sx + r0, sy + r0], fill=(206, 200, 188, 200))
    cave(base, 660, 1520, 330, 305)
    figure(base, 930, 1560, 350, lean=-.15, arms=(.10, .22),
           alpha=eo(sg(t, .45, .8)))
    if t > 2.5:
        pill(base, 560, 1700, "NA GHAR · NA KAPDE", fill=RED, size=26,
             opacity=eo(sg(t, 2.5, .4)), padx=22)


def s2(base, t, dur):
    """The question every morning — eyes in the dark."""
    d = ImageDraw.Draw(base, "RGBA")
    d.rectangle([0, 1080, W, 1180], fill=(232, 226, 214, 255))
    d.rectangle([0, 1660, W, H], fill=(226, 220, 206, 255))        # ground band
    put_host(base, "host_worried", cx=250, bottom=1830, max_h=700,
             scale=1.0, opacity=1.0, bob=math.sin(t * 2) * 4)
    if t > 1.3:
        pill(base, 250, 1450, "HAR SUBHA", fill=(38, 49, 66), size=28,
             opacity=eo(sg(t, 1.3, .4)), track=2)
    # predator eyes open, one pair at a time
    for i, (x, y, s) in enumerate(((700, 1340, 1.0), (900, 1250, .82), (790, 1450, .62))):
        g = eo(sg(t, .5 + i * .6, .5)) * (.65 + .35 * math.sin(t * 3 + i))
        if g > .05:
            for sgn in (-1, 1):
                cx = x + sgn * 34 * s
                d.ellipse([cx - 30 * s, y - 19 * s, cx + 30 * s, y + 19 * s],
                          fill=(216, 52, 44, int(225 * g)))
                d.ellipse([cx - 12 * s, y - 12 * s, cx + 12 * s, y + 12 * s],
                          fill=(24, 20, 20, int(248 * g)))
    p_ic = vlib.eob(vlib.sg(t, .08, .42))
    if p_ic > .02:
        for k in range(3):
            glow_ring(base, 760, 900, 120 + 190 * eo(sg(t, .16 + k * .18, .9)), 5, RED,
                      .30 * (1 - sg(t, .16 + k * .18, .9)))
        vlib.put(base, "icon_warning", cx=760, cy=900, max_w=300,
                 scale=.55 + .45 * p_ic, opacity=cl(sg(t, .08, .18) * 1.8))
    if t > 2.4:
        a = eo(sg(t, 2.4, .45))
        stamp(base, 620, 610, "ZINDA?", ang=-8, color=RED, size=96, scale=.9 + .1 * a,
              opacity=a)
    for i in range(3):
        if t > 1.0 + i * .35:
            sparkle(ImageDraw.Draw(base, "RGBA"), 600 + i * 120, 1080 - i * 20,
                    16 * eo(sg(t, 1.0 + i * .35, .3)), RED, 5)


def s3(base, t, dur):
    """Lightning, then the first fire — the channel's own icon language."""
    d = ImageDraw.Draw(base, "RGBA")
    if t < 1.1:
        k = 1 - abs(t - .22) / .32
        if k > 0:
            rng = np.random.default_rng(4)
            x = 700
            pts = [(x, 200)]
            for i in range(7):
                x += rng.integers(-46, 46)
                pts.append((x, 200 + (i + 1) * 120))
            d.line(pts, fill=(255, 214, 96, int(255 * k)), width=9)
            b2 = Image.new("RGB", (W, H), (255, 255, 255))
            base.paste(Image.blend(base, b2, .30 * k))
    ignite = eo(sg(t, .85, .6))
    if ignite > .01:
        flame(base, 700, 1500, .55 + .75 * ignite, t, hot=ignite)
    figure(base, 330, 1500, 300, lean=.35, arms=(.12, 1.0),
           alpha=eo(sg(t, .2, .5)))
    if ignite > .4:
        a = eo(sg(t, 1.6, .4))
        pill(base, 330, 1180, "PEHLI AAG", fill=RED, size=28, opacity=a, track=3)
        put_host(base, "host_happy", cx=1000, bottom=1830, max_h=520,
                 scale=.96 + .04 * eo(sg(t, 1.6, .5)), opacity=a)
    if t > 3.0:
        a = eo(sg(t, 3.0, .5))
        stamp(base, 700, 700, "DOST", ang=7, color=RED, size=88, scale=.9 + .1 * a, opacity=a)


def s4(base, t, dur):
    """Warmth, light, and the dark stays outside the ring."""
    flame(base, 540, 1560, .95, t, 1.0, seed=2)
    d = ImageDraw.Draw(base, "RGBA")
    for i, x in enumerate((250, 830, 1030)):
        figure(base, x, 1660 - i * 10, 265, lean=(.12 if i == 0 else -.12),
               arms=(.5, .5), alpha=.96)
    # warm ring on the paper
    p = eo(sg(t, .3, .9))
    if p > .02:
        glow_ring(base, 540, 1600, 300 + 60 * math.sin(t * 2), 5, GOLD,
                  .35 * p)
    for i, (txt, at, col) in enumerate((("GARMI", .5, RED), ("ROSHNI", 1.7, GOLD),
                                        ("DARINDE DOOR", 2.9, (38, 49, 66)))):
        if t > at:
            a = eo(sg(t, at, .4))
            pill(base, 540, 480 + i * 96, txt, fill=col, size=30,
                 opacity=a, track=3, scale=.94 + .06 * a)


def s5(base, t, dur):
    """Stone into tools — sparks land on the same frames as the cues."""
    stone_stack(base, 640, 1500, t)
    figure(base, 300, 1560, 310, lean=.42, arms=(.25, 1.0))
    d = ImageDraw.Draw(base, "RGBA")
    for i, at in enumerate((.75, 1.55, 2.35, 3.15)):
        p = sg(t, at, .30)
        if 0 < p < 1:
            cx, cy = 560, 1330
            halo(base, cx, cy, 170, (255, 226, 150), .55 * (1 - p), .95)
            for k in range(11):
                a = k / 11 * math.tau
                r = 34 + 130 * p
                d.line([(cx + math.cos(a) * r * .5, cy + math.sin(a) * r * .4),
                        (cx + math.cos(a) * r, cy + math.sin(a) * r * .8)],
                       fill=(232, 150, 40, int(255 * (1 - p))), width=5)
    if t > 1.3:
        a = eo(sg(t, 1.3, .45))
        stamp(base, 560, 640, "HATHIYAR", ang=-7, color=RED, size=80,
              scale=.9 + .1 * a, opacity=a)
    if t > 3.0:
        pill(base, 300, 1200, "SHIKAAR", fill=(38, 49, 66), size=28,
             opacity=eo(sg(t, 3.0, .4)), track=3)


def s6(base, t, dur):
    """Alone weak, in a group lethal."""
    mammoth(base, 820, 1440, 470, INK, .94, t)
    pill(base, 820, 980, "AKELA?", fill=(38, 49, 66), size=26,
         opacity=eo(sg(t, .35, .4)))
    for i, (x, ph) in enumerate(((190, 0), (320, .6), (430, 1.2), (520, 1.8))):
        figure(base, x, 1560, 240, lean=.2, walk=t * 5 + ph * 3, arms=(.7, .45),
               spear=(80, -170, .30, 250),
               alpha=eo(sg(t, .9 + i * .12, .5)))
    if t > 1.3:
        a = eo(sg(t, 1.3, .45))
        stamp(base, 620, 560, "JHUND", ang=-6, color=RED, size=92, scale=.9 + .1 * a,
              opacity=a)
    if t > 2.7:
        a = eo(sg(t, 2.7, .45))
        put_text_scaled(base, "KHATARNAAK", F(N9, 74), RED, 540, 1680, .96, a)


def s7(base, t, dur):
    """Hide and cave — clothing and shelter."""
    cave(base, 810, 1570, 260, 240)
    d = ImageDraw.Draw(base, "RGBA")
    figure(base, 320, 1640, 320, lean=-.05, arms=(.35, .35),
           cloak=eo(sg(t, .5, .8)))
    flame(base, 880, 1520, .42, t, .8, seed=5)
    if t > .6:
        a = eo(sg(t, .6, .4))
        pill(base, 300, 1220, "KHAAL", fill=RED, size=28, opacity=a, track=3)
    if t > 1.5:
        a = eo(sg(t, 1.5, .42))
        stamp(base, 540, 660, "JACKET", ang=-7, color=RED, size=78,
              scale=.9 + .1 * a, opacity=a)
    if t > 2.4:
        a = eo(sg(t, 2.4, .4))
        pill(base, 810, 1120, "GUFA = GHAR", fill=(38, 49, 66), size=28, opacity=a, track=3)
    # a sleeping family by the fire: rolled ink shapes
    for i, x in enumerate((930, 1040)):
        d.ellipse([x - 70, 1582, x + 70, 1650], fill=(198, 160, 96, 248))     # blanket
        d.ellipse([x - 34, 1596, x + 34, 1648], fill=(214, 178, 112, 250))    # fold
        d.ellipse([x - 98, 1596, x - 60, 1644], fill=INK + (245,))            # head
        d.arc([x - 96, 1598, x - 62, 1642], 200, 340, fill=(236, 214, 186, 230), width=5)


def s8(base, t, dur):
    """Language — the weapon that is not a weapon."""
    figure(base, 300, 1600, 330, lean=.10, arms=(.72, .18))
    figure(base, 790, 1600, 330, lean=-.10, arms=(.18, .72))
    d = ImageDraw.Draw(base, "RGBA")
    for k in range(3):
        p = (t * .55 + k / 3) % 1.0
        r = 50 + 230 * p
        a = int(200 * (1 - p) * eo(sg(t, .3, .5)))
        d.ellipse([545 - r, 1150 - r * .55, 545 + r, 1150 + r * .55],
                  outline=RED + (a,), width=5)
    bubble(base, 545, 940, 300, 150, fill=WHITE, outline=INK, lw=5,
           tail=(500, 1060), opacity=eo(sg(t, .7, .4)))
    if t > .9:
        put_text_scaled(base, "aa · oh · hm", F(S8, 52), INK, 545, 938, .98,
                        eo(sg(t, .9, .4)))
    if t > 1.6:
        a = eo(sg(t, 1.6, .45))
        stamp(base, 545, 560, "ZUBAAN", ang=-5, color=RED, size=96, scale=.9 + .1 * a,
              opacity=a)
    if t > 3.1:
        pill(base, 545, 700, "SIKHANA", fill=(38, 49, 66), size=28,
             opacity=eo(sg(t, 3.1, .4)), track=3)


def s9(base, t, dur):
    """Seeds to harvest — the first sunrise that means food."""
    ink_sun(base, 540, 860, 150, t)
    wheat(base, 1560, t, 9)
    sprout(base, 300, 1600, eo(sg(t, .45, 2.0)) * 1.3, t)
    figure(base, 210, 1600, 280, lean=.35, arms=(.3, .85), alpha=.95)
    d = ImageDraw.Draw(base, "RGBA")
    for k in range(7):
        p = sg(t, .2 + k * .12, 1.2)
        if 0 < p < 1:
            sx = 300 + (k - 3) * 24
            d.ellipse([sx - 6, 1080 + p * 460, sx + 6, 1092 + p * 460],
                      fill=(196, 150, 60, int(220 * (1 - p * .4))))
    if t > 1.4:
        a = eo(sg(t, 1.4, .45))
        stamp(base, 700, 660, "BEEJ", ang=8, color=RED, size=86, scale=.9 + .1 * a,
              opacity=a)
    if t > 3.0:
        a = eo(sg(t, 3.0, .45))
        pill(base, 700, 800, "BHOOKH KAM", fill=(38, 49, 66), size=26, opacity=a, track=3)


def s10(base, t, dur):
    """The payoff — same human, new tools. Darker card, like Law 1."""
    base.paste(Image.new("RGB", (W, H), NIGHT))
    halo(base, 690, 1180, 420, (120, 170, 235), .55 + .2 * math.sin(t * 2.4), .95)
    d = ImageDraw.Draw(base, "RGBA")
    rng = np.random.default_rng(21)
    for i in range(10):
        x = i * 112 - 20
        hh = int(rng.integers(240, 560))
        d.rectangle([x, 1400 - hh, x + 96, 1400], fill=(16, 20, 30, 255))
        for r in range(int(hh / 66)):
            for c in range(3):
                if rng.random() > .55:
                    yy = 1400 - hh + 20 + r * 62
                    d.rectangle([x + 14 + c * 26, yy, x + 30 + c * 26, yy + 18],
                                fill=(250, 208, 140, int(rng.integers(90, 220))))
    d.rectangle([0, 1400, W, H], fill=(8, 9, 13, 255))
    figure(base, 470, 1660, 380, color=(232, 223, 203), lean=-.06, arms=(.3, .9),
           alpha=1.0)
    halo(base, 560, 1400, 150, (170, 210, 255), .75, .9)
    d.rounded_rectangle([536, 1256, 588, 1344], 9, fill=(226, 240, 255, 250))
    d.rounded_rectangle([543, 1266, 581, 1334], 6, fill=(120, 180, 250, 255))
    a1 = eo(sg(t, .5, .5))
    if a1 > .02:
        put_text_scaled(base, "hum wahi insaan hain", F(S7, 56), WHITE, 540, 1080, .98, a1)
    a2 = eo(sg(t, 1.35, .5))
    if a2 > .02:
        put_text_scaled(base, "SIRF TOOLS", F(N9, 94), GOLD_L, 540, 830, .98, a2)
        put_text_scaled(base, "BADLE HAIN", F(N9, 94), GOLD_L, 540, 940, .98, a2)
    if t > 3.2:
        a3 = eo(sg(t, 3.2, .5))
        pill(base, 540, 1700, "FOLLOW · MONARCH STICKMAN", fill=(232, 223, 203),
             fg=(20, 22, 28), size=26, opacity=a3, track=2)


SCENES = {1: s1, 2: s2, 3: s3, 4: s4, 5: s5, 6: s6, 7: s7, 8: s8, 9: s9, 10: s10}

CAM = {1: ((1.11, 1.005), "out"), 2: ((1.01, 1.10), "in"), 3: ((1.00, 1.09), "in"),
       4: ((1.07, 1.00), "out"), 5: ((1.02, 1.11), "in"), 6: ((1.13, 1.04), "out"),
       7: ((1.09, 1.01), "out"), 8: ((1.01, 1.07), "in"), 9: ((1.02, 1.09), "in"),
       10: ((1.00, 1.13), "in")}

# (time-in-beat, amplitude, decay-in-frames) — aligned with the 49 sound cues
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

PARTS = {1: ("dust", 22, 11), 2: ("dust", 18, 12), 3: ("ember", 40, 13),
         4: ("ember", 48, 14), 5: ("spark", 30, 15), 6: ("dust", 24, 16),
         7: ("ember", 26, 17), 8: ("dust", 18, 18), 9: ("confetti", 30, 19),
         10: ("ember", 22, 20)}
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

    # punch optics on the picture only — the captions stay razor sharp
    ic = impact_curve(b["n"], tl)
    if ic > .006:
        k = min(1.0, ic / .030)
        img = chroma(img, int(round(1 + 3 * k)))
        img = zoom_blur(img, .42 * k)

    if b["n"] == 10:
        pass                                   # the end card carries its own text
    else:
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
    img = anamorphic(img, .55 if b["n"] == 10 else .30)
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
    silent = os.path.join(OUT, "ancient_silent.mp4")
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
            compose(t).save(os.path.join(OUT, f"still_{t:05.2f}.jpg"), quality=90)
            print(os.path.join(OUT, f"still_{t:05.2f}.jpg"))
    else:
        render_full()
