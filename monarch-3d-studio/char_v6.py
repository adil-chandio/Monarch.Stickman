#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
char_v6 — hand-painted character matched to the style-4 reference frame.

Measured from the reference (head diameter = 2R):
  * ink outline  ~0.095 R      (bold, confident; my old one was 0.044 R)
  * upper arm    ~0.22 R radius,  forearm ~0.16 R   (old: 0.36 R -> too thick)
  * thigh        ~0.30 R,        shin     ~0.21 R
  * eye          ~0.32 R wide, 0.42 R tall, centres +/-0.30 R
  * head is a slightly tall oval (rx = R, ry = 1.055 R)
  * torso width ~1.24 R at the shoulders, near-straight sides
  * fills are warm off-white, ink is dark navy #2D2E42

Compositing unifies the character with the painting:
  * radial shading on the head, vertical falloff on the torso
  * warm key light on the light side, cool fill in shadow
  * silhouette softened ~0.5 px + paper grain
  * contact shadow tinted by the plate underneath
"""

import math

import numpy as np
import cv2

# ink / fill sampled from the reference frame
INK = (66, 46, 45)            # BGR  (RGB 45,46,66)
SHIRT = (250, 249, 245)       # warm off-white
SKIN = (252, 251, 247)
SHADE = (198, 196, 192)       # cool shadow colour
BLUSH = (150, 170, 235)

# --- everything below is in head-radius units (R = 1.0), measured from the
# --- reference frames: 8.1 R tall, torso 0.90 R wide, limbs 0.26 R thick.
HEAD_RX = 1.00
HEAD_RY = 1.05
SHW = 0.42                    # half torso width at the shoulders
SHW_HIP = 0.55                # the shirt flares toward the hips
TORSO = 2.80                  # shoulder line -> hip
NECK = 0.10
HEAD_SEAT = 1.05              # neck point -> head centre

UARM, FARM = 1.13, 0.94
THIGH, SHIN = 1.58, 1.46

R_UARM, R_FARM = 0.132, 0.110
R_THIGH, R_SHIN = 0.150, 0.115

LINE = 0.056                      # ink width, in R units


def _d(deg, facing):
    a = math.radians(deg)
    return np.array([math.sin(a) * facing, math.cos(a)], np.float32)


def fk(p, facing=1):
    lean = math.radians(p.get("lean", 0.0))
    up = np.array([math.sin(lean) * facing, -math.cos(lean)], np.float32)
    right = np.array([-up[1], up[0]], np.float32)

    pelvis = np.array([0.0, p.get("py", 0.0)], np.float32)
    chest = pelvis + up * TORSO
    neck = chest + up * NECK
    head = neck + up * HEAD_SEAT

    J = dict(pelvis=pelvis, chest=chest, neck=neck, head=head)
    J["shL"] = chest - right * SHW
    J["shR"] = chest + right * SHW
    J["hpL"] = pelvis - right * SHW_HIP
    J["hpR"] = pelvis + right * SHW_HIP

    for s, ka, kb in (("L", "shL", "elL"), ("R", "shR", "elR")):
        J["el" + s] = J["sh" + s] + _d(p.get(ka, 0), facing) * UARM
        J["ha" + s] = J["el" + s] + _d(p.get(ka, 0) + p.get(kb, 0),
                                        facing) * FARM
    for s, ka, kb in (("L", "hipL", "knL"), ("R", "hipR", "knR")):
        J["kn" + s] = J["hp" + s] + _d(p.get(ka, 0), facing) * THIGH
        J["an" + s] = J["kn" + s] + _d(p.get(ka, 0) + p.get(kb, 0),
                                        facing) * SHIN

    low = max(J["anL"][1], J["anR"][1]) + 0.028
    for k in list(J.keys()):
        J[k] = np.array([J[k][0], J[k][1] - low], np.float32)
    return J


# ------------------------------------------------------------------ poses
def pose_walk(t, cadence=1.0, carry=True, phase=0.0):
    ph = 2 * math.pi * cadence * t + phase
    A, K = 19.0, 30.0
    hipL = A * math.sin(ph)
    p = dict(lean=3.5,
             shL=-15 * math.sin(ph), elL=-5,
             shR=15 * math.sin(ph), elR=-5,
             hipL=hipL, knL=-6 - K * max(0.0, math.cos(ph)),
             hipR=-hipL, knR=-6 - K * max(0.0, math.cos(ph + math.pi)),
             py=-0.009 * abs(math.cos(ph)))
    if carry:
        p["shR"], p["elR"] = 40.0, 44.0
    return p


def pose_idle(t, carry=True):
    b = math.sin(t * 1.5) * 1.4
    p = dict(lean=1.8, shL=-5 + b, elL=-3, shR=5 - b, elR=-3,
             hipL=3, knL=3, hipR=-3, knR=3, py=-0.003)
    if carry:
        p["shR"], p["elR"] = 40.0, 44.0
    return p


def pose_sip(k):
    """k in 0..1 -> raise the cup toward the mouth and back"""
    return dict(lean=1.8, shL=-5, elL=-3,
                shR=40 + 44 * k, elR=44 + 30 * k,
                hipL=3, knL=3, hipR=-3, knR=3, py=0.0)


# ------------------------------------------------------------------ utils
def _cap(img, a, b, r1, r2, color):
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


def _soft(img, cx, cy, rx, ry, color, alpha, blur):
    h, w = img.shape[:2]
    x0, x1 = int(max(0, cx - rx * 2.2)), int(min(w, cx + rx * 2.2))
    y0, y1 = int(max(0, cy - ry * 2.2)), int(min(h, cy + ry * 2.2))
    if x1 <= x0 or y1 <= y0:
        return
    m = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.ellipse(m, (int(cx - x0), int(cy - y0)),
                (max(1, int(rx)), max(1, int(ry))), 0, 0, 360, 255, -1,
                cv2.LINE_AA)
    if blur > 0:
        m = cv2.GaussianBlur(m, (0, 0), blur)
    a = (m.astype(np.float32) / 255.0 * alpha)[..., None]
    reg = img[y0:y1, x0:x1].astype(np.float32)
    img[y0:y1, x0:x1] = (reg * (1 - a) +
                         np.array(color, np.float32) * a).astype(np.uint8)


def _boil(J, t, amp):
    out = {}
    for i, (k, v) in enumerate(J.items()):
        sx = math.sin(t * 6.9 + i * 2.3) * 0.6 + math.sin(t * 3.3 + i) * 0.4
        sy = math.cos(t * 5.7 + i * 1.9) * 0.6 + math.cos(t * 2.9 + i) * 0.4
        out[k] = np.array([v[0] + sx * amp, v[1] + sy * amp], np.float32)
    return out


# ------------------------------------------------------------------ face
def _face(img, p, rx, ry, facing, mood, t, blink_at, lw):
    x, y = float(p[0]), float(p[1])
    f = 1 if facing >= 0 else -1
    ex_off = rx * 0.285
    ey = y - ry * 0.12
    ew, eh = rx * 0.150, ry * 0.190

    blink = ((t - blink_at) % 3.9) < 0.12
    for sgn in (-1, 1):
        ex = x + sgn * ex_off + f * rx * 0.035
        if blink:
            cv2.line(img, (int(ex - ew * 1.05), int(ey)),
                     (int(ex + ew * 1.05), int(ey)), INK, int(lw * 0.9),
                     cv2.LINE_AA)
        else:
            cv2.ellipse(img, (int(ex), int(ey)), (int(ew), int(eh)), 0, 0,
                        360, INK, -1, cv2.LINE_AA)

    # brows: thin, slightly angled strokes
    by = ey - ry * 0.46
    bw = rx * 0.150
    tilt = {"neutral": 0.020, "happy": -0.020, "curious": -0.045,
            "sad": 0.060}.get(mood, 0.020)
    for sgn in (-1, 1):
        ex = x + sgn * ex_off + f * rx * 0.035
        cv2.line(img, (int(ex - bw), int(by + tilt * ry * sgn)),
                 (int(ex + bw), int(by - tilt * ry * sgn)), INK,
                 max(2, int(lw * 0.46)), cv2.LINE_AA)

    my = y + ry * 0.34
    mw = rx * 0.175
    if mood in ("happy", "curious"):
        cv2.ellipse(img, (int(x + f * rx * 0.03), int(my - ry * 0.10)),
                    (int(mw), int(ry * 0.13)), 0, 14, 166, INK,
                    max(2, int(lw * 0.70)), cv2.LINE_AA)
    elif mood == "sad":
        cv2.ellipse(img, (int(x + f * rx * 0.03), int(my + ry * 0.10)),
                    (int(mw), int(ry * 0.11)), 0, 196, 344, INK,
                    max(2, int(lw * 0.70)), cv2.LINE_AA)
    else:
        cv2.line(img, (int(x - mw * 0.55), int(my)),
                 (int(x + mw * 0.60), int(my - ry * 0.02)), INK,
                 max(2, int(lw * 0.70)), cv2.LINE_AA)

    if mood == "happy":
        for sgn in (-1, 1):
            _soft(img, x + sgn * rx * 0.62, y + ry * 0.24,
                  rx * 0.145, ry * 0.085, BLUSH, 0.34, max(2, rx * 0.055))


# ------------------------------------------------------------------ draw
def draw(bg, gy, cx, scale, pose, facing=1, t=0.0, mood="happy",
         blink_at=0.6, cup=True, ss=3, boil=0.0020, light=-1):
    """composite onto a painterly plate; light=-1 means key light from left"""
    J = _boil(fk(pose, facing), t, boil)

    xs = [cx + v[0] * scale for v in J.values()]
    ys = [gy + v[1] * scale for v in J.values()]
    pad = max(0.30 * scale, (HEAD_RY + 0.12) * scale)
    x0 = int(max(0, min(xs) - pad))
    x1 = int(min(bg.shape[1], max(xs) + pad))
    y0 = int(max(0, min(ys) - pad))
    y1 = int(min(bg.shape[0], max(ys) + pad * 0.5))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None

    Wd, Hd = (x1 - x0) * ss, (y1 - y0) * ss
    V = np.zeros((Hd, Wd, 3), np.uint8)
    M = np.zeros((Hd, Wd), np.uint8)

    lw = max(2, int(LINE * scale * ss))

    def Pv(v):
        return ((cx + v[0] * scale - x0) * ss,
                (gy + v[1] * scale - y0) * ss)

    def limb(a, b, r1, r2, colour=INK):
        pa, pb = Pv(a), Pv(b)
        _cap(V, pa, pb, r1 * scale * ss, r2 * scale * ss, colour)
        _cap(M, pa, pb, r1 * scale * ss, r2 * scale * ss, 255)

    near = "R" if facing >= 0 else "L"
    far = "L" if facing >= 0 else "R"

    # ---- far limbs
    limb(J["sh" + far], J["el" + far], R_UARM, R_FARM)
    limb(J["el" + far], J["ha" + far], R_FARM, R_FARM * 0.82)
    limb(J["hp" + far], J["kn" + far], R_THIGH, R_SHIN)
    limb(J["kn" + far], J["an" + far], R_SHIN, R_SHIN * 0.78)

    # ---- torso: rounded rectangle, near-straight sides
    sh_l, sh_r = Pv(J["shL"]), Pv(J["shR"])
    hp_l, hp_r = Pv(J["hpL"]), Pv(J["hpR"])
    rad = max(3, 0.020 * scale * ss)
    tl = np.array([[sh_l[0], sh_l[1]], [sh_r[0], sh_r[1]],
                   [hp_r[0], hp_r[1]], [hp_l[0], hp_l[1]]], np.int32)
    cv2.fillPoly(V, [tl], SHIRT, cv2.LINE_AA)
    cv2.fillPoly(M, [tl], 255, cv2.LINE_AA)

    # neck
    nk_a, nk_b = Pv(J["neck"]), Pv(J["head"])
    _cap(V, nk_a, nk_b, lw * 0.5, lw * 0.5, INK)
    _cap(M, nk_a, nk_b, lw * 0.5, lw * 0.5, 255)

    # ---- near limbs
    limb(J["hp" + near], J["kn" + near], R_THIGH, R_SHIN)
    limb(J["kn" + near], J["an" + near], R_SHIN, R_SHIN * 0.78)
    limb(J["sh" + near], J["el" + near], R_UARM, R_FARM)
    limb(J["el" + near], J["ha" + near], R_FARM, R_FARM * 0.82)

    # ---- feet
    for s in ("L", "R"):
        p = Pv(J["an" + s])
        c = (int(p[0] + facing * 0.030 * scale * ss),
             int(p[1] + 0.008 * scale * ss))
        ax = (max(2, int(0.045 * scale * ss)), max(2, int(0.024 * scale * ss)))
        cv2.ellipse(V, c, ax, 0, 0, 360, INK, -1, cv2.LINE_AA)
        cv2.ellipse(M, c, ax, 0, 0, 360, 255, -1, cv2.LINE_AA)

    # ---- head
    hp = Pv(J["head"])
    rx, ry = HEAD_RX * scale * ss, HEAD_RY * scale * ss
    cv2.ellipse(V, (int(hp[0]), int(hp[1])), (int(rx), int(ry)), 0, 0, 360,
                SKIN, -1, cv2.LINE_AA)
    cv2.ellipse(M, (int(hp[0]), int(hp[1])), (int(rx), int(ry)), 0, 0, 360,
                255, -1, cv2.LINE_AA)

    if cup:
        cp = Pv(J["ha" + near] + np.array([facing * 0.004, -0.026],
                                          np.float32))
        _cup(V, M, cp[0], cp[1], scale * ss, INK)

    # ---- volume shading (inside the fills only)
    lightp = -1 if light < 0 else 1
    yy, xx = np.mgrid[0:Hd, 0:Wd].astype(np.float32)
    lightk = (V.mean(axis=2) > 170).astype(np.uint8) * 255

    dhx = (xx - (hp[0] - lightp * rx * 0.30)) / max(1.0, rx * 1.45)
    dhy = (yy - (hp[1] - ry * 0.30)) / max(1.0, ry * 1.45)
    head_s = np.clip((np.sqrt(dhx ** 2 + dhy ** 2) - 0.35) / 0.85, 0, 1)

    tx = (xx - (sh_l[0] + sh_r[0]) * 0.5) / max(1.0, abs(sh_r[0] - sh_l[0]) * 0.9)
    torso_s = np.clip((lightp * tx + 0.45) / 1.2, 0, 1) * 0.55
    ty = np.clip((yy - (sh_l[1] + hp_l[1]) * 0.5) /
                 max(1.0, abs(hp_l[1] - sh_l[1]) * 0.8), 0, 1) * 0.25
    shade = np.clip(np.maximum(head_s * 0.85, torso_s + ty), 0, 0.72)

    m = cv2.bitwise_and(lightk, M)
    m = cv2.GaussianBlur(m, (0, 0), max(1.0, 0.012 * scale * ss))
    a = (m.astype(np.float32) / 255.0 * shade)[..., None]
    V = V.astype(np.float32) * (1 - a) + np.array(SHADE, np.float32) * a
    V = np.clip(V, 0, 255).astype(np.uint8)

    # ---- limb volume: shade the underside, rim-light the top edge
    limbmask = cv2.subtract(M, np.zeros_like(M))
    inner = cv2.erode(limbmask, np.ones((3, 3), np.uint8), 1)
    dark_fill = (V.mean(axis=2) < 110).astype(np.uint8) * 255
    limbz = cv2.bitwise_and(inner, cv2.bitwise_and(
        np.full_like(M, 255), dark_fill))
    # gradient across each limb: lighter on the key-light side
    yy2, xx2 = np.mgrid[0:Hd, 0:Wd].astype(np.float32)
    grad = np.clip((xx2 - (cx - x0) * ss) / max(1.0, 0.30 * scale * ss) *
                   (-lightp) * 0.5 + 0.5, 0, 1)
    rim = (grad * 46).astype(np.float32)
    a_rim = (cv2.GaussianBlur(limbz, (0, 0), max(1.0, 0.012 * scale * ss))
             .astype(np.float32) / 255.0)[..., None]
    V = np.clip(V.astype(np.float32) + a_rim * rim[..., None] *
                np.array([1.0, 0.98, 0.94], np.float32), 0, 255).astype(np.uint8)
    # deepen the far side
    shade_l = (np.clip((1 - grad) * 0.55, 0, 1) * 34)[..., None]
    V = np.clip(V.astype(np.float32) - a_rim * shade_l, 0, 255).astype(np.uint8)

    # ---- hatch strokes on the shadow side (hand-drawn shading)
    hatch = np.zeros((Hd, Wd), np.uint8)
    step = max(4, int(0.055 * scale * ss))
    x_from = int(sh_l[0] if lightp > 0 else sh_r[0])
    x_to = int(x_from + (0.28 * (sh_r[0] - sh_l[0]) if lightp > 0
                         else -0.28 * (sh_r[0] - sh_l[0])))
    y_a, y_b = int(sh_l[1]), int(hp_l[1])
    for k in range(-abs(y_b - y_a) - step * 2, abs(x_to - x_from) + step * 2,
                   step):
        p1 = (x_from + k, y_a - step)
        p2 = (x_from + k + (y_b - y_a), y_b + step)
        cv2.line(hatch, p1, p2, 255, max(1, int(0.010 * scale * ss)),
                 cv2.LINE_AA)
    hatch = cv2.bitwise_and(hatch, M)
    hatch = cv2.bitwise_and(hatch, lightk)
    hb = cv2.GaussianBlur(hatch, (0, 0), 0.6 * ss)
    ha = (hb.astype(np.float32) / 255.0 * 0.16)[..., None]
    V = (V.astype(np.float32) * (1 - ha) + np.array((150, 150, 152),
                                                   np.float32) * ha)
    V = np.clip(V, 0, 255).astype(np.uint8)

    # ---- ink outlines last, so they stay bold and clean
    tv = _round(tl, int(rad))
    cv2.polylines(V, [tv.reshape(-1, 1, 2)], True, INK, lw, cv2.LINE_AA)
    cv2.ellipse(V, (int(hp[0]), int(hp[1])), (int(rx), int(ry)), 0, 0, 360,
                INK, lw, cv2.LINE_AA)
    _face(V, (hp[0], hp[1]), rx, ry, facing, mood, t, blink_at, lw)

    # ---- downscale
    Vs = cv2.resize(V, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    Ms = cv2.resize(M, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    alpha = Ms.astype(np.float32) / 255.0

    # ================= integrate with the painting =================
    reg = bg[y0:y1, x0:x1].astype(np.float32)

    # --- scene light: pull the character toward the plate's ambient colour
    local = cv2.GaussianBlur(reg, (0, 0), max(12, 0.10 * scale))
    lum = local.mean(axis=2, keepdims=True)
    tint = np.clip(local / np.maximum(lum, 1e-3), 0.80, 1.22)
    gain = np.clip(lum / 232.0, 0.72, 1.04)
    ambient = tint * gain
    k_amb = 0.34
    Vs = Vs.astype(np.float32) * ((1 - k_amb) + k_amb * ambient)

    # --- ambient occlusion inside the silhouette edges
    er = cv2.erode(Ms, np.ones((3, 3), np.uint8), iterations=1)
    ao = cv2.GaussianBlur((Ms - er).astype(np.float32) / 255.0, (0, 0),
                          max(1.2, 0.018 * scale))
    ao = np.clip(ao, 0, 1)[..., None]
    Vs = Vs * (1 - 0.22 * ao)

    # --- soft contact + cast shadow, drawn as plate darkening
    sh = np.zeros(alpha.shape, np.uint8)
    cxpix = cx - x0
    sh_y = gy - y0
    lightp = -1 if light < 0 else 1
    # core under the feet
    cv2.ellipse(sh, (int(cxpix + lightp * 0.05 * scale), int(sh_y)),
                (max(3, int(0.30 * scale)), max(2, int(0.048 * scale))),
                0, 0, 360, 210, -1, cv2.LINE_AA)
    # stretched cast shadow away from the key light
    far_x = cxpix - lightp * 1.15 * scale
    poly = np.array([[cxpix - lightp * 0.16 * scale, sh_y - 0.02 * scale],
                     [cxpix - lightp * 0.22 * scale, sh_y + 0.03 * scale],
                     [far_x, sh_y + 0.10 * scale],
                     [far_x, sh_y + 0.02 * scale]], np.int32)
    cv2.fillPoly(sh, [poly], 120, cv2.LINE_AA)
    sh = cv2.GaussianBlur(sh, (0, 0), max(4, 0.035 * scale))
    shf = (sh.astype(np.float32) / 255.0 * 0.62)[..., None]
    reg = reg * (1 - shf * 0.80)

    # --- composite, then a hair of grain so it sits in the paper texture
    al = cv2.GaussianBlur(alpha, (0, 0), 0.7)[..., None]
    out = reg * (1 - al) + Vs * al
    rng = np.random.default_rng(int(abs(t) * 977) % 99991)
    out = out + rng.normal(0, 1.9, (out.shape[0], out.shape[1], 1)) * al
    bg[y0:y1, x0:x1] = np.clip(out, 0, 255).astype(np.uint8)

    return dict(head=(hp[0] / ss + x0, hp[1] / ss + y0),
                hr=rx / ss, hand=(J["ha" + near][0], J["ha" + near][1]))


def _round(pts, r, segs=5):
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
            t_ = k / segs
            out.append((1 - t_) ** 2 * p0 + 2 * (1 - t_) * t_ * b +
                        t_ * t_ * p1)
    return np.array([[int(round(q[0])), int(round(q[1]))] for q in out],
                    np.int32)


def _cup(V, M, cx, cy, scale, ink):
    k = scale / 620.0
    hh, tw, bw = 26 * k, 17 * k, 13 * k
    pts = np.array([[cx - tw, cy - hh], [cx + tw, cy - hh],
                    [cx + bw, cy + hh * 0.5], [cx - bw, cy + hh * 0.5]],
                   np.int32)
    cv2.fillPoly(V, [pts], (246, 246, 242), cv2.LINE_AA)
    cv2.fillPoly(M, [pts], 255, cv2.LINE_AA)
    y0, y1 = int(cy - hh * 0.40), int(cy + hh * 0.08)
    band = np.array([[cx - tw * 0.95, y0], [cx + tw * 0.95, y0],
                     [cx + bw * 1.12, y1], [cx - bw * 1.12, y1]], np.int32)
    cv2.fillPoly(V, [band], (150, 132, 112), cv2.LINE_AA)
    lid = ((int(cx), int(cy - hh)), (int(tw * 1.05), max(2, int(hh * 0.17))))
    cv2.ellipse(V, lid[0], lid[1], 0, 0, 360, (240, 240, 236), -1,
                cv2.LINE_AA)
    lw = max(2, int(2.6 * k))
    cv2.polylines(V, [pts], True, ink, lw, cv2.LINE_AA)
    cv2.ellipse(V, lid[0], lid[1], 0, 0, 360, ink, lw, cv2.LINE_AA)
