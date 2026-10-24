#!/usr/bin/env python3
"""
Law 1 explainer v3 (9:16, cinematic whiteboard-cartoon) — no branding chrome.
Camera moves · kinetic captions · particles · transitions · color grading.
"""
import os, sys, math, subprocess
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageEnhance
import numpy as np

from vlib import *          # noqa
import vlib
from timeline_v4 import BEATS, TOTAL


ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "v3out")

# ---- animation probe: records when every element appears/moves (see probe.py)
import probe  # noqa: E402
probe.ENABLED = os.environ.get("MV_PROBE") == "1"
os.makedirs(OUT, exist_ok=True)
FF = "/tmp/v/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
FPS = 30
TRANS_W = 0.30

# =====================================================================
#  camera + look per beat
# =====================================================================
CAM = {
    1:  dict(z=(1.11, 1.005), f=(.5, .5), ph=(.5, .48), e="out"),
    2:  dict(z=(1.01, 1.10), f=(.5, .5), ph=(.5, .5), e="in"),
    3:  dict(z=(1.00, 1.09), f=(.5, .5), ph=(.5, .46), e="in"),
    4:  dict(z=(1.07, 1.00), f=(.5, .46), ph=(.5, .5), e="out"),
    5:  dict(z=(1.02, 1.11), f=(.54, .5), ph=(.58, .5), e="in"),
    6:  dict(z=(1.13, 1.04), f=(.5, .5), ph=(.5, .5), e="out"),
    7:  dict(z=(1.09, 1.01), f=(.5, .46), ph=(.5, .5), e="out"),
    8:  dict(z=(1.01, 1.07), f=(.5, .5), ph=(.5, .5), e="in"),
    9:  dict(z=(1.02, 1.09), f=(.5, .5), ph=(.5, .5), e="in"),
    10: dict(z=(1.00, 1.14), f=(.5, .5), ph=(.5, .48), e="in"),
}

SHAKES = {
    1: [(0.02, 26, 14), (0.55, 12, 16)],
    2: [(0.62, 15, 16), (1.05, 8, 18)],
    5: [(2.35, 18, 15), (0.55, 7, 16)],
    6: [(0.00, 30, 13), (1.80, 24, 13)],
    8: [(2.02, 9, 17)],
    10: [(0.85, 20, 13), (4.10, 12, 15)],
}

GRADE = {
    1: dict(tint=(255, 238, 232), amt=.05, contrast=1.06, sat=1.05),
    2: dict(tint=(255, 250, 238), amt=.04, contrast=1.03, sat=1.02),
    3: dict(tint=(255, 245, 222), amt=.11, contrast=1.03, sat=1.02),
    4: dict(tint=(255, 245, 224), amt=.12, contrast=1.02, sat=1.0),
    5: dict(tint=(255, 230, 200), amt=.12, contrast=1.06, sat=1.06),
    6: dict(tint=(206, 216, 236), amt=.16, contrast=1.10, sat=.86),
    7: dict(tint=(250, 247, 240), amt=.05, contrast=1.04, sat=1.0),
    8: dict(tint=(255, 249, 232), amt=.07, contrast=1.02, sat=1.05),
    9: dict(tint=(252, 250, 246), amt=.04, contrast=1.03, sat=.98),
    10: dict(tint=(30, 40, 60), amt=.03, contrast=1.06, sat=1.02),
}

PARTS = {
    1: ("spark", 16, 11), 2: ("dust", 26, 12), 3: ("dust", 30, 13), 4: ("dust", 24, 14),
    5: ("ember", 46, 15), 6: ("dust", 22, 16), 7: ("dust", 28, 17), 8: ("confetti", 44, 18),
    9: ("dust", 20, 19), 10: ("ember", 24, 20),
}
_parts = {k: make_particles(v[0], v[1], v[2]) for k, v in PARTS.items()}

def shake_for(n, tl):
    sx = sy = 0.0
    for t0, amp, dec in SHAKES.get(n, []):
        d = tl - t0
        if 0 <= d < 1.1:
            k = amp * math.exp(-d * dec)
            sx += k * math.sin(d * 61 + t0)
            sy += k * math.cos(d * 47 + t0 * 2)
    sx += 1.2 * math.sin(tl * 1.7 + n)
    sy += 1.0 * math.cos(tl * 1.3 + n * 2)
    return sx, sy

# SFX-synced impact punches: (local time, zoom amount)
IMPACTS = {
    1:  [(0.02, .034), (0.30, .012)],
    2:  [(0.05, .024), (0.62, .010)],
    5:  [(2.35, .012)],
    6:  [(0.00, .040), (1.80, .028)],
    8:  [(2.02, .010)],
    10: [(0.82, .034), (3.00, .012)],
}


def impact_curve(n, tl):
    v = 0.0
    for ht, amp in IMPACTS.get(n, []):
        d = tl - ht
        if -0.03 < d < 0.75:
            v += amp * math.exp(-max(d, 0.0) * 7.0) * cl((d + .03) / .05)
    return v


def camera_for(n, tl):
    c = CAM[n]
    dur = next(b["dur"] for b in BEATS if b["n"] == n)
    p = cl(tl / max(.8, dur * .92))
    if c["e"] == "in": p = eio(p)
    elif c["e"] == "out": p = eo(p)
    z = lerp(c["z"][0], c["z"][1], p) + impact_curve(n, tl)
    fx = lerp(c["f"][0], c["ph"][0], p)
    fy = lerp(c["f"][1], c["ph"][1], p)
    return z, fx, fy, shake_for(n, tl)

# =====================================================================
#  HOST CHARACTER  (the hooded narrator from the reference)
# =====================================================================
HOST_DIR = os.path.join(ROOT, "assets")
_host_cache = {}


