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
PANTS = (88, 70, 62)          # BGR slate trousers, ink outline keeps them cloth
SHOE = (52, 42, 38)           # near-black shoes
SOLE = (120, 120, 118)
SKIN_HAND = (248, 247, 241)

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
    # the head is a separate mass: it can nod / lag behind the torso
    tilt = math.radians(p.get("tilt", 0.0) * facing)
    hv = up * HEAD_SEAT
    hv = np.array([hv[0] * math.cos(tilt) - hv[1] * math.sin(tilt),
                   hv[0] * math.sin(tilt) + hv[1] * math.cos(tilt)], np.float32)
    head = neck + hv

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


def pose_seated(t=0.0, lean=5.0):
    """seated on a bistro chair: thighs forward, shins vertical, feet planted"""
    b = math.sin(t * 1.4) * 1.2
    return dict(lean=lean + b * 0.25,
                shL=-8, elL=-6, shR=8, elR=-6,
                hipL=80, knL=-80, hipR=78, knR=-78,
                py=0.0)


def _solve_arm(pose, target, facing=1, side="R"):
    """exact 2-bone IK in the (sin,cos) angle convention used by fk()"""
    J = fk(pose, facing)
    S = J["sh" + side]
    T = np.array(target, np.float32)
    v = T - S
    d = float(np.hypot(*v))
    if d < 1e-4:
        return None
    u, f = UARM, FARM
    dc = min(max(d, abs(u - f) + 1e-3), u + f - 1e-3)
    if dc != d:                      # clamp unreachable targets onto the reach
        v = v * (dc / d)
        d = dc
    cosA = (u * u + d * d - f * f) / (2 * u * d)
    A = math.acos(max(-1.0, min(1.0, cosA)))
    base_ang = math.atan2(v[0] * facing, v[1])
    out = []
    for sgn in (+1, -1):
        sh = (base_ang + sgn * A) * 180.0 / math.pi
        E = S + np.array([math.sin(math.radians(sh)) * facing,
                          math.cos(math.radians(sh))]) * u
        v2 = T - E
        phi = math.degrees(math.atan2(v2[0] * facing, v2[1]))
        out.append((sh, phi - sh, E))
    return out


def arm_to(pose, target, facing=1, side="R"):
    """pose the given arm so the hand lands on target (elbow forward)"""
    sols = _solve_arm(pose, target, facing, side)
    if not sols:
        return dict(pose)
    # keep the elbow DOWN (a sipping arm folds low, never up at the ear)
    best = max(sols, key=lambda s: s[2][1])
    p = dict(pose)
    if side == "R":
        p["shR"], p["elR"] = best[0], best[1]
    else:
        p["shL"], p["elL"] = best[0], best[1]
    return p


