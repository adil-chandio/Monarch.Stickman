#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proof clip v5 — painterly plates + hand-drawn character.

Shot 1  wide establishing, slow push-in, character walks in
Shot 2  close-up (blurred plate, 3x supersampled character)
Shot 3  lateral tracking pan, character walks, sips the coffee

1920x1080, 24 fps, 10.00 s.
"""

import math
import os
import subprocess
import time

import numpy as np
import cv2

import char_v5 as CH

FPS = 24
DUR = 10.0
N = int(FPS * DUR)
OUT = "proof_cozy_v5.mp4"
W, H = 1920, 1080

SH1 = (0.0, 3.3)
SH2 = (3.3, 6.6)
SH3 = (6.6, 10.0)

PLATE_W, PLATE_H = 1920, 1080


def ease(t):
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


class Plate:
    """a painterly background plate with a simple camera"""

    def __init__(self, path):
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        self.img = cv2.resize(img, (PLATE_W, PLATE_H), interpolation=cv2.INTER_CUBIC)

    def view(self, z=1.0, cx=PLATE_W * 0.5, cy=PLATE_H * 0.5, blur=0.0):
        """(cx, cy) = plate point at screen centre, clamped inside the plate"""
        hw, hh = W * 0.5 / z, H * 0.5 / z
        cx = float(np.clip(cx, hw, PLATE_W - hw))
        cy = float(np.clip(cy, hh, PLATE_H - hh))
        M = np.float32([[z, 0, W * 0.5 - z * cx],
                        [0, z, H * 0.5 - z * cy]])
        out = cv2.warpAffine(self.img, M, (W, H), flags=cv2.INTER_CUBIC,
                             borderMode=cv2.BORDER_REFLECT_101)
        if blur > 0:
            out = cv2.GaussianBlur(out, (0, 0), blur)
        return out


def w2s(x, y, z, cx, cy):
    """plate coords -> screen coords for the camera used by Plate.view"""
    return (W * 0.5 + (x - cx) * z, H * 0.5 + (y - cy) * z)


def grade(img, vig=0.26, warm=1.02):
    out = img.astype(np.float32)
    out[..., 2] *= warm
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w * 0.66)) ** 2 +
                ((yy - h / 2) / (h * 0.68)) ** 2)
    v = np.clip(1.03 - vig * r ** 2.4, 0.60, 1.0)[:, :, None]
    out *= v
    return np.clip(out, 0, 255).astype(np.uint8)


PLATE_CAFE = None
PLATE_STREET = None


def init():
    global PLATE_CAFE, PLATE_STREET
    PLATE_CAFE = Plate("plates/cafe_wide.png")
    PLATE_STREET = Plate("plates/street_walk.png")


# plate coords: where the character stands in each shot
CX0, GY0 = 1250.0, 1005.0      # cafe cobbles (shot 1 + 2)
PX_IDLE = 1245.0               # standing spot for the close-up
GY3 = 1000.0                   # street pavement (shot 3)


def frame(fi):
    t = fi / FPS

    # ---------------- shot 1: wide establishing, slow push-in ----------------
    if t < SH1[1]:
        tl = (t - SH1[0]) / (SH1[1] - SH1[0])
        z = 1.0 + 0.06 * ease(tl)
        cam = (CX0 + 10 * ease(tl), 540.0)
        img = PLATE_CAFE.view(z, cam[0], cam[1])

        p = min(1.0, tl / 0.80)
        px = 1120 + 230 * ease(p)
        walking = p < 1.0
        pose = CH.pose_walk(t, 1.05) if walking else CH.pose_idle(t)
        sx, sy = w2s(px, GY0, z, cam[0], cam[1])
        CH.draw(img, sy, sx, 640 * z, pose, facing=1, t=t, mood="happy",
                blink_at=0.5)
        return grade(img)

    # ---------------- shot 2: close-up on the face ----------------
    if t < SH2[1]:
        tl = (t - SH2[0]) / (SH2[1] - SH2[0])
        z = 1.95
        cam = (PX_IDLE - 10, GY0 - (1010.0 - H * 0.5) / z - 8 * ease(tl))
        img = PLATE_CAFE.view(z, cam[0], cam[1], blur=13)
        if tl < 0.26:
            mood = "neutral"
        elif tl < 0.42:
            mood = "curious"
        else:
            mood = "happy"
        sx, sy = w2s(PX_IDLE, GY0, z, cam[0], cam[1])
        pose = CH.pose_idle(t)
        Jc = CH.fk(pose)
        scale = 0.40 * H / (2 * CH.HEAD_R)       # head = 40% of frame height
        sy = 0.33 * H - Jc["head"][1] * scale    # face in the upper third
        CH.draw(img, sy, sx, scale, pose, facing=1, t=t,
                mood=mood, blink_at=1.5, cup=False)
        return grade(img, vig=0.20)

    # ---------------- shot 3: lateral tracking ----------------
    tl = (t - SH3[0]) / (SH3[1] - SH3[0])
    z = 1.02
    px = 780 + 470 * tl                      # character walks across the plate
    camx = px + 30                            # camera follows, slight lead
    img = PLATE_STREET.view(z, camx, 560.0)
    pose = CH.pose_walk(t, 1.12)
    if 0.60 < tl < 0.88:                      # sip mid-walk
        k = (tl - 0.60) / 0.28
        kk = k * 2.0 if k < 0.5 else (1.0 - k) * 2.0
        pose = CH.pose_sip(kk)
        pose["hipL"], pose["knL"] = 9, -5
        pose["hipR"], pose["knR"] = -9, -5
    sx, sy = w2s(px, GY3, z, camx, 560.0)
    CH.draw(img, sy, sx, 505 * z, pose, facing=1, t=t, mood="happy",
            blink_at=2.2)
    return grade(img)


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
                            stderr=subprocess.PIPE)
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