def host_sprite(name):
    """RGBA sprite, cropped to its own ink, edge-padded for the glow layer."""
    if name in _host_cache:
        return _host_cache[name]
    p = os.path.join(HOST_DIR, name + ".png")
    if not os.path.exists(p):
        return None
    im = Image.open(p).convert("RGBA")
    a = np.asarray(im)
    ys, xs = np.where(a[..., 3] > 24)
    if len(xs) == 0:
        return None
    x0, x1 = xs.min(), xs.max() + 1
    y0, y1 = ys.min(), ys.max() + 1
    im = im.crop((x0, y0, x1, y1))
    _host_cache[name] = im
    return im


def _host_glow(name, h):
    """bright eye/smile glow, blurred, same size as the sprite"""
    key = ("g", name, int(h))
    if key in _host_cache:
        return _host_cache[key]
    im = host_sprite(name)
    if im is None:
        return None
    w = max(8, int(im.width * h / im.height))
    im = im.resize((w, h), Image.LANCZOS)
    arr = np.asarray(im).astype(np.float32)
    lum = arr[..., :3].max(2)
    m = np.clip((lum - 140) / 110, 0, 1)[..., None]
    g = (arr[..., :3] * m)
    gimg = Image.fromarray(g.astype(np.uint8)).filter(ImageFilter.GaussianBlur(8))
    ga = np.asarray(gimg).astype(np.float32)
    ga = ga.max(2)
    glow = Image.fromarray(np.dstack([ga, ga, ga + 6, np.clip(ga * .92, 0, 255)]).astype(np.uint8), "RGBA")
    _host_cache[key] = (im, glow)
    return _host_cache[key]


