#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
proof clip v7 — clothed character, seated table interaction + street walk.
Shot 1 (0-4.2)  seated at the bistro table, reaches for the mug and sips
Shot 2 (4.2-7.4) street walk, lateral tracking
Shot 3 (7.4-10)  wide push-in with the cafe terrace behind
1920x1080, 24 fps, 10.00 s.
"""

import math
import os
import subprocess
import time

import numpy as np
import cv2

import char_v7 as CH

FPS = 24
DUR = 10.0
N = int(FPS * DUR)
OUT = "proof_cozy_v7.mp4"
W, H = 1920, 1080

PLATES = {}


def ease(t):
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def load(name):
    if name not in PLATES:
        p = cv2.imread(f"plates/{name}.png", cv2.IMREAD_COLOR)
        PLATES[name] = cv2.resize(p, (W, H), interpolation=cv2.INTER_CUBIC)
    return PLATES[name]


def cam(img, z=1.0, cx=W * 0.5, cy=H * 0.5, blur=0.0):
    hw, hh = W * 0.5 / z, H * 0.5 / z
    cx = float(np.clip(cx, hw, W - hw))
    cy = float(np.clip(cy, hh, H - hh))
    M = np.float32([[z, 0, W * 0.5 - z * cx], [0, z, H * 0.5 - z * cy]])
    out = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC,
                         borderMode=cv2.BORDER_REFLECT_101)
    if blur:
        out = cv2.GaussianBlur(out, (0, 0), blur)
    return out, (z, cx, cy)


def w2s(x, y, c):
    z, cx, cy = c
    return (W * 0.5 + (x - cx) * z, H * 0.5 + (y - cy) * z)


def grade(img, vig=0.22):
    out = img.astype(np.float32)
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w * 0.70)) ** 2 +
                ((yy - h / 2) / (h * 0.72)) ** 2)
    out *= np.clip(1.02 - vig * r ** 2.6, 0.70, 1.0)[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


# ---- seated shot geometry (plate pixels at 1920x1080)
SEAT_X, FLOOR_Y, R = 900.0, 985.0, 100.0
GY = FLOOR_Y                        # pose_seated already has feet on y=0
MUG_X, MUG_Y = 1156.0, 641.0        # mug resting on the near-left table top
WOOD = (150, 168, 150)              # BGR sage wood
WOOD_D = (120, 139, 124)
INK = (66, 46, 45)


def init():
    pass


def _chair(img, sx, sy, Rp, bob=0.0):
    """sage bistro chair in plate pixels, seat exactly under the hips"""
    def P(u, v):
        return (int(sx + u * Rp), int(sy + v * Rp))

    seat_y = -1.70 + bob
    back_x, front_x = -0.55, 1.95
    th = 0.11
    lw = lambda f: max(2, int(f * Rp))

    # --- far side (drawn first, a touch darker)
    cv2.line(img, P(back_x + 0.16, seat_y - 2.15), P(back_x + 0.16, seat_y),
             WOOD_D, lw(0.10), cv2.LINE_AA)
    for x0, x1 in ((back_x + 0.16, back_x + 0.02), (front_x + 0.16, front_x - 0.10)):
        cv2.line(img, P(x0, seat_y + th * 0.6), P(x1, -0.02), WOOD_D, lw(0.09),
                 cv2.LINE_AA)
    cv2.line(img, P(back_x + 0.16, seat_y), P(front_x + 0.16, seat_y - 0.07),
             WOOD_D, lw(0.11), cv2.LINE_AA)
    # --- seat slab, seen slightly from the front so the top reads
    seat = np.array([P(back_x, seat_y), P(front_x, seat_y - 0.10),
                     P(front_x, seat_y + th - 0.10), P(back_x, seat_y + th)],
                    np.int32)
    cv2.fillPoly(img, [seat], WOOD, cv2.LINE_AA)
    cv2.polylines(img, [seat], True, INK, lw(0.032), cv2.LINE_AA)
    # --- backrest: post + rungs
    cv2.line(img, P(back_x, seat_y), P(back_x - 0.06, seat_y - 2.15), WOOD,
             lw(0.16), cv2.LINE_AA)
    cv2.line(img, P(back_x, seat_y), P(back_x - 0.06, seat_y - 2.15), INK,
             lw(0.022), cv2.LINE_AA)
    for v, ln in ((-2.15, 0.42), (-1.52, 0.50), (-0.95, 0.46)):
        cv2.line(img, P(back_x - 0.06, seat_y + v),
                 P(back_x - 0.06 + ln, seat_y + v + 0.16), WOOD, lw(0.10),
                 cv2.LINE_AA)
        cv2.line(img, P(back_x - 0.06, seat_y + v),
                 P(back_x - 0.06 + ln, seat_y + v + 0.16), INK, lw(0.018),
                 cv2.LINE_AA)
    # --- near legs
    for x0, x1 in ((front_x, front_x - 0.02), (back_x, back_x - 0.06)):
        cv2.line(img, P(x0, seat_y + th * 0.5), P(x1, 0.0), WOOD, lw(0.11),
                 cv2.LINE_AA)
        cv2.line(img, P(x0, seat_y + th * 0.5), P(x1, 0.0), INK, lw(0.018),
                 cv2.LINE_AA)
    # --- contact shadow
    ov = img.copy()
    cv2.ellipse(ov, P(0.70, 0.01), (int(1.35 * Rp), int(0.10 * Rp)), 0, 0, 360,
                (148, 150, 146), -1, cv2.LINE_AA)
    cv2.addWeighted(cv2.GaussianBlur(ov, (0, 0), 0.03 * Rp), 0.28, img, 0.72, 0,
                    img)


def seated_pose(t):
    """pose through shot 1: sitting -> reach for the mug -> sip -> back"""
    base = CH.pose_seated(t, lean=18)
    # IK reach to the mug standing on the table
    S = CH.fk(base, 1)["shR"]
    reach = CH.arm_to(base, ((MUG_X - SEAT_X) / R, (MUG_Y - GY) / R))

    SIP_SH, SIP_EL = 88.0, 130.0
    lift = ease(min(1.0, max(0.0, (t - 0.75) / 1.05)))
    hold = ease(min(1.0, max(0.0, (t - 2.55) / 0.55)))
    down = ease(min(1.0, max(0.0, (t - 3.35) / 0.80)))
    k = max(0.0, lift - down)                 # 0 = on the table, 1 = at the lips

    p = dict(reach)
    sh0, el0 = reach["shR"], reach["elR"]
    # shortest way round for the forearm
    el1 = SIP_EL
    while el1 - el0 > 180:
        el1 -= 360
    while el1 - el0 < -180:
        el1 += 360
    p["shR"] = sh0 + (SIP_SH - sh0) * k
    p["elR"] = el0 + (el1 - el0) * k
    # a little head tilt while sipping
    p["lean"] = 18 + 6.0 * k
    return p, k


def frame(fi):
    t = fi / FPS

    # ---------------- shot 1: seated, reach + sip ----------------
    if t < 4.2:
        tl = t / 4.2
        # wide two-shot, then a push-in for the sip, then back out
        push = ease((t - 2.10) / 0.55) - ease((t - 3.30) / 0.60)
        push = max(0.0, min(1.0, push))
        z = 1.36 + 0.16 * ease(tl) + 0.46 * push
        cxc = 1005.0 + 20.0 * push
        cyc = 625.0 - 165.0 * push
        img, c = cam(load("cafe_table5"), z, cxc, cyc)
        sx, sy = w2s(SEAT_X, GY, c)
        Rp = R * z
        _chair(img, sx, sy, Rp)
        p, k = seated_pose(t)
        held = k > 0.06
        if not held:                        # mug still standing on the table
            mx, my = w2s(MUG_X, MUG_Y, c)
            _mug_stand(img, (mx, my), Rp)
        CH.draw(img, sy, sx, Rp, p, t=t, mood="happy",
                blink_at=1.9, cup=held, front_arm=held)
        return grade(img)

    # ---------------- shot 2: street walk ----------------
    if t < 7.4:
        tl = (t - 4.2) / 3.2
        px = 800 + 420 * tl
        img, c = cam(load("street_walk"), 1.02, px + 30, 560.0)
        sx, sy = w2s(px, 1000.0, c)
        pose = CH.pose_walk(t, 1.10)
        CH.draw(img, sy, sx, 82, pose, t=t, mood="happy", blink_at=2.4,
                cup=True)
        return grade(img)

    # ---------------- shot 3: wide, terrace in frame ----------------
    tl = (t - 7.4) / 2.6
    z = 1.06 - 0.05 * ease(tl)
    img, c = cam(load("cafe_wide"), z, 1150.0, 560.0)
    sx, sy = w2s(1150.0, 930.0, c)
    pose = CH.pose_walk(t, 1.0) if tl < 0.72 else CH.pose_idle(t)
    CH.draw(img, sy, sx, 86 * z, pose, t=t, mood="happy", blink_at=0.4,
            cup=True)
    return grade(img)


def _mug_stand(img, p, R):
    """the same mug as char_v7._cup, sitting on the table on its saucer"""
    cx, cy = p
    cx, cy = int(cx), int(cy)
    # saucer
    ov = img.copy()
    cv2.ellipse(ov, (cx, cy + int(0.20 * R)),
                (int(0.24 * R), int(0.075 * R)), 0, 0, 360, (238, 238, 232),
                -1, cv2.LINE_AA)
    cv2.ellipse(ov, (cx, cy + int(0.20 * R)),
                (int(0.24 * R), int(0.075 * R)), 0, 0, 360, INK,
                max(2, int(0.016 * R)), cv2.LINE_AA)
    img[:] = ov
    hh, tw, bw = 0.235 * R, 0.150 * R, 0.108 * R
    pts = np.array([[cx - tw, cy - hh], [cx + tw, cy - hh],
                    [cx + bw, cy + hh * 0.55], [cx - bw, cy + hh * 0.55]],
                   np.int32)
    cv2.fillPoly(img, [pts], (246, 246, 242), cv2.LINE_AA)
    band = np.array([[cx - tw * 0.95, cy - hh * 0.36], [cx + tw * 0.95, cy - hh * 0.36],
                     [cx + bw * 1.10, cy + hh * 0.06], [cx - bw * 1.10, cy + hh * 0.06]],
                    np.int32)
    cv2.fillPoly(img, [band], (150, 132, 112), cv2.LINE_AA)
    lid = ((cx, int(cy - hh)), (int(tw * 1.02), max(2, int(hh * 0.16))))
    cv2.ellipse(img, lid[0], lid[1], 0, 0, 360, (238, 238, 232), -1, cv2.LINE_AA)
    lw = max(2, int(0.030 * R))
    cv2.polylines(img, [pts], True, INK, lw, cv2.LINE_AA)
    cv2.ellipse(img, lid[0], lid[1], 0, 0, 360, INK, lw, cv2.LINE_AA)


def main():
    init()
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ff = "ffmpeg"
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
           "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", OUT]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    t0 = time.time()
    for fi in range(N):
        proc.stdin.write(frame(fi).tobytes())
        if fi % 24 == 0:
            print(f"frame {fi}/{N} {time.time()-t0:.1f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    print("DONE", OUT, f"{os.path.getsize(OUT)/1e6:.1f} MB", flush=True)


if __name__ == "__main__":
    main()
