#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hand-drawn character renderer (v5) — composited over painterly background
plates so the result matches the reference style-4 cozy illustration look.

Key differences from the flat cv2 engine:
  * tapered limbs (thick at the joint, thin at the wrist/ankle)
  * layered soft shading inside head + torso (volume, not flat white)
  * 3x supersampled drawing, downscaled -> clean thin ink lines
  * per-frame "line boil" so the ink feels drawn by hand, not CAD
  * blurred contact shadow that sits in the plate's light
"""

import math

import numpy as np
import cv2

# ---------------------------------------------------------------- palette
INK = (58, 44, 36)          # dark navy-brown ink  (BGR)
SHIRT = (250, 249, 245)
SKIN = (250, 249, 246)
SHADE_COOL = (226, 224, 218)
SHADE_WARM = (208, 214, 224)
BLUSH = (168, 186, 246)

# ---------------------------------------------------------------- proportions
HEAD_R = 0.163
NECK = 0.300
TORSO_TO_SHOULDER = 0.265
HEAD_SEAT = 0.175          # head centre above the neck point
SHW = 0.142                # half shoulder width
HIPW = 0.080
THIGH, SHIN = 0.215, 0.190
UARM, FARM = 0.170, 0.158


def _d(deg, facing):
    a = math.radians(deg)
    return np.array([math.sin(a) * facing, math.cos(a)], np.float32)


def fk(p, facing=1):
    """pose dict (degrees) -> joint positions, y down, feet anchored at 0"""
    lean = math.radians(p.get("lean", 0.0))
    up = np.array([math.sin(lean) * facing, -math.cos(lean)], np.float32)
    right = np.array([-up[1], up[0]], np.float32)

    pelvis = np.array([0.0, p.get("py", 0.0)], np.float32)
    chest = pelvis + up * TORSO_TO_SHOULDER
    neck = pelvis + up * NECK
    head = neck + up * HEAD_SEAT

    J = dict(pelvis=pelvis, chest=chest, neck=neck, head=head)
    J["shL"] = chest + up * 0.020 - right * SHW
    J["shR"] = chest + up * 0.020 + right * SHW
    J["hpL"] = pelvis - right * HIPW
    J["hpR"] = pelvis + right * HIPW

    for side, ka, kb in (("L", "shL", "elL"), ("R", "shR", "elR")):
        sh = J["sh" + side]
        J["el" + side] = sh + _d(p.get(ka, 0), facing) * UARM
        J["ha" + side] = J["el" + side] + _d(
            p.get(ka, 0) + p.get(kb, 0), facing) * FARM

    for side, ka, kb in (("L", "hipL", "knL"), ("R", "hipR", "knR")):
        hp = J["hp" + side]
        J["kn" + side] = hp + _d(p.get(ka, 0), facing) * THIGH
        J["an" + side] = J["kn" + side] + _d(
            p.get(ka, 0) + p.get(kb, 0), facing) * SHIN

    low = max(J["anL"][1], J["anR"][1]) + 0.030
    for k in list(J.keys()):
        J[k] = np.array([J[k][0], J[k][1] - low], np.float32)
    return J


# ---------------------------------------------------------------- poses
def pose_walk(t, cadence=0.95, carry=True, phase=0.0):
    ph = 2 * math.pi * cadence * t + phase
    A, K = 21.0, 30.0
    hipL = A * math.sin(ph)
    knL = -7 - K * max(0.0, math.cos(ph))
    hipR = -hipL
    knR = -7 - K * max(0.0, math.cos(ph + math.pi))
    p = dict(lean=4.0, shL=-17 * math.sin(ph), elL=-6,
             shR=17 * math.sin(ph), elR=-6,
             hipL=hipL, knL=knL, hipR=hipR, knR=knR,
             py=-0.010 * abs(math.cos(ph)))
    if carry:
        p["shR"], p["elR"] = 42.0, 46.0
    return p


def pose_idle(t, carry=True):
    b = math.sin(t * 1.6) * 1.6
    p = dict(lean=2.0, shL=-6 + b, elL=-4, shR=6 - b, elR=-4,
             hipL=3, knL=4, hipR=-3, knR=4, py=-0.004 * math.sin(t * 1.6))
    if carry:
        p["shR"], p["elR"] = 42.0, 46.0
    return p


def pose_sip(t):
    """raise the cup to the mouth and back"""
    k = 0.5 - 0.5 * math.cos(min(1.0, max(0.0, t)) * math.pi)
    return dict(lean=2.0, shL=-6, elL=-4,
                shR=42 + 46 * k, elR=46 + 34 * k,
                hipL=3, knL=4, hipR=-3, knR=4, py=0.0)


# ---------------------------------------------------------------- helpers
def _taper(img, a, b, r1, r2, color):
    """tapered capsule: thick at the joint, thin at the extremity"""
    a = np.asarray(a, np.float64)
    b = np.asarray(b, np.float64)
    v = b - a
    L = float(np.hypot(v[0], v[1]))
    if L < 1e-6:
        cv2.circle(img, (int(a[0]), int(a[1])), int(max(1, r1)), color, -1,
                   cv2.LINE_AA)
        return
    n = np.array([-v[1], v[0]]) / L
    pts = np.array([a + n * r1, b + n * r2, b - n * r2, a - n * r1])
    cv2.fillPoly(img, [pts.astype(np.int32)], color, cv2.LINE_AA)
    cv2.circle(img, (int(a[0]), int(a[1])), int(max(1, r1)), color, -1,
               cv2.LINE_AA)
    cv2.circle(img, (int(b[0]), int(b[1])), int(max(1, r2)), color, -1,
               cv2.LINE_AA)


def _round(pts, r, segs=6):
    P_ = [np.array(p, np.float64) for p in pts]
    out = []
    n = len(P_)
    for i in range(n):
        a, b, c = P_[(i - 1) % n], P_[i], P_[(i + 1) % n]
        va, vc = a - b, c - b
        la, lc = np.linalg.norm(va), np.linalg.norm(vc)
        if la < 1e-6 or lc < 1e-6:
            out.append(b)
            continue
        rr = min(r, la * 0.45, lc * 0.45)
        p0, p1 = b + va / la * rr, b + vc / lc * rr
        for k in range(segs + 1):
            t = k / segs
            out.append((1 - t) ** 2 * p0 + 2 * (1 - t) * t * b + t * t * p1)
    return np.array([[int(round(q[0])), int(round(q[1]))] for q in out],
                    np.int32)


def _soft(img, cx, cy, rx, ry, color, alpha, blur):
    h, w = img.shape[:2]
    x0, x1 = int(max(0, cx - rx * 2)), int(min(w, cx + rx * 2))
    y0, y1 = int(max(0, cy - ry * 2)), int(min(h, cy + ry * 2))
    if x1 <= x0 or y1 <= y0:
        return
    m = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.ellipse(m, (int(cx - x0), int(cy - y0)), (max(1, int(rx)),
                max(1, int(ry))), 0, 0, 360, 255, -1, cv2.LINE_AA)
    if blur > 0:
        m = cv2.GaussianBlur(m, (0, 0), blur)
    a = (m.astype(np.float32) / 255.0 * alpha)[..., None]
    reg = img[y0:y1, x0:x1].astype(np.float32)
    reg = reg * (1 - a) + np.array(color, np.float32) * a
    img[y0:y1, x0:x1] = reg.astype(np.uint8)


def _boil(J, t, amp):
    """tiny per-frame perturbation: ink lines breathe like hand drawing"""
    out = {}
    for i, (k, v) in enumerate(J.items()):
        sx = math.sin(t * 7.3 + i * 2.1) * 0.55 + math.sin(t * 3.1 + i) * 0.45
        sy = math.cos(t * 6.1 + i * 1.7) * 0.55 + math.cos(t * 2.7 + i) * 0.45
        out[k] = np.array([v[0] + sx * amp, v[1] + sy * amp], np.float32)
    return out


# ---------------------------------------------------------------- face
def _face(img, p, r, facing, mood, t, blink_at):
    """dot eyes, brows, 3-point mouth, blush — reference face grammar"""
    x, y = int(p[0]), int(p[1])
    f = 1 if facing >= 0 else -1
    lw = max(2, int(r * 0.052))
    ed = r * 0.34
    ey = int(y - r * 0.04)
    er = max(2, int(r * 0.080))

    blink = ((t - blink_at) % 3.7) < 0.13
    for sgn in (-1, 1):
        ex = int(x + sgn * ed + f * r * 0.05)
        if blink:
            cv2.line(img, (int(ex - er * 1.2), ey), (int(ex + er * 1.2), ey),
                     INK, lw, cv2.LINE_AA)
        else:
            cv2.ellipse(img, (ex, ey), (er, int(er * 1.18)), 0, 0, 360, INK,
                        -1, cv2.LINE_AA)

    bw = r * 0.155
    by = ey - r * 0.27
    tilt = {"neutral": 0.030, "happy": -0.030, "curious": -0.055,
            "sad": 0.070}.get(mood, 0.030)
    for sgn in (-1, 1):
        ex = x + sgn * ed + f * r * 0.05
        cv2.line(img, (int(ex - bw), int(by + tilt * r * sgn)),
                 (int(ex + bw), int(by - tilt * r * sgn)), INK,
                 max(2, int(lw * 0.92)), cv2.LINE_AA)

    my = int(y + r * 0.33)
    mw = r * 0.23
    if mood in ("happy", "curious"):
        cv2.ellipse(img, (int(x + f * r * 0.04), int(my - r * 0.09)),
                    (int(mw), int(r * 0.16)), 0, 12, 168, INK, lw, cv2.LINE_AA)
    elif mood == "sad":
        cv2.ellipse(img, (int(x + f * r * 0.04), int(my + r * 0.12)),
                    (int(mw), int(r * 0.14)), 0, 195, 348, INK, lw,
                    cv2.LINE_AA)
    else:
        cv2.line(img, (int(x - mw * 0.7), my), (int(x + mw * 0.8), my - 1),
                 INK, lw, cv2.LINE_AA)

    if mood == "happy":
        for sgn in (-1, 1):
            cx_ = int(x + sgn * r * 0.60 + f * r * 0.05)
            cy_ = int(y + r * 0.20)
            m = np.zeros(img.shape[:2], np.uint8)
            cv2.ellipse(m, (cx_, cy_), (int(r * 0.19), int(r * 0.11)), 0, 0,
                        360, 255, -1, cv2.LINE_AA)
            m = cv2.GaussianBlur(m, (0, 0), r * 0.06)
            a = (m.astype(np.float32) / 255.0 * 0.50)[..., None]
            reg = img.astype(np.float32)
            img[:] = (reg * (1 - a) + np.array(BLUSH, np.float32) * a
                      ).astype(np.uint8)


# ---------------------------------------------------------------- body
def draw(bg, gy, cx, scale, pose, facing=1, t=0.0, mood="happy",
         blink_at=0.6, cup=True, ss=3, boil=0.0022):
    """composite the character onto bg (BGR); gy = ground line in px."""
    J = _boil(fk(pose, facing), t, boil)

    sx = [cx + v[0] * scale for v in J.values()]
    sy = [gy + v[1] * scale for v in J.values()]
    pad = 0.26 * scale
    x0 = int(max(0, min(sx) - pad))
    x1 = int(min(bg.shape[1], max(sx) + pad))
    y0 = int(max(0, min(sy) - pad))
    y1 = int(min(bg.shape[0], max(sy) + pad * 0.55))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return dict(head=None)

    W, H = (x1 - x0) * ss, (y1 - y0) * ss
    V = np.zeros((H, W, 3), np.uint8)      # colour layer
    M = np.zeros((H, W), np.uint8)         # silhouette

    lw = max(2, int(scale * 0.0072 * ss))
    ink = INK

    def Pv(v):
        return ((cx + v[0] * scale - x0) * ss, (gy + v[1] * scale - y0) * ss)

    def limb(a_, b_, r1, r2, paint=(True, True)):
        pa, pb = Pv(a_), Pv(b_)
        _taper(V, pa, pb, r1 * scale * ss, r2 * scale * ss, ink)
        _taper(M, pa, pb, r1 * scale * ss, r2 * scale * ss, 255)

    near = "R" if facing >= 0 else "L"
    far = "L" if facing >= 0 else "R"

    # ---- far limbs, torso, near limbs, feet, head, cup  (same order as before)
    sd = np.array([facing * 0.012, 0.028], np.float32)
    limb(J["sh" + far] + sd, J["el" + far], 0.029, 0.023)
    limb(J["el" + far], J["ha" + far], 0.024, 0.018)
    limb(J["hp" + far] + np.array([0, 0.012], np.float32),
         J["kn" + far], 0.036, 0.028)
    limb(J["kn" + far], J["an" + far], 0.029, 0.020)

    sh_l, sh_r = Pv(J["shL"]), Pv(J["shR"])
    hp_l, hp_r = Pv(J["hpL"]), Pv(J["hpR"])
    tb = 0.020 * scale * ss
    ins = 0.030 * scale * ss      # torso inset: arms sit OUTSIDE the shirt
    tl = _round([[sh_l[0] + ins * 0.55, sh_l[1] - tb * 0.9],
                 [sh_r[0] - ins * 0.55, sh_r[1] - tb * 0.9],
                 [hp_r[0] + ins * 0.15, hp_r[1]],
                 [hp_l[0] - ins * 0.15, hp_l[1]]],
                max(3, 0.022 * scale * ss))
    cv2.fillPoly(V, [tl], SHIRT, cv2.LINE_AA)
    cv2.fillPoly(M, [tl], 255, cv2.LINE_AA)

    _taper(V, Pv(J["neck"]),
           Pv(J["head"] + np.array([0, 0.105], np.float32)),
           lw * 0.60, lw * 0.60, ink)
    _taper(M, Pv(J["neck"]),
           Pv(J["head"] + np.array([0, 0.105], np.float32)),
           lw * 0.60, lw * 0.60, 255)

    limb(J["hp" + near] + np.array([0, 0.012], np.float32),
         J["kn" + near], 0.036, 0.028)
    limb(J["kn" + near], J["an" + near], 0.029, 0.020)
    limb(J["sh" + near] + sd, J["el" + near], 0.029, 0.023)
    limb(J["el" + near], J["ha" + near], 0.024, 0.018)

    for side in ("L", "R"):
        p = Pv(J["an" + side])
        c = (int(p[0] + facing * 0.026 * scale * ss),
             int(p[1] + 0.010 * scale * ss))
        ax = (max(2, int(0.040 * scale * ss)), max(2, int(0.023 * scale * ss)))
        cv2.ellipse(V, c, ax, 0, 0, 360, ink, -1, cv2.LINE_AA)
        cv2.ellipse(M, c, ax, 0, 0, 360, 255, -1, cv2.LINE_AA)

    hp = Pv(J["head"])
    hr = HEAD_R * scale * ss
    hp = (hp[0], hp[1])
    cv2.circle(V, (int(hp[0]), int(hp[1])), int(hr), SKIN, -1, cv2.LINE_AA)
    cv2.circle(M, (int(hp[0]), int(hp[1])), int(hr), 255, -1, cv2.LINE_AA)

    if cup:
        key = "ha" + near
        cp = Pv(J[key] + np.array([facing * 0.004, -0.024], np.float32))
        _cup(V, M, cp[0], cp[1], scale * ss / 520.0, ink)

    # ---- cel shading on the light fills only (ink stays pure)
    light = (V.mean(axis=2) > 170).astype(np.uint8) * 255
    light = np.maximum(light, 0)
    mask_shade = np.zeros((H, W), np.uint8)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # head: cool shadow on the lower-back quadrant
    dh = np.sqrt(((xx - hp[0]) / max(1.0, hr)) ** 2 +
                 ((yy - hp[1]) / max(1.0, hr)) ** 2)
    ang = np.arctan2((yy - hp[1]) / max(1.0, hr),
                     (xx - hp[0]) / max(1.0, hr))
    head_w = np.clip((dh - 0.42) / 0.55, 0, 1) *         np.clip((np.cos(ang - (-facing * 2.2)) + 0.35) / 1.35, 0, 1)
    mask_shade = np.maximum(mask_shade,
                            (np.clip(head_w, 0, 1) * 190).astype(np.uint8))
    # torso: soft vertical falloff on the back edge
    tx = (xx - (sh_l[0] + sh_r[0]) * 0.5) / max(1.0, 0.28 * scale * ss)
    torso_w = np.clip(((-facing) * tx + 0.55) / 1.4, 0, 1) * 0.55
    mask_shade = np.maximum(mask_shade, (torso_w * 190).astype(np.uint8))

    mask_shade = cv2.bitwise_and(mask_shade, light)
    mask_shade = cv2.bitwise_and(mask_shade, M)
    mask_shade = cv2.GaussianBlur(mask_shade, (0, 0), 0.7 * ss)
    a_sh = (mask_shade.astype(np.float32) / 255.0 * 1.0)[..., None]
    V = (V.astype(np.float32) * (1 - a_sh) +
         np.array((206, 208, 212), np.float32) * a_sh)

    # ---- ink outlines on top (crisp, never shaded)
    cv2.polylines(V, [tl], True, ink, lw, cv2.LINE_AA)
    cv2.circle(V, (int(hp[0]), int(hp[1])), int(hr), ink, lw, cv2.LINE_AA)
    _face(V, hp, hr, facing, mood, t, blink_at)
    V = np.clip(V, 0, 255).astype(np.uint8)

    # ---- downscale + composite
    Vs = cv2.resize(V, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    Ms = cv2.resize(M, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    alpha = np.clip(Ms.astype(np.float32) / 255.0 * 1.06, 0, 1)[..., None]
    reg = bg[y0:y1, x0:x1].astype(np.float32)
    comp = reg * (1 - alpha) + Vs.astype(np.float32) * alpha

    # ---- contact shadow in the plate
    _soft(bg, cx + facing * 0.02 * scale, gy + 0.002 * scale,
          0.20 * scale, 0.042 * scale, (120, 116, 110), 0.42,
          max(6, 0.032 * scale))

    bg[y0:y1, x0:x1] = np.clip(comp, 0, 255).astype(np.uint8)
    return dict(head=(hp[0] / ss + x0, hp[1] / ss + y0), hr=hr / ss)


def _cup(V, M, cx, cy, k, ink):
    """reference-style takeaway cup (white body, blue-grey band, lid)"""
    hh, tw, bw = 30 * k, 20 * k, 15 * k
    cx, cy = float(cx), float(cy)
    pts = np.array([[cx - tw, cy - hh], [cx + tw, cy - hh],
                    [cx + bw, cy + hh * 0.55], [cx - bw, cy + hh * 0.55]],
                   np.int32)
    cv2.fillPoly(V, [pts], (250, 250, 247), cv2.LINE_AA)
    cv2.fillPoly(M, [pts], 255, cv2.LINE_AA)
    y0, y1 = int(cy - hh * 0.42), int(cy + hh * 0.10)
    band = np.array([[cx - tw * 0.93, y0], [cx + tw * 0.93, y0],
                     [cx + bw * 1.12, y1], [cx - bw * 1.12, y1]], np.int32)
    cv2.fillPoly(V, [band], (168, 150, 128), cv2.LINE_AA)
    lid = ((int(cx), int(cy - hh)), (int(tw * 1.06), max(2, int(hh * 0.16))))
    cv2.ellipse(V, lid[0], lid[1], 0, 0, 360, (238, 238, 233), -1, cv2.LINE_AA)
    cv2.polylines(V, [pts], True, ink, max(2, int(2.4 * k)), cv2.LINE_AA)
    cv2.ellipse(V, lid[0], lid[1], 0, 0, 360, ink, max(2, int(2.4 * k)),
                cv2.LINE_AA)