def reach_arm(pose, target, facing=1, side="R", iters=4):
    return arm_to(pose, target, facing, side)


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
def _face(img, p, rx, ry, facing, mood, t, blink_at, lw, tilt=0.0):
    """face drawn in head-local coords, then nodded by `tilt` degrees"""
    x, y = float(p[0]), float(p[1])
    f = 1 if facing >= 0 else -1
    ta = math.radians(tilt * facing)

    def RT(u, v):
        return (x + u * math.cos(ta) - v * math.sin(ta),
                y + u * math.sin(ta) + v * math.cos(ta))

    def F(cx_, cy_, rx_, ry_, a0, a1, col, w):
        cx_, cy_ = RT(cx_, cy_)
        cv2.ellipse(img, (int(cx_), int(cy_)), (int(rx_), int(ry_)),
                    math.degrees(ta), a0, a1, col, w, cv2.LINE_AA)

    ex_off = rx * 0.285
    ey = -ry * 0.12
    ew, eh = rx * 0.150, ry * 0.190
    blink = ((t - blink_at) % 3.9) < 0.12
    for sgn in (-1, 1):
        ex = sgn * ex_off + f * rx * 0.035
        if blink:
            ax, ay = RT(ex - ew * 1.05, ey)
            bx, by = RT(ex + ew * 1.05, ey)
            cv2.line(img, (int(ax), int(ay)), (int(bx), int(by)), INK,
                     int(lw * 0.9), cv2.LINE_AA)
        else:
            cx_, cy_ = RT(ex, ey)
            cv2.ellipse(img, (int(cx_), int(cy_)), (int(ew), int(eh)),
                        math.degrees(ta), 0, 360, INK, -1, cv2.LINE_AA)

    # brows
    by = ey - ry * 0.46
    bw = rx * 0.150
    bt = {"neutral": 0.020, "happy": -0.020, "curious": -0.045,
          "sad": 0.060}.get(mood, 0.020)
    for sgn in (-1, 1):
        ex = sgn * ex_off + f * rx * 0.035
        ax, ay = RT(ex - bw, by + bt * ry * sgn)
        bx, by2 = RT(ex + bw, by - bt * ry * sgn)
        cv2.line(img, (int(ax), int(ay)), (int(bx), int(by2)), INK,
                 max(2, int(lw * 0.46)), cv2.LINE_AA)

    my = ry * 0.34
    mw = rx * 0.175
    if mood in ("happy", "curious"):
        F(f * rx * 0.03, my - ry * 0.10, mw, ry * 0.13, 14, 166, INK,
          max(2, int(lw * 0.70)))
    elif mood == "sad":
        F(f * rx * 0.03, my + ry * 0.10, mw, ry * 0.11, 196, 344, INK,
          max(2, int(lw * 0.70)))
    elif mood == "sip":
        cx_, cy_ = RT(f * rx * 0.06, my - ry * 0.04)
        cv2.ellipse(img, (int(cx_), int(cy_)), (int(rx * 0.085),
                    int(ry * 0.075)), 0, 0, 360, INK, -1, cv2.LINE_AA)
    else:
        ax, ay = RT(-mw * 0.55, my)
        bx, by2 = RT(mw * 0.60, my - ry * 0.02)
        cv2.line(img, (int(ax), int(ay)), (int(bx), int(by2)), INK,
                 max(2, int(lw * 0.70)), cv2.LINE_AA)

    if mood in ("happy", "sip"):
        for sgn in (-1, 1):
            bx, by2 = RT(sgn * rx * 0.62, ry * 0.24)
            _soft(img, bx, by2, rx * 0.145, ry * 0.085, BLUSH, 0.34,
                  max(2, rx * 0.055))


