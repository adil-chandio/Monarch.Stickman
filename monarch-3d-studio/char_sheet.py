#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
char_sheet.py — the model sheet for the cozy character.

Everything is measured in head-radius units (R).  The sheet is the spec that
char_v8 / proof_clip_v8 must match:  front, 3/4, side, back, six expressions,
the props, the palette and the proportion bar.

    python3 char_sheet.py   ->  char_sheet_v7.jpg
"""

import math

import numpy as np
import cv2

import char_v7 as CH

SS = 1                       # draw straight at sheet resolution
W, H = 2400, 1700

INK = CH.INK
SHIRT = CH.SHIRT
SKIN = CH.SKIN
PANTS = (88, 70, 62)          # slate, ink outline keeps them cloth
SHOE = (58, 48, 44)
SOLE = (150, 150, 146)
PAPER = (238, 242, 242)
SAGE = (150, 168, 150)
TERRA = (110, 132, 176)      # BGR terracotta
BLUSH = (150, 170, 235)

GY = 1030                    # ground line on the sheet (canvas px)


# ------------------------------------------------------------------ helpers
def T(img, s, p, size, col=INK, sp=1.0, thick=1):
    """letter-spaced label; returns the x after the last glyph"""
    x, y = p
    for ch in s:
        cv2.putText(img, ch, (int(x), int(y)), cv2.FONT_HERSHEY_DUPLEX, size,
                    col, thick, cv2.LINE_AA)
        (w, _), _ = cv2.getTextSize(ch, cv2.FONT_HERSHEY_DUPLEX, size, thick)
        x += (w + sp * size * 10.0)
    return x


def cap(img, a, b, r1, r2, colour=INK):
    cv2.line(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), colour,
             max(2, int((r1 + r2) * 1.0)), cv2.LINE_AA)
    for p, r in ((a, r1), (b, r2)):
        cv2.circle(img, (int(p[0]), int(p[1])), max(1, int(r)), colour, -1,
                   cv2.LINE_AA)


def disc(img, p, r, colour=INK):
    cv2.circle(img, (int(p[0]), int(p[1])), max(1, int(r)), colour, -1,
               cv2.LINE_AA)


def ring(img, p, r, colour=INK, w=3):
    cv2.circle(img, (int(p[0]), int(p[1])), max(1, int(r)), colour, max(1, w),
               cv2.LINE_AA)


def paper(w, h):
    img = np.full((h, w, 3), PAPER, np.uint8)
    rng = np.random.default_rng(7)
    n = rng.normal(0, 3.2, (h, w, 1))
    img = np.clip(img + n, 0, 255).astype(np.uint8)
    # faint deckled border
    cv2.rectangle(img, (26, 26), (w - 26, h - 26), (208, 214, 212), 2)
    cv2.rectangle(img, (34, 34), (w - 34, h - 34), (218, 223, 220), 1)
    return img


# ------------------------------------------------------------------ figures
class Rig:
    """front / back / 3-4 view built from the same R-space numbers as fk()."""

    def __init__(self, ox, R, gy=GY):
        self.ox, self.R, self.gy = ox, R, gy

    def P(self, x, y, sq=1.0):
        return (self.ox + x * sq * self.R, self.gy + y * self.R)

    def U(self, v):
        return v * self.R


def face(img, c, rx, ry, kind="smile", sq=1.0, dx=0.0, back=False):
    """front-facing face, drawn in canvas px"""
    if back:
        return
    ex, ey = rx * 0.34 + dx, c[1] - ry * 0.10
    ew, eh = rx * 0.17, ry * 0.235
    lw = max(2, int(rx * 0.055))
    if kind in ("smile", "surprise", "sip", "content"):
        for s in (-1, 1):
            cv2.ellipse(img, (int(c[0] + s * ex + dx), int(ey)), (int(ew), int(eh)),
                        0, 0, 360, INK, -1, cv2.LINE_AA)
            cv2.circle(img, (int(c[0] + s * ex + dx - ew * 0.30),
                             int(ey - eh * 0.35)), int(ew * 0.34),
                       (250, 250, 246), -1, cv2.LINE_AA)
    elif kind == "blink":
        for s in (-1, 1):
            cv2.line(img, (int(c[0] + s * ex - ew + dx), int(ey)),
                     (int(c[0] + s * ex + ew + dx), int(ey)), INK, lw,
                     cv2.LINE_AA)
    elif kind == "happy":
        for s in (-1, 1):
            cv2.ellipse(img, (int(c[0] + s * ex + dx), int(ey + eh * 0.25)),
                        (int(ew * 1.15), int(eh * 0.85)), 0, 200, 340, INK, lw,
                        cv2.LINE_AA)
    # brows
    by = ey - ry * 0.34
    for s in (-1, 1):
        y0 = by - (ry * 0.06 if kind == "surprise" else 0)
        cv2.line(img, (int(c[0] + s * ex - ew * 1.05 + dx), int(by + ry * 0.03)),
                 (int(c[0] + s * ex + ew * 1.05 + dx), int(y0)), INK,
                 max(2, int(lw * 0.8)), cv2.LINE_AA)
    # mouth
    my = c[1] + ry * 0.34
    if kind == "sip":
        cv2.ellipse(img, (int(c[0] + dx), int(my)), (int(rx * 0.13), int(ry * 0.13)),
                    0, 0, 360, INK, -1, cv2.LINE_AA)
    elif kind == "surprise":
        cv2.ellipse(img, (int(c[0] + dx), int(my)), (int(rx * 0.11), int(ry * 0.16)),
                    0, 0, 360, (60, 44, 44), -1, cv2.LINE_AA)
    else:
        bow = 0.20 if kind in ("happy", "content") else 0.28
        cv2.ellipse(img, (int(c[0] + dx), int(my - ry * 0.10)),
                    (int(rx * 0.34), int(ry * bow)), 0, 20, 160, INK, lw,
                    cv2.LINE_AA)
    # blush
    for s in (-1, 1):
        cv2.ellipse(img, (int(c[0] + s * rx * 0.62 + dx), int(c[1] + ry * 0.20)),
                    (int(rx * 0.17), int(ry * 0.10)), 0, 0, 360, BLUSH, -1,
                    cv2.LINE_AA)


def hand(img, p, r, sq=1.0):
    disc(img, p, r, INK)
    disc(img, (p[0] + r * 0.55, p[1] - r * 0.75), r * 0.48, INK)


def sleeve_cap(img, a, b, r1, r2, frac=0.34):
    mid = (a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac)
    cap(img, a, mid, r1 * 2.15, r2 * 1.75, SHIRT)
    cap(img, a, mid, r1 * 2.15, r2 * 1.75, SHIRT)
    cv2.line(img, (int(mid[0] - r2 * 1.6), int(mid[1])),
             (int(mid[0] + r2 * 1.6), int(mid[1])), INK,
             max(2, int(r1 * 0.55)), cv2.LINE_AA)


def shoe_front(img, p, R, sq=1.0):
    w, h = 0.34 * R * sq, 0.30 * R
    cv2.ellipse(img, (int(p[0]), int(p[1] + 0.04 * R)), (int(w), int(h)), 0, 0,
                360, SHOE, -1, cv2.LINE_AA)
    cv2.ellipse(img, (int(p[0]), int(p[1] + 0.13 * R)), (int(w * 1.02),
                int(h * 0.42)), 0, 0, 360, SOLE, -1, cv2.LINE_AA)
    cv2.ellipse(img, (int(p[0]), int(p[1] + 0.04 * R)), (int(w), int(h)), 0, 0,
                360, INK, max(2, int(R * 0.035)), cv2.LINE_AA)


def figure(img, ox, R, view="front"):
    """front / back / 3-4 standing figure"""
    sq = 1.0
    dx = 0.0
    if view == "tq":
        sq, dx = 0.80, 0.13
    back = view == "back"

    def P(x, y):
        return (ox + x * sq * R, GY + y * R)

    hip_y, sho_y = -3.30, -5.95
    # ---- legs
    for s in (-1, 1):
        hp, kn, an = P(s * 0.26, hip_y), P(s * 0.27, -1.78), P(s * 0.28, -0.24)
        cap(img, hp, kn, 0.150 * R, 0.125 * R, INK)
        cap(img, kn, an, 0.122 * R, 0.100 * R, INK)
        cap(img, hp, kn, 0.150 * R - 3, 0.125 * R - 3, PANTS)
        cap(img, kn, an, 0.122 * R - 3, 0.100 * R - 3, PANTS)
        cv2.circle(img, (int(an[0]), int(an[1] - 0.03 * R)), int(0.135 * R),
                   PANTS, -1, cv2.LINE_AA)          # cuff break
        shoe_front(img, an, R, sq)
    # ---- far arm
    for s, far in ((-1, True), (1, False)):
        sh = P(s * 0.44, sho_y + 0.05)
        el = P(s * 0.62, -4.78)
        ha = P(s * 0.70, -3.86)
        cap(img, sh, el, 0.132 * R, 0.110 * R)
        cap(img, el, ha, 0.110 * R, 0.090 * R)
        hand(img, ha, 0.145 * R)
        sleeve_cap(img, sh, el, 0.132 * R, 0.110 * R)
    # ---- shirt (A-line trapezoid, rounded hem)
    lw_ = 0.46 if view != "tq" else 0.40
    rw_ = 0.46 if view != "tq" else 0.54
    tl = np.array([P(-lw_, sho_y), P(rw_, sho_y), P(rw_ + 0.14, hip_y + 0.12),
                   P(0.00, hip_y + 0.30), P(-lw_ - 0.14, hip_y + 0.12)],
                  np.float32)
    tl = np.array([[int(x), int(y)] for x, y in tl], np.int32)
    cv2.fillPoly(img, [tl], SHIRT, cv2.LINE_AA)
    cv2.polylines(img, [tl], True, INK, max(2, int(0.052 * R)), cv2.LINE_AA)
    # waistband
    wb = np.array([P(-0.58, hip_y + 0.10), P(0.58, hip_y + 0.10),
                   P(0.60, hip_y + 0.24), P(-0.60, hip_y + 0.24)], np.int32)
    cv2.fillPoly(img, [wb], PANTS, cv2.LINE_AA)
    # placket + buttons / back yoke
    if not back:
        cv2.line(img, (int(P(0, sho_y + 0.10)[0]), int(P(0, sho_y + 0.10)[1])),
                 (int(P(0, hip_y + 0.08)[0]), int(P(0, hip_y + 0.08)[1])), INK,
                 max(2, int(0.022 * R)), cv2.LINE_AA)
        for v in (1.2, 2.2):
            disc(img, P(0.10, sho_y + v), 0.035 * R, (120, 110, 108))
    else:
        cv2.line(img, (int(P(0, sho_y + 0.22)[0]), int(P(0, sho_y + 0.22)[1])),
                 (int(P(0, sho_y + 0.30)[0]), int(P(0, sho_y + 0.30)[1])), INK,
                 max(2, int(0.020 * R)), cv2.LINE_AA)
    # collar
    cl = np.array([P(-0.20, sho_y), P(0.0, sho_y + 0.30), P(0.20, sho_y)], np.int32)
    if not back:
        cv2.fillPoly(img, [cl], (246, 245, 240), cv2.LINE_AA)
        cv2.polylines(img, [cl], True, INK, max(2, int(0.030 * R)), cv2.LINE_AA)
    else:
        cv2.line(img, (int(P(-0.20, sho_y)[0]), int(P(-0.20, sho_y)[1])),
                 (int(P(0.20, sho_y)[0]), int(P(0.20, sho_y)[1])), INK,
                 max(2, int(0.030 * R)), cv2.LINE_AA)
    # ---- head
    hc = P(dx * 1.5, -7.15)
    rx, ry = 1.00 * R, 1.05 * R
    cv2.ellipse(img, (int(hc[0]), int(hc[1])), (int(rx), int(ry)), 0, 0, 360,
                SKIN, -1, cv2.LINE_AA)
    cv2.ellipse(img, (int(hc[0]), int(hc[1])), (int(rx), int(ry)), 0, 0, 360,
                INK, max(3, int(0.055 * R)), cv2.LINE_AA)
    # neck
    cv2.line(img, (int(hc[0]), int(hc[1] + ry * 0.86)),
             (int(hc[0]), int(P(0, sho_y)[1])), INK,
             max(2, int(0.075 * R)), cv2.LINE_AA)
    face(img, hc, rx, ry, "smile", dx=dx * R, back=back)


# ------------------------------------------------------------------ sheet
def main():
    w, h = W * SS, H * SS
    img = paper(w, h)
    S = lambda v: int(v)

    # ---------------- header
    T(img, "MONARCH COZY", (S(70), S(96)), 0.95, INK, 1.1, 2)
    T(img, "CHARACTER MODEL SHEET  v7   /   STYLE 4 - COZY INK & WASH",
      (S(70), S(140)), 0.62, (150, 120, 96), 0.9, 2)
    cv2.line(img, (S(70), S(158)), (S(2330), S(158)), (206, 212, 210),
             2, cv2.LINE_AA)
    T(img, "8.20 R TALL   /   3.9 HEADS   /   R = 0.22 M", (S(1640), S(96)),
      0.62, (150, 120, 96), 0.9, 2)

    # ---------------- four views
    R = 100
    views = [("front", 470, "FRONT"), ("tq", 900, "3/4"),
             ("side", 1290, "SIDE"), ("back", 1700, "BACK")]
    for view, ox, name in views:
        if view == "side":
            base = CH.pose_idle(0.0)
            base.update(shR=-14, elR=-10, shL=10, elL=-8)
            CH.draw(img, GY, ox, R, base, facing=1, t=0.3, mood="happy",
                    cup=False, ss=1, boil=0.0)
        else:
            figure(img, ox, R, view)
        T(img, name, (S(ox / SS - 40), S((GY + 60) / SS)), 0.58,
          (150, 120, 96), 0.9, 2)
        cv2.line(img, (S((ox - 150) / SS), S((GY + 22) / SS)),
                 (S((ox + 150) / SS), S((GY + 22) / SS)), (206, 212, 210),
                 1, cv2.LINE_AA)

    # ---------------- callouts on the front view (kept clear of the body)
    ox = 470
    def call(txt, p_from, y_lab):
        x0, y0 = int(p_from[0]), int(p_from[1])
        y1 = int(y_lab)
        x_end = T(img, txt, (40, y1 + 5), 0.46, (128, 104, 82), 0.6, 1)
        cv2.line(img, (x0, y0), (int(x_end) + 10, y1), (176, 150, 120), 2,
                 cv2.LINE_AA)
        cv2.circle(img, (x0, y0), 3, (176, 150, 120), -1, cv2.LINE_AA)

    call("HEAD  2.10 R", (ox - R * 0.80, GY - R * 7.35), GY - R * 7.95)
    call("3/4 SLEEVE + CUFF", (ox - R * 0.60, GY - R * 5.10), GY - R * 6.30)
    call("A-LINE SHIRT  0.92 R AT HEM", (ox - R * 0.58, GY - R * 3.95),
         GY - R * 4.85)
    call("MITTEN HAND 0.15 R", (ox - R * 0.70, GY - R * 3.80), GY - R * 3.45)
    call("TAPERED TROUSER 0.30 -> 0.20 R", (ox - R * 0.28, GY - R * 2.20),
         GY - R * 2.05)
    call("BOOT + 0.20 R SOLE", (ox - R * 0.30, GY - R * 0.30), GY - R * 0.60)

    # ---------------- expression row
    T(img, "EXPRESSIONS", (60, 1122), 0.72, INK, 1.0, 2)
    kinds = [("neutral", "NEUTRAL"), ("smile", "SMILE"), ("blink", "BLINK"),
             ("happy", "JOY"), ("surprise", "SURPRISED"), ("sip", "SIP")]
    ey0 = 1210
    for i, (kind, label) in enumerate(kinds):
        cx = 120 + i * 152
        rr = 52
        cv2.ellipse(img, (cx, ey0), (int(rr), int(rr * 1.05)), 0, 0, 360, SKIN,
                    -1, cv2.LINE_AA)
        cv2.ellipse(img, (cx, ey0), (int(rr), int(rr * 1.05)), 0, 0, 360, INK,
                    3, cv2.LINE_AA)
        face(img, (cx, ey0), rr, rr * 1.05, kind)
        T(img, label, (cx - 34, 1292), 0.42, (150, 120, 96), 0.6, 1)

    # ---------------- props
    T(img, "PROPS", (1080, 1122), 0.72, INK, 1.0, 2)
    px, py, R2 = 1160, 1212, 96
    # standing mug on its saucer
    cv2.ellipse(img, (px, py + int(0.22 * R2)), (int(0.27 * R2), int(0.085 * R2)),
                0, 0, 360, (238, 238, 232), -1, cv2.LINE_AA)
    cv2.ellipse(img, (px, py + int(0.22 * R2)), (int(0.27 * R2), int(0.085 * R2)),
                0, 0, 360, INK, 3, cv2.LINE_AA)
    hh, tw, bw = 0.235 * R2, 0.150 * R2, 0.108 * R2
    pts = np.array([[px - tw, py - hh], [px + tw, py - hh],
                    [px + bw, py + hh * 0.5], [px - bw, py + hh * 0.5]], np.int32)
    cv2.fillPoly(img, [pts], (246, 246, 242), cv2.LINE_AA)
    band = np.array([[px - tw * 0.9, py - hh * 0.28], [px + tw * 0.9, py - hh * 0.28],
                     [px + bw * 1.1, py + hh * 0.12], [px - bw * 1.1, py + hh * 0.12]],
                    np.int32)
    cv2.fillPoly(img, [band], (150, 132, 112), cv2.LINE_AA)
    lid = ((px, int(py - hh)), (int(tw * 1.02), max(2, int(hh * 0.16))))
    cv2.ellipse(img, lid[0], lid[1], 0, 0, 360, (238, 238, 232), -1, cv2.LINE_AA)
    cv2.polylines(img, [pts], True, INK, 3, cv2.LINE_AA)
    cv2.ellipse(img, lid[0], lid[1], 0, 0, 360, INK, 3, cv2.LINE_AA)
    T(img, "MUG  0.47 R", (px - 60, 1320), 0.42, (150, 120, 96), 0.6, 1)

    # held cup, tilted, drawn on its own scratch canvases
    cv2.rectangle(img, (1330, 1112), (1500, 1332), (236, 240, 240), -1)
    hx, hy = 1400, 1212
    Vc = img
    Mc = np.zeros(img.shape[:2], np.uint8)
    CH._cup(Vc, Mc, hx, hy, 96, INK)
    disc(img, (hx + 6, hy + 6), 14, INK)
    T(img, "HELD  (TILT 9 deg)", (1320, 1320), 0.42, (150, 120, 96), 0.6, 1)

    # chair icon
    cx0, cy0 = 1600, 1152
    cv2.line(img, (cx0, cy0), (cx0, cy0 + 130), SAGE, 13, cv2.LINE_AA)
    cv2.line(img, (cx0, cy0 + 130), (cx0 + 110, cy0 + 124), SAGE, 11, cv2.LINE_AA)
    for x in (cx0, cx0 + 108):
        cv2.line(img, (x, cy0 + 130), (x, cy0 + 215), SAGE, 9, cv2.LINE_AA)
    T(img, "BISTRO CHAIR", (cx0 - 50, 1392), 0.42, (150, 120, 96), 0.6, 1)

    # ---------------- palette
    T(img, "PALETTE", (60, 1382), 0.62, INK, 1.0, 2)
    pal = [("INK", INK), ("SHIRT", SHIRT), ("PANTS", PANTS), ("BOOT", SHOE),
           ("SOLE", SOLE), ("SAGE", SAGE), ("TERRA", TERRA), ("BLUSH", BLUSH)]
    for i, (name, col) in enumerate(pal):
        cx = 62 + i * 104
        cy = 1412
        cv2.rectangle(img, (cx, cy), (cx + 62, cy + 62), col, -1, cv2.LINE_AA)
        cv2.rectangle(img, (cx, cy), (cx + 62, cy + 62), INK, 2, cv2.LINE_AA)
        T(img, name, (cx, cy + 88), 0.40, (128, 104, 82), 0.5, 1)

    # ---------------- proportion bar (4 heads, horizontal)
    T(img, "PROPORTIONS", (60, 1560), 0.62, INK, 1.0, 2)
    bxx, byy, rr = 300, 1572, 26
    for i in range(4):
        x0 = bxx + i * int(2 * rr)
        cv2.rectangle(img, (x0, byy), (x0 + int(2 * rr), byy + int(2.05 * rr)),
                      (216, 222, 218), -1, cv2.LINE_AA)
        cv2.rectangle(img, (x0, byy), (x0 + int(2 * rr), byy + int(2.05 * rr)),
                      INK, 2, cv2.LINE_AA)
    T(img, "4 x HEAD = 8.20 R", (bxx + 230, 1608), 0.42,
      (128, 104, 82), 0.5, 1)

    # ---------------- motion notes
    T(img, "RULES FOR ANIMATION", (1120, 1440), 0.62, INK, 1.0, 2)
    notes = ["HEAD LEADS BY 1 FRAME",
             "LEAN SPRING  k=48  c=11",
             "CUP SLOSH 2.4 Hz PENDULUM",
             "HEEL -> WEIGHT -> PUSH, 12 FRAMES",
             "ARM SWINGS 6 FRAMES AFTER THE LEG",
             "SQUASH 0.94 / STRETCH 1.06"]
    for i, t in enumerate(notes):
        T(img, t, (1122, 1480 + i * 32), 0.40, (128, 104, 82), 0.5, 1)

    out = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
    cv2.imwrite("char_sheet_v7.jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 94])
    print("wrote char_sheet_v7.jpg", out.shape)


if __name__ == "__main__":
    main()