def put_host(base, name, bottom=None, top=None, cx=None, left=None, right=None,
             max_h=None, max_w=None, scale=1.0, opacity=1.0, bob=0.0, rot=0.0,
             glow=True):
    """place the hooded character, scaled by height so it reads as one figure"""
    sp = _host_glow(name, int((max_h or 400) * max(.25, scale)))
    if sp is None:
        return
    im, gl = sp
    vis = cl(opacity)
    if vis <= .01:
        return
    iw, ih = im.size
    if max_w is not None and max_h is not None:
        w = min(max_w, max_h * iw / ih)
    elif max_h is not None:
        w = max_h * iw / ih
    elif max_w is not None:
        w = max_w
    else:
        w = iw
    nw = max(8, int(round(w * scale)))
    nh = max(4, int(round(nw * ih / iw)))
    if rot:
        im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
        gl = gl.rotate(rot, resample=Image.BICUBIC, expand=True)
        nh = max(nh, im.height)
    x = left if left is not None else (right - nw if right is not None else
                                       (cx - nw / 2 if cx is not None else W / 2 - nw / 2))
    y = bottom - nh + int(bob) if bottom is not None else (top if top is not None else H - nh)
    # soft contact shadow
    sh = Image.new("RGBA", (nw + 120, nh + 120), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([40, nh + 40, nw + 80, nh + 96], fill=(20, 18, 16, 150))
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    a_sh = sh.getchannel("A").point(lambda v: int(v * vis * .8))
    base.paste(sh, (int(x) - 40, int(y) - 40), a_sh)
    if glow:
        gg = gl.resize((nw, nh), Image.LANCZOS).copy()
        gg.putalpha(gg.getchannel("A").point(
            lambda v: int(v * vis * (.45 + .55 * abs(math.sin(t_glob * 4.2))))))
        base.paste(gg, (int(x), int(y)), gg)
    body = im.resize((nw, nh), Image.LANCZOS).copy()
    body.putalpha(body.getchannel("A").point(lambda v: int(v * vis)))
    base.paste(body, (int(x), int(y)), body)
    return (x, y, nw, nh)


t_glob = 0.0

# =====================================================================
#  SCENES
# =====================================================================
def s1(base, t, dur):
    # red hazard glow on edges
    halo(base, 200, 1780, 520, (255, 228, 218), .9, .7)
    halo(base, 900, 1760, 460, (255, 224, 214), .8, .7)
    boss_sil(base, 800, 1500, w=470, opacity=.17, blur=2.4)

    # warning icon slam
    p = eob(sg(t, .08, .42))
    if p > .02:
        for k in range(3):
            r = 120 + 190 * eo(sg(t, .16 + k * .18, .9))
            glow_ring(base, 800, 980, r, 5, RED, .32 * (1 - sg(t, .16 + k * .18, .9)))
        put(base, "icon_warning", cx=800, cy=980, max_w=330,
            scale=.55 + .45 * p, opacity=cl(sg(t, .08, .18) * 1.8))
        d = ImageDraw.Draw(base)
        for i, (sx, sy) in enumerate([(600, 800), (1000, 860), (980, 1150)]):
            if t > .5 + i * .1:
                sparkle(d, sx, sy, 15 * eo(sg(t, .5 + i * .1, .24)), RED, 5)

    if t > .9:
        a = eo(sg(t, .9, .4))
        pill(base, 800, 1235, "WARNING", fill=RED, size=30, opacity=a, padx=26, track=3,
             scale=.9 + .1 * a)

    # big hook slam
    if t < 1.5:
        a = cl(sg(t, .02, .1)) * (1 - cl(sg(t, 1.05, .35)))
        if a > .02:
            sc = 1.06 - .06 * eo(sg(t, 0, .3))
            hw = int(560 * sc)
            hh = int(150 * sc)
            shadow_rr(base, (540 - hw // 2, 470 - hh // 2, 540 + hw // 2, 470 + hh // 2), 16,
                      alpha=int(60 * a), blur=18, dy=10, fill=RED)
            put_text_scaled(base, "RUK JAO!", F(N9, 116), WHITE, 540, 462, sc, a)
            for k in range(2):
                glow_ring(base, 540, 470, 120 + 250 * eo(sg(t, k * .12, .6)), 5, RED,
                          .30 * (1 - sg(t, k * .12, .6)) * a)

    # character
    q = eo(sg(t, 0, .5))
    bob = math.sin(t * 2.2) * 6
    put_host(base, "host_worried", cx=330, bottom=1830 + bob, max_h=840,
        scale=.97 + .03 * q, opacity=cl(sg(t, 0, .16)))
    if t > 1.5:
        a = eo(sg(t, 1.5, .4))
        pill(base, 330, 1410, "AAP", fill=(38, 49, 66), size=30, opacity=a, track=2)
    if t > 4.4:
        a = eo(sg(t, 4.4, .4))
        pill(base, 330, 1500, "CAREER \u00b7 WARNING", fill=RED, size=25, opacity=a, padx=22)


def s2(base, t, dur):
    halo(base, 540, 470, 430, (255, 240, 200), .95, .8)
    # crown descends
    y = lerp(-260, 452, eob(sg(t, .05, .62), 1.35))
    p = cl(sg(t, .05, .62))
    if p > .01:
        put(base, "icon_crown", cx=540, cy=y, max_w=238, max_h=212,
            scale=.85 + .15 * p, opacity=cl(p * 3))
        if t > .55:
            d = ImageDraw.Draw(base)
            for i, (sx, sy) in enumerate([(370, 350), (720, 372), (545, 300), (300, 470), (790, 470)]):
                a = eo(sg(t, .58 + i * .07, .3))
                if a > 0:
                    star4(base, sx, sy, 12 * a, GOLD_L, a)
        if t > .58:
            for k in range(2):
                r = 90 + 240 * eo(sg(t, .58 + k * .14, .8))
                glow_ring(base, 540, 452, r, 4, GOLD, .30 * (1 - sg(t, .58 + k * .14, .8)))

    # LAW ONE kinetic
    if t > .30:
        a1 = cl(sg(t, .30, .28)); a2 = cl(sg(t, .40, .28))
        T(base, (540, 760), "LAW", F(S8, 116 * (.9 + .1 * eob(sg(t, .3, .4)))), INK, alpha=a1)
        T(base, (540, 905), "ONE", F(S9, 158 * (.88 + .12 * eob(sg(t, .4, .42)))), RED, alpha=a2)
    pr = eio(sg(t, .62, .45))
    if pr > 0:
        ImageDraw.Draw(base).rounded_rectangle([540 - 300 * pr, 1028, 540 + 300 * pr, 1040], 6, fill=GOLD)
        if pr > .95:
            star4(base, 540 - 310, 1034, 8, GOLD_L, .9); star4(base, 540 + 310, 1034, 8, GOLD_L, .9)
    if t > 1.05:
        a = cl(sg(t, 1.05, .3))
        T(base, (540, 1122), "NEVER OUTSHINE", F(S7, 72), INK, alpha=a)
    if t > 1.35:
        a = cl(sg(t, 1.35, .3))
        T(base, (540, 1208), "THE MASTER", F(S7, 72), RED, alpha=a)
    if t > 1.9:
        a = eo(sg(t, 1.9, .45))
        pill(base, 540, 1330, "48 LAWS OF POWER", fill=(38, 49, 66), size=27, opacity=a, padx=28, track=3)
    if t > 2.6:
        a = eo(sg(t, 2.6, .45))
        bob = math.sin(t * 2.4) * 5
        put_host(base, "host_think", right=1045, bottom=1850 + bob, max_h=470, opacity=a * .95)


def s3(base, t, dur):
    # spotlight
    sp = eo(sg(t, 0, .7))
    cone = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(cone).polygon([(300, 250), (780, 250), (1010, 1250), (70, 1250)],
                                 fill=(255, 236, 186, int(60 * sp)))
    cone = cone.filter(ImageFilter.GaussianBlur(40))
    base.paste(cone, (0, 0), cone)
    halo(base, 540, 900, 430, (255, 240, 205), .85, .9)

    a = eo(sg(t, .05, .3))
    pill(base, 540, 360, "FRANCE  \u00b7  1661", fill=INK, size=34, opacity=a, padx=32, track=3,
         scale=.92 + .08 * eob(sg(t, .05, .35)))

    q = eo(sg(t, .18, .55))
    if q > .02:
        put(base, "king_throne", cx=540, cy=880, max_w=740, max_h=720,
            scale=.92 + .08 * eob(sg(t, .18, .62)), opacity=q)

    if t > 1.25:
        a = eo(sg(t, 1.25, .35))
        pill(base, 540, 1330, "KING LOUIS XIV", fill=GOLD, fg=INK, size=34, opacity=a, padx=34,
             track=2, scale=.94 + .06 * a)
    if t > 1.95:
        a = eo(sg(t, 1.95, .3))
        T(base, (540, 1428), "KA FINANCE MINISTER", F(N7, 25), (132, 128, 120), alpha=a)
        n_show = int(cl((t - 2.15) / 0.045, 0, 15))
        if n_show > 0:
            name = "Nicolas Fouquet"[:n_show]
            T(base, (540, 1505), name + ("|" if t < 3.2 and int(t * 3) % 2 == 0 else ""),
              F(S8, 62), RED, alpha=cl(sg(t, 1.95, .2)))
    if t > 2.9:
        a = eo(sg(t, 2.9, .4))
        pill(base, 540, 1610, "MINISTER OF FINANCE", fill=(38, 49, 66), size=24, opacity=a, padx=24, track=2)


def s4(base, t, dur):
    bx0, by0, bx1, by1 = 84, 372, 996, 962
    q = eo(sg(t, .02, .5))
    if q > .02:
        shadow_rr(base, (bx0, by0, bx1, by1), 26, alpha=70, blur=22, dy=14)
        cover(base, os.path.join(ASSETS, "palace_party.png"), (bx0, by0, bx1, by1), radius=26,
              opacity=q, focus_y=cl(.35 + .25 * sg(t, 0, dur)), zoom=1.04 + .06 * sg(t, 0, dur),
              focus_x=.5)
        ImageDraw.Draw(base).rounded_rectangle([bx0, by0, bx1, by1], 26, outline=INK, width=4)
    if t > .45:
        a = eo(sg(t, .45, .35))
        pill(base, 540, 1010, "VAUX-LE-VICOMTE  \u00b7  1661", fill=(38, 49, 66), size=22,
             opacity=a, padx=22, track=2)

    if t > 1.0:
        a = cl(sg(t, 1.0, .28))
        s = .9 + .1 * eob(sg(t, 1.0, .4))
        bubble(base, 560, 1250, 840 * s, 250 * s, opacity=a, tail=(300, 1560))
        T(base, (560, 1190), "\u201cYeh to KING se bhi", F(S7, 52), INK, alpha=a)
        d = ImageDraw.Draw(base)
        f = F(S7, 52)
        parts = [("zyada ", INK), ("ROYAL", RED), (" hai!\u201d", INK)]
        tot = sum(tw(d, x, f) for x, _ in parts)
        x = 560 - tot / 2
        for txt, col in parts:
            d.text((x, 1278), txt, font=f, fill=col + (int(255 * a),), anchor="ls")
            x += tw(d, txt, f)

    if t > 2.1:
        a = eo(sg(t, 2.1, .4))
        put_host(base, "host_happy", left=40, bottom=1856, max_h=460, opacity=a)
        pill(base, 730, 1660, "MEHMAAN HAIRAN", fill=GOLD, fg=INK, size=26, opacity=a, padx=24, track=2)


def s5(base, t, dur):
    q = eo(sg(t, 0, .4))
    if q > .02:
        put(base, "king_throne", cx=285, bottom=1330, max_h=520, opacity=q)
    if t > .2:
        pill(base, 285, 1402, "KING", fill=INK, size=26, opacity=eo(sg(t, .2, .35)), track=2)

    g = eio(sg(t, .35, 3.4))
    if g > 0:
        gl = .55 + .45 * math.sin(t * 5.5)
        halo(base, 800, 940, 250 * (.5 + .6 * g), (255, 170, 90), .55 * gl * cl(g * 2), 1.1)
        put(base, "icon_flame", cx=800, cy=940, max_w=330, max_h=350,
            scale=.40 + .95 * g + .02 * math.sin(t * 7), opacity=cl(g * 2.4))
        draw_particles(base, _parts[5], t, "ember", cl(g))
    if t > 1.45:
        a = cl(sg(t, 1.45, .35))
        put_text_scaled(base, "JALAN", F(S9, 96), RED, 800, 1218,
                        scale=.75 + .25 * eob(sg(t, 1.45, .45)), alpha=a)
        T(base, (800, 1288), "J E A L O U S Y", F(N7, 22), (96, 92, 86), alpha=a * .95)
    if t > 2.35:
        a = eo(sg(t, 2.35, .45))
        bob = math.sin(t * 2.6) * 5
        put_host(base, "host_think", cx=540, bottom=1868 + bob, max_h=620, opacity=a * .97)
    if t > 4.1:
        a = eo(sg(t, 4.1, .4))
        # heat vignette
        red = Image.new("RGB", (W, H), (255, 120, 60))
        base.paste(Image.blend(base, red, .10 * a * (0.7 + .3 * math.sin(t * 6))), (0, 0))


def s6(base, t, dur):
    halo(base, 540, 1080, 470, (226, 226, 228), .9, .85)
    # bars slam
    if t > 0:
        bp = eob(sg(t, 0, .5), 1.5)
        off = int((1 - cl(bp)) * 1100)
        bars = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        db = ImageDraw.Draw(bars)
        for i in range(6):
            x = 120 + i * 170
            db.rectangle([x, 520 - off, x + 26, 1930 - off], fill=(40, 42, 50, 220))
        for i in range(2):
            y = 880 + i * 560
            db.rectangle([0, y - off, W, y + 20 - off], fill=(40, 42, 50, 200))
        base.paste(bars, (0, 0), bars)
    q2 = eo(sg(t, .12, .45))
    if q2 > .02:
        bob = math.sin(t * 1.9) * 4
        put_host(base, "host_worried", cx=540, bottom=1745 + bob, max_h=780, opacity=q2 * .96)
    if t > 1.75:
        sp = eob(sg(t, 1.75, .38))
        stamp(base, 540, 640, "GIRAFTAR!", ang=-8, color=RED, size=86,
              scale=.5 + .5 * sp, opacity=cl(sp * 1.8))
        if sp > .8:
            for k in range(2):
                r = 130 + 240 * eo(sg(t, 1.85 + k * .12, .7))
                glow_ring(base, 540, 640, r, 4, RED, .28 * (1 - sg(t, 1.85 + k * .12, .7)))
    if t > 2.85:
        a = eo(sg(t, 2.85, .4))
        pill(base, 540, 1660, "SIRF EK PALACE KI WAJAH SE", fill=INK, size=25, opacity=a, padx=24)
    if t > 3.6:
        a = eo(sg(t, 3.6, .4))
        pill(base, 540, 1755, "1661  \u2192  1680  \u00b7  QAID", fill=RED, size=24, opacity=a, padx=24)


def s7(base, t, dur):
    sp = eo(sg(t, .02, .5))
    cone = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(cone).polygon([(420, 250), (660, 250), (960, 900), (120, 900)],
                                 fill=(255, 232, 172, int(80 * sp)))
    cone = cone.filter(ImageFilter.GaussianBlur(30))
    base.paste(cone, (0, 0), cone)

    if t > .12:
        a = cl(sg(t, .12, .3))
        s = .86 + .14 * eob(sg(t, .12, .45))
        T(base, (540, 520), "MASTER", F(S9, 118 * s), INK, alpha=a)
    if t > .55:
        pr = eio(sg(t, .55, .45))
        ImageDraw.Draw(base).rounded_rectangle([540 - 250 * pr, 600, 540 + 250 * pr, 610], 5, fill=RED)
        py = 520 + math.sin(t * 2.2) * 7
        put(base, "icon_crown", cx=540, cy=py - 150, max_w=110, opacity=eo(sg(t, .6, .3)))
    if t > 1.1:
        a = cl(sg(t, 1.1, .35))
        T(base, (540, 745), "INSECURE", F(S7, 78), RED, alpha=a)
    if t > 1.35:
        a = cl(sg(t, 1.35, .35))
        T(base, (540, 832), "MAT KARO", F(S7, 78), INK, alpha=a)
    if t > 1.9:
        a = eo(sg(t, 1.9, .45))
        put_host(base, "host_think", cx=250, bottom=1875, max_h=660, opacity=a)
    if t > 3.7:
        a = eo(sg(t, 3.7, .45))
        shadow_rr(base, (560, 1150, 1010, 1350), 24, alpha=48, blur=16, dy=8, fill=WHITE)
        ImageDraw.Draw(base).rounded_rectangle([560, 1150, 1010, 1350], 24, outline=(216, 212, 204), width=3)
        T(base, (785, 1212), "tumhari kamyabi", F(S4, 34), INK_SOFT, alpha=a)
        T(base, (785, 1282), "= uska inaam", F(S7, 44), BLUE_DEEP, alpha=a)


def s8(base, t, dur):
    halo(base, 540, 950, 430, (255, 244, 210), .9, .85)
    if t > .05:
        a = cl(sg(t, .05, .3))
        T(base, (540, 470), "SMART RAHO...", F(S7, 76), INK, alpha=a)
    q = eob(sg(t, .35, .5))
    if q > .02:
        tilt = 4 * math.sin(t * 1.8) * (1 - .5 * sg(t, 2, 1))
        put(base, "icon_scale", cx=540, cy=880, max_w=420, max_h=330, rot=tilt,
            scale=.72 + .28 * q, opacity=cl(q * 2))
    if t > 1.15:
        a = eo(sg(t, 1.15, .35))
        pill(base, 340, 1140, "TALENT", fill=BLUE, size=33, opacity=a, scale=.9 + .1 * a, track=2)
    if t > 1.4:
        a = eo(sg(t, 1.4, .35))
        pill(base, 748, 1140, "CREDIT", fill=GOLD, fg=INK, size=33, opacity=a, scale=.9 + .1 * a, track=2)
    if t > 1.95:
        arrow(base, [(410, 1225), (540, 1305), (678, 1225)], color=RED, width=8,
              progress=eio(sg(t, 1.95, .6)))
        if t > 2.1:
            draw_particles(base, _parts[8], t - 2.1, "confetti", cl(sg(t, 2.1, .35)), y_min=340)
        a = eo(sg(t, 2.25, .4))
        pill(base, 540, 1372, "CREDIT MASTER KO DO", fill=RED, size=32, opacity=a, padx=30)
    if t > 3.0:
        a = eo(sg(t, 3.0, .45))
        jump = -abs(math.sin(t * 3.2)) * 16
        put_host(base, "host_happy", cx=862, bottom=1876 + jump, max_h=500, opacity=a)
    if t > 4.7:
        a = eo(sg(t, 4.7, .4))
        pill(base, 470, 1620, "uske saaye se bada mat bano", fill=(38, 49, 66), size=26,
             opacity=a, padx=24)


def s9(base, t, dur):
    q = eo(sg(t, .02, .45))
    if q > .02:
        s = .94 + .06 * eob(sg(t, .02, .45))
        cx, cy, w, h = 540, 1010, 852 * s, 820 * s
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        shadow_rr(base, box, 30, alpha=78, blur=26, dy=16, fill=WHITE)
        d = ImageDraw.Draw(base)
        d.rounded_rectangle(box, 30, outline=INK, width=4)
        d.text((box[0] + 30, box[1] + 4), "\u201c", font=F(S9, 150), fill=GOLD)
        # ticking clock
        ccx, ccy, cr = box[2] - 92, box[1] + 96, 34
        d.ellipse([ccx - cr, ccy - cr, ccx + cr, ccy + cr], outline=(206, 202, 194), width=4)
        ang = -math.pi / 2 + t * 2.2
        d.line([(ccx, ccy), (ccx + math.cos(ang) * cr * .62, ccy + math.sin(ang) * cr * .62)],
               fill=RED, width=4)
        d.line([(ccx, ccy), (ccx, ccy - cr * .42)], fill=INK_SOFT, width=3)
        if t > .18:
            a1 = cl(sg(t, .18, .30))
            T(base, (cx, cy - 190), "Log kamyabi", F(S7, 68), INK, alpha=a1)
            T(base, (cx, cy - 100), "bhool jate hain...", F(S7, 68), INK, alpha=a1)
        if t > 1.55:
            a2 = cl(sg(t, 1.55, .35))
            T(base, (cx, cy + 45), "lekin apni", F(S7, 68), INK, alpha=a2)
            T(base, (cx, cy + 152), "BEIZZATI", F(S9, 96), RED, alpha=a2)
            underline(base, cx - 205, cx + 205, cy + 205, RED, 11, eio(sg(t, 2.15, .55)))
            T(base, (cx, cy + 285), "kabhi nahi bhoolte.", F(S7, 66), INK, alpha=a2)
    if t > 3.2:
        a = eo(sg(t, 3.2, .45))
        put_host(base, "host_worried", cx=900, bottom=1878, max_h=420, opacity=a)


def s10(base, t, dur):
    base.paste(Image.new("RGB", (W, H), (5, 7, 11)), (0, 0))
    im = Image.open(os.path.join(ASSETS, "chained_hand.png")).convert("RGB")
    s = max(W / im.width, H / im.height) * 1.02
    nw, nh = int(im.width * s), int(im.height * s)
    im = im.resize((nw, nh), Image.LANCZOS)
    l, tp = (nw - W) // 2, int((nh - H) * .40)
    base.paste(im.crop((l, tp, l + W, tp + H)), (0, 0))
    # dark gradients
    top = Image.new("RGB", (W, 900), (3, 4, 8))
    m = Image.new("L", (1, 900))
    for i in range(900):
        m.putpixel((0, i), int(255 * .92 * (1 - i / 899) ** 1.5))
    base.paste(top, (0, 0), m.resize((W, 900)))
    bot = Image.new("RGB", (W, 860), (2, 3, 6))
    m2 = Image.new("L", (1, 860))
    for i in range(860):
        m2.putpixel((0, i), int(255 * .97 * (i / 859) ** 1.3))
    base.paste(bot, (0, H - 860), m2.resize((W, 860)))
    draw_particles(base, _parts[10], t, "ember", .7)

    a = cl(sg(t, .1, .45))
    T(base, (540, 1318), "YEH THI", F(N6, 36), (236, 232, 223), alpha=a)
    put_text_scaled(base, "LAW ONE", F(S9, 116), WHITE, 540, 1426,
                    scale=1 + .04 * sg(t, .1, .5), alpha=a)
    if t > .55:
        pr = eio(sg(t, .55, .45))
        d = ImageDraw.Draw(base)
        d.rounded_rectangle([540 - 205 * pr, 1500, 540 + 205 * pr, 1510], 5,
                            fill=GOLD + (int(255 * cl(sg(t, .55, .2))),))
    if t > .95:
        a3 = cl(sg(t, .95, .4))
        T(base, (540, 1570), "Fouquet ki zindagi qaid mein khatam hui.", F(S4, 33), (228, 223, 214), alpha=a3)
        T(base, (540, 1622), "Apne master ko kabhi neecha mat dikhao.", F(S7, 35), GOLD_L, alpha=a3)
    if t > 1.75:
        a4 = eo(sg(t, 1.75, .45))
        T(base, (540, 1704), "WAQT \u2014 aur bhi nahi hai.", F(S4, 30), (208, 202, 192), alpha=a4)
    if t > 2.35:
        a5 = eo(sg(t, 2.35, .45))
        T(base, (540, 1800), "LAW 02  \u2014  NEVER TRUST FRIENDS TOO MUCH", F(N6, 19),
          (226, 220, 210), alpha=a5 * .9)
        # swipe-up cue
        bob = math.sin(t * 4.2) * 7
        cx, cy = 540, 1852 + bob
        d2 = ImageDraw.Draw(base)
        for i, al in ((0, .95), (1, .55), (2, .3)):
            yy = cy + i * 13
            d2.line([(cx - 20, yy), (cx, yy + 13), (cx + 20, yy)],
                    fill=(255, 214, 112, int(255 * al * a5)), width=4, joint="curve")


SCENES = {1: s1, 2: s2, 3: s3, 4: s4, 5: s5, 6: s6, 7: s7, 8: s8, 9: s9, 10: s10}

# =====================================================================
#  CAPTION (kinetic)
# =====================================================================
CAP_W = 944
CAP_LEFT = (W - CAP_W) // 2
CAP_TOP = 118
CAP_FS = 54
CAP_LH = 70
CAP_PX = 38
CAP_PY = 28
_cap_layout = {}

def cap_layout(cue):
    if cue in _cap_layout: return _cap_layout[cue]
    f = F(S7, CAP_FS)
    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    lines = wrap(tmp, cue, f, CAP_W - CAP_PX * 2 - 12)
    # shrink if 3+ lines
    fs = CAP_FS
    while len(lines) > 2 and fs > 40:
        fs -= 3
        f = F(S7, fs)
        lines = wrap(tmp, cue, f, CAP_W - CAP_PX * 2 - 12)
    h = len(lines) * CAP_LH + CAP_PY * 2
    _cap_layout[cue] = (lines, h, f, fs)
    return _cap_layout[cue]

def draw_caption(base, b, tl):
    cues = b["cue_times"]
    idx = 0
    for i, c in enumerate(cues):
        if tl >= c["t"] - 0.02: idx = i
    cue = cues[idx]
    txt, kws = cue["text"], cue["kw"]
    age = tl - cue["t"]
    lines, h, f, fs = cap_layout(txt)

    # panel entrance
    pin = eob(cl(age / 0.28))
    dy = int((1 - pin) * -34)
    dx = int((1 - pin) * -40)
    sc = .96 + .04 * pin
    pw = int(CAP_W * sc); ph_ = int(h * sc)
    px = (W - pw) // 2 + dx
    py = CAP_TOP + (h - ph_) // 2 + dy

    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    # shadow
    d.rounded_rectangle([px + 2, py + 11, px + pw, py + ph_ + 11], 26, fill=(10, 14, 22, 70))
    # bar
    d.rounded_rectangle([px, py, px + pw, py + ph_], 26, fill=BLUE + (255,))
    # top gloss
    gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dg = ImageDraw.Draw(gl)
    for i in range(5):
        a = int(12 * (1 - i / 5))
        dg.rounded_rectangle([px + 3 + i, py + 3 + i, px + pw - 3 - i, py + ph_ * .55 - i],
                             24, fill=(255, 255, 255, a))
    lay = Image.alpha_composite(lay, gl)
    d = ImageDraw.Draw(lay)
    bh = max(0, int((ph_ - 16) * eob(cl(age / .34))))
    if bh > 6:
        d.rounded_rectangle([px - 16, py + (ph_ - bh) // 2, px - 7, py + (ph_ + bh) // 2],
                            5, fill=(255, 214, 112, 235))

    words = txt.split()
    # progressive reveal by word count within the cue
    total = max(1, len(words))
    reveal = int(cl(age / 0.10, 0, total))
    n_show = max(1, reveal)
    asc, desc = f.getmetrics()
    sp_w = tw(d, " ", f)
    kws_upper = {k.upper() for k in kws}
    word_i = 0
    newest = n_show - 1
    for li, line in enumerate(lines):
        lw = line.split()
        lwid = sum(tw(d, wd, f) for wd in lw) + sp_w * (len(lw) - 1)
        x = px + pw / 2 - lwid / 2
        line_cy = py + CAP_PY * sc + (li + .5) * CAP_LH * sc
        baseline = line_cy + (asc - desc) / 2 - 2
        for wd in lw:
            ww = tw(d, wd, f)
            core = wd.strip('.,!?"“”…:;').upper()
            is_kw = core in kws_upper
            wt = age - word_i * .095
            if wt >= 0:
                wa = cl(wt / .13)
                rise = (1 - eo(cl(wt / .22))) * 15
                col = (255, 214, 112) if is_kw else (255, 255, 255)
                if is_kw:
                    gp = eo(cl(wt / .26))
                    uy = line_cy + (asc + desc) * .30
                    uw = ww * .94 * gp
                    d.rounded_rectangle([x + ww * .03, uy, x + ww * .03 + uw, uy + 6], 3,
                                        fill=(255, 214, 112, int(235 * cl(wt / .12))))
                pop = 1.0 + (.24 * math.exp(-wt * 12) if word_i == newest else 0.0)
                rot = (2.6 * math.exp(-wt * 11) * (1 if word_i % 2 else -1)
                       if word_i == newest else 0.0)
                if pop > 1.001 or rot:
                    imgw = rgba_text(wd, f, col, int(255 * wa))
                    if pop > 1.001:
                        imgw = imgw.resize((max(1, int(imgw.width * pop)),
                                            max(1, int(imgw.height * pop))), Image.BICUBIC)
                    if rot:
                        imgw = imgw.rotate(rot, resample=Image.BICUBIC, expand=True)
                    lay.paste(imgw, (int(x - (imgw.width - ww) / 2),
                                     int(baseline - asc - (imgw.height - (asc + desc)) / 2 + rise)),
                              imgw)
                else:
                    d.text((x, baseline - rise), wd, font=f, fill=col + (int(255 * wa),),
                           anchor="ls")
            x += ww + sp_w
            word_i += 1

    base.paste(lay, (0, 0), lay)

# =====================================================================
#  OVERLAY
# =====================================================================
def draw_overlay(base, tg, total, n):
    """Nothing but a hairline progress line - no handles, no tags, no headings."""
    d = ImageDraw.Draw(base)
    dark = n == 10
    mark = GOLD_L if dark else GOLD
    pw = int((W - 100) * cl(tg / max(total, .001)))
    d.rounded_rectangle([50, H - 22, W - 50, H - 19], 2,
                        fill=(38, 40, 46) if dark else (224, 220, 212))
    if pw > 2:
        d.rounded_rectangle([50, H - 22, 50 + pw, H - 19], 2, fill=mark)


# =====================================================================
#  CINEMATIC POST
# =====================================================================
def light_sweep(img, p, amt=.30, ang=340):
    """soft diagonal highlight that travels across the frame"""
    x = -700 + p * (W + 1400)
    lay = Image.new("L", (W, H), 0)
    dd = ImageDraw.Draw(lay)
    dd.polygon([(x, 0), (x + 300, 0), (x + 300 + 520, H), (x + 520, H)], fill=255)
    lay = lay.filter(ImageFilter.GaussianBlur(85))
    a = np.asarray(img).astype(np.float32)
    m = (np.asarray(lay).astype(np.float32) / 255.0 * amt)[..., None]
    return Image.fromarray(np.clip(a + (255.0 - a) * m, 0, 255).astype(np.uint8))


def bloom(img, amt=.55, thr=205):
    small = img.resize((W // 5, H // 5), Image.BILINEAR)
    a = np.asarray(small).astype(np.float32)
    lum = a.max(2)
    m = np.clip((lum - thr) / max(1.0, 255 - thr), 0, 1)[..., None]
    bright = Image.fromarray((a * m).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))
    bl = np.asarray(bright.resize((W, H), Image.BILINEAR)).astype(np.float32)
    return Image.fromarray(np.clip(np.asarray(img).astype(np.float32) + bl * amt, 0, 255).astype(np.uint8))


def chroma(img, px=2):
    a = np.asarray(img)
    if a.ndim == 2:
        return img
    r = np.roll(a[..., 0], px, axis=1)
    b = np.roll(a[..., 2], -px, axis=1)
    return Image.fromarray(np.dstack([r, a[..., 1], b]))


def weave(img, t, amp=.7):
    dx = amp * math.sin(t * 2.31) + .4 * math.sin(t * 5.7)
    dy = .55 * math.sin(t * 1.73 + 1.2)
    if abs(dx) < .25 and abs(dy) < .25:
        return img
    return img.transform(img.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.BILINEAR)


# =====================================================================
#  COMPOSITION
# =====================================================================
def scene_frame(n, tl):
    b = next(x for x in BEATS if x["n"] == n)
    base = Image.new("RGB", (W, H), NIGHT) if n == 10 else paper_bg()
    SCENES[n](base, tl, b["dur"])
    z, fx, fy, sh = camera_for(n, tl)
    base = apply_camera(base, z, fx, fy, sh)
    # particles (paper beats only unless scene drew its own)
    kind, cnt, seed = PARTS[n]
    if n in (8,):
        pass
    elif n not in (5, 10):
        draw_particles(base, _parts[n], tl, kind, .85)
    g = GRADE[n]
    base = grade(base, g["tint"], g["amt"], g["contrast"], 1.0, g.get("sat", 1.0))
    base = apply_vignette(base, .30 if n == 10 else .16)
    return base

def compose(t):
    global t_glob
    t_glob = t
    # current beat
    idx = 0
    for i, b in enumerate(BEATS):
        if t >= b["start"] - 1e-6: idx = i
    b = BEATS[idx]
    tl = t - b["start"]
    img = scene_frame(b["n"], tl)

    # transition into this beat
    if idx > 0:
        prev = BEATS[idx - 1]
        p = (t - (b["start"] - TRANS_W * .5)) / TRANS_W
        if 0 <= p <= 1:
            a = scene_frame(prev["n"], prev["dur"] + (t - b["start"]) + .05)
            img = transition(a, img, b["trans"], p)
            if b["trans"] in ("flash", "punch"):
                img = flash(img, WHITE, .34 * math.sin(math.pi * cl(p)))

    # caption (all beats except end card, which carries its own text)
    if b["n"] == 1 and tl < BEATS[0]["cue_times"][1]["t"]:
        pass                      # the hook headline is already on screen
    elif b["n"] != 10:
        draw_caption(img, b, tl)

    # end-card / hook flashes
    if b["n"] == 1:
        img = flash(img, (255, 245, 240), .45 * max(0, 1 - tl / .16))
    if b["n"] == 6 and tl < .30:
        img = flash(img, (255, 255, 255), .55 * max(0, 1 - tl / .30))
    if b["n"] == 6 and 1.72 < tl < 1.9:
        img = flash(img, (255, 240, 240), .35 * (1 - abs(tl - 1.81) / .09))
    if b["n"] == 2 and .55 < tl < .72:
        img = flash(img, (255, 248, 225), .30 * (1 - abs(tl - .635) / .085))
    if b["n"] == 10:
        gl = 0.0
        if .15 < tl < .5: gl = .55 * (1 - abs(tl - .32) / .18)
        elif 3.0 < tl < 3.3: gl = .5 * (1 - abs(tl - 3.15) / .15)
        if gl > 0:
            img = glitch(img, t, gl)

    # cinematic post
    if tl < .66:
        img = light_sweep(img, eo(cl(tl / .66)), .34 if b["n"] != 10 else .12)
    if b["n"] == 10:
        img = bloom(img, .55, 200)
    ic = impact_curve(b["n"], tl)
    if ic > .008:
        img = chroma(img, int(round(1 + 5 * min(1.0, ic / .030))))
    img = weave(img, t, .8 if b["n"] != 10 else 1.2)

    draw_overlay(img, t, TOTAL, b["n"])
    img = apply_grain(img, int(t * FPS), .05)
    return img

def derived_events():
    """Events that are not element draws: camera punches, caption changes, beats."""
    derived, captions, beats = [], [], []
    for b in BEATS:
        beats.append(dict(t=round(b["start"], 3), n=b["n"], kind=b.get("kind"),
                          trans=b.get("trans")))
        for ht, amp in IMPACTS.get(b["n"], []):
            derived.append(dict(t=round(b["start"] + ht, 3), type="impact", el="camera",
                                label=f"punch{amp:.3f}", amp=round(min(1.0, amp / .040), 2),
                                x=None, y=None, fs=0, scale=1.0))
        cues = b.get("cue_times", [])
        for ci, c in enumerate(cues):
            captions.append(dict(t=round(b["start"] + c["t"], 3), beat=b["n"], cue=ci,
                                 text=c["text"], kw=c.get("kw", [])))
    return {"derived": derived, "captions": captions, "beats": beats}


# =====================================================================
#  RENDER
# =====================================================================
def render_video():
    total_frames = int(round(TOTAL * FPS))
    silent = os.path.join(OUT, "video_v8_silent.mp4")
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-x264-params", "keyint=48:min-keyint=24", "-movflags", "+faststart", silent]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(total_frames):
        proc.stdin.write(compose(i / FPS).tobytes())
        if i % 60 == 0:
            print(f"  frame {i}/{total_frames}  ({i / total_frames * 100:4.1f}%)", flush=True)
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed")
    return silent, total_frames


def mux(video, wav, final):
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", video, "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000",
                    "-shortest", "-movflags", "+faststart", final], check=True)
    return final


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    if mode == "stills":
        for ts in [float(x) for x in sys.argv[2:]]:
            p = os.path.join(OUT, f"still_{ts:06.2f}.png")
            compose(ts).save(p)
            print("saved", p)
    elif mode == "events":
        import json
        probe.ENABLED = True
        probe.install(sys.modules[__name__])
        for b in BEATS:
            frames = int(round(b["dur"] * FPS))
            for i in range(frames):
                t = b["start"] + i / FPS
                probe.T_NOW = t
                compose(t)
        extra = derived_events()
        data = probe.dump(os.path.join(OUT, "anim_events.json"), extra)
        ev = data["events"]
        print(f"{len(ev)} element events, {len(extra['derived'])} derived "
              f"-> {os.path.join(OUT, 'anim_events.json')}")
        from collections import Counter
        print("  by type:", dict(Counter(e["type"] for e in ev)))
        print("  by element:", dict(Counter(e["el"] for e in ev)))
    elif mode == "timeline":
        print(f"TOTAL {TOTAL:.2f}s")
        for b in BEATS:
            print(f"  beat {b['n']:2d} {b['kind']:7s} start {b['start']:6.2f} dur {b['dur']:5.2f}")
    else:
        import audio_v8
        print(f"TOTAL {TOTAL:.2f}s  frames {int(TOTAL * FPS)}")
        v, n = render_video()
        print("silent:", v, n)
        wav = audio_v8.build()
        final = os.path.join(OUT, "MonarchVoice_Law1_v8_CINEMATIC_9x16.mp4")
        mux(v, wav, final)
        print("FINAL:", final)