# ------------------------------------------------------------------ draw
def draw(bg, gy, cx, scale, pose, facing=1, t=0.0, mood="happy",
         blink_at=0.6, cup=True, ss=3, boil=0.0020, light=-1,
         front_arm=False):
    """composite onto a painterly plate; light=-1 means key light from left"""
    sq = float(pose.get("squash", 1.0))
    J = fk(pose, facing)
    if abs(sq - 1.0) > 1e-3:
        sxq = 1.0 / math.sqrt(sq)
        J = {k: np.array([v[0] * sxq, v[1] * sq], np.float32)
             for k, v in J.items()}
    J = _boil(J, t, boil)

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
    mug_pos = [None]

    def _draw_cup():
        if not cup:
            return
        cp = Pv(J["ha" + near] + np.array([-facing * 0.070, -0.070],
                                          np.float32))
        mug_pos[0] = (cp[0] / ss + x0, cp[1] / ss + y0)
        _cup(V, M, cp[0], cp[1], scale * ss, INK,
             tilt=pose.get('cup_tilt', -9.0))

    def sleeve(a_, b_, rsh, rarm, colour=INK):
        """let a limb taper from the shoulder into a thinner forearm"""
        pa, pb = Pv(a_), Pv(b_)
        _cap(V, pa, pb, rsh * scale * ss, rarm * scale * ss, colour)
        _cap(M, pa, pb, rsh * scale * ss, rarm * scale * ss, 255)

    def hand(p_, r_, colour=INK):
        c = Pv(p_)
        rr = r_ * scale * ss
        # thumb sits on the body side of the fist
        th = (c[0] - facing * rr * 0.55, c[1] - rr * 0.72)
        cv2.circle(V, (int(th[0]), int(th[1])), int(rr * 0.46), colour, -1,
                   cv2.LINE_AA)
        cv2.circle(M, (int(th[0]), int(th[1])), int(rr * 0.46), 255, -1,
                   cv2.LINE_AA)
        cv2.circle(V, (int(c[0]), int(c[1])), int(rr), colour, -1,
                   cv2.LINE_AA)
        cv2.circle(M, (int(c[0]), int(c[1])), int(rr), 255, -1,
                   cv2.LINE_AA)

    def shoe(ankle, toe_dir, near=False, pitch=0.0):
        """side-view boot: rounded toe, slight heel, thick sole"""
        p = Pv(ankle)
        R = scale * ss
        heel = p[0] - toe_dir * 0.22 * R
        toe = p[0] + toe_dir * 0.52 * R
        top = p[1] - 0.06 * R
        sole_y = p[1] + 0.20 * R
        col = SHOE if near else tuple(int(v * 0.86) for v in SHOE)

        # upper: rounded wedge
        up = np.array([[heel, top + 0.04 * R],
                       [heel + toe_dir * 0.06 * R, top],
                       [toe - toe_dir * 0.16 * R, top + 0.01 * R],
                       [toe, top + 0.09 * R],
                       [toe, sole_y - 0.055 * R],
                       [heel, sole_y - 0.055 * R]], np.int32)
        if abs(pitch) > 0.5:
            def RP(pt):
                dx, dy = pt[0] - p[0], pt[1] - p[1]
                a_ = math.radians(pitch * toe_dir)
                return (p[0] + dx * math.cos(a_) - dy * math.sin(a_),
                        p[1] + dx * math.sin(a_) + dy * math.cos(a_))
            up = np.array([RP(q) for q in up], np.int32)
        cv2.fillPoly(V, [up], col, cv2.LINE_AA)
        cv2.fillPoly(M, [up], 255, cv2.LINE_AA)
        # rounded toe cap
        cv2.ellipse(V, (int(toe - toe_dir * 0.015 * R), int(top + 0.10 * R)),
                    (int(0.055 * R), int(0.075 * R)), 0, 0, 360, col, -1,
                    cv2.LINE_AA)
        cv2.ellipse(M, (int(toe - toe_dir * 0.015 * R), int(top + 0.10 * R)),
                    (int(0.055 * R), int(0.075 * R)), 0, 0, 360, 255, -1,
                    cv2.LINE_AA)
        # sole
        sole = np.array([[heel - toe_dir * 0.01 * R, sole_y - 0.062 * R],
                         [toe, sole_y - 0.062 * R],
                         [toe, sole_y], [heel - toe_dir * 0.01 * R,
                                         sole_y]], np.int32)
        cv2.fillPoly(V, [sole], SOLE, cv2.LINE_AA)
        cv2.fillPoly(M, [sole], 255, cv2.LINE_AA)
        # only the top edge and the sole line get ink, not a full outline
        cv2.line(V, (int(heel), int(top + 0.04 * R)),
                 (int(toe - toe_dir * 0.10 * R), int(top + 0.02 * R)), INK,
                 max(2, int(lw * 0.6)), cv2.LINE_AA)
        cv2.line(V, (int(heel), int(sole_y - 0.062 * R)),
                 (int(toe), int(sole_y - 0.062 * R)), INK,
                 max(2, int(lw * 0.55)), cv2.LINE_AA)

    def cuff(ankle, r):
        p = Pv(ankle)
        R = scale * ss
        cv2.circle(V, (int(p[0]), int(p[1] - 0.04 * R)), int(r * R * 1.35),
                   PANTS, -1, cv2.LINE_AA)
        cv2.circle(M, (int(p[0]), int(p[1] - 0.04 * R)), int(r * R * 1.35),
                   255, -1, cv2.LINE_AA)

    # ================= far leg (trousers + shoe) =================
    OL = 0.026
    sleeve(J["hp" + far], J["kn" + far], R_THIGH + OL, R_SHIN + OL, INK)
    sleeve(J["kn" + far], J["an" + far], R_SHIN + OL, R_SHIN * 0.80 + OL, INK)
    sleeve(J["hp" + far], J["kn" + far], R_THIGH, R_SHIN, PANTS)
    sleeve(J["kn" + far], J["an" + far], R_SHIN, R_SHIN * 0.80, PANTS)
    cuff(J["an" + far], R_SHIN * 0.80)
    shoe(J["an" + far], facing, near=False)

    # ================= far arm (ink, thin) =================
    sleeve(J["sh" + far], J["el" + far], R_UARM, R_FARM)
    sleeve(J["el" + far], J["ha" + far], R_FARM, R_FARM * 0.82)
    hand(J["ha" + far], R_FARM * 1.15)

    # ================= shirt =================
    sh_l, sh_r = Pv(J["shL"]), Pv(J["shR"])
    hp_l, hp_r = Pv(J["hpL"]), Pv(J["hpR"])
    rad = max(3, 0.020 * scale * ss)
    flare = 0.13 * (abs(sh_r[0] - sh_l[0]))          # hem wider than shoulders
    hem = 0.020 * scale * ss
    tl = np.array([[sh_l[0] + lw * 0.2, sh_l[1] - lw * 0.4],
                   [sh_r[0] - lw * 0.2, sh_r[1] - lw * 0.4],
                   [hp_r[0] + flare, hp_r[1] + hem],
                   [hp_l[0] - flare, hp_l[1] + hem]], np.int32)
    tl = _round(tl, max(3, int(0.030 * scale * ss)))
    cv2.fillPoly(V, [tl.reshape(-1, 1, 2)], SHIRT, cv2.LINE_AA)
    cv2.fillPoly(M, [tl.reshape(-1, 1, 2)], 255, cv2.LINE_AA)

    # waistband / trouser top, so the legs read as trousers
    wb = np.array([[hp_l[0], hp_l[1] - 0.014 * scale * ss],
                   [hp_r[0], hp_r[1] - 0.014 * scale * ss],
                   [hp_r[0], hp_r[1] + 0.030 * scale * ss],
                   [hp_l[0], hp_l[1] + 0.030 * scale * ss]], np.int32)
    cv2.fillPoly(V, [wb], PANTS, cv2.LINE_AA)
    cv2.fillPoly(M, [wb], 255, cv2.LINE_AA)

    # neck
    nk_a, nk_b = Pv(J["neck"]), Pv(J["head"])
    _cap(V, nk_a, nk_b, lw * 0.5, lw * 0.5, INK)
    _cap(M, nk_a, nk_b, lw * 0.5, lw * 0.5, 255)

    # collar: two small navy wedges at the top of the shirt
    cw = 0.055 * scale * ss
    col_l = np.array([[sh_l[0], sh_l[1] - lw * 0.4],
                      [sh_l[0] + cw * 1.25, sh_l[1] - lw * 0.2],
                      [sh_l[0] + cw * 0.35, sh_l[1] + cw * 0.75]], np.int32)
    col_r = np.array([[sh_r[0], sh_r[1] - lw * 0.4],
                      [sh_r[0] - cw * 1.25, sh_r[1] - lw * 0.2],
                      [sh_r[0] - cw * 0.35, sh_r[1] + cw * 0.75]], np.int32)
    for c_ in (col_l, col_r):
        cv2.fillPoly(V, [c_], INK, cv2.LINE_AA)
        cv2.fillPoly(M, [c_], 255, cv2.LINE_AA)

    # placket + buttons (a shirt, not a slab)
    mid_x = (sh_l[0] + sh_r[0]) * 0.5 + facing * 0.10 * scale * ss
    p_top = (mid_x, (sh_l[1] + sh_r[1]) * 0.5 + 0.10 * scale * ss)
    p_bot = (mid_x + facing * 0.10 * scale * ss, (hp_l[1] + hp_r[1]) * 0.5)
    cv2.line(V, (int(p_top[0]), int(p_top[1])), (int(p_bot[0]), int(p_bot[1])),
             INK, max(2, int(lw * 0.38)), cv2.LINE_AA)
    for fr_ in (0.30, 0.58, 0.84):
        bx = p_top[0] + (p_bot[0] - p_top[0]) * fr_ + facing * 0.085 * scale * ss
        by = p_top[1] + (p_bot[1] - p_top[1]) * fr_
        cv2.circle(V, (int(bx), int(by)), max(2, int(0.019 * scale * ss)),
                   (150, 140, 136), -1, cv2.LINE_AA)
    # hem: a soft fold curve instead of a straight cut
    hy = (hp_l[1] + hp_r[1]) * 0.5 + 0.035 * scale * ss
    cv2.line(V, (int(hp_l[0] - flare * 0.9), int(hy - 0.03 * scale * ss)),
             (int(p_bot[0]), int(hy + 0.05 * scale * ss)), INK,
             max(2, int(lw * 0.34)), cv2.LINE_AA)
    cv2.line(V, (int(p_bot[0]), int(hy + 0.05 * scale * ss)),
             (int(hp_r[0] + flare * 0.9), int(hy - 0.03 * scale * ss)), INK,
             max(2, int(lw * 0.34)), cv2.LINE_AA)

    # ================= near leg =================
    sleeve(J["hp" + near], J["kn" + near], R_THIGH + OL, R_SHIN + OL, INK)
    sleeve(J["kn" + near], J["an" + near], R_SHIN + OL, R_SHIN * 0.80 + OL, INK)
    sleeve(J["hp" + near], J["kn" + near], R_THIGH, R_SHIN, PANTS)
    sleeve(J["kn" + near], J["an" + near], R_SHIN, R_SHIN * 0.80, PANTS)
    cuff(J["an" + near], R_SHIN * 0.80)
    shoe(J["an" + near], facing, near=True,
         pitch=pose.get("foot" + near, 0.0))

    # ================= near arm: ink, with a short shirt sleeve =================
    def _near_arm():
        sleeve(J["sh" + near], J["el" + near], R_UARM, R_FARM)
        sleeve(J["el" + near], J["ha" + near], R_FARM, R_FARM * 0.82)
        hand(J["ha" + near], R_FARM * 1.15)
        # short sleeve: shirt cap over the top of the upper arm
        sa, sb = Pv(J["sh" + near]), Pv(J["el" + near])
        if front_arm:
            _draw_cup()
            return
        fr = 0.32
        mid = (int(sa[0] + (sb[0] - sa[0]) * fr),
               int(sa[1] + (sb[1] - sa[1]) * fr))
        _cap(V, sa, mid, (R_UARM + 0.090) * scale * ss,
             (R_UARM + 0.040) * scale * ss, SHIRT)
        _cap(M, sa, mid, (R_UARM + 0.090) * scale * ss,
             (R_UARM + 0.040) * scale * ss, 255)
        cv2.line(V, mid, (int(mid[0]), int(mid[1])), INK,
                 max(2, int(lw * 0.35)), cv2.LINE_AA)
        _draw_cup()

    if not front_arm:
        _near_arm()

    # ---- head
    hp = Pv(J["head"])
    rx, ry = HEAD_RX * scale * ss, HEAD_RY * scale * ss
    cv2.ellipse(V, (int(hp[0]), int(hp[1])), (int(rx), int(ry)), 0, 0, 360,
                SKIN, -1, cv2.LINE_AA)
    cv2.ellipse(M, (int(hp[0]), int(hp[1])), (int(rx), int(ry)), 0, 0, 360,
                255, -1, cv2.LINE_AA)

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
    ha = (hb.astype(np.float32) / 255.0 * 0.085)[..., None]
    V = (V.astype(np.float32) * (1 - ha) + np.array((150, 150, 152),
                                                   np.float32) * ha)
    V = np.clip(V, 0, 255).astype(np.uint8)

    # ---- ink outlines last, so they stay bold and clean
    tv = _round(tl, int(rad))
    cv2.polylines(V, [tv.reshape(-1, 1, 2)], True, INK, lw, cv2.LINE_AA)
    cv2.ellipse(V, (int(hp[0]), int(hp[1])), (int(rx), int(ry)), 0, 0, 360,
                INK, lw, cv2.LINE_AA)
    _face(V, (hp[0], hp[1]), rx, ry, facing, mood, t, blink_at, lw,
          tilt=pose.get('tilt', 0.0))
    if front_arm:
        _near_arm()          # arm crosses in front of the face on a sip
    else:
        _draw_cup()

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
                hr=rx / ss, mug=mug_pos[0],
                hand=(cx + J["ha" + near][0] * scale,
                      gy + J["ha" + near][1] * scale))


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


