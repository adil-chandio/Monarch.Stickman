#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MONARCHVOICE // NEO PROTOCOL  -  V2 CINEMATIC ENGINE
1920x1080 @ 30fps, 20s, procedural 3D-look stickman film.
No GPU / no Blender needed: pure numpy + OpenCV raster with faked volumetrics.
"""

import os
import math
import random
import subprocess
import time
import numpy as np
import cv2

cv2.setNumThreads(0)  # keep it single-thread predictable (faster in sandbox)

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
W, H = 1920, 1080
FPS = 30
DUR = 20.0
NFRAMES = int(DUR * FPS)
OUT_SILENT = "v2_silent.mp4"
OUT_FINAL = "MonarchVoice-NEO-PROTOCOL-1080p.mp4"
GROUND = 905.0

CYAN = np.array([255, 226, 90], np.float32)      # BGR  (hero)
WHITE = np.array([245, 245, 255], np.float32)
MAGENTA = np.array([86, 62, 255], np.float32)    # BGR (villain = crimson)
RED = np.array([70, 70, 255], np.float32)
GOLD = np.array([120, 210, 255], np.float32)
DEEP = np.array([48, 22, 14], np.float32)        # dark navy body

random.seed(7)
np.random.seed(7)


# ----------------------------------------------------------------------------
# MATH HELPERS
# ----------------------------------------------------------------------------
def clamp(v, a, b): return a if v < a else (b if v > b else v)
def lerp(a, b, t): return a + (b - a) * t
def smooth(t): return t * t * (3 - 2 * t)
def ease_io(t): return 0.5 - 0.5 * math.cos(math.pi * clamp(t, 0, 1))
def ease_out(t): t = clamp(t, 0, 1); return 1 - (1 - t) ** 3
def ease_in(t): t = clamp(t, 0, 1); return t ** 3
def pulse(t, t0, dur):  # 1 -> 0 decaying, 1 during window
    if t < t0 or t > t0 + dur: return 0.0
    return (1 - (t - t0) / dur) ** 2
def flash(t, t0, d=0.12):
    if t < t0 or t > t0 + d: return 0.0
    return (1 - (t - t0) / d) ** 1.6


# ----------------------------------------------------------------------------
# TEXT
# ----------------------------------------------------------------------------
FONT = cv2.FONT_HERSHEY_DUPLEX
FONT_B = cv2.FONT_HERSHEY_TRIPLEX


def text(img, s, x, y, scale=1.0, color=WHITE, thick=2, alpha=1.0,
         center=False, spacing=0.0, font=FONT, glow=True):
    col = tuple(int(c) for c in (np.array(color) * clamp(alpha, 0, 1)))
    units = []
    total = 0
    for ch in s:
        (w, h), _ = cv2.getTextSize(ch, font, scale, thick)
        units.append((ch, w))
        total += w + int(scale * spacing * 2)
    if center:
        x -= total // 2
    cx = int(x)
    for ch, w in units:
        if alpha > 0.02 and ch != " ":
            cv2.putText(img, ch, (cx, int(y)), font, scale, (0, 0, 0),
                        thick + 3, cv2.LINE_AA)
            cv2.putText(img, ch, (cx, int(y)), font, scale, col, thick, cv2.LINE_AA)
        cx += w + int(scale * spacing * 2)
    return total


def hline(img, x1, x2, y, color, thick=1, alpha=1.0):
    col = tuple(int(c) for c in (np.array(color) * clamp(alpha, 0, 1)))
    cv2.line(img, (int(x1), int(y)), (int(x2), int(y)), col, thick, cv2.LINE_AA)


# ----------------------------------------------------------------------------
# STATIC BACKDROP  (city, neon skyline, moon) - baked once for speed
# ----------------------------------------------------------------------------
BW, BH = 2800, 1200  # wide backdrop


def _skyline(layer, x0, x1, base_y, hmin, hmax, col, win_col, win_p, seed,
             win_size=(4, 6), lit=True):
    rng = random.Random(seed)
    x = x0
    while x < x1:
        bw = rng.randint(34, 96)
        bh = rng.randint(hmin, hmax)
        top = base_y - bh
        cv2.rectangle(layer, (x, top), (x + bw, base_y), col, -1)
        # rooftop details
        if rng.random() < 0.5:
            aw = rng.randint(2, 5)
            ax = x + rng.randint(6, max(7, bw - 6))
            cv2.rectangle(layer, (ax, top - rng.randint(12, 46)),
                          (ax + aw, top), col, -1)
        if rng.random() < 0.35:
            bx = x + bw // 2
            cv2.line(layer, (bx, top), (bx, top - rng.randint(20, 70)), col, 2)
        if lit:
            wy = top + 10
            while wy < base_y - 8:
                wx = x + 6
                while wx < x + bw - 8:
                    if rng.random() < win_p:
                        wc = tuple(int(c * rng.uniform(0.35, 1.0)) for c in win_col)
                        cv2.rectangle(layer, (wx, wy),
                                      (wx + win_size[0], wy + win_size[1]), wc, -1)
                    wx += win_size[0] + rng.randint(5, 11)
                wy += win_size[1] + rng.randint(7, 14)
        x += bw + rng.randint(3, 16)


def build_backdrop():
    img = np.zeros((BH, BW, 3), np.float32)
    # vertical gradient: deep indigo -> violet horizon -> ember glow
    ys = np.linspace(0, 1, BH)[:, None]
    top = np.array([58, 26, 20], np.float32)      # BGR
    mid = np.array([92, 36, 46], np.float32)
    hor = np.array([150, 70, 96], np.float32)
    sky = np.where(ys < 0.52, top + (mid - top) * (ys / 0.52),
                   mid + (hor - mid) * ((ys - 0.52) / 0.48))
    img[:] = sky[:, None, :]

    # moon / hazy sun disc
    moon = np.zeros((BH, BW), np.float32)
    cv2.circle(moon, (2050, 250), 86, 1.0, -1)
    moon = cv2.GaussianBlur(moon, (0, 0), 40)
    img += moon[:, :, None] * np.array([150, 150, 190], np.float32)
    cv2.circle(img, (2050, 250), 58, (225, 225, 245), -1, cv2.LINE_AA)

    # far skyline
    far = np.zeros((BH, BW, 3), np.uint8)
    _skyline(far, 0, BW, 800, 120, 300, (52, 30, 26), (150, 120, 90),
             0.14, 11, (3, 4))
    img = np.maximum(img, far.astype(np.float32) * 0.95)

    # atmospheric haze band
    haze = np.zeros((BH, BW, 3), np.float32)
    haze[680:900] = np.array([70, 40, 60], np.float32)
    haze = cv2.GaussianBlur(haze, (0, 0), 40)
    img = img + haze

    # mid skyline
    mid_l = np.zeros((BH, BW, 3), np.uint8)
    _skyline(mid_l, 0, BW, 905, 180, 470, (30, 17, 16), (140, 170, 205),
             0.30, 23, (5, 7))
    img = np.maximum(img, mid_l.astype(np.float32))

    # near skyline (silhouette, big)
    near = np.zeros((BH, BW, 3), np.uint8)
    _skyline(near, 0, BW, 960, 260, 620, (16, 9, 10), (110, 190, 255),
             0.22, 41, (7, 9))
    img = np.maximum(img, near.astype(np.float32))

    # neon signs on near layer
    rng = random.Random(99)
    signs = np.zeros((BH, BW, 3), np.float32)
    for _ in range(26):
        x = rng.randint(0, BW - 60)
        y = rng.randint(560, 880)
        w = rng.randint(6, 16)
        h = rng.randint(60, 190)
        col = rng.choice([(255, 190, 60), (200, 60, 255), (90, 220, 255),
                          (80, 90, 255)])
        signs[y:y + h, x:x + w] = col
    signs = cv2.GaussianBlur(signs, (0, 0), 7)
    img = img + signs * 0.48

    # global haze lift
    img = cv2.GaussianBlur(img, (0, 0), 1.1)
    return np.clip(img, 0, 255).astype(np.uint8)


BACKDROP = None


def get_backdrop():
    global BACKDROP
    if BACKDROP is None:
        BACKDROP = build_backdrop()
        BACKDROP.setflags(write=False)
    return BACKDROP


# ----------------------------------------------------------------------------
# CAMERA
# ----------------------------------------------------------------------------
class Cam:
    def __init__(self):
        self.x = 960.0
        self.y = 470.0
        self.z = 1.0
        self.sx = 0.0
        self.sy = 0.0

    def apply(self, x, y):
        return ((x - self.x) * self.z + W * 0.5 + self.sx,
                (y - self.y) * self.z + H * 0.5 + self.sy)

    def rapply(self, x, y):  # reflected in wet floor
        return self.apply(x, 2 * GROUND - y)


# shakes: (time, amplitude, duration)
SHAKES = [(5.55, 9, 1.2), (6.15, 7, 0.5), (7.42, 26, 0.7), (9.72, 16, 0.35),
          (10.30, 16, 0.35), (11.50, 12, 0.3), (12.10, 13, 0.3), (12.90, 16, 0.35),
          (14.02, 22, 0.55), (16.45, 34, 0.9), (17.05, 14, 0.4), (19.00, 12, 0.6)]


def shake_at(t):
    dx = dy = 0.0
    for t0, amp, dur in SHAKES:
        if t0 <= t <= t0 + dur:
            k = (1 - (t - t0) / dur) ** 2
            dx += math.sin((t - t0) * 61.0) * amp * k
            dy += math.cos((t - t0) * 47.0) * amp * k * 0.8
    return dx, dy


def camera_for(t, hero_x):
    c = Cam()
    # (time, focus_x, zoom, ground screen fraction)
    keys = [
        (0.0,  960, 0.92, 0.82),
        (2.2,  900, 0.96, 0.84),
        (3.4,  hp_x(3.4) + 80, 1.06, 0.90),
        (4.8,  hp_x(4.8) + 50, 1.02, 0.90),
        (6.2,  950, 0.98, 0.86),
        (7.6, 1030, 0.96, 0.86),
        (9.4,  990, 1.04, 0.90),
        (9.80, 1000, 1.12, 0.92),
        (10.4,  990, 1.10, 0.92),
        (11.3, 1000, 1.06, 0.90),
        (13.4, 1090, 1.06, 0.90),
        (14.1, 1010, 1.05, 0.90),
        (15.3,  880, 1.06, 0.90),
        (16.3,  930, 1.10, 0.92),
        (16.5, 1120, 1.20, 0.94),
        (17.2, 1140, 1.12, 0.92),
        (18.2, 1010, 0.98, 0.88),
        (19.0,  960, 0.94, 0.84),
        (20.0,  960, 0.96, 0.86),
    ]
    for i in range(len(keys) - 1):
        t0, x0, z0, g0 = keys[i]
        t1, x1, z1, g1 = keys[i + 1]
        if t0 <= t <= t1:
            k = ease_io((t - t0) / max(1e-6, t1 - t0))
            c.x = lerp(x0, x1, k)
            c.z = lerp(z0, z1, k)
            gy = lerp(g0, g1, k)
            break
    else:
        _, c.x, c.z, gy = keys[-1]
    # solve camera Y so GROUND lands on the requested screen height
    c.y = GROUND - ((gy * H) - H * 0.5) / max(0.2, c.z)
    # handheld drift
    c.sx = math.sin(t * 0.9) * 3.0 + math.sin(t * 2.7) * 1.4
    c.sy = math.cos(t * 0.7) * 2.4 + math.sin(t * 3.4) * 1.1
    dx, dy = shake_at(t)
    c.sx += dx
    c.sy += dy
    return c


# ----------------------------------------------------------------------------
# FLOOR + ENVIRONMENT
# ----------------------------------------------------------------------------
RAIN = None
EMBERS = None
DEBRIS = None


def init_particles():
    global RAIN, EMBERS, DEBRIS
    rng = np.random.RandomState(3)
    RAIN = np.stack([rng.uniform(0, 3000, 520),
                     rng.uniform(-200, 1200, 520),
                     rng.uniform(0.7, 1.9, 520),
                     rng.uniform(14, 46, 520)], axis=1)
    EMBERS = np.stack([rng.uniform(0, 2200, 130),
                       rng.uniform(500, 1000, 130),
                       rng.uniform(0.15, 0.7, 130),
                       rng.uniform(1.0, 3.4, 130),
                       rng.uniform(0, 6.28, 130)], axis=1)
    DEBRIS = np.stack([rng.uniform(0, 6.28, 90),
                       rng.uniform(0.4, 1.0, 90),
                       rng.uniform(3, 11, 90),
                       rng.uniform(2, 15, 90)], axis=1)


def draw_floor(img, emis, cam, t):
    """wet neon street with perspective grid"""
    horizon = 700
    y0 = int(cam.apply(0, horizon)[1])
    y0c = max(0, min(H - 1, y0))
    if y0c < H:
        ramp = np.linspace(0.0, 1.0, H - y0c)[:, None]
        base = np.array([30, 16, 20], np.float32) * (1 - ramp) + \
               np.array([9, 6, 8], np.float32) * ramp
        reg = img[y0c:].astype(np.float32)
        # vertical soft mask: fade floor in over ~70px so no hard line
        m = np.clip(np.linspace(0.0, 1.0, H - y0c)[:, None] / 0.075 + 0.0, 0, 1)
        m = (m ** 0.7)[:, :, None]
        floor = reg * 0.16 + base[:, None, :]
        img[y0c:] = (reg * (1 - m) + floor * m).astype(np.uint8)

        # perspective grid lines converging to vanishing point
        vx, vy = cam.apply(960, horizon)
        for i in range(-16, 17):
            gx = 960 + i * 150
            p0 = cam.apply(gx * 1.9 - 960 * 0.9, GROUND + 950)
            cv2.line(emis, (int(vx), int(vy)), (int(p0[0]), int(p0[1])),
                     (26, 16, 8), 1, cv2.LINE_AA)
        # horizontal grid (depth rows)
        for j in range(1, 15):
            yy = horizon + (GROUND - horizon) * (j / 14.0) ** 2.1
            p1 = cam.apply(-400, yy)
            p2 = cam.apply(2320, yy)
            a = 0.16 + 0.5 * (j / 14.0) ** 2
            cv2.line(emis, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])),
                     tuple(int(c * a) for c in (70, 120, 190)), 1, cv2.LINE_AA)

    # wet floor vertical neon smears (reflections of signs)
    rng = np.random.RandomState(21)
    for i in range(20):
        wx = rng.uniform(-300, 2200)
        p = cam.apply(wx, GROUND)
        hh = rng.uniform(40, 150) * cam.z
        ww = rng.uniform(3, 10)
        a = 0.06 + 0.11 * (0.5 + 0.5 * math.sin(t * 1.6 + i))
        col = [(255, 180, 60), (200, 60, 255), (90, 220, 255)][i % 3]
        cv2.rectangle(emis, (int(p[0]), int(p[1])),
                      (int(p[0] + ww), int(p[1] + hh)),
                      tuple(int(c * a) for c in col), -1)

    # centre runway glow (quarter-res for speed)
    p = cam.apply(960, GROUND)
    sw, sh = W // 4, H // 4
    band = np.zeros((sh, sw), np.float32)
    cv2.ellipse(band, (int(p[0] / 4), int(p[1] / 4)),
                (max(2, int(760 * cam.z / 4)), max(2, int(95 * cam.z / 4))),
                0, 0, 360, 1.0, -1)
    band = cv2.GaussianBlur(band, (0, 0), 11)
    band = cv2.resize(band, (W, H), interpolation=cv2.INTER_LINEAR)
    add = np.clip(band[:, :, None] * np.array([10, 16, 22], np.float32),
                  0, 255).astype(np.uint8)
    cv2.add(emis, add, emis)


def draw_rain(emis, cam, t):
    for (rx, ry, sp, ln) in RAIN:
        yy = (ry + t * 1250 * sp) % 1400 - 220
        xx = (rx + t * 190 * sp) % 3000 - 500
        p1 = cam.apply(xx, yy)
        p2 = cam.apply(xx - 0.16 * ln, yy + ln)
        if p1[0] < -60 or p1[0] > W + 60:
            continue
        cv2.line(emis, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])),
                 (44, 52, 60), 1, cv2.LINE_AA)


def draw_embers(emis, cam, t):
    for (ex, ey, sp, r, ph) in EMBERS:
        yy = 1010 - ((t * 55 * sp + ey) % 520)
        xx = ex + math.sin(t * 1.7 + ph) * 26
        p = cam.apply(xx, yy)
        a = 0.35 + 0.3 * math.sin(t * 4 + ph)
        col = tuple(int(c * a) for c in (70, 150, 255))
        cv2.circle(emis, (int(p[0]), int(p[1])), max(1, int(r)), col, -1,
                   cv2.LINE_AA)


# ----------------------------------------------------------------------------
# FIGURE / SKELETON RENDERER
# ----------------------------------------------------------------------------
PROP = dict(head=0.34, neck=0.18, torso=1.00, uarm=0.48, farm=0.44,
            thigh=0.66, shin=0.62, foot=0.22, shoulder=0.28, hip=0.17)

POSES = {
    "idle":     dict(lean=4, head=-3, shL=17, elL=26, shR=-15, elR=30,
                     hipL=5, knL=3, hipR=-5, knR=3, py=0, rot=0, cape=25),
    "guard":    dict(lean=10, head=-6, shL=52, elL=-78, shR=-40, elR=-86,
                     hipL=14, knL=-18, hipR=-12, knR=-14, py=2, rot=0, cape=40),
    "walk_a":    dict(lean=6, head=-2, shL=36, elL=-26, shR=-34, elR=-22,
                     hipL=30, knL=-14, hipR=-28, knR=-8, py=0, rot=0, cape=34),
    "walk_b":    dict(lean=6, head=-2, shL=-32, elL=-24, shR=34, elR=-28,
                     hipL=-27, knL=-10, hipR=29, knR=-14, py=0, rot=0, cape=30),
    "charge":   dict(lean=26, head=-18, shL=32, elL=-96, shR=26, elR=-100,
                     hipL=44, knL=-88, hipR=-30, knR=-70, py=14, rot=0, cape=60),
    "dash":     dict(lean=34, head=-24, shL=-42, elL=-16, shR=-58, elR=-10,
                     hipL=58, knL=-44, hipR=-46, knR=-54, py=4, rot=0, cape=78),
    "punch_r":  dict(lean=14, head=-8, shL=-52, elL=-22, shR=96, elR=-4,
                     hipL=26, knL=-16, hipR=-22, knR=-10, py=2, rot=0, cape=50),
    "punch_l":  dict(lean=14, head=-8, shL=98, elL=-4, shR=-50, elR=-24,
                     hipL=-24, knL=-12, hipR=28, knR=-18, py=2, rot=0, cape=50),
    "kick":     dict(lean=-6, head=6, shL=-70, elL=-30, shR=60, elR=-40,
                     hipL=92, knL=-6, hipR=-16, knR=-8, py=0, rot=0, cape=44),
    "hit":      dict(lean=-26, head=24, shL=-86, elL=-38, shR=-64, elR=-44,
                     hipL=-22, knL=-24, hipR=18, knR=-30, py=0, rot=0, cape=20),
    "air":      dict(lean=-14, head=10, shL=-108, elL=-30, shR=-92, elR=-36,
                     hipL=-46, knL=-30, hipR=34, knR=-64, py=0, rot=0, cape=18),
    "down":     dict(lean=-8, head=16, shL=-120, elL=-20, shR=-104, elR=-26,
                     hipL=-30, knL=-16, hipR=-6, knR=-22, py=0, rot=-78, cape=6),
    "victory":  dict(lean=-8, head=-14, shL=158, elL=16, shR=150, elR=22,
                     hipL=14, knL=-6, hipR=-14, knR=-6, py=-4, rot=0, cape=54),
    "victory2": dict(lean=-10, head=-16, shL=166, elL=26, shR=142, elR=18,
                     hipL=16, knL=-8, hipR=-16, knR=-8, py=-6, rot=0, cape=60),
    "land":     dict(lean=30, head=-14, shL=44, elL=-70, shR=-44, elR=-72,
                     hipL=54, knL=-104, hipR=-46, knR=-96, py=22, rot=0, cape=70),
    "taunt":    dict(lean=-6, head=8, shL=24, elL=-118, shR=-30, elR=-24,
                     hipL=10, knL=-6, hipR=-12, knR=-6, py=-2, rot=0, cape=30),
    "block":    dict(lean=8, head=-2, shL=68, elL=-92, shR=64, elR=-96,
                     hipL=18, knL=-26, hipR=-16, knR=-22, py=4, rot=0, cape=44),
}


def blend_pose(a, b, k):
    out = {}
    for key in a:
        out[key] = lerp(a[key], b[key], k)
    return out


def bone_dirs(pose, facing):
    """FK -> world-ish local joint dict (units), pelvis at origin."""
    p = pose
    lean = math.radians(p["lean"])
    def d(deg):
        a = math.radians(deg)
        return np.array([math.sin(a) * facing, math.cos(a)], np.float32)
    # spine: lean degrees away from vertical, tilted toward facing dir
    lean_a = math.radians(p["lean"])
    up = np.array([math.sin(lean_a) * facing, -math.cos(lean_a)], np.float32)

    pelvis = np.array([0.0, p["py"]], np.float32)
    chest = pelvis + up * PROP["torso"]
    neck = chest + up * PROP["neck"]
    headc = neck + up * (PROP["head"] + 0.12)

    sh_l = chest + up * 0.12 + np.array([-0.11 * facing, 0.0], np.float32)
    sh_r = chest + up * 0.12 + np.array([0.11 * facing, 0.0], np.float32)
    el_l = sh_l + d(p["shL"]) * PROP["uarm"]
    ha_l = el_l + d(p["shL"] + p["elL"]) * PROP["farm"]
    el_r = sh_r + d(p["shR"]) * PROP["uarm"]
    ha_r = el_r + d(p["shR"] + p["elR"]) * PROP["farm"]

    hp_l = pelvis + np.array([-0.19 * facing, 0.0], np.float32)
    hp_r = pelvis + np.array([0.19 * facing, 0.0], np.float32)
    kn_l = hp_l + d(p["hipL"]) * PROP["thigh"]
    an_l = kn_l + d(p["hipL"] + p["knL"]) * PROP["shin"]
    kn_r = hp_r + d(p["hipR"]) * PROP["thigh"]
    an_r = kn_r + d(p["hipR"] + p["knR"]) * PROP["shin"]
    ft_l = an_l + d(p["hipL"] + p["knL"] + 90 * facing) * 0 + \
        np.array([0.22 * facing, 0.02], np.float32)
    ft_r = an_r + np.array([0.22 * facing, 0.02], np.float32)

    joints = dict(pelvis=pelvis, chest=chest, neck=neck, head=headc,
                  shL=sh_l, shR=sh_r, elL=el_l, haL=ha_l, elR=el_r, haR=ha_r,
                  hpL=hp_l, hpR=hp_r, knL=kn_l, anL=an_l, knR=kn_r, anR=an_r,
                  ftL=ft_l, ftR=ft_r, head_r=PROP["head"])
    if abs(p.get("rot", 0)) > 0.1:
        ang = math.radians(p["rot"])
        ca, sa = math.cos(ang), math.sin(ang)
        piv = joints["pelvis"]
        for k, v in list(joints.items()):
            if k in ("head_r",):
                continue
            rel = v - piv
            joints[k] = piv + np.array([rel[0] * ca - rel[1] * sa,
                                        rel[0] * sa + rel[1] * ca], np.float32)
    return joints


def cape_chain(pose, joints, facing, t, phase):
    """centre-line of the cape, hanging from the shoulders, flowing back"""
    n = 10
    top = joints["chest"] + np.array([-0.16 * facing, -0.10], np.float32)
    length = 0.95 + pose.get("cape", 30) / 130.0
    flow = clamp(pose.get("cape", 30) / 100.0, 0.05, 1.0)
    pts = []
    for i in range(n + 1):
        k = i / n
        # blend from straight-down to swept-back as we go down the cloth
        back = (0.30 + 0.95 * flow) * k ** 1.35
        sway = math.sin(t * 3.0 + phase + k * 2.2) * 0.10 * (0.25 + k)
        x = top[0] - facing * (back * length + sway)
        y = top[1] + length * k * 0.92
        pts.append(np.array([x, y], np.float32))
    return pts


def contact_shadow(target, cam, x, ground_y, scale, strength=1.0):
    """soft ambient-occlusion pool under a character"""
    if strength <= 0.02:
        return
    p = cam.apply(x, ground_y + 2)
    w = int(scale * 0.60 * cam.z)
    h = max(4, int(scale * 0.12 * cam.z))
    if w < 3:
        return
    ov = np.zeros((H, W), np.float32)
    cv2.ellipse(ov, (int(p[0]), int(p[1])), (w, h), 0, 0, 360, 1.0, -1)
    ov = cv2.GaussianBlur(ov, (0, 0), max(2, h * 0.7))[:, :, None]
    target[:] = (target.astype(np.float32) *
                 (1.0 - ov * (0.7 * strength))).astype(np.uint8)


def draw_figure(scene, emis, cam, x, y, scale, pose, facing, t, theme,
                alpha=1.0, energy=0.0, phase=0.0, reflection=True,
                body_only=False, ghost=False, sx=1.0, sy=1.0, tint=None):
    """draw articulated stick figure. (x,y) = ground point under pelvis."""
    if alpha <= 0.02:
        return
    J = bone_dirs(pose, facing)
    base = np.array([x, y], np.float32)

    # ---- snap rig so the lowest foot always sits on the ground plane ----
    foot_y = max(J["anL"][1], J["anR"][1], J["ftL"][1], J["ftR"][1])
    for _k in list(J.keys()):
        if _k == "head_r":
            continue
        J[_k] = J[_k] - np.array([0.0, foot_y], np.float32)

    def P(v, refl=False, extra=(0, 0)):
        wx = base[0] + v[0] * scale * sx + extra[0]
        wy = base[1] + v[1] * scale * sy + extra[1]
        sp = cam.apply(wx, wy)
        if refl:
            sp = cam.apply(wx, 2 * GROUND - wy)
        return (int(sp[0]), int(sp[1]))

    th = max(2, int(scale * 0.085))
    if ghost:
        th = max(2, int(th * 0.85))
    theme = np.array(tint if tint is not None else theme, np.float32)
    body = np.clip(theme * (0.55 if ghost else 1.0), 0, 255)
    dark = np.clip(DEEP * alpha, 0, 255)

    # ---- cape: tapered cloth ribbon with two-sided geometry ----
    if not body_only:
        cp = cape_chain(pose, J, facing, t, phase)
        left, right = [], []
        for i, v in enumerate(cp):
            k = i / (len(cp) - 1)
            half = 0.055 + 0.16 * k                    # joint units
            if i < len(cp) - 1:
                dvec = cp[i + 1] - v
                ln = max(1e-4, float(np.hypot(*dvec)))
                nrm = np.array([-dvec[1], dvec[0]], np.float32) / ln
            else:
                nrm = np.array([0.0, 1.0], np.float32)
            left.append(v + nrm * half)
            right.append(v - nrm * half)
        poly = np.array([P(p) for p in left] + [P(p) for p in right][::-1],
                        np.int32)
        # reflective copy in the wet floor
        pr = np.array([cam.apply(base[0] + p[0] * 1.0,
                                 2 * GROUND - (base[1] + p[1]))
                       for p in (left + right[::-1])], np.int32)
        cv2.fillPoly(scene, [pr], tuple(int(c * alpha * 0.16) for c in theme),
                     cv2.LINE_AA)
        cv2.fillPoly(scene, [poly], tuple(int(c * alpha * 0.55) for c in theme),
                     cv2.LINE_AA)
        # rim light along both edges + glow layer
        layer = np.zeros_like(scene)
        cv2.polylines(layer, [poly], True,
                      tuple(int(c * alpha * 0.55) for c in theme), 2,
                      cv2.LINE_AA)
        layer = cv2.GaussianBlur(layer, (0, 0), 5)
        cv2.add(emis, layer, emis)
        cv2.polylines(scene, [np.array([P(p) for p in left], np.int32)],
                      False, tuple(int(c * alpha * 0.9) for c in theme),
                      max(1, th // 3), cv2.LINE_AA)
        cv2.polylines(scene, [np.array([P(p) for p in right], np.int32)],
                      False, tuple(int(c * alpha * 0.75) for c in theme),
                      max(1, th // 3), cv2.LINE_AA)

    bones = [("chest", "neck"), ("neck", "pelvis"), ("pelvis", "chest"),
             ("shL", "elL"), ("elL", "haL"), ("shR", "elR"), ("elR", "haR"),
             ("hpL", "knL"), ("knL", "anL"), ("hpR", "knR"), ("knR", "anR"),
             ("pelvis", "hpL"), ("pelvis", "hpR"), ("chest", "shL"),
             ("chest", "shR"), ("anL", "ftL"), ("anR", "ftR")]

    for refl in ([False, True] if reflection else [False]):
        rf = refl
        a2 = alpha * (0.30 if refl else 1.0)
        for (a, b) in bones:
            p1, p2 = P(J[a], rf), P(J[b], rf)
            if not refl:
                cv2.line(scene, p1, p2, tuple(int(c * a2) for c in DEEP),
                         int(th * 2.0) + 3, cv2.LINE_AA)
                cv2.line(scene, p1, p2, tuple(int(c * a2) for c in body),
                         th, cv2.LINE_AA)
            if not body_only:
                cv2.line(emis, p1, p2,
                         tuple(int(c * a2 * 0.40) for c in body),
                         int(th * 2.2), cv2.LINE_AA)
        # joint nodes
        jr = max(2, int(th * 0.72))
        for jk in ("chest", "pelvis", "elL", "elR", "knL", "knR",
                   "shL", "shR", "hpL", "hpR", "anL", "anR", "haL", "haR"):
            jp = P(J[jk], rf)
            if refl:
                cv2.circle(scene, jp, max(1, int(jr * 0.7)),
                           tuple(int(c * a2 * 0.6) for c in body), -1,
                           cv2.LINE_AA)
            else:
                cv2.circle(scene, jp, jr + 2,
                           tuple(int(c * a2) for c in DEEP), -1, cv2.LINE_AA)
                cv2.circle(scene, jp, jr, tuple(int(c * a2) for c in body),
                           -1, cv2.LINE_AA)
                cv2.circle(emis, jp, int(jr * 1.5),
                           tuple(int(c * a2 * 0.22) for c in body), -1,
                           cv2.LINE_AA)
        # head
        hc = P(J["head"], rf)
        hr = int(J["head_r"] * scale)
        if refl:
            cv2.circle(scene, hc, max(2, int(hr * 0.8)),
                       tuple(int(c * a2 * 0.7) for c in body), -1, cv2.LINE_AA)
        else:
            cv2.circle(scene, hc, hr, tuple(int(c * a2) for c in DEEP), -1,
                       cv2.LINE_AA)
            cv2.circle(scene, hc, hr, tuple(int(c * a2) for c in body),
                       max(2, th // 2), cv2.LINE_AA)
            # visor
            v1 = P(J["head"] + np.array([0.10 * facing, -0.02])) if not rf else None
            # draw visor directly from world offsets
            hw = base[0] + (J["head"][0] + 0.10 * facing) * scale
            hy = base[1] + (J["head"][1] - 0.02) * scale
            e1 = cam.apply(hw - 0.20 * scale, hy)
            e2 = cam.apply(hw + 0.12 * scale, hy)
            gcol = tuple(int(c * alpha) for c in
                         (np.array([255, 255, 255]) * 0.45 + theme * 0.55))
            cv2.line(emis, (int(e1[0]), int(e1[1])), (int(e2[0]), int(e2[1])),
                     gcol, max(2, int(4 * 1.5)), cv2.LINE_AA)
            cv2.line(scene, (int(e1[0]), int(e1[1])), (int(e2[0]), int(e2[1])),
                     tuple(int(c * a2) for c in gcol), 2, cv2.LINE_AA)
            # energy core
            if energy > 0.02:
                cc = P(J["chest"])
                r = int(scale * 0.10 * (1 + 0.25 * math.sin(t * 9 + phase)))
                cv2.circle(emis, cc, max(2, r), tuple(int(c * alpha * 0.9)
                                                     for c in theme), -1,
                           cv2.LINE_AA)
                cv2.circle(emis, cc, max(3, int(r * 2.4)),
                           tuple(int(c * alpha * 0.35 * energy) for c in theme),
                           2, cv2.LINE_AA)

    if ghost:
        return

    # aura spikes
    if energy > 0.05:
        p0 = P(J["pelvis"])
        rng = random.Random(int(phase * 1000) + int(t * 20)) 
        for i in range(int(6 + 9 * energy)):
            ang = rng.uniform(-math.pi, math.pi)
            ln = scale * rng.uniform(0.35, 1.25) * energy
            ox, oy = math.cos(ang) * scale * 0.35, math.sin(ang) * scale * 0.55
            sx, sy = p0[0] + ox, p0[1] + oy
            ex, ey = sx + math.cos(ang) * ln, sy + math.sin(ang) * ln
            a = rng.uniform(0.18, 0.5) * energy * alpha
            cv2.line(emis, (int(sx), int(sy)), (int(ex), int(ey)),
                     tuple(int(c * a) for c in theme), 2, cv2.LINE_AA)


# ----------------------------------------------------------------------------
# CHARACTER TIMELINES (world coords, ground point)
# ----------------------------------------------------------------------------
def sample_track(track, t):
    """track: list of (time, dict). Returns interpolated pose/pos/state dict."""
    if t <= track[0][0]:
        return dict(track[0][1])
    if t >= track[-1][0]:
        return dict(track[-1][1])
    for i in range(len(track) - 1):
        t0, a = track[i]
        t1, b = track[i + 1]
        if t0 <= t <= t1:
            k = (t - t0) / max(1e-6, t1 - t0)
            e = b.get("ease", "io")
            k = ease_io(k) if e == "io" else (ease_out(k) if e == "out"
                                              else (ease_in(k) if e == "in" else k))
            out = {}
            for key in a:
                va, vb = a[key], b.get(key, a[key])
                if isinstance(va, (int, float)) and not isinstance(va, bool):
                    out[key] = lerp(va, vb, k)
                elif isinstance(va, str):
                    out[key] = vb if k > 0.5 else va
                else:
                    out[key] = vb if k > 0.5 else va
            return out
    return dict(track[-1][1])


def build_hero_track():
    P = POSES
    def st(pose, x, y=GROUND, facing=1, ease="io", energy=0.0, scale=1.0):
        d = dict(pose=P[pose], x=x, y=y, facing=facing, ease=ease,
                 energy=energy, scale=scale)
        return d
    tr = [
        (0.0, st("idle", 170, GROUND, 1, "io", 0.0)),
        (2.30, st("idle", 170, GROUND, 1, "io", 0.0)),
        (2.55, st("walk_a", 230, GROUND, 1, "io", 0.0)),
        (2.85, st("walk_b", 300, GROUND, 1, "io", 0.0)),
        (3.15, st("walk_a", 380, GROUND, 1, "io", 0.0)),
        (3.45, st("walk_b", 460, GROUND, 1, "io", 0.0)),
        (3.75, st("walk_a", 540, GROUND, 1, "io", 0.0)),
        (4.05, st("walk_b", 600, GROUND, 1, "io", 0.05)),
        (4.35, st("idle", 640, GROUND, 1, "out", 0.1)),
        (4.75, st("idle", 640, GROUND, 1, "io", 0.15)),
        (5.05, st("charge", 640, GROUND, 1, "io", 0.35)),
        (5.55, st("charge", 640, GROUND, 1, "io", 0.95)),
        (5.85, st("guard", 640, GROUND, 1, "out", 0.75)),
        (6.25, st("guard", 640, GROUND, 1, "io", 0.45)),
        (6.60, st("idle", 660, GROUND, 1, "io", 0.30)),
        (7.40, st("idle", 690, GROUND, 1, "io", 0.28)),
        (7.95, st("guard", 730, GROUND, 1, "io", 0.35)),
        (8.70, st("guard", 760, GROUND, 1, "io", 0.30)),
        (9.45, st("guard", 770, GROUND, 1, "io", 0.40)),
        (9.58, st("charge", 780, GROUND, 1, "in", 0.55)),
        (9.72, st("dash", 940, GROUND, 1, "out", 0.80)),
        (9.80, st("punch_r", 985, GROUND, 1, "out", 0.75)),
        (10.05, st("punch_r", 1000, GROUND, 1, "io", 0.55)),
        (10.18, st("guard", 960, GROUND, 1, "out", 0.5)),
        (10.32, st("dash", 1000, GROUND, 1, "out", 0.85)),
        (10.42, st("punch_l", 1040, GROUND, 1, "out", 0.8)),
        (10.60, st("punch_l", 1050, GROUND, 1, "io", 0.6)),
        (10.72, st("air", 1030, GROUND - 40, 1, "out", 0.5)),
        (10.95, st("air", 950, GROUND - 120, 1, "io", 0.4)),
        (11.15, st("land", 880, GROUND, 1, "in", 0.55)),
        (11.32, st("punch_r", 940, GROUND, 1, "out", 0.7)),
        (11.50, st("punch_r", 965, GROUND, 1, "io", 0.75)),
        (11.75, st("guard", 985, GROUND, 1, "io", 0.55)),
        (11.95, st("dash", 1040, GROUND, 1, "out", 0.7)),
        (12.10, st("punch_l", 1085, GROUND, 1, "out", 0.7)),
        (12.30, st("punch_l", 1100, GROUND, 1, "io", 0.6)),
        (12.55, st("kick", 1130, GROUND, 1, "out", 0.7)),
        (12.90, st("kick", 1165, GROUND, 1, "io", 0.85)),
        (13.05, st("guard", 1140, GROUND, 1, "io", 0.55)),
        (13.40, st("guard", 1130, GROUND, 1, "io", 0.5)),
        (13.75, st("guard", 1128, GROUND, 1, "io", 0.4)),
        (13.92, st("hit", 1100, GROUND, 1, "out", 0.3)),
        (14.10, st("air", 1030, GROUND - 90, 1, "out", 0.2)),
        (14.55, st("air", 900, GROUND - 150, 1, "io", 0.1)),
        (15.05, st("down", 780, GROUND - 30, 1, "in", 0.05)),
        (15.22, st("land", 780, GROUND, 1, "out", 0.35)),
        (15.45, st("charge", 780, GROUND, 1, "io", 0.7)),
        (15.95, st("charge", 790, GROUND, 1, "io", 1.0)),
        (16.15, st("dash", 940, GROUND, 1, "in", 1.0)),
        (16.35, st("dash", 1090, GROUND, 1, "out", 1.0)),
        (16.45, st("punch_r", 1145, GROUND, 1, "out", 0.95)),
        (16.90, st("punch_r", 1150, GROUND, 1, "io", 0.6)),
        (17.10, st("guard", 1120, GROUND, 1, "io", 0.4)),
        (17.45, st("victory", 1040, GROUND, 1, "io", 0.5)),
        (18.10, st("victory2", 1040, GROUND, 1, "io", 0.75)),
        (18.80, st("victory", 1040, GROUND, 1, "io", 0.45)),
        (19.30, st("victory", 1040, GROUND, 1, "io", 0.3)),
        (20.0, st("victory", 1040, GROUND, 1, "io", 0.25)),
    ]
    return tr


def build_villain_track():
    P = POSES
    def st(pose, x, y=GROUND, facing=-1, ease="io", energy=0.0):
        return dict(pose=P[pose], x=x, y=y, facing=facing, ease=ease,
                    energy=energy, scale=1.05)
    tr = [
        (0.0, st("idle", 1400, -600, -1, "io", 0.0)),
        (6.05, st("idle", 1400, -560, -1, "io", 0.25)),
        (6.30, st("air", 1380, -300, -1, "in", 0.5)),
        (7.20, st("air", 1340, 40, -1, "in", 0.7)),
        (7.38, st("land", 1340, GROUND, -1, "out", 0.95)),
        (7.70, st("land", 1340, GROUND, -1, "io", 0.6)),
        (8.05, st("taunt", 1330, GROUND, -1, "io", 0.5)),
        (8.80, st("taunt", 1300, GROUND, -1, "io", 0.45)),
        (9.45, st("guard", 1240, GROUND, -1, "io", 0.5)),
        (9.58, st("charge", 1230, GROUND, -1, "in", 0.6)),
        (9.72, st("dash", 1060, GROUND, -1, "out", 0.9)),
        (9.80, st("punch_l", 1015, GROUND, -1, "out", 0.85)),
        (10.05, st("punch_l", 1000, GROUND, -1, "io", 0.65)),
        (10.18, st("guard", 1040, GROUND, -1, "out", 0.6)),
        (10.32, st("dash", 1000, GROUND, -1, "out", 0.9)),
        (10.42, st("punch_r", 960, GROUND, -1, "out", 0.85)),
        (10.62, st("punch_r", 950, GROUND, -1, "io", 0.65)),
        (10.90, st("guard", 1010, GROUND, -1, "io", 0.6)),
        (11.20, st("guard", 1060, GROUND, -1, "io", 0.55)),
        (11.36, st("hit", 1100, GROUND, -1, "out", 0.3)),
        (11.58, st("block", 1150, GROUND, -1, "out", 0.4)),
        (11.75, st("guard", 1170, GROUND, -1, "io", 0.5)),
        (11.95, st("guard", 1190, GROUND, -1, "io", 0.5)),
        (12.12, st("hit", 1230, GROUND, -1, "out", 0.3)),
        (12.35, st("guard", 1260, GROUND, -1, "io", 0.45)),
        (12.55, st("block", 1290, GROUND, -1, "out", 0.45)),
        (12.92, st("hit", 1330, GROUND, -1, "out", 0.25)),
        (13.15, st("guard", 1360, GROUND, -1, "io", 0.5)),
        (13.55, st("charge", 1340, GROUND, -1, "io", 0.7)),
        (13.75, st("charge", 1330, GROUND, -1, "io", 0.9)),
        (13.95, st("dash", 1240, GROUND, -1, "out", 0.95)),
        (14.08, st("punch_r", 1180, GROUND, -1, "out", 0.95)),
        (14.45, st("punch_r", 1175, GROUND, -1, "io", 0.7)),
        (14.75, st("taunt", 1200, GROUND, -1, "io", 0.5)),
        (15.40, st("taunt", 1220, GROUND, -1, "io", 0.45)),
        (15.80, st("charge", 1240, GROUND, -1, "io", 0.8)),
        (16.10, st("charge", 1250, GROUND, -1, "io", 1.0)),
        (16.30, st("guard", 1255, GROUND, -1, "io", 0.95)),
        (16.45, st("hit", 1300, GROUND, -1, "out", 0.2)),
        (16.70, st("air", 1420, GROUND - 120, -1, "out", 0.0)),
        (17.15, st("air", 1600, GROUND - 170, -1, "io", 0.0)),
        (17.55, st("down", 1700, GROUND, -1, "in", 0.0)),
        (18.20, st("down", 1702, GROUND, -1, "io", 0.0)),
        (20.0, st("down", 1705, GROUND, -1, "io", 0.0)),
    ]
    return tr


HERO_TRACK = build_hero_track()
VILLAIN_TRACK = build_villain_track()


def hp_x(t):
    return sample_track(HERO_TRACK, t)["x"]


# ----------------------------------------------------------------------------
# IMPACTS / FX
# ----------------------------------------------------------------------------
IMPACTS = [
    (5.55, 640, GROUND - 210, 0.7, CYAN, "charge"),
    (6.15, 640, GROUND - 240, 1.2, CYAN, "burst"),
    (7.42, 1340, GROUND, 1.6, MAGENTA, "land"),
    (9.80, 1000, GROUND - 250, 1.3, WHITE, "clash"),
    (10.42, 1000, GROUND - 255, 1.2, WHITE, "clash"),
    (10.95, 900, GROUND - 120, 0.5, CYAN, "dust"),
    (11.50, 1060, GROUND - 260, 0.9, GOLD, "hit"),
    (12.10, 1185, GROUND - 250, 0.95, GOLD, "hit"),
    (12.90, 1260, GROUND - 190, 1.15, GOLD, "hit"),
    (14.08, 1090, GROUND - 265, 1.25, MAGENTA, "hit"),
    (15.05, 800, GROUND, 0.8, CYAN, "dust"),
    (16.45, 1215, GROUND - 255, 2.1, WHITE, "finish"),
    (19.00, 1040, GROUND - 200, 0.8, CYAN, "logo"),
]


def add_glow(target, center, radius, color, strength=1.0):
    """cheap soft radial light added to a BGR float/uint8 image"""
    cxp, cyp = int(center[0]), int(center[1])
    r = int(max(6, radius))
    if cxp + r < 0 or cxp - r > W or cyp + r < 0 or cyp - r > H:
        return
    q = 4
    g = np.zeros((H // q, W // q), np.float32)
    cv2.circle(g, (cxp // q, cyp // q), max(2, r // q), 1.0, -1)
    g = cv2.GaussianBlur(g, (0, 0), max(2.0, r / q / 2.2))
    g = cv2.resize(g, (W, H), interpolation=cv2.INTER_LINEAR)
    add = np.clip(g[:, :, None] * (np.array(color, np.float32) * strength),
                  0, 255).astype(np.uint8)
    cv2.add(target, add, target)


def draw_impacts(emis, scene, cam, t):
    for (t0, ix, iy, power, col, kind) in IMPACTS:
        if t < t0:
            continue
        dt = t - t0
        # flash
        f = flash(t, t0, 0.16 + 0.10 * power)
        GK = dict(finish=0.52, clash=0.68, burst=0.45, hit=0.34, land=0.20,
                  dust=0.08, charge=0.28, logo=0.20)
        gk = GK.get(kind, 0.4)
        if f > 0.01 and gk > 0.05:
            add_glow(emis, cam.apply(ix, iy), 170 * power * cam.z * (1 + dt * 4),
                     col, gk * f)
        # expanding rings
        for k in range(3):
            rt = dt - k * 0.09
            if rt <= 0:
                continue
            rr = (rt * 620 + 40) * power
            a = max(0.0, (1 - rt / (0.55 + 0.25 * power))) * 0.9
            if a <= 0:
                continue
            p = cam.apply(ix, iy)
            cv2.ellipse(emis, (int(p[0]), int(p[1])),
                        (int(rr * cam.z), int(rr * cam.z * 0.55)),
                        0, 0, 360, tuple(int(c * a) for c in col),
                        max(1, int(4 * cam.z * a + 1)), cv2.LINE_AA)
        # ground shockwave
        if kind in ("land", "finish", "burst", "hit") and dt < 1.1:
            for k in range(2):
                rt = dt - k * 0.12
                if rt <= 0:
                    continue
                rr = rt * 900 * power
                a = max(0.0, 1 - rt / 0.9) * 0.85
                p = cam.apply(ix, GROUND)
                cv2.ellipse(emis, (int(p[0]), int(p[1])),
                            (int(rr * cam.z), int(rr * cam.z * 0.26)),
                            0, 0, 360, tuple(int(c * a * 0.8) for c in col),
                            max(1, int(5 * a + 1)), cv2.LINE_AA)
        # radial speed burst
        if kind in ("finish", "clash", "burst") and dt < 0.35:
            p = cam.apply(ix, iy)
            rng = random.Random(int(t0 * 100))
            a = (1 - dt / 0.35) ** 2
            for i in range(int(28 + 34 * power)):
                ang = rng.uniform(0, 6.283)
                r0 = rng.uniform(20, 70) * power
                r1 = r0 + rng.uniform(120, 520) * power * (0.3 + dt * 4)
                col2 = tuple(int(c * a * 0.8) for c in
                             (WHITE if i % 3 else col))
                cv2.line(emis, (int(p[0] + math.cos(ang) * r0 * cam.z),
                                int(p[1] + math.sin(ang) * r0 * cam.z)),
                         (int(p[0] + math.cos(ang) * r1 * cam.z),
                          int(p[1] + math.sin(ang) * r1 * cam.z)),
                         col2, 2, cv2.LINE_AA)
        # sparks
        if dt < 1.4 and kind != "logo":
            rng = random.Random(int(t0 * 977) + 5)
            for i in range(int(30 + 40 * power)):
                ang = rng.uniform(-3.1, 0.1)
                sp = rng.uniform(240, 900) * power
                life = rng.uniform(0.45, 1.2)
                if dt > life:
                    continue
                vx = math.cos(ang) * sp
                vy = math.sin(ang) * sp
                px = ix + vx * dt
                py = iy + vy * dt + 900 * dt * dt
                p1 = cam.apply(px, py)
                p2 = cam.apply(px - vx * 0.018, py - vy * 0.018)
                a = (1 - dt / life)
                cv2.line(emis, (int(p1[0]), int(p1[1])),
                         (int(p2[0]), int(p2[1])),
                         tuple(int(c * a) for c in
                               (col * 0.4 + GOLD * 0.6)), 2, cv2.LINE_AA)
        # debris chunks
        if kind in ("land", "finish") and dt < 2.0:
            for i, (ph, sz, sp, up) in enumerate(DEBRIS[:40]):
                if dt > 1.9:
                    break
                ang = ph + i * 0.07
                px = ix + math.cos(ang) * sp * dt * 38
                py = iy - (up * dt * 60 - 520 * dt * dt)
                if py > GROUND + 6:
                    continue
                p = cam.apply(px, py)
                s = max(1, int(sz * 0.9 * cam.z))
                cv2.rectangle(emis, (int(p[0]), int(p[1])),
                              (int(p[0] + s), int(p[1] + s)),
                              (30, 24, 26), -1)


# ----------------------------------------------------------------------------
# POST FX
# ----------------------------------------------------------------------------
VIGNETTE = None
GRAIN = None


def build_post_assets():
    global VIGNETTE, GRAIN
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W / 2, H / 2
    r = np.sqrt(((xx - cx) / (W * 0.60)) ** 2 + ((yy - cy) / (H * 0.62)) ** 2)
    v = np.clip(1.06 - 0.55 * r ** 2.1, 0.18, 1.0).astype(np.float32)
    VIGNETTE = v[:, :, None]
    rng = np.random.RandomState(5)
    GRAIN = [(rng.normal(0, 2.0, (H, W, 1)).astype(np.float32)) for _ in range(6)]


def post_process(scene, emis, t, strength=1.0):
    # ---- bloom ----
    small = cv2.resize(emis, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
    b1 = cv2.GaussianBlur(small, (0, 0), 9.0)
    b2 = cv2.GaussianBlur(small, (0, 0), 3.0)
    bloom = cv2.resize(b1, (W, H), interpolation=cv2.INTER_LINEAR) * 1.15
    bloom += cv2.resize(b2, (W, H), interpolation=cv2.INTER_LINEAR) * 0.85
    bloom += cv2.resize(small, (W, H), interpolation=cv2.INTER_LINEAR) * 0.55

    out = scene.astype(np.float32) + bloom * (0.50 * strength)
    # soft highlight rolloff
    out = 255.0 - (255.0 - np.clip(out, 0, 255)) * 0.965

    # ---- chromatic aberration on energy moments ----
    ca = 0.0
    for (t0, _, _, power, _, kind) in IMPACTS:
        if kind in ("finish", "clash", "burst"):
            ca = max(ca, flash(t, t0, 0.22) * power)
    if ca > 0.05:
        s = int(3 + 9 * ca)
        b, g, r = cv2.split(out.astype(np.uint8))
        M = np.float32([[1, 0, s], [0, 1, 0]])
        M2 = np.float32([[1, 0, -s], [0, 1, 0]])
        r = cv2.warpAffine(r, M, (W, H))
        b = cv2.warpAffine(b, M2, (W, H))
        out = cv2.merge([b, g, r]).astype(np.float32)

    # ---- colour grade (teal shadows / warm highs) ----
    out[..., 0] *= 0.97          # B
    out[..., 1] *= 1.01          # G
    out[..., 2] *= 1.05          # R
    out = out * VIGNETTE
    out = np.clip(out, 0, 255)

    # ---- grain ----
    g = GRAIN[int(t * 30) % len(GRAIN)]
    out += g * 0.9

    # ---- flashes ----
    fl = 0.0
    FK = dict(finish=0.20, hit=0.10, clash=0.13, burst=0.08, land=0.05)
    for (t0, _, _, power, _, kind) in IMPACTS:
        if kind in FK:
            fl = max(fl, flash(t, t0, 0.09) * FK[kind] * (0.6 + 0.4 * power))
    if fl > 0.01:
        out = out + (255 - out) * fl

    return np.clip(out, 0, 255).astype(np.uint8)


# ----------------------------------------------------------------------------
# HUD / TITLES
# ----------------------------------------------------------------------------
CHAPTERS = [
    (0.0, 2.2, "NEO PROTOCOL"),
    (3.35, 6.0, "01  //  THE CITY"),
    (6.0, 9.5, "02  //  ARRIVAL"),
    (9.5, 11.2, "03  //  CLASH"),
    (11.2, 13.6, "04  //  PRESSURE"),
    (13.6, 15.4, "05  //  FALL"),
    (15.4, 17.2, "06  //  FINISH"),
    (17.2, 19.0, "07  //  MONARCH"),
    (19.0, 20.0, "MONARCHVOICE"),
]


def draw_hud(img, t, hero_x):
    a = clamp((t - 0.4) / 0.6, 0, 1) * clamp((19.4 - t) / 0.5, 0, 1)
    if a <= 0.01:
        return
    # REC
    if int(t * 2) % 2 == 0:
        cv2.circle(img, (72, 64), 7, (60, 60, 245), -1, cv2.LINE_AA)
    text(img, "REC", 90, 72, 0.62, WHITE, 1, 0.85 * a, spacing=1.6)
    text(img, "MONARCH  //  NEO", 90, 104, 0.44, (200, 200, 200), 1, 0.55 * a,
         spacing=1.2)
    # brackets
    for (bx, by, dx, dy) in [(46, 132, 1, 1), (W - 46, 132, -1, 1)]:
        pass
    # timecode top right
    tc = "%02d:%02d:%02d" % (int(t) // 60, int(t) % 60, int((t * FPS) % FPS))
    text(img, tc, W - 72, 62, 0.6, WHITE, 1, 0.7 * a, center=False, spacing=1.0)
    text(img, "1920x1080  •  30 FPS", W - 72, 92, 0.42, (190, 190, 190), 1,
         0.5 * a, spacing=1.0)

    # chapter label bottom-left
    for (t0, t1, name) in CHAPTERS:
        if t0 <= t <= t1 and t > 2.3:
            fa = clamp((t - t0) / 0.35, 0, 1) * clamp((t1 - t) / 0.3, 0, 1)
            text(img, name, 72, H - 66, 0.5, (230, 230, 230), 1, 0.75 * fa,
                 spacing=2.2)
            hline(img, 72, 72 + 210 * fa, H - 48, (150, 150, 150), 1, 0.5 * fa)
            break

    # progress bar
    pr = t / DUR
    hline(img, 72, W - 72, H - 26, (60, 60, 60), 1, 0.35 * a)
    hline(img, 72, 72 + (W - 144) * pr, H - 26, CYAN, 2, 0.75 * a)

    # corner marks
    m = 40
    for (cx, cy, sx, sy) in [(m, m, 1, 1), (W - m, m, -1, 1),
                             (m, H - m, 1, -1), (W - m, H - m, -1, -1)]:
        cv2.line(img, (cx, cy), (cx + 26 * sx, cy), (210, 210, 210), 1, cv2.LINE_AA)
        cv2.line(img, (cx, cy), (cx, cy + 26 * sy), (210, 210, 210), 1, cv2.LINE_AA)


def draw_titles(img, t):
    # ---- opening title ----
    if 0.35 < t < 3.3:
        a = clamp((t - 0.35) / 0.7, 0, 1) * clamp((3.15 - t) / 0.6, 0, 1)
        text(img, "MONARCHVOICE  STUDIOS", W // 2, H // 2 - 44, 1.05,
             (235, 235, 235), 2, a, center=True, spacing=4.5, font=FONT_B)
        hline(img, W // 2 - 250 * a, W // 2 + 250 * a, H // 2 - 6, CYAN, 2, a * 0.9)
        text(img, "P R E S E N T S", W // 2, H // 2 + 52, 0.55,
             (200, 200, 200), 1, a * 0.85, center=True, spacing=5.0)
        if 0.9 < t < 3.1:
            a2 = clamp((t - 0.9) / 0.6, 0, 1) * clamp((3.05 - t) / 0.5, 0, 1)
            text(img, "N E O   P R O T O C O L", W // 2, H // 2 + 190, 1.35,
                 CYAN, 2, a2, center=True, spacing=3.0, font=FONT_B)
            text(img, "A REAL-TIME 3D STICKMAN FILM", W // 2, H // 2 + 240, 0.45,
                 (190, 190, 190), 1, a2 * 0.8, center=True, spacing=3.0)

    # ---- clash / hit callouts ----
    for (t0, label, sub) in [(9.78, "CLASH", "PHASE 01"),
                             (16.45, "FINISH", "PHASE 02")]:
        if t0 <= t < t0 + 0.9:
            a = clamp((t - t0) / 0.08, 0, 1) * clamp((t0 + 0.9 - t) / 0.35, 0, 1)
            sc = 1.5 + (1 - a) * 0.5
            text(img, label, W // 2, 300, sc * 0.9, WHITE, 3, a, center=True,
                 spacing=6.0, font=FONT_B)
            hline(img, W // 2 - 180, W // 2 + 180, 336, CYAN, 2, a * 0.8)
            text(img, sub, W // 2, 372, 0.45, (220, 220, 220), 1, a * 0.7,
                 center=True, spacing=4.0)

    # ---- end card ----
    if t > 18.95:
        a = clamp((t - 18.95) / 0.7, 0, 1)
        ov = np.zeros((H, W, 3), np.float32)
        cv2.rectangle(ov, (0, 0), (W, H), (8, 5, 12), -1)
        # radial mask so centre stays clear
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.55)) ** 2 +
                    ((yy - H / 2) / (H * 0.62)) ** 2)
        m = np.clip((r - 0.35) * 1.1, 0, 0.88)[:, :, None] * a
        img[:] = (img.astype(np.float32) * (1 - m) + ov * m).astype(np.uint8)

        # rotating ring logo
        cx, cy = W // 2, H // 2 - 70
        for i, (rr, col, th) in enumerate([(96, CYAN, 3), (118, (120, 90, 200), 1)]):
            ang0 = (t * (110 if i == 0 else -70)) % 360
            cv2.ellipse(img, (cx, cy), (int(rr * a), int(rr * a * 0.98)),
                        ang0, 0, 300, tuple(int(c * a) for c in col),
                        th, cv2.LINE_AA)
        cv2.circle(img, (cx, cy), int(52 * a), tuple(int(c * a) for c in CYAN),
                   2, cv2.LINE_AA)
        text(img, "M", cx, cy + 26, 1.5, WHITE, 2, a, center=True, spacing=0,
             font=FONT_B)

        a2 = clamp((t - 19.25) / 0.6, 0, 1)
        text(img, "MONARCHVOICE", W // 2, cy + 210, 1.5, (240, 240, 240), 2,
             a2, center=True, spacing=7.0, font=FONT_B)
        hline(img, W // 2 - 260 * a2, W // 2 + 260 * a2, cy + 240, CYAN, 2, a2)
        a3 = clamp((t - 19.45) / 0.5, 0, 1)
        text(img, "N E O   P R O T O C O L", W // 2, cy + 290, 0.62, CYAN, 1,
             a3, center=True, spacing=4.0)
        text(img, "3D  •  FULL HD  •  ORIGINAL SCORE", W // 2, cy + 340, 0.42,
             (185, 185, 185), 1, a3 * 0.8, center=True, spacing=2.4)


# ----------------------------------------------------------------------------
# FRAME RENDER
# ----------------------------------------------------------------------------
def render_frame(fi):
    t = fi / FPS
    hp = sample_track(HERO_TRACK, t)
    vp = sample_track(VILLAIN_TRACK, t)
    cam = camera_for(t, hp["x"])

    scene = np.zeros((H, W, 3), np.uint8)
    emis = np.zeros((H, W, 3), np.uint8)

    # ---- backdrop parallax crop ----
    bd = get_backdrop()
    zoom = 1.0 + (cam.z - 1.0) * 0.45
    cw = W / zoom
    ch = H / zoom
    cx = clamp(cam.x - cam.sx * 0.6, cw / 2, BW - cw / 2)
    cy = clamp(470 + (cam.y - 470) * 0.35 + (H - ch) * 0.5, ch / 2, BH - ch / 2)
    x0 = int(clamp(cx - cw / 2, 0, BW - cw))
    y0 = int(clamp(cy - ch / 2, 0, BH - ch))
    crop = bd[y0:y0 + int(ch), x0:x0 + int(cw)]
    scene = cv2.resize(crop, (W, H), interpolation=cv2.INTER_LINEAR)

    draw_floor(scene, emis, cam, t)

    # ---- energy charge states ----
    hero_energy = hp["energy"] + 0.25 * flash(t, 5.55, 0.9) + \
        0.5 * flash(t, 6.15, 0.6) + 0.35 * flash(t, 16.45, 0.7)
    vill_energy = vp["energy"] + 0.5 * flash(t, 7.42, 0.7)

    # ---- afterimages during dashes ----
    for who, track, col, sc in [("hero", HERO_TRACK, CYAN, 1.0),
                                ("villain", VILLAIN_TRACK, MAGENTA, 1.05)]:
        st = hp if who == "hero" else vp
        dash_k = 0.0
        for t0, _, _, power, _, kind in IMPACTS:
            if kind == "clash":
                dash_k = max(dash_k, flash(t, t0 - 0.18, 0.30))
        dash_k = max(dash_k, flash(t, 16.30, 0.35), flash(t, 9.60, 0.25),
                     flash(t, 15.95, 0.30))
        if dash_k > 0.02:
            for gi in range(1, 4):
                gt = t - gi * 0.035
                gs = sample_track(track, gt)
                draw_figure(scene, emis, cam, gs["x"], gs["y"], 190 * sc,
                            gs["pose"], gs["facing"], gt, col,
                            alpha=0.22 * dash_k, energy=0.0, phase=0.3,
                            reflection=False, ghost=True)

    # ---- characters ----
    contact_shadow(scene, cam, hp["x"], GROUND, 168.0)
    contact_shadow(scene, cam, vp["x"], GROUND, 172.0,
                   0.0 if t < 6.2 else 1.0)
    draw_figure(scene, emis, cam, hp["x"], hp["y"], 168 * hp.get("scale", 1.0),
                hp["pose"], hp["facing"], t, CYAN, 1.0, hero_energy, 0.0)
    if t > 6.0:
        draw_figure(scene, emis, cam, vp["x"], vp["y"],
                    164 * vp.get("scale", 1.05), vp["pose"], vp["facing"], t,
                    MAGENTA, 1.0, vill_energy, 1.7)

    draw_impacts(emis, scene, cam, t)
    draw_rain(emis, cam, t)
    draw_embers(emis, cam, t)

    # ---- camera shake driven subtle motion blur ----
    out = post_process(scene, emis, t)

    # ---- radial speed streaks around the action (subtle, screen space) ----
    for (t0, dur, cx0) in [(9.65, 0.22, 1000), (16.28, 0.26, 1080),
                            (14.0, 0.18, 1020)]:
        if t0 <= t < t0 + dur:
            a = (1 - (t - t0) / dur) ** 2
            p = cam.apply(cx0, GROUND - 260)
            rng = random.Random(int(t * 60))
            for i in range(26):
                ang = rng.uniform(0, 6.283)
                r0 = rng.uniform(320, 520)
                r1 = r0 + rng.uniform(80, 260)
                cv2.line(out, (int(p[0] + math.cos(ang) * r0),
                               int(p[1] + math.sin(ang) * r0 * 0.6)),
                         (int(p[0] + math.cos(ang) * r1),
                          int(p[1] + math.sin(ang) * r1 * 0.6)),
                         tuple(int(c * a * 0.35) for c in (200, 230, 255)),
                         2, cv2.LINE_AA)

    draw_titles(out, t)
    draw_hud(out, t, hp["x"])
    return out


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
def main():
    init_particles()
    build_post_assets()
    get_backdrop()

    ff = None
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    t_start = time.time() if 'time' in globals() else 0
    NUL = subprocess.DEVNULL
    video_only = "v2_video_only.mp4"

    proc = None
    vw = None
    if ff:
        cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
               "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
               "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
               "-g", "60", "-movflags", "+faststart", video_only]
        print(" ".join(cmd), flush=True)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=NUL,
                                stderr=NUL)
    else:
        vw = cv2.VideoWriter(OUT_SILENT, cv2.VideoWriter_fourcc(*"mp4v"),
                             FPS, (W, H))

    import time as _t
    t0 = _t.time()
    for fi in range(NFRAMES):
        fr = render_frame(fi)
        if proc is not None:
            proc.stdin.write(fr.tobytes())
        else:
            vw.write(fr)
        if fi % 30 == 0:
            el = _t.time() - t0
            print(f"frame {fi}/{NFRAMES}  {el:.1f}s "
                  f"({el / max(1, fi + 1):.3f}s/f)", flush=True)

    if proc is not None:
        proc.stdin.close()
        proc.wait()
        print("video encode done", flush=True)
        audio = "soundtrack_v2.wav"
        if os.path.exists(audio):
            subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error",
                            "-i", video_only, "-i", audio,
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                            "-ar", "44100", "-shortest", "-movflags",
                            "+faststart", OUT_FINAL], check=True)
        else:
            os.replace(video_only, OUT_FINAL)
    else:
        vw.release()
        if ff:
            subprocess.run([ff, "-y", "-i", OUT_SILENT, "-c:v", "libx264",
                            "-crf", "21", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", OUT_FINAL], check=True)

    sz = os.path.getsize(OUT_FINAL) / 1e6 if os.path.exists(OUT_FINAL) else 0
    print(f"DONE {OUT_FINAL}  {sz:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
