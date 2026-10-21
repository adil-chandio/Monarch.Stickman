#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reference-matched 10 s proof clip — Style 4 "Cozy Storytelling" grammar.
Shot 1 wide establishing (walk-in) -> Shot 2 close-up (emotion) -> Shot 3 tracking.
24 fps, 1920x1080, soft warm grade.
"""

import math
import os
import subprocess
import time

import numpy as np
import cv2

import generate_video_v2 as B
import style_engine as S

FPS = 24
DUR = 10.0
N = int(FPS * DUR)
OUT = "proof_cozy_10s.mp4"

SH1 = (0.0, 3.3)
SH2 = (3.3, 6.6)
SH3 = (6.6, 10.0)

POSES = B.POSES


def ease(t):
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def extras(img, t):
    """soft warm sky gradient — keeps the flat cel sky from looking dead"""
    top = np.array([206, 222, 238], np.float32)
    bot = np.array([236, 238, 238], np.float32)
    g = np.linspace(0, 1, 520, dtype=np.float32)[:, None, None]
    img[:520] = (img[:520].astype(np.float32) * 0.5 +
                 (top * (1 - g) + bot * g) * 0.5).astype(np.uint8)


def draw_bg(img, t, cam):
    """cozy cafe background, camera-aware (redrawn in screen space by offset)"""
    S.bg_cafe(img, t)
    extras(img, t)
    # parallax shift of the far layer
    dx = int((940 - cam.x) * 0.35)
    if dx:
        M = np.float32([[1, 0, dx], [0, 1, 0]])
        far = img[:560].copy()
        img[:560] = cv2.warpAffine(far, M, (img.shape[1], 560),
                                   borderMode=cv2.BORDER_REPLICATE)


def character(img, cam, x, ground, scale, pose, facing, t, mood,
              cfg=None, blink=0.0):
    return S.draw_char(img, cam, x, ground, scale, pose, facing=facing, t=t,
                       cfg=cfg, mood=mood, blink_phase=blink)


def grade(img, warm=1.04, vig=0.30):
    out = img.astype(np.float32)
    out[..., 2] *= warm
    out[..., 0] *= 0.985
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w * 0.62)) ** 2 + ((yy - h / 2) / (h * 0.64)) ** 2)
    v = np.clip(1.02 - vig * r ** 2.2, 0.55, 1.0)[:, :, None]
    out *= v
    gray = out.mean(axis=2, keepdims=True)
    out = gray + (out - gray) * 1.12          # slight saturation lift
    out = out * 0.97 + np.array([6, 4, 2], np.float32) * 0.3
    return np.clip(out, 0, 255).astype(np.uint8)



class ScreenCam:
    """maps world coords to a zoomed screen-space framing"""
    def __init__(self, k=1.0, cx=960.0, ground_screen=1366.0, sx=0.0, sy=0.0):
        self.k, self.cx, self.gy = k, cx, ground_screen
        self.z = k
        self.sx, self.sy = sx, sy

    def apply(self, x, y):
        return (S.W * 0.5 + (x - self.cx) * self.k + self.sx,
                self.gy + (y - SG) * self.k + self.sy)


COZY_CFG = dict(shirt=(252, 252, 250), limb=S.NAVY, limb_w=15, outline=4,
                face="cozy", sleeve=False)

# reference-calibrated poses: relaxed arms clear of the torso, soft knees
REF_IDLE = dict(lean=2, head=-1, shL=-8, elL=-2, shR=8, elR=-2,
                hipL=4, knL=5, hipR=-4, knR=-5, py=0, rot=0, cape=0)
REF_WALK_A = dict(lean=5, head=-2, shL=30, elL=-12, shR=-26, elR=-8,
                  hipL=21, knL=-3, hipR=-19, knR=-30, py=0, rot=0, cape=0)
REF_WALK_B = dict(lean=5, head=-2, shL=-24, elL=-8, shR=28, elR=-14,
                  hipL=-19, knL=-30, hipR=21, knR=-3, py=1, rot=0, cape=0)


def walk_pose(t, cadence=1.05, carry=True):
    """continuous procedural walk cycle built on the reference pose scale"""
    ph = 2 * math.pi * cadence * t
    A, K = 20.0, 30.0
    hipL = A * math.sin(ph)
    hipR = -hipL
    knL = -3 - K * max(0.0, math.cos(ph))
    knR = -3 - K * max(0.0, math.cos(ph + math.pi))
    armL = -14.0 * math.sin(ph)
    armR = 14.0 * math.sin(ph)
    p = dict(lean=5, head=-2, shL=armL, elL=-10, shR=armR, elR=-10,
             hipL=hipL, knL=knL, hipR=hipR, knR=knR,
             py=1.2 * math.cos(2 * ph), rot=0, cape=0)
    if carry:
        p["shR"], p["elR"] = 44, 48
    return p


def _carry(base):
    p = dict(base)
    p["shL"], p["elL"] = 50, 44          # near arm forward, holding the cup
    return p


CARRY = {"a": _carry(REF_WALK_A), "b": _carry(REF_WALK_B)}

SG = S.GROUND


def frame(fi):
    t = fi / FPS

    # ---------------- shot 1: wide establishing (walk-in) ----------------
    if t < SH1[1]:
        tl = (t - SH1[0]) / (SH1[1] - SH1[0])
        z = 1.0 + 0.05 * ease(tl)
        cam = S.Cam(940, 0.90, z)
        img = np.zeros((S.H, S.W, 3), np.uint8)
        draw_bg(img, t, cam)
        wx = 760 + 160 * ease(min(1.0, tl / 0.82))
        pose = walk_pose(t, 1.02) if tl < 0.82 else REF_IDLE
        info = character(img, cam, wx, SG, 290, pose, 1, t, "happy", COZY_CFG,
                         blink=0.4)
        if tl < 0.82:
            _cup_at(img, cam, wx, SG, 290, info)
        return grade(img)

    # ---------------- shot 2: close-up on the face ----------------
    if t < SH2[1]:
        tl = (t - SH2[0]) / (SH2[1] - SH2[0])
        bg = np.zeros((S.H, S.W, 3), np.uint8)
        draw_bg(bg, t, S.Cam(940, 0.90, 1.0))
        bg = cv2.GaussianBlur(bg, (0, 0), 6)
        M = np.float32([[1.18, 0, -S.W * 0.09], [0, 1.18, -S.H * 0.10]])
        bg = cv2.warpAffine(bg, M, (S.W, S.H), borderMode=cv2.BORDER_REPLICATE)
        cam_cu = ScreenCam(k=2.02 + 0.16 * tl, cx=940, ground_screen=1720)
        mood = "neutral" if tl < 0.30 else "happy"
        character(bg, cam_cu, 940, SG, 290, REF_IDLE, 1, t, mood,
                  COZY_CFG, blink=1.1)
        return grade(bg, vig=0.20)

    # ---------------- shot 3: lateral tracking, cup in hand ----------------
    tl = (t - SH3[0]) / (SH3[1] - SH3[0])
    wx = 760 + 270 * tl
    cam = S.Cam(wx + 20, 0.90, 1.02)
    img = np.zeros((S.H, S.W, 3), np.uint8)
    draw_bg(img, t, cam)
    pose = walk_pose(t, 1.12)
    info = character(img, cam, wx, SG, 290, pose, 1, t, "happy", COZY_CFG,
                     blink=2.0)
    _cup_at(img, cam, wx, SG, 290, info)
    return grade(img)


def _cup_at(img, cam, wx, ground, scale, info):
    """cup rides in the near hand (joints already anchored by the engine)"""
    J = info["joints"]
    key = "ha" + info.get("near", "R")
    hx, hy = J[key][0] + 0.03, J[key][1] - 0.05
    p = cam.apply(wx + hx * scale, ground + hy * scale)
    _cup(img, p, scale)


def _cup(img, p, scale):
    """reference-style takeaway cup: tapered white body, brown band, lid"""
    k = scale / 260.0
    cx, cy = int(p[0]), int(p[1])
    tw, bw, hh = 18 * k, 13 * k, 25 * k
    pts = np.array([[cx - tw, cy - hh], [cx + tw, cy - hh],
                    [cx + bw, cy + hh], [cx - bw, cy + hh]], np.int32)
    cv2.fillPoly(img, [pts], (250, 250, 247), cv2.LINE_AA)
    # brown sleeve band
    y0, y1 = cy - int(hh * 0.45), cy + int(hh * 0.15)
    tp = tw + (bw - tw) * ((-hh * 0.45 - -hh) / (2 * hh))
    bp = tw + (bw - tw) * ((hh * 0.15 + hh) / (2 * hh))
    cv2.fillPoly(img, [np.array([[cx - int(tp), y0], [cx + int(tp), y0],
                                 [cx + int(bp), y1], [cx - int(bp), y1]],
                                np.int32)], (128, 104, 74), cv2.LINE_AA)
    # lid
    cv2.ellipse(img, (cx, cy - int(hh)), (int(tw + 2 * k), max(2, int(4 * k))),
                0, 0, 360, (238, 238, 233), -1, cv2.LINE_AA)
    cv2.polylines(img, [pts], True, (27, 36, 50), max(2, int(2 * k)),
                  cv2.LINE_AA)
    cv2.ellipse(img, (cx, cy - int(hh)), (int(tw + 2 * k), max(2, int(4 * k))),
                0, 0, 360, (27, 36, 50), max(2, int(2 * k)), cv2.LINE_AA)


def main():
    ff = None
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{S.W}x{S.H}",
           "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264",
           "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
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
