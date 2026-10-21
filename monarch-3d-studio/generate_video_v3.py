#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MONARCHVOICE // MOTION LAB  —  30 s stickman explainer film
1920x1080 @ 30 fps.  Real physics (projectile, momentum, impulse, energy)
driven by a small simulator, rendered with the v2 cinematic engine.
Language: easy Roman-Urdu + English, burnt-in.
"""

import os
import math
import random
import subprocess
import time

import numpy as np
import cv2

import generate_video_v2 as B

cv2.setNumThreads(0)

W, H = B.W, B.H
FPS = B.FPS
DUR = 30.0
NFRAMES = int(DUR * FPS)
GROUND = B.GROUND
OUT = "MonarchVoice-MOTION-LAB-30s-1080p.mp4"
AUDIO = "soundtrack_v3.wav"
VIDEO_ONLY = "v3_video_only.mp4"

CYAN = B.CYAN
CRIMSON = B.MAGENTA
WHITE = B.WHITE
GOLD = B.GOLD
LIME = np.array([110, 255, 170], np.float32)
ORANGE = np.array([70, 170, 255], np.float32)
VIOLET = np.array([255, 130, 220], np.float32)
GREY = np.array([150, 150, 160], np.float32)

# ---------------- physics constants (1 m = 268 px) ----------------
PPM = 268.0
GRAV = 9.81 * PPM          # px / s^2
G_REAL = 9.81

random.seed(11)
np.random.seed(11)

# ---------------- chapter map ----------------
CH = [
    (0.0, 3.2, "intro"),
    (3.2, 10.2, "gravity"),
    (10.2, 15.8, "momentum"),
    (15.8, 21.4, "reaction"),
    (21.4, 27.2, "energy"),
    (27.2, 30.0, "outro"),
]

CAPTIONS = {
    "intro": [
        (0.30, 2.10, "Action ke peeche ek LAW hota hai.",
         "Every move you see? There is physics behind it.", 0),
        (2.10, 3.10, "4 laws • 30 seconds • asaan Urdu-English me",
         "4 laws · 30 seconds · easy Urdu-English", 1),
    ],
    "gravity": [
        (0.0, 2.6, "1) GRAVITY — jo upar jaye, wapis neeche aayega.",
         "Law 1 · Gravity always pulls you back down.", 0),
        (2.6, 5.2, "Speed double karo → height 4 guna!",
         "h = v² / 2g   (height ∝ speed squared)", 1),
        (5.2, 7.0, "Isi liye jump ki timing sab kuch hai.",
         "That's why timing decides every jump.", 0),
    ],
    "momentum": [
        (0.0, 3.0, "2) MOMENTUM — bhaari cheez rukna mushkil.",
         "Law 2 · Momentum p = mass × velocity", 0),
        (3.0, 5.6, "Same force → halki cheez udti hai, bhaari sirf sarti hai.",
         "F = m × a : more mass, less acceleration.", 1),
    ],
    "reaction": [
        (0.0, 2.7, "3) ACTION = REACTION — utni hi force wapis milti hai.",
         "Law 3 · Newton: equal and opposite force.", 0),
        (2.7, 5.6, "Impulse same → halki body zyada peeche udti hai.",
         "Same impulse, smaller mass = bigger recoil.", 1),
    ],
    "energy": [
        (0.0, 2.3, "4) ENERGY — khatam nahi hoti, sirf badalti hai.",
         "Law 4 · Energy is conserved, only transformed.", 0),
        (2.3, 4.4, "Upar wazan girega → lever ghumega → hero launch!",
         "PE = mgh  →  KE = ½mv²  →  height again", 1),
        (4.4, 5.8, "Wahi energy, naya rukh. Chain kabhi tootti nahi.",
         "Same energy, new direction — nothing is lost.", 0),
    ],
    "outro": [
        (0.0, 1.8, "Bas! 4 laws, 30 seconds.",
         "That's it — motion, explained.", 0),
    ],
}

# ---------------- extra poses (animation principles) ----------------
B.POSES.update({
    "anticip": dict(lean=34, head=-16, shL=-34, elL=-24, shR=-30, elR=-20,
                    hipL=52, knL=-98, hipR=-46, knR=-90, py=20, rot=0, cape=62),
    "push":    dict(lean=40, head=-18, shL=88, elL=-6, shR=82, elR=-4,
                    hipL=50, knL=-40, hipR=-32, knR=-54, py=8, rot=0, cape=48),
    "hpush":   dict(lean=54, head=-24, shL=96, elL=-2, shR=92, elR=0,
                    hipL=64, knL=-28, hipR=-20, knR=-72, py=16, rot=0, cape=30),
    "recoil":  dict(lean=-32, head=22, shL=-98, elL=-42, shR=-88, elR=-46,
                    hipL=-28, knL=-32, hipR=28, knR=-18, py=0, rot=0, cape=74),
    "float":   dict(lean=-6, head=4, shL=-34, elL=-22, shR=-28, elR=-16,
                    hipL=-42, knL=-52, hipR=32, knR=-70, py=0, rot=0, cape=16),
    "reach":   dict(lean=8, head=-4, shL=104, elL=-14, shR=98, elR=-12,
                    hipL=16, knL=-8, hipR=-16, knR=-8, py=0, rot=0, cape=36),
    "shock":   dict(lean=-16, head=16, shL=-72, elL=-58, shR=-66, elR=-62,
                    hipL=-18, knL=-14, hipR=18, knR=-12, py=0, rot=0, cape=52),
})

P = B.POSES
IDLE, GUARD, WALKA, WALKB = P["idle"], P["guard"], P["walk_a"], P["walk_b"]
AIR, LAND, DOWN, VICT = P["air"], P["land"], P["down"], P["victory"]
PUNCH, KICK, HIT, CHARGE = P["punch_r"], P["kick"], P["hit"], P["charge"]
ANTIC, PUSH, HPUSH = P["anticip"], P["push"], P["hpush"]
RECOIL, FLOAT, REACH, SHOCK = P["recoil"], P["float"], P["reach"], P["shock"]


# ---------------------------------------------------------------- helpers
def clamp(v, a, b):
    return a if v < a else (b if v > b else v)


def lerp(a, b, t):
    return a + (b - a) * t


def ease_io(t):
    t = clamp(t, 0, 1)
    return 0.5 - 0.5 * math.cos(math.pi * t)


def ease_out(t):
    t = clamp(t, 0, 1)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t, 0, 1)
    return t * t * t


def smoothstep(a, b, x):
    if b == a:
        return 0.0
    t = clamp((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def blink_alpha(t, t0, t1, fade=0.3):
    return smoothstep(t0, t0 + fade, t) * (1 - smoothstep(t1 - fade, t1, t))


def chapter_of(t):
    for (a, b, name) in CH:
        if a <= t < b:
            return name, t - a, b - a
    return CH[-1][2], t - CH[-1][0], CH[-1][1] - CH[-1][0]


class Warp:
    """piecewise slow-motion mapping: visual time -> physics time"""

    def __init__(self, segs):
        # segs: list of (phys_start, phys_end, speed)
        self.segs = sorted(segs)
        self.marks = []
        vcur = 0.0
        for (a, b, s) in self.segs:
            dur_v = (b - a) / s
            self.marks.append((vcur, vcur + dur_v, a, b, s))
            vcur += dur_v
        self.vtotal = vcur

    def __call__(self, tv):
        for (v0, v1, a, b, s) in self.marks:
            if tv < v1:
                return a + (tv - v0) * s
        last = self.marks[-1] if self.marks else None
        if last is None:
            return tv
        return last[3] + (tv - last[1])

    def visual_len(self, phys_len):
        end = self.marks[-1][3] if self.marks else 0.0
        return (self.marks[-1][1] if self.marks else 0.0) + (phys_len - end)

    def slow_amount(self, tv):
        for (v0, v1, a, b, s) in self.marks:
            if v0 <= tv < v1:
                return s
        return 1.0


# ---------------------------------------------------------------- drawing kit
def scr(cam, x, y):
    p = cam.apply(x, y)
    return int(p[0]), int(p[1])


def arrow(img, cam, x1, y1, x2, y2, color, thick=4, head=16, alpha=1.0,
          label=None, label_off=(0, -14), font_scale=0.5):
    p1 = scr(cam, x1, y1)
    p2 = scr(cam, x2, y2)
    a = clamp(alpha, 0, 1)
    col = tuple(int(c * a) for c in color)
    cv2.line(img, p1, p2, col, thick, cv2.LINE_AA)
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    for sgn in (-0.5, 0.5):
        hx = int(p2[0] - head * math.cos(ang + sgn))
        hy = int(p2[1] - head * math.sin(ang + sgn))
        cv2.line(img, p2, (hx, hy), col, thick, cv2.LINE_AA)
    if label:
        mx = (p1[0] + p2[0]) // 2 + label_off[0]
        my = (p1[1] + p2[1]) // 2 + label_off[1]
        B.text(img, label, mx, my, font_scale, color, 1, a, center=True,
               spacing=1.4)


def dashed_arc(emis, cam, pts, color, alpha=0.5, dash=9):
    a = clamp(alpha, 0, 1)
    if a <= 0.02 or len(pts) < 2:
        return
    col = tuple(int(c * a) for c in color)
    col_soft = tuple(int(c * a * 0.45) for c in color)
    layer = np.zeros_like(emis)
    for i in range(0, len(pts) - 1):
        if (i // dash) % 2:
            continue
        p1 = cam.apply(pts[i][0], pts[i][1])
        p2 = cam.apply(pts[i + 1][0], pts[i + 1][1])
        cv2.line(emis, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])),
                 col, 3, cv2.LINE_AA)
        cv2.line(layer, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])),
                 col_soft, 9, cv2.LINE_AA)
    layer = cv2.GaussianBlur(layer, (0, 0), 9)
    cv2.add(emis, layer, emis)


def ruler(scene, emis, cam, x, y0, y1, color, alpha=1.0, label=None):
    """vertical measurement line with end ticks"""
    a = clamp(alpha, 0, 1)
    if a <= 0.02:
        return
    col = tuple(int(c * a) for c in color)
    p0 = cam.apply(x, y0)
    p1 = cam.apply(x, y1)
    cv2.line(emis, (int(p0[0]), int(p0[1])), (int(p1[0]), int(p1[1])), col, 2,
             cv2.LINE_AA)
    for p in (p0, p1):
        cv2.line(emis, (int(p[0] - 12), int(p[1])), (int(p[0] + 12), int(p[1])),
                 col, 2, cv2.LINE_AA)
    if label:
        B.text(scene, label, int(p0[0] + 22), int((p0[1] + p1[1]) / 2), 0.52,
               color, 1, a, spacing=1.2)


def draw_crate(scene, emis, cam, x, w, h, color, label="", alpha=1.0,
               speed=0.0):
    a = clamp(alpha, 0, 1)
    if a <= 0.02:
        return
    p = cam.apply(x, GROUND)
    bx, by = p
    ws = w * cam.z
    hs = h * cam.z
    dx = 0.24 * ws
    dy = 0.15 * hs
    x0, x1 = bx - ws / 2, bx + ws / 2
    top, bot = by - hs, by
    front = np.array([[x0, top], [x1, top], [x1, bot], [x0, bot]], np.int32)
    topf = np.array([[x0, top], [x0 + dx, top - dy],
                     [x1 + dx, top - dy], [x1, top]], np.int32)
    side = np.array([[x1, top], [x1 + dx, top - dy],
                     [x1 + dx, bot - dy], [x1, bot]], np.int32)
    cv2.fillPoly(scene, [front], tuple(int(c * a * 0.30) for c in color),
                 cv2.LINE_AA)
    cv2.fillPoly(scene, [topf], tuple(int(c * a * 0.55) for c in color),
                 cv2.LINE_AA)
    cv2.fillPoly(scene, [side], tuple(int(c * a * 0.42) for c in color),
                 cv2.LINE_AA)
    for poly in (front, topf, side):
        cv2.polylines(scene, [poly], True, tuple(int(c * a) for c in color), 2,
                      cv2.LINE_AA)
        L = np.zeros_like(scene)
        cv2.polylines(L, [poly], True, tuple(int(c * a * 0.5) for c in color), 3,
                      cv2.LINE_AA)
        L = cv2.GaussianBlur(L, (0, 0), 6)
        cv2.add(emis, L, emis)
    if label:
        B.text(scene, label, int(bx), int((top + bot) / 2 + 8), 0.46, color, 1,
               a, center=True, spacing=1.6)
    # motion smear
    if speed > 60:
        n = int(clamp(speed / 90.0, 0, 7))
        for i in range(1, n + 1):
            off = -i * 9
            cv2.rectangle(emis, (int(x0 + off), int(top)),
                          (int(x1 + off), int(bot)),
                          tuple(int(c * 0.05 * a) for c in color), 1)


def draw_ball(scene, emis, cam, x, y, r, color, label="", alpha=1.0,
              trail=None):
    a = clamp(alpha, 0, 1)
    if a <= 0.02:
        return
    p = cam.apply(x, y)
    rs = max(3, int(r * cam.z))
    B.add_glow(emis, p, rs * 3.2, color, 0.55 * a)
    cv2.circle(scene, (int(p[0]), int(p[1])), rs,
               tuple(int(c * a * 0.35) for c in color), -1, cv2.LINE_AA)
    cv2.circle(scene, (int(p[0]), int(p[1])), rs,
               tuple(int(c * a) for c in color), 3, cv2.LINE_AA)
    cv2.circle(scene, (int(p[0] - rs * 0.3), int(p[1] - rs * 0.3)),
               max(2, rs // 3), tuple(int(c * a * 0.9) for c in WHITE), -1,
               cv2.LINE_AA)
    if trail:
        for (tx, ty, ta) in trail:
            tp = cam.apply(tx, ty)
            cv2.circle(emis, (int(tp[0]), int(tp[1])), max(2, int(rs * ta * 0.6)),
                       tuple(int(c * 0.35 * ta * a) for c in color), -1,
                       cv2.LINE_AA)
    if label:
        B.text(scene, label, int(p[0]), int(p[1] - rs - 14), 0.44, color, 1, a,
               center=True, spacing=1.2)


def lever(scene, emis, cam, px, angle_deg, length, color, alpha=1.0,
          pivot_y=None):
    a = clamp(alpha, 0, 1)
    if a <= 0.02:
        return
    py = GROUND - 34 if pivot_y is None else pivot_y
    ang = math.radians(angle_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    ex1 = px - length * ca
    ey1 = py - length * sa
    ex2 = px + length * ca
    ey2 = py + length * sa
    # fulcrum wedge
    pw = 44
    tri = np.array([[px - pw, GROUND], [px + pw, GROUND], [px, py]], np.int32)
    cv2.fillPoly(scene, [tri], tuple(int(c * a * 0.35) for c in color),
                 cv2.LINE_AA)
    cv2.polylines(scene, [tri], True, tuple(int(c * a * 0.9) for c in color),
                  2, cv2.LINE_AA)
    p1 = cam.apply(ex1, ey1)
    p2 = cam.apply(ex2, ey2)
    pp = cam.apply(px, py)
    th = max(3, int(9 * cam.z))
    cv2.line(scene, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])),
             tuple(int(c * a * 0.7) for c in color), th + 4, cv2.LINE_AA)
    cv2.line(scene, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])),
             tuple(int(c * a) for c in color), th, cv2.LINE_AA)
    cv2.circle(scene, (int(pp[0]), int(pp[1])), max(3, int(10 * cam.z)),
               tuple(int(c * a) for c in color), 2, cv2.LINE_AA)
    L = np.zeros_like(scene)
    cv2.line(L, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])),
             tuple(int(c * a * 0.5) for c in color), th + 8, cv2.LINE_AA)
    L = cv2.GaussianBlur(L, (0, 0), 7)
    cv2.add(emis, L, emis)
    return (ex1, ey1), (ex2, ey2)


def data_panel(img, x, y, lines, alpha=1.0, width=330, color=CYAN):
    """live physics readout card (top-right style)"""
    a = clamp(alpha, 0, 1)
    if a <= 0.02:
        return
    hgt = 34 + 30 * len(lines)
    ov = img.copy()
    cv2.rectangle(ov, (x - 18, y - 26), (x - 18 + width, y - 26 + hgt),
                  (8, 10, 16), -1, cv2.LINE_AA)
    cv2.addWeighted(ov, 0.62 * a, img, 1 - 0.62 * a, 0, img)
    cv2.rectangle(img, (x - 18, y - 26), (x - 18 + width, y - 26 + hgt),
                  tuple(int(c * 0.35 * a) for c in color), 1, cv2.LINE_AA)
    for i, (k, v, c) in enumerate(lines):
        B.text(img, k, x, y + i * 30, 0.40, (170, 180, 195), 1, a * 0.9,
               spacing=1.2)
        B.text(img, v, x + width - 46, y + i * 30, 0.46, c, 1, a,
               center=True, spacing=0.8)


def caption_bar(img, urdu, eng, alpha=1.0, accent=CYAN):
    a = clamp(alpha, 0, 1)
    if a <= 0.02:
        return
    y0 = H - 126
    ov = img.copy()
    cv2.rectangle(ov, (0, y0), (W, H - 40), (4, 5, 9), -1)
    cv2.addWeighted(ov, 0.62 * a, img, 1 - 0.62 * a, 0, img)
    cv2.line(img, (80, y0), (W - 80, y0),
             tuple(int(c * 0.45 * a) for c in accent), 1, cv2.LINE_AA)
    B.text(img, urdu, W // 2, y0 + 42, 0.88, (248, 250, 255), 2, a,
           center=True, spacing=0.8, font=B.FONT_B)
    B.text(img, eng, W // 2, y0 + 76, 0.46, tuple(int(c * a) for c in accent),
           1, a * 0.95, center=True, spacing=1.8)


def law_badge(img, num, title, formula, alpha=1.0, color=CYAN):
    a = clamp(alpha, 0, 1)
    if a <= 0.02:
        return
    x, y = 62, 118
    ov = img.copy()
    cv2.rectangle(ov, (x - 16, y - 34), (x + 430, y + 54), (6, 8, 12), -1)
    cv2.addWeighted(ov, 0.55 * a, img, 1 - 0.55 * a, 0, img)
    cv2.rectangle(img, (x - 16, y - 34), (x + 430, y + 54),
                  tuple(int(c * 0.4 * a) for c in color), 1, cv2.LINE_AA)
    B.text(img, num, x, y + 2, 0.62, color, 2, a, spacing=1.6)
    B.text(img, title, x + 66, y, 0.60, (240, 244, 252), 1, a, spacing=2.4)
    B.text(img, formula, x + 66, y + 30, 0.42, tuple(int(c * a) for c in color),
           1, a * 0.9, spacing=1.2)


def chip_row(img, items, cx, cy, alpha=1.0, color=CYAN):
    a = clamp(alpha, 0, 1)
    if a <= 0.02:
        return
    widths = []
    for s in items:
        (w_, _h), _ = cv2.getTextSize(s, B.FONT, 0.44, 1)
        widths.append(w_ + 42)
    total = sum(widths) + 14 * (len(items) - 1)
    x = cx - total // 2
    for i, s in enumerate(items):
        w_ = widths[i]
        cv2.rectangle(img, (x, cy - 20), (x + w_, cy + 20),
                      tuple(int(c * 0.14 * a) for c in color), -1, cv2.LINE_AA)
        cv2.rectangle(img, (x, cy - 20), (x + w_, cy + 20),
                      tuple(int(c * 0.55 * a) for c in color), 1, cv2.LINE_AA)
        B.text(img, s, x + w_ // 2, cy + 8, 0.44, (230, 238, 250), 1, a,
               center=True, spacing=1.4)
        x += w_ + 14


# ---------------------------------------------------------------- camera
CAM_KEYS = [
    (0.0, 960, 1.00, 0.75),
    (3.2, 960, 1.05, 0.77),
    (4.4, 890, 1.02, 0.79),
    (6.0, 880, 0.94, 0.79),
    (7.4, 1030, 0.82, 0.82),
    (9.0, 1080, 0.88, 0.82),
    (10.2, 1020, 1.00, 0.79),
    (12.2, 1050, 1.00, 0.79),
    (13.8, 1150, 0.92, 0.79),
    (15.8, 1120, 0.96, 0.79),
    (16.6, 965, 1.00, 0.79),
    (18.4, 965, 1.04, 0.79),
    (20.0, 965, 0.96, 0.79),
    (21.4, 1000, 0.98, 0.79),
    (22.6, 1010, 0.92, 0.76),
    (24.4, 1060, 0.88, 0.74),
    (26.2, 1050, 0.94, 0.78),
    (27.2, 1030, 1.00, 0.79),
    (28.4, 980, 1.02, 0.77),
    (30.0, 970, 1.05, 0.79),
]

SHAKES = [
    (3.2 + 1.05, 12, 0.5), (3.2 + 2.0, 20, 0.55),         # jump landings
    (10.2 + 2.35, 9, 0.35),                                # crate stop
    (10.2 + 4.05, 11, 0.4),                                # kick
    (15.8 + 1.05, 22, 0.55), (15.8 + 3.55, 26, 0.6),       # punches
    (21.4 + 1.25, 18, 0.5), (21.4 + 2.5, 24, 0.55),        # ball / landing
    (27.2 + 0.1, 14, 0.5),
]


def camera_for(t):
    c = B.Cam()
    keys = CAM_KEYS
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
    c.y = GROUND - ((gy * H) - H * 0.5) / max(0.2, c.z)
    c.sx = math.sin(t * 0.8) * 2.6 + math.sin(t * 2.4) * 1.2
    c.sy = math.cos(t * 0.65) * 2.1 + math.sin(t * 3.1) * 0.9
    for (t0, amp, dur) in SHAKES:
        if t0 <= t <= t0 + dur:
            k = (1 - (t - t0) / dur) ** 2
            c.sx += math.sin((t - t0) * 58) * amp * k
            c.sy += math.cos((t - t0) * 44) * amp * k * 0.75
    return c


# ---------------------------------------------------------------- chapter: intro
def sc_intro(tl, dur):
    hero = dict(x=1580, y=GROUND, pose=IDLE, facing=-1, scale=0.86,
                theme=CYAN, energy=0.25 + 0.2 * math.sin(tl * 3), sx=1, sy=1)
    if 0.5 < tl < 1.4:
        k = ease_io((tl - 0.5) / 0.9)
        hero["pose"] = B.blend_pose(IDLE, GUARD, k * 0.6)
    return dict(actors=[hero], overlay=None, panel=None)


# ---------------------------------------------------------------- chapter: gravity
class GravityScene:
    """Law 1 — projectile motion with a real parabola + slow-mo apex"""
    T1 = dict(t0=0.60, v0=1350.0, x=620.0, drift=520.0)
    T2 = dict(t0=3.45, v0=1700.0, x=620.0, drift=760.0)

    def __init__(self, dur):
        self.dur = dur
        apex1 = self.T1["t0"] + self.T1["v0"] / GRAV
        apex2 = self.T2["t0"] + self.T2["v0"] / GRAV
        f1 = 2 * self.T1["v0"] / GRAV
        f2 = 2 * self.T2["v0"] / GRAV
        self.warp = Warp([(0.0, self.T1["t0"], 1.0),
                          (self.T1["t0"], self.T1["t0"] + f1, 0.62),
                          (self.T1["t0"] + f1, self.T2["t0"], 1.0),
                          (self.T2["t0"], self.T2["t0"] + f2, 0.58),
                          (self.T2["t0"] + f2, self.T2["t0"] + f2 + 1.0, 1.0)])

    def apex_h(self, j):
        return j["v0"] ** 2 / (2 * GRAV)

    def flight(self, j):
        return 2 * j["v0"] / GRAV

    def hero_state(self, p):
        for j, tag in ((self.T1, 1), (self.T2, 2)):
            flight = self.flight(j)
            land = j["t0"] + flight
            if j["t0"] <= p <= land:
                dt = p - j["t0"]
                h = j["v0"] * dt - 0.5 * GRAV * dt * dt
                x = j["x"] + j["drift"] * (dt / flight)
                vy = j["v0"] - GRAV * dt
                air_k = clamp(dt / flight, 0, 1)
                pose = AIR if abs(vy) > 350 else FLOAT
                sy = 1.0 + 0.05 * abs(vy) / j["v0"]
                sx = 1.0 - 0.04 * abs(vy) / j["v0"]
                return dict(x=x, y=GROUND - h, pose=pose, facing=1,
                            scale=1.12, theme=CYAN, energy=0.45,
                            sx=sx, sy=sy, airborne=True, h=h, vy=vy,
                            peak=(abs(vy) < 240))
            if land < p <= land + 0.30:
                k = ease_out((p - land) / 0.30)
                return dict(x=j["x"] + j["drift"], y=GROUND,
                            pose=B.blend_pose(LAND, IDLE, k), facing=1,
                            scale=1.12, theme=CYAN, energy=0.3,
                            sx=lerp(1.16, 1.0, k), sy=lerp(0.80, 1.0, k),
                            landed=True)
        if p < self.T1["t0"]:
            k = ease_io(p / self.T1["t0"])
            pose = B.blend_pose(IDLE, ANTIC, k)
            return dict(x=self.T1["x"], y=GROUND, pose=pose, facing=1,
                        scale=1.12, theme=CYAN, energy=0.3,
                        sx=lerp(1.0, 1.08, k), sy=lerp(1.0, 0.88, k))
        if p < self.T2["t0"]:
            k = ease_io((p - 1.9) / (self.T2["t0"] - 1.9))
            k = clamp(k, 0, 1)
            pose = B.blend_pose(IDLE, ANTIC, k * 0.9)
            return dict(x=self.T2["x"], y=GROUND, pose=pose, facing=1,
                        scale=1.12, theme=CYAN, energy=0.3,
                        sx=lerp(1.0, 1.07, k), sy=lerp(1.0, 0.90, k))
        return dict(x=self.T2["x"] + self.T2["drift"], y=GROUND, pose=IDLE,
                    facing=1, scale=1.12, theme=CYAN, energy=0.3, sx=1, sy=1)

    def render_state(self, tl):
        p = self.warp(tl)
        hs = self.hero_state(p)
        # trajectory of the two jumps (drawn once they happen)
        arcs = []
        for j, col in ((self.T1, CYAN), (self.T2, VIOLET)):
            flight = self.flight(j)
            if p >= j["t0"] + 0.02:
                pts = []
                n = 40
                for i in range(n + 1):
                    dt = flight * i / n
                    h = j["v0"] * dt - 0.5 * GRAV * dt * dt
                    pts.append((j["x"] + j["drift"] * (dt / flight),
                                GROUND - h))
                grown = clamp((p - j["t0"]) / max(0.20, flight * 0.55), 0, 1)
                arcs.append((pts[:max(2, int(len(pts) * grown))], col,
                             j, 0.95))
        overlay = ("gravity", dict(p=p, arcs=arcs, hs=hs, scene=self))
        return dict(actors=[hs], overlay=overlay, panel=("gravity", p, hs),
                    slow=self.warp.slow_amount(tl))


# ---------------------------------------------------------------- chapter: momentum
class MomentumScene:
    """Law 2 — F = ma with a heavy crate, then a light box kick"""
    F_N = 90.0           # applied force (newtons)
    M_CRATE = 40.0       # kg
    MU = 0.78            # friction coefficient
    KICK_T = 3.15
    KICK_V = 0.0
    BOX_X = 1400.0
    LIGHT_M = 5.0
    KICK_ANG = 42.0

    def __init__(self, dur):
        self.dur = dur
        self.a = (self.F_N / self.M_CRATE) * PPM          # px/s^2 while pushing
        self.fric = self.MU * G_REAL * PPM
        self.push_t0 = 0.90
        self.push_dur = 0.62
        # integrate crate motion once
        self.crate_x0 = 985.0
        self.crate_track = self._sim_crate()
        self.hero_x0 = 815.0
        self.contact = 925.0

    def _sim_crate(self):
        dt = 1 / 240.0
        x, v = self.crate_x0, 0.0
        pos = {}
        t = 0.0
        while t < self.dur + 0.2:
            if self.push_t0 <= t < self.push_t0 + self.push_dur:
                v += self.a * dt
            else:
                if v > 0:
                    v = max(0.0, v - self.fric * dt)
            x += v * dt
            pos[round(t, 3)] = (x, v)
            t += dt
        return pos

    def crate_at(self, t):
        k = round(clamp(t, 0, self.dur + 0.15), 3)
        if k in self.crate_track:
            return self.crate_track[k]
        best = min(self.crate_track.keys(), key=lambda kk: abs(kk - k))
        return self.crate_track[best]

    def box_at(self, p):
        """light crate (5 kg) shoved with the SAME force -> 8x acceleration"""
        dt = p - self.KICK_T
        if dt < 0:
            return None
        a_l = (self.F_N / self.LIGHT_M) * PPM
        fric = self.MU * G_REAL * PPM
        push = 0.22
        if dt <= push:
            x = self.BOX_X + 0.5 * a_l * dt * dt
            v = a_l * dt
        else:
            v0 = a_l * push
            t2 = min(dt - push, v0 / fric)      # never integrate past the stop
            d = max(0.0, v0 * t2 - 0.5 * fric * t2 * t2)
            x = self.BOX_X + 0.5 * a_l * push ** 2 + d
            v = max(0.0, v0 - fric * t2)
        return dict(x=x, y=GROUND, vx=v, vy=0.0, air=False)

    def render_state(self, tl):
        cx, cv = self.crate_at(tl)
        # hero state machine: walk -> push heavy -> walk -> push light
        hx = self.contact + 12
        if tl < self.push_t0:
            k = ease_io(tl / self.push_t0)
            hx = lerp(self.hero_x0, self.contact, k)
            pose = WALKA if int(tl * 6) % 2 == 0 else WALKB
            if tl > self.push_t0 - 0.22:
                pose = B.blend_pose(pose, ANTIC, 0.7)
            hs = dict(x=hx, y=GROUND, pose=pose, facing=1, scale=1.14,
                      theme=CYAN, energy=0.3, sx=1, sy=1)
        elif tl < self.push_t0 + self.push_dur + 0.12:
            pose = B.blend_pose(ANTIC, HPUSH,
                                clamp((tl - self.push_t0) / 0.22, 0, 1))
            strain = int(tl * 18) % 2
            hs = dict(x=self.contact + 12 + strain * 2, y=GROUND, pose=pose,
                      facing=1, scale=1.14, theme=CYAN, energy=0.55,
                      sx=1.02, sy=0.98)
        elif tl < self.KICK_T - 0.55:
            k = ease_io((tl - (self.push_t0 + self.push_dur + 0.12)) / 0.75)
            stop_x = self.crate_at(tl)[0]
            hx = lerp(self.contact + 12, max(self.BOX_X - 170, stop_x + 235), clamp(k, 0, 1))
            walk = WALKA if int(tl * 7) % 2 == 0 else WALKB
            hs = dict(x=hx, y=GROUND,
                      pose=B.blend_pose(HPUSH, walk, clamp(k * 3, 0, 1)),
                      facing=1, scale=1.14, theme=CYAN, energy=0.35,
                      sx=1, sy=1)
        elif tl < self.KICK_T:
            k = ease_io((tl - (self.KICK_T - 0.55)) / 0.55)
            hs = dict(x=max(self.BOX_X - 170, self.crate_at(tl)[0] + 235), y=GROUND,
                      pose=B.blend_pose(WALKA, ANTIC, k), facing=1,
                      scale=1.14, theme=CYAN, energy=0.5, sx=1.02,
                      sy=lerp(1.0, 0.94, k))
        elif tl < self.KICK_T + 0.60:
            k = clamp((tl - self.KICK_T) / 0.14, 0, 1)
            strain = int(tl * 20) % 2
            hs = dict(x=max(self.BOX_X - 158, self.crate_at(tl)[0] + 225) + strain * 2, y=GROUND,
                      pose=B.blend_pose(ANTIC, HPUSH, k), facing=1,
                      scale=1.14, theme=CYAN, energy=0.8, sx=0.98, sy=1.03)
        else:
            k = ease_io((tl - (self.KICK_T + 0.60)) / 0.45)
            hs = dict(x=max(self.BOX_X - 158, self.crate_at(tl)[0] + 225), y=GROUND,
                      pose=B.blend_pose(HPUSH, IDLE, clamp(k, 0, 1)),
                      facing=1, scale=1.14, theme=CYAN, energy=0.35,
                      sx=1, sy=1)

        box = self.box_at(tl)
        crate_speed = abs(cv)
        p_crate = self.M_CRATE * (crate_speed / PPM)
        overlay = ("momentum", dict(tl=tl, crate=(cx, crate_speed, p_crate),
                                    box=box, scene=self, hs=hs))
        box = self.box_at(tl)
        a_heavy = (self.F_N / self.M_CRATE)
        a_light = (self.F_N / self.LIGHT_M)
        panel_lines = [
            ("FORCE", f"{self.F_N:.0f} N", GOLD),
            ("MASS", f"{self.M_CRATE:.0f} / {self.LIGHT_M:.0f} kg", CYAN),
            ("ACCEL", f"{a_heavy:.1f} → {a_light:.1f} m/s²", LIME),
            ("SPEED", f"{crate_speed / PPM:.1f} m/s", VIOLET),
        ]
        return dict(actors=[hs], overlay=overlay,
                    panel=("lines", panel_lines), crate=(cx, crate_speed),
                    box=box, slow=1.0)


def posestr(pose):
    return pose


# ---------------------------------------------------------------- chapter: reaction
class ReactionScene:
    """Law 3 — equal/opposite impulses, then unequal masses"""
    J1 = 95.0      # impulse (N·s) both directions
    J2 = 100.0
    M_HERO1, M_VILL1 = 70.0, 70.0
    M_HERO2, M_VILL2 = 50.0, 150.0
    X_H, X_V = 800.0, 1130.0

    def __init__(self, dur):
        self.dur = dur
        self.p1 = 1.05           # first punch
        self.p2 = 3.45           # second punch

    def _recoil(self, dt, v0, fric=0.55 * G_REAL * PPM, tmax=2.0):
        """slide-back distance under friction after an impulse"""
        v = abs(v0)
        if dt <= 0:
            return 0.0, v
        t = min(dt, tmax)
        # constant deceleration
        x = v * t - 0.5 * fric * t * t
        vv = max(0.0, v - fric * t)
        x = max(0.0, x)
        return x, vv

    def render_state(self, tl):
        fric = 0.55 * G_REAL * PPM
        # ---- actor 1 ----
        if tl < self.p1:
            k = ease_io((tl - 0.3) / 0.35)
            hx = lerp(self.X_H, self.X_H + 42, clamp(k, 0, 1))
            vx = lerp(self.X_V, self.X_V - 42, clamp(k, 0, 1))
            hp = B.blend_pose(GUARD, PUNCH, clamp(k, 0, 1))
            vp = B.blend_pose(GUARD, P["punch_l"], clamp(k, 0, 1))
            hs = dict(x=hx, y=GROUND, pose=hp, facing=1, scale=1.02,
                      theme=CYAN, energy=0.4, sx=1, sy=1)
            vs = dict(x=vx, y=GROUND, pose=vp, facing=-1, scale=1.06,
                      theme=CRIMSON, energy=0.4, sx=1, sy=1)
            phase = "windup1"
        elif tl < self.p2 - 0.55:
            dt = tl - self.p1
            d1, _ = self._recoil(dt, self.J1 / self.M_HERO1 * PPM, fric)
            d2, _ = self._recoil(dt, self.J1 / self.M_VILL1 * PPM, fric)
            k = clamp(dt / 0.25, 0, 1)
            hs = dict(x=self.X_H + 42 - d1, y=GROUND,
                      pose=B.blend_pose(PUNCH, RECOIL, k), facing=1,
                      scale=1.02, theme=CYAN, energy=0.5, sx=1.02, sy=0.98)
            vs = dict(x=self.X_V - 42 + d2, y=GROUND,
                      pose=B.blend_pose(P["punch_l"], RECOIL, k), facing=-1,
                      scale=1.06, theme=CRIMSON, energy=0.5, sx=1.02, sy=0.98)
            phase = "recoil1"
        elif tl < self.p2:
            dt = tl - self.p1
            d1, _ = self._recoil(dt, self.J1 / self.M_HERO1 * PPM, fric)
            d2, _ = self._recoil(dt, self.J1 / self.M_VILL1 * PPM, fric)
            k = ease_io((tl - (self.p2 - 0.55)) / 0.3)
            hp = B.blend_pose(RECOIL, GUARD, k)
            vp = B.blend_pose(RECOIL, GUARD, k)
            # villain grows heavier for round 2
            vs_scale = lerp(0.96, 1.18, k)
            hs = dict(x=self.X_H + 42 - d1 + 34 * k, y=GROUND, pose=hp,
                      facing=1, scale=1.14, theme=CYAN, energy=0.4, sx=1, sy=1)
            vs = dict(x=self.X_V - 42 + d2 - 22 * k, y=GROUND, pose=vp,
                      facing=-1, scale=vs_scale * 1.08, theme=CRIMSON, energy=0.45,
                      sx=1, sy=1)
            phase = "windup2"
        else:
            dt = tl - self.p2
            d1, _ = self._recoil(dt, self.J2 / self.M_HERO2 * PPM, fric)
            d2, _ = self._recoil(dt, self.J2 / self.M_VILL2 * PPM, fric)
            k = clamp(dt / 0.22, 0, 1)
            hs = dict(x=self.X_H + 76 - d1, y=GROUND,
                      pose=B.blend_pose(PUNCH, RECOIL, k), facing=1,
                      scale=1.02, theme=CYAN, energy=0.6, sx=1.03, sy=0.97)
            vs = dict(x=self.X_V - 64 + d2, y=GROUND,
                      pose=B.blend_pose(PUNCH, RECOIL, k * 0.8), facing=-1,
                      scale=1.30, theme=CRIMSON, energy=0.55, sx=1, sy=1)
            phase = "recoil2"

        overlay = ("reaction", dict(tl=tl, phase=phase, scene=self))
        lines = [("IMPULSE", f"{self.J1:.0f} N·s", GOLD),
                 ("MASS A", f"{self.M_HERO1:.0f} kg", CYAN),
                 ("MASS B", f"{self.M_VILL1:.0f} kg", CRIMSON),
                 ("FORCE", "F = −F", WHITE)]
        return dict(actors=[hs, vs], overlay=overlay,
                    panel=("lines", lines), slow=1.0)


# ---------------------------------------------------------------- chapter: energy
class EnergyScene:
    """Law 4 — PE -> KE -> launch (drop weight on a lever)"""
    M_BALL = 120.0
    DROP_H = 470.0            # px
    PIVOT = 1060.0
    LEVER_L = 175.0
    PIVOT_Y = GROUND - 34
    LAUNCH_V = 1150.0
    BALL_X = 1060.0 - 175.0
    HERO_X = 1060.0 + 175.0
    TILT = 15.0

    def __init__(self, dur):
        self.dur = dur
        self.t_ball = 0.55
        self.t_hit = self.t_ball + math.sqrt(2 * self.DROP_H / GRAV)
        self.t_launch = self.t_hit + 0.12
        self.flight = 2 * self.LAUNCH_V / GRAV
        self.t_land = self.t_launch + self.flight
        self.t_end = self.t_land + 0.12
        self.warp = Warp([(0.0, self.t_ball, 1.0),
                          (self.t_ball, self.t_end, 0.36),
                          (self.t_end, self.t_end + 0.9, 1.0)])

    def ball_y(self, p):
        floor = self.PIVOT_Y
        top = floor - self.DROP_H
        if p < self.t_ball:
            return top
        dt = p - self.t_ball
        h = 0.5 * GRAV * dt * dt
        return max(floor, top + h)

    def hero(self, p):
        if p < self.t_launch:
            k = ease_io(p / self.t_launch)
            return dict(x=self.HERO_X - 18 * k, y=self.PIVOT_Y - 4,
                        pose=B.blend_pose(IDLE, ANTIC, k * 0.55), facing=-1,
                        scale=1.10, theme=CYAN, energy=0.35, sx=1, sy=1)
        if p <= self.t_land:
            dt = p - self.t_launch
            h = self.LAUNCH_V * dt - 0.5 * GRAV * dt * dt
            vy = self.LAUNCH_V - GRAV * dt
            return dict(x=self.HERO_X + 48 * (dt / self.flight),
                        y=self.PIVOT_Y - 4 - max(0.0, h),
                        pose=AIR if vy > 200 else FLOAT, facing=1, scale=1.10,
                        theme=CYAN, energy=0.55,
                        sx=1 - 0.05 * vy / self.LAUNCH_V,
                        sy=1 + 0.06 * vy / self.LAUNCH_V)
        k = ease_out(clamp((p - self.t_land) / 0.32, 0, 1))
        return dict(x=self.HERO_X + 48, y=GROUND,
                    pose=B.blend_pose(LAND, IDLE, k), facing=1, scale=1.10,
                    theme=CYAN, energy=0.35, sx=lerp(1.18, 1.0, k),
                    sy=lerp(0.80, 1.0, k))

    def render_state(self, tl):
        p = self.warp(tl)
        ball = self.ball_y(p)
        hs = self.hero(p)
        # lever angle: 0 until hit, then tilt as ball pushes left side
        ang = 0.0
        if p >= self.t_hit:
            k = ease_out(clamp((p - self.t_hit) / 0.22, 0, 1))
            ang = self.TILT * k
            if p > self.t_launch + 1.4:
                back = ease_io(clamp((p - (self.t_launch + 1.4)) / 0.5, 0, 1))
                ang *= (1 - back)
        pe = self.M_BALL * G_REAL * (self.DROP_H / PPM)
        ball_v = (self.ball_y(p - 0.02) - ball) / 0.02 if p > self.t_ball else 0
        ke = 0.5 * self.M_BALL * (abs(ball_v) / PPM) ** 2
        overlay = ("energy", dict(p=p, ball_y=ball, ang=ang, scene=self,
                                  pe=pe, ke=ke))
        lines = [("PE  mgh", f"{pe / 1000:.2f} kJ", VIOLET),
                 ("KE  ½mv²", f"{ke / 1000:.2f} kJ", LIME),
                 ("LAUNCH v", f"{self.LAUNCH_V / PPM:.1f} m/s", CYAN),
                 ("HEIGHT", f"{self.LAUNCH_V ** 2 / (2 * GRAV) / PPM:.1f} m",
                  GOLD)]
        return dict(actors=[hs], overlay=overlay,
                    panel=("lines", lines), ball=ball, lever_ang=ang,
                    slow=self.warp.slow_amount(tl))


# ---------------------------------------------------------------- chapter: outro
def sc_outro(tl, dur):
    k = ease_io(tl / 0.8)
    hero = dict(x=1650, y=GROUND, pose=B.blend_pose(IDLE, VICT, k), facing=-1,
                scale=0.62, theme=CYAN, energy=0.4, sx=1, sy=1)
    return dict(actors=[hero], overlay=("outro", dict(tl=tl)), panel=None)


SCENES = {}


def scene_for(name, dur):
    if name == "gravity":
        if "gravity" not in SCENES:
            SCENES["gravity"] = GravityScene(dur)
        return SCENES["gravity"]
    if name == "momentum":
        if "momentum" not in SCENES:
            SCENES["momentum"] = MomentumScene(dur)
        return SCENES["momentum"]
    if name == "reaction":
        if "reaction" not in SCENES:
            SCENES["reaction"] = ReactionScene(dur)
        return SCENES["reaction"]
    if name == "energy":
        if "energy" not in SCENES:
            SCENES["energy"] = EnergyScene(dur)
        return SCENES["energy"]
    return None


# ---------------------------------------------------------------- overlays
def overlay_gravity(scene, emis, cam, t, info, out):
    p = info["p"]
    for (pts, col, j, a) in info["arcs"]:
        dashed_arc(emis, cam, pts, col, 0.85)
        # apex marker + ruler
        apex = j["v0"] ** 2 / (2 * GRAV)
        ax = j["x"] + j["drift"] * 0.5
        if p > j["t0"] + 0.4:
            aa = clamp((p - (j["t0"] + 0.4)) / 0.4, 0, 1)
            ap = scr(cam, ax, GROUND - apex)
            cv2.circle(emis, ap, 5, tuple(int(c * aa) for c in col), -1,
                       cv2.LINE_AA)
            ruler(scene, emis, cam, ax + 250, GROUND, GROUND - apex, col, aa,
                  f"{apex / PPM:.1f} m")
            B.text(out, "h = v² / 2g", ap[0] + 26, ap[1] - 18, 0.46, col, 1,
                   aa * 0.95, spacing=1.2)
    # live velocity vector on the hero
    hs = info["hs"]
    if hs.get("airborne") and 0.1 < p < 10:
        vy = hs.get("vy", 0)
        arrow(emis, cam, hs["x"], hs["y"] - 240, hs["x"],
              hs["y"] - 240 + clamp(-vy * 0.10, -140, 140), LIME, 3, 12,
              0.8, "v")
    # ground marker for takeoff
    if 1.0 < p < 9:
        for j in (GravityScene.T1, GravityScene.T2):
            gp = scr(cam, j["x"], GROUND)
            cv2.ellipse(emis, gp, (26, 8), 0, 0, 360,
                        tuple(int(c * 0.5) for c in CYAN), 1, cv2.LINE_AA)


def overlay_momentum(scene, emis, cam, t, info, out):
    sc = info["scene"]
    cx, cspeed, p_crate = info["crate"]
    # force arrow on the crate
    if sc.push_t0 <= info["tl"] <= sc.push_t0 + sc.push_dur + 0.1:
        a = 0.9
        arrow(emis, cam, cx - 150, GROUND - 90, cx - 55, GROUND - 90, GOLD, 5,
              18, a, "F")
    # velocity arrow
    if cspeed > 30:
        arrow(emis, cam, cx + 80, GROUND - 60, cx + 80 + cspeed * 0.10,
              GROUND - 60, LIME, 4, 14, 0.85, "v")
    # momentum bar over the crate
    if p_crate > 1:
        p = scr(cam, cx, GROUND - 230)
        wmax = 200
        w = int(wmax * clamp(p_crate / 130.0, 0, 1))
        cv2.rectangle(emis, (p[0] - wmax // 2, p[1]),
                      (p[0] - wmax // 2 + wmax, p[1] + 12),
                      (40, 40, 46), -1, cv2.LINE_AA)
        cv2.rectangle(emis, (p[0] - wmax // 2, p[1]),
                      (p[0] - wmax // 2 + w, p[1] + 12),
                      tuple(int(c) for c in VIOLET), -1, cv2.LINE_AA)
        B.text(out, f"p = {p_crate:.0f} kg·m/s", p[0], p[1] - 12, 0.44, VIOLET,
               1, 0.9, center=True, spacing=1.2)
    # box trail
    box = info["box"]
    if box and box["air"]:
        B.text(out, "5 kg", scr(cam, box["x"], box["y"] - 30)[0],
               scr(cam, box["x"], box["y"] - 30)[1], 0.40, ORANGE, 1, 0.8,
               center=True)


def overlay_reaction(scene, emis, cam, t, info, out):
    sc = info["scene"]
    tl = info["tl"]
    pairs = [(sc.p1, sc.X_H + 60, sc.X_V - 60, sc.J1, sc.M_HERO1, sc.M_VILL1),
             (sc.p2, sc.X_H + 100, sc.X_V - 85, sc.J2, sc.M_HERO2, sc.M_VILL2)]
    for (tp, x1, x2, J, m1, m2) in pairs:
        if tp - 0.02 <= tl <= tp + 0.55:
            a = clamp(1 - (tl - tp) / 0.55, 0, 1)
            cy = GROUND - 250
            arrow(emis, cam, x1, cy, x1 + 105, cy, CRIMSON, 5, 18, a * 0.95, "F")
            arrow(emis, cam, x2, cy, x2 - 105, cy, CYAN, 5, 18, a * 0.95, "F")
            B.text(out, "F  =  −F", int((scr(cam, (x1 + x2) / 2, cy)[0])),
                   int(scr(cam, (x1 + x2) / 2, cy)[1]) - 34, 0.62, WHITE, 2,
                   a, center=True, spacing=3.0)
    # mass tags above heads
    for (x, m, kg, col) in ((sc.X_H + 55, 1, 0, CYAN), (sc.X_V - 55, 1, 0,
                                                        CRIMSON)):
        pass
    tl_now = tl
    masses = [("A", sc.M_HERO1 if tl_now < sc.p2 else sc.M_HERO2, CYAN,
               sc.X_H + 55),
              ("B", sc.M_VILL1 if tl_now < sc.p2 else sc.M_VILL2, CRIMSON,
               sc.X_V - 55)]
    for (tag, m, col, x) in masses:
        p = scr(cam, x, GROUND - 470)
        B.text(out, f"{tag}: {m:.0f} kg", p[0], p[1], 0.46, col, 1, 0.85,
               center=True, spacing=1.4)


def overlay_energy(scene, emis, cam, t, info, out):
    p = info["p"]
    sc = info["scene"]
    # energy chain card
    if p > sc.t_ball:
        a = clamp((p - sc.t_ball) / 0.4, 0, 1)
        x = 90
        y = H - 300
        items = [("GRAVITY", "PE = mgh"), ("IMPACT", "KE = ½mv²"),
                 ("LEVER", "transfer"), ("LAUNCH", "PE again")]
        for i, (k, v) in enumerate(items):
            xx = x + i * 205
            cv2.rectangle(emis, (xx, y), (xx + 175, y + 62),
                          tuple(int(c * 0.30 * a) for c in VIOLET), -1,
                          cv2.LINE_AA)
            cv2.rectangle(emis, (xx, y), (xx + 175, y + 62),
                          tuple(int(c * 0.95 * a) for c in VIOLET), 2,
                          cv2.LINE_AA)
            B.text(out, k, xx + 88, y + 26, 0.38, (200, 210, 225), 1, a,
                   center=True, spacing=1.8)
            B.text(out, v, xx + 88, y + 50, 0.42, VIOLET, 1, a, center=True,
                   spacing=1.0)
            if i < 3:
                arrow(emis, cam, xx * 0 + 0, 0, 0, 0, VIOLET, 2, 8, 0)
                cv2.line(out, (xx + 178, y + 31), (xx + 200, y + 31),
                         tuple(int(c * 0.6 * a) for c in VIOLET), 2,
                         cv2.LINE_AA)
    # launch arrow
    hs = None


# ---------------------------------------------------------------- HUD
def draw_hud(out, t, chapter, slow, law):
    a = clamp((t - 0.2) / 0.5, 0, 1) * clamp((DUR - 0.2 - t) / 0.5, 0, 1)
    # top-left brand
    if int(t * 2) % 2 == 0:
        cv2.circle(out, (70, 66), 6, (60, 60, 245), -1, cv2.LINE_AA)
    B.text(out, "MOTION LAB", 88, 74, 0.56, WHITE, 1, 0.9 * a, spacing=2.6)
    B.text(out, "MONARCHVOICE // PHYSICS EXPLAINER", 88, 100, 0.38,
           (185, 195, 210), 1, 0.6 * a, spacing=1.6)
    # timecode
    tc = "00:%02d:%02d" % (int(t) % 60, int((t * FPS) % FPS))
    B.text(out, tc, W - 74, 66, 0.54, WHITE, 1, 0.72 * a, spacing=1.2)
    B.text(out, "1920×1080 · 30 FPS", W - 74, 92, 0.36, (180, 190, 205), 1,
           0.5 * a, spacing=1.0)
    # slow-mo tag
    if slow < 0.98:
        x = W - 300
        cv2.rectangle(out, (x, 118), (x + 226, 160),
                      (30, 60, 70), -1, cv2.LINE_AA)
        cv2.rectangle(out, (x, 118), (x + 226, 160),
                      tuple(int(c) for c in CYAN), 1, cv2.LINE_AA)
        B.text(out, f"SLOW-MO {slow:.2f}×", x + 113, 146, 0.44, CYAN, 1, a,
               center=True, spacing=1.8)
    # progress
    pr = t / DUR
    y = H - 30
    cv2.line(out, (62, y), (W - 62, y), (58, 62, 70), 1, cv2.LINE_AA)
    cv2.line(out, (62, y), (62 + int((W - 124) * pr), y),
             tuple(int(c) for c in CYAN), 2, cv2.LINE_AA)
    for (a0, b0, nm) in CH:
        x = 62 + int((W - 124) * (a0 / DUR))
        cv2.line(out, (x, y - 6), (x, y + 6), (120, 128, 140), 1, cv2.LINE_AA)
    # corner marks
    m = 34
    for (cx, cy, sx, sy) in [(m, m, 1, 1), (W - m, m, -1, 1),
                             (m, H - 60, 1, -1), (W - m, H - 60, -1, -1)]:
        cv2.line(out, (cx, cy), (cx + 22 * sx, cy), (205, 210, 220), 1,
                 cv2.LINE_AA)
        cv2.line(out, (cx, cy), (cx, cy + 22 * sy), (205, 210, 220), 1,
                 cv2.LINE_AA)


def draw_chapter_ui(out, t, chapter, tl, info):
    # titles for chapter cards
    if chapter == "intro":
        a = clamp((tl - 0.15) / 0.5, 0, 1) * clamp((3.2 - tl) / 0.5, 0, 1)
        B.text(out, "T H E   P H Y S I C S", W // 2, 300, 0.72,
               (200, 210, 225), 1, a * 0.8, center=True, spacing=5.0)
        B.text(out, "OF ACTION", W // 2, 372, 1.55, WHITE, 3, a, center=True,
               spacing=7.0, font=B.FONT_B)
        cv2.line(out, (W // 2 - 210, 406), (W // 2 + 210, 406),
                 tuple(int(c * a) for c in CYAN), 2, cv2.LINE_AA)
        a2 = clamp((tl - 0.9) / 0.6, 0, 1)
        B.text(out, "Stickman physics explainer · easy Urdu + English",
               W // 2, 452, 0.52, (215, 222, 235), 1, a2 * 0.85, center=True,
               spacing=2.0)
        chip_row(out, ["1 · GRAVITY", "2 · MOMENTUM", "3 · REACTION",
                       "4 · ENERGY"], W // 2, 512, a2,
                 CYAN)
    elif chapter == "outro":
        a = clamp(tl / 0.6, 0, 1)
        ov = out.copy()
        cv2.rectangle(ov, (0, 0), (W, H), (6, 5, 12), -1)
        cv2.addWeighted(ov, 0.45 * a, out, 1 - 0.45 * a, 0, out)
        cx, cy = W // 2, 300
        for i, (rr, col, th) in enumerate([(74, CYAN, 3), (94, (150, 110, 220),
                                                          1)]):
            ang0 = (t * (120 if i == 0 else -80)) % 360
            cv2.ellipse(out, (cx, cy), (int(rr * a), int(rr * a)), ang0, 0, 300,
                        tuple(int(c * a) for c in col), th, cv2.LINE_AA)
        B.text(out, "M", cx, cy + 20, 1.2, WHITE, 2, a, center=True,
               font=B.FONT_B)
        a2 = clamp((tl - 0.35) / 0.5, 0, 1)
        B.text(out, "MONARCHVOICE", W // 2, 480, 1.25, (240, 244, 252), 2, a2,
               center=True, spacing=6.0, font=B.FONT_B)
        cv2.line(out, (W // 2 - 210, 508), (W // 2 + 210, 508),
                 tuple(int(c * a2) for c in CYAN), 2, cv2.LINE_AA)
        B.text(out, "M O T I O N   ·   M A S T E R E D", W // 2, 556, 0.55,
               CYAN, 1, a2, center=True, spacing=3.4)
        chip_row(out, ["GRAVITY", "MOMENTUM", "ACTION=REACTION", "ENERGY"],
                 W // 2, 616, clamp((tl - 0.7) / 0.5, 0, 1), VIOLET)


# ---------------------------------------------------------------- frame
def _focus_y(chapter, tl, dur):
    """lowest actor height so the camera can follow jumps"""
    if chapter in ("gravity", "energy"):
        try:
            st = scene_for(chapter, dur).render_state(tl)
            ys = [a["y"] for a in st["actors"]]
            return min(ys)
        except Exception:
            return GROUND
    return GROUND


def render_frame(fi):
    t = fi / FPS
    chapter, tl, dur = chapter_of(t)
    cam = camera_for(t)
    fy = _focus_y(chapter, tl, dur)
    if fy < GROUND - 320:
        cam.y -= min(300.0, (GROUND - 320 - fy) * 0.42)

    scene = np.zeros((H, W, 3), np.uint8)
    emis = np.zeros((H, W, 3), np.uint8)

    # ---- backdrop ----
    bd = B.get_backdrop()
    zoom = 1.0 + (cam.z - 1.0) * 0.45
    cw, chh = W / zoom, H / zoom
    cx = clamp(cam.x - cam.sx * 0.6, cw / 2, B.BW - cw / 2)
    cy = clamp(470 + (cam.y - 470) * 0.35 + (H - chh) * 0.5, chh / 2,
               B.BH - chh / 2)
    x0 = int(clamp(cx - cw / 2, 0, B.BW - cw))
    y0 = int(clamp(cy - chh / 2, 0, B.BH - chh))
    crop = bd[y0:y0 + int(chh), x0:x0 + int(cw)]
    scene = cv2.resize(crop, (W, H), interpolation=cv2.INTER_LINEAR)
    B.draw_floor(scene, emis, cam, t)

    B.IMPACTS = []                       # keep v2 post FX neutral
    info = {}
    actors = []
    slow = 1.0

    if chapter == "intro":
        st = sc_intro(tl, dur)
        actors = st["actors"]
    elif chapter == "outro":
        st = sc_outro(tl, dur)
        actors = st["actors"]
    else:
        sc = scene_for(chapter, dur)
        st = sc.render_state(tl)
        actors = st["actors"]
        slow = st.get("slow", 1.0)
        info = st
        # props: crate + box (momentum)
        if chapter == "momentum":
            cxw, cspeed = st["crate"]
            B.contact_shadow(scene, cam, cxw + 10, GROUND, 120.0)
            draw_crate(scene, emis, cam, cxw, 190, 175, ORANGE,
                       "40 kg", 1.0, cspeed)
            b = st["box"]
            bx = b["x"] if b else MomentumScene.BOX_X
            bs = b["vx"] if b else 0.0
            B.contact_shadow(scene, cam, bx, GROUND, 52.0, 1.0)
            draw_crate(scene, emis, cam, bx, 84, 78, GOLD, "5 kg", 1.0, bs)
        # props: lever + ball (energy)
        if chapter == "energy":
            lever(scene, emis, cam, EnergyScene.PIVOT, st["lever_ang"],
                  EnergyScene.LEVER_L, VIOLET, 1.0, EnergyScene.PIVOT_Y)
            draw_ball(scene, emis, cam, EnergyScene.BALL_X, st["ball"], 58,
                      GOLD, "120 kg")
            B.contact_shadow(scene, cam, EnergyScene.BALL_X, GROUND, 96.0, 0.75)
        if chapter == "gravity":
            pass

    # ---- actors ----
    for a in actors:
        B.contact_shadow(scene, cam, a["x"], GROUND, 168.0,
                         0.25 if a.get("airborne") else 1.0)
        B.draw_figure(scene, emis, cam, a["x"], a["y"], 168 * a.get("scale", 1.0),
                      a["pose"], a["facing"], t, a.get("theme", CYAN), 1.0,
                      a.get("energy", 0.0), 0.0, True, False, False,
                      a.get("sx", 1.0), a.get("sy", 1.0))

    B.draw_rain(emis, cam, t)
    B.draw_embers(emis, cam, t)

    out = B.post_process(scene, emis, t)

    # ---- overlays (crisp, after grade) ----
    ov = info.get("overlay") if info else None
    if ov:
        kind, data = ov
        if kind == "gravity":
            overlay_gravity(scene, out, cam, t, data, out)
        elif kind == "momentum":
            overlay_momentum(scene, out, cam, t, data, out)
        elif kind == "reaction":
            overlay_reaction(scene, out, cam, t, data, out)
        elif kind == "energy":
            overlay_energy(scene, out, cam, t, data, out)
    # blend any remaining emissive additions (glows) into the final frame
    out = np.clip(out.astype(np.float32) + emis.astype(np.float32) * 0.55,
                  0, 255).astype(np.uint8)

    # law badge
    LAWBADGE = {"gravity": ("LAW 01", "GRAVITY", "h = ½ g t²", CYAN),
                "momentum": ("LAW 02", "MOMENTUM", "p = m v   ·   F = m a",
                             ORANGE),
                "reaction": ("LAW 03", "ACTION = REACTION", "F₁ = −F₂",
                             CRIMSON),
                "energy": ("LAW 04", "ENERGY", "E = mgh = ½mv²", VIOLET)}
    if chapter in LAWBADGE:
        num, title, formula, col = LAWBADGE[chapter]
        k = clamp((tl - 0.05) / 0.4, 0, 1)
        law_badge(out, num, title, formula, k, col)

    # live data panel
    if info and info.get("panel"):
        panel = info["panel"]
        ptype, pdata = panel[0], panel[1]
        if ptype == "lines":
            k = clamp((tl - 0.15) / 0.4, 0, 1)
            data_panel(out, W - 372, 190, pdata, k, 320,
                       LAWBADGE.get(chapter, ("", "", "", CYAN))[3])

    # captions
    for (c0, c1, urdu, eng, style) in CAPTIONS.get(chapter, []):
        alpha = blink_alpha(tl, c0, c1, 0.28)
        if alpha > 0.01:
            caption_bar(out, urdu, eng, alpha, CYAN if style == 0 else VIOLET)

    draw_chapter_ui(out, t, chapter, tl, info)
    draw_hud(out, t, chapter, slow, chapter)
    return out


# ---------------------------------------------------------------- main
def main():
    B.init_particles()
    B.build_post_assets()
    B.get_backdrop()

    ff = None
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    if not ff:
        raise RuntimeError("ffmpeg binary not available")

    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-an",
           "-c:v", "libx264", "-preset", "medium", "-crf", "21",
           "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
           "-g", "60", "-movflags", "+faststart", VIDEO_ONLY]
    print(" ".join(cmd), flush=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    t0 = time.time()
    for fi in range(NFRAMES):
        fr = render_frame(fi)
        proc.stdin.write(fr.tobytes())
        if fi % 30 == 0:
            el = time.time() - t0
            print(f"frame {fi}/{NFRAMES}  {el:.1f}s "
                  f"({el / max(1, fi + 1):.3f}s/f)", flush=True)
    proc.stdin.close()
    proc.wait()
    print("video encode done", flush=True)

    if os.path.exists(AUDIO):
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", VIDEO_ONLY, "-i", AUDIO, "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                        "-shortest", "-movflags", "+faststart", OUT],
                       check=True)
    else:
        os.replace(VIDEO_ONLY, OUT)
    sz = os.path.getsize(OUT) / 1e6
    print(f"DONE {OUT}  {sz:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
