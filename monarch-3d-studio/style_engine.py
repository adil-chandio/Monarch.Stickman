#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MONARCHVOICE // REFERENCE STYLE ENGINE
Implements the visual grammar of kaomei/stickman-video-director:
  - white-filled round head with simple expressive face (dot eyes, brows, mouth)
  - filled shirt torso + dark capsule limbs + oval feet
  - flat cel-shaded full-colour cartoon environments (3-4 depth layers)
  - soft contact shadows, 24 fps cadence, wide / close / tracking camera grammar

Used to produce style-proof frames before committing to a full film.
"""

import math
import random

import numpy as np
import cv2

import generate_video_v2 as B

W, H = 1920, 1080
GROUND = 905.0

# ---------------------------------------------------------------- palettes
NAVY = (40, 34, 30)          # BGR dark navy line art
WHITE_HEAD = (250, 250, 249)
COZY = dict(
    sky=(232, 236, 226),
    wall=(206, 216, 219),
    wall2=(184, 197, 203),
    street=(214, 214, 205),
    tree=(150, 186, 132),
    tree_dark=(120, 158, 108),
    table=(196, 206, 178),
    table_dark=(160, 172, 146),
    wood=(150, 172, 196),
    accent=(110, 150, 205),
    line=NAVY,
)
TECH = dict(
    bg=(248, 248, 250),
    grid=(226, 230, 236),
    glass=(238, 216, 120),     # BGR cyan-ish
    glass_edge=(228, 190, 80),
    accent=(240, 170, 60),
)

# ---------------------------------------------------------------- helpers
def E(v, a, b):
    return a if v < a else (b if v > b else v)


def lerp(a, b, t):
    return a + (b - a) * t


def cap(img, p1, p2, color, thick):
    """capsule limb: line with round caps"""
    cv2.line(img, p1, p2, color, thick, cv2.LINE_AA)
    r = max(1, thick // 2)
    cv2.circle(img, p1, r, color, -1, cv2.LINE_AA)
    cv2.circle(img, p2, r, color, -1, cv2.LINE_AA)


def soft_shadow(target, x, y, w, h, strength=0.55):
    """elliptical contact shadow multiplied into the scene"""
    ov = np.zeros((target.shape[0], target.shape[1]), np.float32)
    cv2.ellipse(ov, (int(x), int(y)), (max(2, int(w)), max(2, int(h))), 0, 0,
                360, 1.0, -1)
    ov = cv2.GaussianBlur(ov, (0, 0), max(2, h * 0.8))[:, :, None]
    target[:] = (target.astype(np.float32) *
                 (1 - ov * strength)).astype(np.uint8)


def fill_poly(img, pts, color):
    cv2.fillPoly(img, [np.int32(pts)], color, cv2.LINE_AA)


def round_poly(pts, r, segs=7):
    """corner-rounded polygon points (used for the shirt torso)"""
    P = [np.array(p, np.float32) for p in pts]
    out = []
    n = len(P)
    for i in range(n):
        a, b, c = P[(i - 1) % n], P[i], P[(i + 1) % n]
        va, vc = a - b, c - b
        la, lc = np.linalg.norm(va), np.linalg.norm(vc)
        if la < 1e-3 or lc < 1e-3:
            out.append(b)
            continue
        rr = min(r, la * 0.45, lc * 0.45)
        p0 = b + va / la * rr
        p1 = b + vc / lc * rr
        for k in range(segs + 1):
            t = k / segs
            q = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p1
            out.append(q)
    return np.array([[int(round(p[0])), int(round(p[1]))] for p in out],
                    np.int32)


def stroke_poly(img, pts, color, w=3, closed=True):
    cv2.polylines(img, [np.int32(pts)], closed, color, w, cv2.LINE_AA)


# ---------------------------------------------------------------- character
DEFAULT_CHAR = dict(
    head_fill=WHITE_HEAD, line=NAVY, limb=NAVY,
    limb_w=13, outline=4, shirt=(250, 250, 248), shirt_line=NAVY,
    hat=None, hat_color=(58, 40, 208), face="cozy", shoe=None, hair=None,
    sleeve=True, scale_lw=1.0,
)


def draw_char(img, cam, x, ground_y, scale, pose, facing=1, t=0.0,
              cfg=None, blink_phase=0.0, mood="neutral", squash=(1.0, 1.0)):
    """Reference-style character: filled head + shirt + capsule limbs."""
    c = dict(DEFAULT_CHAR)
    if cfg:
        c.update(cfg)
    J = B.bone_dirs(pose, facing)
    foot = max(J["anL"][1], J["anR"][1], J["ftL"][1], J["ftR"][1])
    for k in list(J.keys()):
        if k == "head_r":
            continue
        J[k] = J[k] - np.array([0.0, foot], np.float32)

    # reference proportions: short torso, legs ~1.5 head diameters
    py = float(J["pelvis"][1])
    for k in ("chest", "neck", "head", "shL", "shR", "elL", "elR", "haL", "haR"):
        J[k] = np.array([J[k][0], py + (J[k][1] - py) * 0.78], np.float32)
    for side in ("L", "R"):
        hip = float(J["hp" + side][1])
        for k in ("kn" + side, "an" + side, "ft" + side):
            J[k] = np.array([J[k][0], hip + (J[k][1] - hip) * 0.86], np.float32)
    # arms keep their length -> rebuild from the new shoulder positions
    ua, fa = 0.46, 0.42

    def _d(deg):
        a = math.radians(deg)
        return np.array([math.sin(a) * facing, math.cos(a)], np.float32)

    for side, ka, kb in (("L", "shL", "elL"), ("R", "shR", "elR")):
        sh = J["sh" + side]
        J["el" + side] = sh + _d(pose[ka]) * ua
        J["ha" + side] = J["el" + side] + _d(pose[ka] + pose[kb]) * fa

    # re-anchor: shorter legs must not lift the character off the ground
    f2 = max(J["anL"][1], J["anR"][1], J["ftL"][1], J["ftR"][1])
    for k in list(J.keys()):
        if k != "head_r":
            J[k] = J[k] - np.array([0.0, f2], np.float32)

    # reference proportions: shoulders as wide as the head is round,
    # hips a touch narrower -> slim trapezoid torso instead of a spike
    J["shL"] = J["shL"] + np.array([-0.19 * facing, 0.0], np.float32)
    J["shR"] = J["shR"] + np.array([0.19 * facing, 0.0], np.float32)
    J["hpL"] = J["hpL"] + np.array([-0.06 * facing, 0.0], np.float32)
    J["hpR"] = J["hpR"] + np.array([0.06 * facing, 0.0], np.float32)
    J["head"] = J["head"] + np.array([0.0, 0.02], np.float32)

    sx, sy = squash

    def P(v):
        wx = x + v[0] * scale * sx
        wy = ground_y + v[1] * scale * sy
        p = cam.apply(wx, wy)
        return (int(p[0]), int(p[1]))

    lw = max(2, int(c["limb_w"] * c["scale_lw"] * scale / 168.0))
    ol = max(2, int(c["outline"] * scale / 168.0))

    # ---- contact shadow ----
    gp = cam.apply(x, ground_y + 3)
    soft_shadow(img, gp[0], gp[1], scale * 0.42, scale * 0.075, 0.5)

    # ---------- far arm (behind torso) ----------
    far = "L" if facing >= 0 else "R"   # front-side arm is drawn on top
    sh_drop = np.array([0.0, 0.05], np.float32)
    cap(img, P(J["sh" + far] + sh_drop), P(J["el" + far]), c["limb"], lw)
    cap(img, P(J["el" + far]), P(J["ha" + far]), c["limb"], lw)
    # far leg
    cap(img, P(J["hp" + far]), P(J["kn" + far]), c["limb"], lw)
    cap(img, P(J["kn" + far]), P(J["an" + far]), c["limb"], lw)
    _foot(img, P(J["an" + far]), facing, scale, c["limb"], c.get("shoe"))

    # ---------- torso (shirt) ----------
    sh_l, sh_r = P(J["shL"]), P(J["shR"])
    hp_l, hp_r = P(J["hpL"]), P(J["hpR"])
    # torso slightly inset from the shoulder joints so the arms read
    # as limbs beside the body (reference does the same)
    ins = 0.035 * scale * sx * cam.z
    def _in(p, sgn):
        return (int(p[0] + sgn * ins), int(p[1]))
    torso = round_poly([_in(sh_l, 1), _in(sh_r, -1), _in(hp_r, -1),
                        _in(hp_l, 1)], max(4, int(scale * 0.035)))
    cv2.fillPoly(img, [torso], c["shirt"], cv2.LINE_AA)
    cv2.polylines(img, [torso], True, c["shirt_line"], ol, cv2.LINE_AA)
    # neck: short navy connector from the shoulder line up into the head
    sh_mid = (J["shL"] + J["shR"]) * 0.5
    cap(img, P(sh_mid + np.array([0, -0.02], np.float32)),
        P(J["head"] + np.array([0, 0.26], np.float32)),
        c["limb"], max(3, lw - 3))

    # ---------- near arm ----------
    near = "R" if facing >= 0 else "L"
    cap(img, P(J["sh" + near] + sh_drop), P(J["el" + near]), c["limb"], lw)
    cap(img, P(J["el" + near]), P(J["ha" + near]), c["limb"], lw)
    if c["sleeve"]:
        # short sleeve cap on the upper arm
        a, b = P(J["sh" + near]), P(J["el" + near])
        mx = (int(lerp(a[0], b[0], 0.42)), int(lerp(a[1], b[1], 0.42)))
        cap(img, a, mx, c["shirt"], lw + 4)
        cv2.circle(img, mx, (lw + 4) // 2, c["shirt"], -1, cv2.LINE_AA)

    # ---------- near leg ----------
    cap(img, P(J["hp" + near]), P(J["kn" + near]), c["limb"], lw)
    cap(img, P(J["kn" + near]), P(J["an" + near]), c["limb"], lw)
    _foot(img, P(J["an" + near]), facing, scale, c["limb"], c.get("shoe"))

    # ---------- head ----------
    hp = P(J["head"])
    hr = max(6, int(J["head_r"] * scale * sx * cam.z))
    cv2.circle(img, hp, hr, c["head_fill"], -1, cv2.LINE_AA)
    cv2.circle(img, hp, hr, c["line"], ol, cv2.LINE_AA)
    _face(img, hp, hr, facing, c, t + blink_phase, mood)

    # ---------- hat / hair ----------
    if c.get("hat") == "beanie":
        col = c.get("hat_color", (58, 40, 208))
        cap_top = (hp[0], hp[1] - int(hr * 0.62))
        cv2.ellipse(img, cap_top, (int(hr * 1.02), int(hr * 0.92)), 0, 180, 360,
                    col, -1, cv2.LINE_AA)
        cv2.ellipse(img, cap_top, (int(hr * 1.02), int(hr * 0.92)), 0, 180, 360,
                    c["line"], ol, cv2.LINE_AA)
        brim = int(hr * 0.16)
        cv2.rectangle(img, (hp[0] - int(hr * 1.02), cap_top[1] - brim),
                      (hp[0] + int(hr * 1.02), cap_top[1] + brim // 2), col, -1)
        cv2.rectangle(img, (hp[0] - int(hr * 1.02), cap_top[1] - brim),
                      (hp[0] + int(hr * 1.02), cap_top[1] + brim // 2),
                      c["line"], ol)
    if c.get("hair") == "bun":
        col = (34, 30, 26)
        cv2.circle(img, (hp[0], hp[1] - int(hr * 1.02)), max(3, int(hr * 0.30)),
                   col, -1, cv2.LINE_AA)
        cv2.ellipse(img, (hp[0], hp[1] + int(hr * 0.02)),
                    (int(hr * 1.02), int(hr * 0.92)), 0, 180, 360, col, -1,
                    cv2.LINE_AA)
    return dict(head=hp, hr=hr, joints=J, near=near)


def _foot(img, ankle, facing, scale, color, shoe=None):
    fx = int(ankle[0] + facing * scale * 0.055 * 1.0)
    fy = int(ankle[1] + scale * 0.012)
    ax, ay = max(3, int(scale * 0.055)), max(2, int(scale * 0.028))
    cv2.ellipse(img, (fx, fy), (ax, ay), 0, 0, 360,
                shoe if shoe else color, -1, cv2.LINE_AA)


def _face(img, p, hr, facing, c, t, mood="neutral"):
    if c.get("face") == "none":
        return
    x, y = p
    f = 1 if facing >= 0 else -1
    ec = c["line"]
    eye_dx = int(hr * 0.34)
    eye_y = y - int(hr * 0.06)
    er = max(2, int(hr * 0.085))
    # blink every ~3.4 s for 6 frames
    blink = (math.sin(t * 1.85) > 0.985)
    for sgn in (-1, 1):
        ex = x + sgn * eye_dx + int(f * hr * 0.06)
        if blink:
            cv2.line(img, (ex - er, eye_y), (ex + er, eye_y), ec,
                     max(2, er), cv2.LINE_AA)
        else:
            cv2.ellipse(img, (ex, eye_y), (max(2, er - 1), er + 1), 0, 0, 360,
                        ec, -1, cv2.LINE_AA)
    # eyebrows
    bw = max(3, int(hr * 0.17))
    by = eye_y - int(hr * 0.26)
    tilt = {"neutral": 0, "happy": -2, "sad": 3, "worried": 4,
            "angry": -4}.get(mood, 0)
    for sgn in (-1, 1):
        ex = x + sgn * eye_dx + int(f * hr * 0.06)
        cv2.line(img, (ex - bw, by + tilt), (ex + bw, by - tilt), ec,
                 max(2, int(hr * 0.055)), cv2.LINE_AA)
    # mouth
    my = y + int(hr * 0.36)
    mw = max(3, int(hr * 0.26))
    mc = ec
    th = max(2, int(hr * 0.05))
    if mood == "happy":
        cv2.ellipse(img, (x + int(f * hr * 0.05), my - int(hr * 0.10)),
                    (mw, int(hr * 0.16)), 0, 15, 165, mc, th, cv2.LINE_AA)
    elif mood in ("sad", "worried"):
        cv2.ellipse(img, (x + int(f * hr * 0.05), my + int(hr * 0.16)),
                    (mw, int(hr * 0.14)), 0, 195, 345, mc, th, cv2.LINE_AA)
    elif mood == "shock":
        cv2.ellipse(img, (x + int(f * hr * 0.05), my), (int(mw * 0.45),
                    int(hr * 0.16)), 0, 0, 360, mc, th, cv2.LINE_AA)
    else:
        cv2.line(img, (x - mw, my), (x + mw, my), mc, th, cv2.LINE_AA)
    # blush for happy
    if mood == "happy":
        for sgn in (-1, 1):
            cv2.ellipse(img, (x + sgn * int(hr * 0.62), y + int(hr * 0.22)),
                        (max(3, int(hr * 0.14)), max(2, int(hr * 0.07))), 0, 0,
                        360, (170, 190, 245), -1, cv2.LINE_AA)


# ---------------------------------------------------------------- backgrounds
def bg_cafe(img, t=0.0):
    """cozy outdoor cafe — flat cel shaded, warm daylight"""
    img[:] = COZY["sky"]
    # distant street + buildings
    cv2.rectangle(img, (0, 520), (W, 760), COZY["street"], -1)
    rng = random.Random(3)
    x = -60
    while x < W + 120:
        bw = rng.randint(150, 300)
        bh = rng.randint(180, 340)
        col = (rng.randint(196, 216), rng.randint(202, 220), rng.randint(200, 214))
        cv2.rectangle(img, (x, 520 - bh), (x + bw, 520), col, -1)
        for wy in range(520 - bh + 40, 500, 80):
            for wx in range(x + 26, x + bw - 40, 70):
                cv2.rectangle(img, (wx, wy), (wx + 34, wy + 46),
                              (222, 226, 222), -1)
        x += bw + rng.randint(20, 60)
    # pavement line + shadow band
    cv2.rectangle(img, (0, 760), (W, int(GROUND) + 40), (206, 208, 200), -1)
    cv2.line(img, (0, 760), (W, 760), (186, 190, 184), 3, cv2.LINE_AA)
    # tree
    cv2.rectangle(img, (300, 420), (346, 800), (120, 140, 158), -1)
    for (cx, cy, r) in [(300, 380, 150), (420, 420, 120), (210, 430, 110)]:
        cv2.circle(img, (cx, cy), r, COZY["tree"], -1, cv2.LINE_AA)
    for (cx, cy, r) in [(340, 340, 90), (250, 400, 70)]:
        cv2.circle(img, (cx, cy), r, COZY["tree_dark"], -1, cv2.LINE_AA)
    # lamp post
    cv2.rectangle(img, (1500, 300), (1520, 860), (150, 156, 168), -1)
    cv2.ellipse(img, (1510, 292), (34, 24), 0, 0, 360, (150, 156, 168), -1)
    # table (round) + mug + book
    cv2.ellipse(img, (1310, 760), (250, 62), 0, 0, 360, COZY["table_dark"],
                -1, cv2.LINE_AA)
    cv2.ellipse(img, (1310, 742), (250, 58), 0, 0, 360, COZY["table"], -1,
                cv2.LINE_AA)
    cv2.rectangle(img, (1290, 760), (1330, 860), (170, 182, 168), -1)
    # book + mug + phone
    cv2.rectangle(img, (1180, 716), (1330, 748), (232, 226, 210), -1)
    cv2.line(img, (1255, 716), (1255, 748), (200, 196, 184), 2)
    cv2.rectangle(img, (1346, 690), (1388, 752), (60, 96, 150), -1)   # mug body
    cv2.ellipse(img, (1367, 690), (21, 8), 0, 0, 360, (196, 216, 232), -1)
    cv2.rectangle(img, (1420, 726), (1520, 748), (70, 62, 58), -1)     # phone
    # chair
    cv2.rectangle(img, (880, 700), (1030, 730), (186, 198, 190), -1)
    cv2.rectangle(img, (880, 560), (906, 730), (186, 198, 190), -1)
    cv2.rectangle(img, (1004, 730), (1030, 860), (170, 182, 174), -1)
    cv2.rectangle(img, (880, 730), (906, 860), (170, 182, 174), -1)
    return img


def bg_tech(img, t=0.0):
    """2A — pure white high-key studio, faint perspective grid, cyan glass UI"""
    img[:] = (250, 250, 252)
    # horizon
    hy = 620
    # perspective floor grid
    for i in range(-14, 15):
        p0 = (W // 2 + i * 40, hy)
        p1 = (W // 2 + i * 260, H + 100)
        cv2.line(img, p0, p1, TECH["grid"], 2, cv2.LINE_AA)
    for j in range(14):
        yy = hy + int((H - hy) * (j / 13.0) ** 2.0)
        cv2.line(img, (0, yy), (W, yy), TECH["grid"], 1, cv2.LINE_AA)
    # soft top light
    ov = np.zeros((H, W), np.float32)
    cv2.ellipse(ov, (W // 2, 120), (900, 340), 0, 0, 360, 1, -1)
    ov = cv2.GaussianBlur(ov, (0, 0), 120)[:, :, None]
    img[:] = np.clip(img.astype(np.float32) + ov * 6, 0, 255).astype(np.uint8)
    # floating glass panels
    panels = [(250, 250, 300, 170), (1450, 220, 280, 200), (1420, 700, 300, 150)]
    for (px, py, pw, ph) in panels:
        ov = img.copy()
        cv2.rectangle(ov, (px, py), (px + pw, py + ph), TECH["glass"], -1,
                      cv2.LINE_AA)
        cv2.addWeighted(ov, 0.20, img, 0.80, 0, img)
        cv2.rectangle(img, (px, py), (px + pw, py + ph), TECH["glass_edge"], 3,
                      cv2.LINE_AA)
        for k in range(3):
            yy = py + 34 + k * 30
            cv2.line(img, (px + 24, yy), (px + pw - 40 - k * 30, yy),
                     (216, 226, 236), 4, cv2.LINE_AA)
    return img


# ---------------------------------------------------------------- camera
class Cam:
    def __init__(self, x=960.0, gy=0.90, z=1.0, focus_y=None, focus_frac=0.5):
        self.x, self.z, self.sx, self.sy = x, z, 0.0, 0.0
        if focus_y is not None:
            # put world point focus_y at focus_frac of the screen height
            self.y = focus_y - ((focus_frac * H) - H * 0.5) / max(0.2, z)
        else:
            self.y = GROUND - ((gy * H) - H * 0.5) / max(0.2, z)

    def apply(self, x, y):
        return ((x - self.x) * self.z + W * 0.5 + self.sx,
                (y - self.y) * self.z + H * 0.5 + self.sy)


# ---------------------------------------------------------------- proofs
def _render_wide(style, tl, SS=1, W2=None, H2=None):
    """render one wide shot; SS>1 supersamples for clean close-up crops"""
    global W, H
    W0, H0 = W, H
    if W2:
        W, H = W2, H2
    img = np.zeros((H, W, 3), np.uint8)
    if style == "cozy":
        bg_cafe(img, tl)
        cam = Cam(940, 0.90, 1.0)
        cfg = dict(shirt=(250, 250, 248), limb=NAVY, limb_w=13, outline=4,
                   face="cozy")
        draw_char(img, cam, 940, GROUND, 260, B.POSES["idle"], facing=1,
                  t=tl, cfg=cfg, mood="happy", blink_phase=0.7)
        p = cam.apply(940 + 0.62 * 260, GROUND - 0.15 * 260)
        cv2.rectangle(img, (int(p[0]) - 22, int(p[1]) - 8),
                      (int(p[0]) + 14, int(p[1]) + 34), (60, 96, 150), -1)
        cv2.ellipse(img, (int(p[0]) - 4, int(p[1]) - 8), (18, 7), 0, 0, 360,
                    (196, 216, 232), -1)
    else:
        bg_tech(img, tl)
        cam = Cam(900, 0.92, 1.0)
        cfg = dict(shirt=(52, 196, 246), limb=(30, 26, 24), limb_w=13,
                   outline=4, face="cozy", hat="beanie",
                   hat_color=(54, 38, 206), shoe=(40, 36, 34))
        draw_char(img, cam, 900, GROUND, 260, B.POSES["walk_a"], facing=1,
                  t=tl, cfg=cfg, mood="neutral")
        p = cam.apply(900 + 150, GROUND - 300)
        cv2.rectangle(img, (int(p[0]), int(p[1])), (int(p[0]) + 210,
                      int(p[1]) + 130), (232, 208, 120), -1, cv2.LINE_AA)
        cv2.rectangle(img, (int(p[0]), int(p[1])), (int(p[0]) + 210,
                      int(p[1]) + 130), (222, 186, 70), 3, cv2.LINE_AA)
    out = img
    W, H = W0, H0
    return out


def frame(style, tl, mode="wide"):
    """wide shot, or a 2x-supersampled head crop (reference close-up grammar)"""
    if mode == "wide":
        return _render_wide(style, tl)
    SS = 2
    big = _render_wide(style, tl, W2=W * SS, H2=H * SS)
    # locate the head in world space, then crop around it
    sc = 260.0
    cam = Cam(940 if style == "cozy" else 900, 0.90 if style == "cozy" else 0.92,
              1.0)
    head_world = (940 if style == "cozy" else 900,
                  GROUND - (1.02 + 0.40) * sc)
    hp = cam.apply(*head_world)
    cx, cy = int(hp[0] * SS), int(hp[1] * SS)
    cw, ch = int(W * SS * 0.27), int(H * SS * 0.34)
    x0 = int(E(cx - cw // 2, 0, W * SS - cw))
    y0 = int(E(cy - ch // 2, 0, H * SS - ch))
    crop = big[y0:y0 + ch, x0:x0 + cw]
    return cv2.resize(crop, (W, H), interpolation=cv2.INTER_AREA)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "style_proof.jpg"
    tiles = []
    for style, mode in [("cozy", "wide"), ("cozy", "close"), ("tech", "wide")]:
        f = frame(style, 1.0, mode)
        tiles.append(cv2.resize(f, (640, 360), interpolation=cv2.INTER_AREA))
    cv2.imwrite(out, np.vstack([np.hstack(tiles)]), [cv2.IMWRITE_JPEG_QUALITY, 92])
    print("wrote", out)