def _cup(V, M, cx, cy, scale, ink, tilt=-9.0):
    """a small tilted coffee cup (0.47 R tall) with a handle, held by the fist"""
    k = scale
    hh = 0.275 * k
    tw = 0.170 * k
    bw = 0.120 * k
    ang = tilt

    def rot(px, py):
        r = math.radians(ang)
        return (cx + px * math.cos(r) - py * math.sin(r),
                cy + px * math.sin(r) + py * math.cos(r))

    body = np.array([rot(-tw, -hh), rot(tw, -hh), rot(bw, hh), rot(-bw, hh)],
                    np.int32)
    lw = max(2, int(0.028 * k))
    hp = np.array([rot(tw * 0.72, -hh * 0.42), rot(tw * 1.80, -hh * 0.30),
                   rot(tw * 1.74, hh * 0.30), rot(tw * 0.78, hh * 0.36)],
                  np.int32)
    cv2.polylines(V, [hp], False, ink, lw, cv2.LINE_AA)
    cv2.fillPoly(V, [body], (246, 246, 242), cv2.LINE_AA)
    cv2.fillPoly(M, [body], 255, cv2.LINE_AA)
    cc = rot(0, -hh * 0.84)
    cv2.ellipse(V, (int(cc[0]), int(cc[1])), (int(tw * 0.86), int(0.055 * k)),
                ang, 0, 360, (96, 74, 56), -1, cv2.LINE_AA)
    cv2.ellipse(V, (int(cc[0]), int(cc[1])), (int(tw * 0.86), int(0.055 * k)),
                ang, 0, 360, ink, max(1, lw - 1), cv2.LINE_AA)
    bn = 0.40 * k
    band = np.array([rot(-tw * 0.80, hh * 0.12), rot(tw * 0.80, hh * 0.12),
                     rot(tw * 0.72, bn), rot(-tw * 0.72, bn)], np.int32)
    cv2.fillPoly(V, [band], (212, 226, 236), cv2.LINE_AA)
    cv2.polylines(V, [body], True, ink, lw, cv2.LINE_AA)
    hl = np.array([rot(-tw * 0.58, -hh * 0.62), rot(-tw * 0.32, -hh * 0.56),
                   rot(-tw * 0.36, hh * 0.28), rot(-tw * 0.62, hh * 0.22)],
                  np.int32)
    cv2.fillPoly(V, [hl], (255, 255, 253), cv2.LINE_AA)
