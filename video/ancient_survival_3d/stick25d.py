#!/usr/bin/env python3
"""2.5D cut: photoreal plates as a layered set, classic stickman in front.

Earlier passes failed in two directions. The 3D rasteriser gave stick *robots*
(capsule limbs, joint beads, a black void with grid rings standing in for a
world). The pure-plate pass had no characters at all.

This one is 2.5D, which is how a pre-viz reel is actually built:

    layer 0   the photographic set, as two parallax planes (a real forest, a
              real camp fire - the same AI plates the photoreal cut uses)
    layer 1   the characters: flat, drawn stick figures (circle head, four
              straight limbs, one line for the spine) that carry a real
              skeleton inside, so the walk is IK-planted and the head leads
    layer 2   light and air between the layers: fire flicker, embers, ground
              fog, grain

The stickman is placed in screen space and animated by the rig, which is the
2.5D contract: the drawing never pretends to be a 3D model, but its joints are
solved in 3D and projected, so the stride foreshortens correctly when he turns.

    python3 stick25d.py --start 0 --end 120 --segment _build/a.mp4
"""

from __future__ import annotations

import argparse
import math
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import motion
from rig import Rig, BONE_NAMES

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PLATES = HERE / "plates"
BUILD = HERE / "_build"
FONTS = REPO / "video" / "ancient_survival" / "fonts"
OUT = REPO / "video" / "Ancient_Survival_Stickman25D_10s.mp4"

W, H, FPS, DURATION = 1080, 1920, 24, 10.0
SS = 1.5                                   # supersample factor
WC, HC = int(W * SS), int(H * SS)

CREAM = (255, 246, 220)
GOLD = (255, 187, 93)

RIG = Rig("hunter_stand")
UM = 1.76                                  # metres in the skeleton's own scale
NECK = 0.046                               # shoulder bar -> skull base
HEAD_R = 0.100                             # head ball radius, metres


# ------------------------------------------------------------------- plates
class Plate:
    """One photographic set, prepared to cover the canvas with room to move."""

    def __init__(self, name: str) -> None:
        im = Image.open(PLATES / f"{name}.png").convert("RGB")
        # cover-fill the canvas, keeping the middle
        s = max(WC / im.width, HC / im.height) * 1.10
        im = im.resize((max(WC + 2, int(im.width * s)), max(HC + 2, int(im.height * s))),
                       Image.LANCZOS)
        x = (im.width - WC) // 2
        y = (im.height - HC) // 2
        self.base = np.asarray(im.crop((x, y, x + WC, y + HC)), np.float32) / 255.0
        # a second copy for the near layer: the ground slides against the trees
        big = im.resize((int(im.width * 1.10), int(im.height * 1.10)), Image.LANCZOS)
        x2 = (big.width - WC) // 2
        y2 = (big.height - HC) // 2
        self.near = np.asarray(big.crop((x2, y2, x2 + WC, y2 + HC)), np.float32) / 255.0
        yy = np.mgrid[0:HC, 0:WC][0].astype(np.float32) / HC
        mask = np.clip((yy - 0.60) / 0.34, 0.0, 1.0) ** 1.6
        self.mask = cv2.GaussianBlur(mask, (0, 0), 26 * SS)[..., None]

    def layer(self, zoom: float, dx: float, dy: float, zx: float, zy: float,
              near: float = 0.055) -> np.ndarray:
        """Camera move: scale about (zx, zy) in normalized screen coords."""
        def warp(img, k, ox, oy):
            M = np.array([[k, 0, WC * zx - k * (WC * zx + ox)],
                          [0, k, HC * zy - k * (HC * zy + oy)]], np.float32)
            return cv2.warpAffine(img, M, (WC, HC), flags=cv2.INTER_LANCZOS4,
                                  borderMode=cv2.BORDER_REFLECT)

        far = warp(self.base, zoom, dx * WC, dy * HC)
        close = warp(self.near, zoom * (1.0 + near), dx * WC * 1.7, dy * HC * 1.4)
        return far * (1.0 - self.mask) + close * self.mask


# ------------------------------------------------------------------ skeleton
def _rot_yaw(x: float, z: float, yaw: float) -> tuple[float, float]:
    c, s = math.cos(yaw), math.sin(yaw)
    return x * c + z * s, -x * s + z * c


def open_arms(pose, amount: float = 0.14):
    """Let the arms hang clear of the torso; dead-hanging arms vanish into the
    spine line when the figure is drawn flat."""
    pose.add("upperarm_l", rz=-amount)
    pose.add("upperarm_r", rz=amount)
    return pose


def pose_points(pose, yaw: float, height: float) -> dict[str, np.ndarray]:
    """Joint positions in a character-local 2D frame: (x right, y up, depth)."""
    _, anc = RIG.deform(pose, ground=True)
    k = height / UM
    out = {}
    for bone in BONE_NAMES:
        for key, src in ((bone, anc[bone]), (bone + "_head", anc[bone + "_head"])):
            x, z = _rot_yaw(float(src[0]), float(src[2]), yaw)
            out[key] = np.array([x * k, float(src[1]) * k, z * k])
    return out


JOINTS = ("pelvis", "chest", "neck", "upperarm_l", "upperarm_r",
          "forearm_l", "forearm_r", "thigh_l", "thigh_r", "shin_l", "shin_r")

# A classic stick figure: one spine, a shoulder bar, two arms, two legs, a
# head on a short neck. Built from *derived* joints (`build_points`) rather
# than raw bone anchors, because a raw anchor set gives a V-shaped neck and a
# hip line hanging off to one side - the "loose sticks" look of the last pass.
STROKES = [
    ("hip", "shoulder_mid", 0.024),        # spine
    ("shoulder_mid", "head_base", 0.020),  # neck
    ("shoulder_l", "shoulder_mid", 0.017),
    ("shoulder_mid", "shoulder_r", 0.017),
    ("shoulder_l", "elbow_l", 0.018),
    ("elbow_l", "wrist_l", 0.016),
    ("shoulder_r", "elbow_r", 0.018),
    ("elbow_r", "wrist_r", 0.016),
    ("hip", "knee_l", 0.021),
    ("knee_l", "ankle_l", 0.018),
    ("hip", "knee_r", 0.021),
    ("knee_r", "ankle_r", 0.018),
]

FEET = [("ankle_l", "toe_l", 0.015), ("ankle_r", "toe_r", 0.015)]


def build_points(src: dict) -> dict:
    """Fold the rig's bone anchors into stick-figure joints."""
    p = dict(src)
    p["hip"] = src["pelvis_head"]
    p["shoulder_l"] = src["upperarm_l_head"]
    p["shoulder_r"] = src["upperarm_r_head"]
    p["shoulder_mid"] = (p["shoulder_l"] + p["shoulder_r"]) * 0.5
    # a classic stickman has a *short* neck: the rig's skull base sits high
    # enough that using it raw gives a giraffe. Clamp it to ~half a head.
    up = src["head_head"] - p["shoulder_mid"]
    up[2] = 0.0
    n = float(np.linalg.norm(up[:2])) or 1.0
    # in a near-profile pose both shoulders project onto the same pixel, so
    # the arms look like they grow out of the neck. Force a minimum bar.
    half = (p["shoulder_r"] - p["shoulder_mid"]).copy()
    if math.hypot(half[0], half[1]) < 0.045:
        for side, sgn in (("l", -1.0), ("r", 1.0)):
            key = "shoulder_" + side
            new = p["shoulder_mid"] + np.array([sgn * 0.045, -0.010, sgn * 0.02])
            shift = new - p[key]          # the whole arm slides out with it,
            p[key] = new                  # otherwise the upper arms slope back
            p["elbow_" + side] = src["upperarm_" + side] + shift    # in and
            p["wrist_" + side] = src["forearm_" + side] + shift     # make a V
    p["head_base"] = p["shoulder_mid"] + up / n * NECK
    p["head_top"] = p["head_base"] + up / n
    p["elbow_l"], p["wrist_l"] = src["upperarm_l"], src["forearm_l"]
    p["elbow_r"], p["wrist_r"] = src["upperarm_r"], src["forearm_r"]
    p["knee_l"], p["ankle_l"] = src["thigh_l"], src["shin_l"]
    p["knee_r"], p["ankle_r"] = src["thigh_r"], src["shin_r"]
    # feet splay slightly outwards, and never collapse to a zero-length stub
    # when the figure walks straight at the lens
    for side, sgn in (("l", -1.0), ("r", 1.0)):
        ankle, toe = p["ankle_" + side], src["foot_" + side].copy()
        v = (toe - ankle) * 0.85
        v[0] += sgn * 0.030
        p["toe_" + side] = ankle + v
    return p





def draw_figure(canvas: np.ndarray, alpha: np.ndarray, pts, anchor, scale,
                ink=(0.96, 0.97, 1.0), fire=None, depth_fade=True) -> None:
    """Draw one figure into `canvas` (BGR float) with a coverage matte."""
    ax, ay = anchor[0] * WC, anchor[1] * HC

    def to_screen(p):
        # screen space: +x right, +y down. depth = toward the camera
        return np.array([ax + p[0] * scale, ay - p[1] * scale])

    pts = build_points(pts)
    segs = []
    for a, b, w in STROKES:
        pa, pb = pts[a], pts[b]
        segs.append(((pa[2] + pb[2]) * 0.5, pa, pb, w))
    for a, b, w in FEET:
        segs.append((pts[a][2], pts[a], pts[b], w))
    # painter's algorithm: far limbs first
    segs.sort(key=lambda s: s[0])

    for depth, pa, pb, w in segs:
        p, q = to_screen(pa), to_screen(pb)
        thick = max(1, int(round(w * scale)))
        # depth cue: the far side of a three-quarter pose is thinner & dimmer
        c = np.array(ink, np.float32)
        if depth_fade:
            c = c * float(np.clip(0.72 + 0.28 * (depth * 2.4 + 1.0), 0.62, 1.0))
        if fire is not None:
            mid = (pa + pb) * 0.5
            d = math.hypot(mid[0] - fire[0], mid[1] - fire[1])
            warm = max(0.0, 1.0 - d / fire[2]) ** 1.5
            c = c * (1.0 + 0.55 * warm) + np.array([0.26, 0.11, 0.02]) * warm * 0.7
        bgr = np.clip(c[::-1] * 255.0, 0, 255).astype(np.uint8)
        pi, qi = tuple(np.round(p).astype(int)), tuple(np.round(q).astype(int))
        cv2.line(canvas, pi, qi, (int(bgr[0]), int(bgr[1]), int(bgr[2])),
                 thick, cv2.LINE_AA)
        cv2.circle(canvas, pi, thick // 2, (int(bgr[0]), int(bgr[1]), int(bgr[2])),
                   -1, cv2.LINE_AA)
        cv2.circle(canvas, qi, max(1, thick // 2), (int(bgr[0]), int(bgr[1]), int(bgr[2])),
                   -1, cv2.LINE_AA)
        for pt in (pi, qi):
            cv2.circle(alpha, pt, max(1, thick // 2 + 1), 255, -1, cv2.LINE_AA)
        cv2.line(alpha, pi, qi, 255, thick + 2, cv2.LINE_AA)

    # head: a ball seated on the neck, so it can never float away
    pts = build_points(pts) if "head_base" not in pts else pts
    neck = pts["head_base"]
    crown = pts["head_top"]
    d3 = crown - neck
    n3 = float(np.linalg.norm(d3[:2])) or 1.0
    r = HEAD_R * scale
    c3 = neck + d3 / n3 * (r * 0.86 / scale)
    col = np.array(ink, np.float32)
    if fire is not None:
        d = math.hypot(c3[0] - fire[0], c3[1] - fire[1])
        warm = max(0.0, 1.0 - d / fire[2]) ** 1.5
        col = col * (1.0 + 0.5 * warm) + np.array([0.24, 0.10, 0.02]) * warm * 0.75
    centre = to_screen(c3)
    bgr = tuple(int(v) for v in np.clip(col[::-1] * 255.0, 0, 255))
    cv2.circle(canvas, tuple(np.round(centre).astype(int)), int(r), bgr, -1, cv2.LINE_AA)
    cv2.circle(alpha, tuple(np.round(centre).astype(int)), int(r) + 1, 255, -1, cv2.LINE_AA)


def add_shadow(img: np.ndarray, anchor, scale, strength: float = 0.55,
               width: float = 0.85) -> np.ndarray:
    """A soft contact shadow, painted under the feet."""
    ax, ay = int(anchor[0] * WC), int(anchor[1] * HC)
    rx, ry = int(scale * 0.30 * width), int(scale * 0.075)
    if rx < 2 or ry < 2:
        return img
    layer = np.zeros((HC, WC), np.float32)
    cv2.ellipse(layer, (ax, ay), (rx, ry), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
    layer = cv2.GaussianBlur(layer, (0, 0), 9 * SS)
    return img * (1.0 - layer[..., None] * strength)


# --------------------------------------------------------------------- extra
class Air:
    """Fire light, embers, fog and grain - what sits *between* the layers."""

    def __init__(self) -> None:
        rng = np.random.default_rng(7)
        self.embers = rng.random((60, 4))
        yy, xx = np.mgrid[0:HC, 0:WC].astype(np.float32)
        self.nx, self.ny = xx / WC, yy / HC
        self.grain = rng.normal(0, 3.2, (H, W, 1)).astype(np.float32)
        r = np.sqrt(((self.nx - 0.5) / 0.62) ** 2 + ((self.ny - 0.5) / 0.66) ** 2)
        self.vig = np.clip(1.06 - 0.34 * np.clip(r - 0.34, 0, 2) ** 1.6, 0.55, 1.06)
        self.mist = None

    def fog(self, img: np.ndarray, t: float, amount: float = 0.10) -> np.ndarray:
        if self.mist is None:
            rng = np.random.default_rng(3)
            m = rng.normal(0, 1, (26, 14)).astype(np.float32)
            for k in (2, 4, 8):
                m += cv2.resize(rng.normal(0, 1, (max(2, 26 // k), max(2, 14 // k))).astype(np.float32),
                                (14, 26), interpolation=cv2.INTER_CUBIC) * (0.5 * k / 4)
            m -= m.min()
            self.mist = m / max(1e-6, m.max())
        band = np.clip((self.ny - 0.62) / 0.30, 0, 1)
        band = np.clip(np.sin(band * math.pi), 0, 1) ** 1.3
        m = np.roll(self.mist, int(t * 26) % 26, axis=0)
        m = cv2.resize(m, (WC, HC), interpolation=cv2.INTER_CUBIC)
        m = cv2.GaussianBlur(m, (0, 0), 6 * SS)
        a = np.clip(m * band * amount, 0, 1)[..., None]
        tint = np.array([0.60, 0.66, 0.82], np.float32)[::-1]     # BGR
        return img * (1 - a) + tint * a

    def fire_glow(self, img: np.ndarray, t: float, cx: float, cy: float,
                  radius: float, strength: float, flicker: float) -> np.ndarray:
        d = np.sqrt(((self.nx - cx) * 1.0) ** 2 + ((self.ny - cy) * 1.25) ** 2) / radius
        fall = np.clip(1.0 - d, 0, 1) ** 2.0
        keep = np.clip((d - 0.16) / 0.30, 0, 1)
        warm = np.array([0.30, 0.55, 1.0], np.float32)            # BGR of warm light
        return img * (1.0 + fall[..., None] * keep[..., None] * flicker * strength * warm)

    def sparks(self, img: np.ndarray, t: float, cx: float, cy: float,
               spread: float, rise: float) -> np.ndarray:
        out = img
        for i, p in enumerate(self.embers):
            life = 0.9 + p[0] * 1.3
            u = ((t / life) + p[1]) % 1.0
            x = cx + (p[2] - 0.5) * spread * (0.3 + u) + 0.01 * math.sin(t * 2 + i)
            y = cy - rise * (0.1 + u ** 0.7)
            fade = (1.0 - u) ** 1.8 * min(1.0, u * 14)
            if fade < 0.05:
                continue
            xi, yi = int(x * WC), int(y * HC)
            if not (0 <= xi < WC and 0 <= yi < HC):
                continue
            cv2.circle(out, (xi, yi), 2 if u < 0.6 else 1,
                       tuple(float(v) for v in (0.25 * fade, 0.55 * fade, 1.0 * fade)),
                       -1, cv2.LINE_AA)
        return out


# --------------------------------------------------------------------- shots
def _env_curve(p: float) -> float:
    return p * p * (3 - 2 * p)


SHOTS = []          # filled at the bottom


def shot_wide(t: float, p: float):
    e = _env_curve(p)
    look = lambda tt: motion.curve(tt, [(0.0, -0.05), (0.7, -0.02),  # noqa: E731
                                        (1.25, -0.34), (1.9, -0.30)], ease=True)
    pose = motion.watch(t + 0.5, h=1.76, look_fn=look, lag=0.12)
    return dict(plate="bg_night", zoom=1.055 + 0.05 * e, dx=0.004 * e, dy=-0.004 * e,
                fx=0.5, fy=0.62,
                cast=[dict(pose=pose, x=0.47, y=0.845, hf=0.60, yaw=0.95)])


def shot_close(t: float, p: float):
    e = _env_curve(p)
    look = lambda tt: motion.curve(tt, [(0.0, -0.10), (0.4, -0.08),  # noqa: E731
                                        (0.72, -0.66), (1.1, -0.60),
                                        (2.0, -0.52)], ease=True)
    pose = motion.watch(t, h=1.76, look_fn=look, lag=0.10)
    return dict(plate="bg_night", zoom=1.05 + 0.035 * e, dx=-0.005 * e, dy=0.002 * e,
                fx=0.46, fy=0.40,
                cast=[dict(pose=pose, x=0.45, y=0.99, hf=0.72, yaw=1.18)])


def shot_track(t: float, p: float):
    e = _env_curve(p)
    yaw = 1.50
    yaw = 1.02                                    # three-quarter, not flat profile
    pose, wx, _ = motion.walk_forward(t, 0.0, 0.0, yaw, speed=0.55, h=1.76)
    x = 0.30 + 0.40 * e                            # he walks across the frame
    return dict(plate="bg_night", zoom=1.07, dx=-0.012 * e, dy=0.002 * e,
                fx=0.5, fy=0.60,
                cast=[dict(pose=pose, x=x, y=0.845, hf=0.62, yaw=yaw)])


def shot_fire(t: float, p: float):
    e = _env_curve(p)
    a = motion.warm(t, h=1.70, seed=0.31)
    b = motion.warm(t + 1.1, h=1.66, seed=0.72)
    return dict(plate="mid_camp", zoom=1.05 + 0.05 * e, dx=0.006 * e, dy=-0.004 * e,
                fx=0.5, fy=0.66,
                fire=(0.50, 0.70, 0.30),
                cast=[dict(pose=a, x=0.118, y=0.918, hf=0.375, yaw=0.66, open=0.10),
                      dict(pose=b, x=0.884, y=0.902, hf=0.365, yaw=-0.66, open=0.10)])


def shot_group(t: float, p: float):
    e = _env_curve(p)
    look = lambda tt: motion.curve(tt, [(0.0, 0.0), (0.8, 0.24), (2.0, 0.28)])  # noqa
    a = motion.warm(t, h=1.72, seed=0.2)
    c = motion.watch(t, h=1.78, look_fn=look)
    b = motion.warm(t + 0.9, h=1.68, seed=0.66)
    return dict(plate="mid_camp", zoom=1.13 - 0.06 * e, dx=0.010 - 0.016 * e,
                dy=0.006 - 0.010 * e, fx=0.5, fy=0.58,
                fire=(0.50, 0.70, 0.30),
                cast=[dict(pose=a, x=0.152, y=0.884, hf=0.355, yaw=0.34),
                      dict(pose=c, x=0.512, y=0.902, hf=0.352, yaw=0.12),
                      dict(pose=b, x=0.848, y=0.876, hf=0.360, yaw=-0.30)])


SHOTS = [
    (0.0, 2.0, shot_wide),
    (2.0, 4.0, shot_close),
    (4.0, 6.0, shot_track),
    (6.0, 8.0, shot_fire),
    (8.0, 10.0, shot_group),
]

CAPTIONS = [
    (0.00, 2.00, "RAAT KA", "JUNGLE..."),
    (2.00, 4.00, "NA PHONE.", "NA SAFE GHAR."),
    (4.00, 6.00, "PEHLE", "CHALNA SEEKHO"),
    (6.00, 8.00, "AAG =", "PEHLA GHAR"),
    (8.00, 10.00, "PEHRA", "+ TEAMWORK"),
]


# ---------------------------------------------------------------------- reel
class Reel:
    def __init__(self) -> None:
        self.plates = {n: Plate(n) for n in ("bg_night", "mid_camp")}
        self.air = Air()
        self.captions = [{k: self._line(txt, col) for k, (txt, col) in
                          (("first", (a, CREAM)), ("second", (b, GOLD)))}
                         for _, _, a, b in CAPTIONS]
        self.tag = ImageFont.truetype(str(FONTS / "BarlowCondensed-Bold.ttf"), 30)

    @staticmethod
    def _line(text: str, colour) -> Image.Image:
        size = 116
        while size > 40:
            f = ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), size)
            if f.getlength(text) <= 930:
                break
            size -= 6
        d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        box = d.textbbox((0, 0), text, font=f)
        im = Image.new("RGBA", (box[2] - box[0] + 40, box[3] - box[1] + 46), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((20 - box[0], 18 - box[1]), text, font=f,
                                fill=colour + (255,))
        return im

    def shot_for(self, t: float):
        for start, end, fn in SHOTS:
            if start <= t < end:
                return fn, start, end
        s, e, fn = SHOTS[-1]
        return fn, s, e

    def frame(self, t: float) -> Image.Image:
        fn, start, end = self.shot_for(t)
        p = (t - start) / (end - start)
        sc = fn(t, p)

        plate = self.plates[sc["plate"]]
        img = plate.layer(sc["zoom"], sc["dx"], sc["dy"], sc["fx"], sc["fy"])

        # ---- characters: flat drawing, real skeleton --------------------
        matte = np.zeros((HC, WC), np.uint8)
        fire = sc.get("fire")
        cast = []
        for c in sc["cast"]:
            scale = c["hf"] * HC / UM
            cast.append((c, scale, (c["x"], c["y"])))
            img = add_shadow(img, (c["x"], c["y"]), scale, 0.5)
        # every figure goes onto ONE ink layer - copying the plate per figure
        # silently erased everyone except the last one in a group shot
        layer = img.copy()
        for c, scale, anchor in cast:
            pts = pose_points(open_arms(c["pose"], c.get("open", 0.22)),
                              c["yaw"], UM)
            draw_figure(layer, matte, pts, anchor, scale,
                        fire=(fire[0] - c["x"], (c["y"] - fire[1]) * 1.1, fire[2])
                        if fire else None)

        m2 = matte.astype(np.float32) / 255.0          # (H, W)
        m = m2[..., None]
        # a soft dark halo behind the ink: on a bright plate the white figure
        # needs its own black edge or the background eats the silhouette
        dark = cv2.GaussianBlur(m2, (0, 0), 5 * SS)[..., None]
        img = img * (1.0 - 0.34 * dark)
        img = img * (1.0 - m) + layer * m
        bloom = cv2.GaussianBlur(m2, (0, 0), 14 * SS)[..., None]
        img = img + bloom * np.array([0.55, 0.62, 0.72], np.float32) * 0.16

        # ---- air, light, grain -----------------------------------------
        flick = 0.5 + 0.5 * math.sin(t * 9.1) * math.sin(t * 3.7 + 1.2)
        if fire:
            img = self.air.fire_glow(img, t, fire[0], fire[1], fire[2], 0.85, flick)
            img = self.air.sparks(img, t, fire[0], fire[1] - 0.05, 0.16, 0.34)
        img = self.air.fog(img, t, 0.10 if fire else 0.16)

        # gentle film curve
        img = np.clip(img, 0, 1)
        img = img * img * (3 - 2 * img) * 0.20 + img * 0.80
        img = img * self.air.vig[..., None]

        yy = np.linspace(0.0, 1.0, HC, dtype=np.float32)
        scrim = 1.0 - 0.42 * np.clip((yy - 0.66) / 0.34, 0.0, 1.0) ** 1.5
        img = img * scrim[:, None, None]

        out = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
        out = np.clip(out * 255.0, 0, 255) + self.air.grain
        im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=32, threshold=2))
        self.overlay(im, t)
        return im

    def overlay(self, im: Image.Image, t: float) -> None:
        d = ImageDraw.Draw(im, "RGBA")
        d.text((54, 104), "MONARCHVOICE  /  SURVIVAL FILE 01  /  PRE-VIZ 2.5D",
               font=self.tag, fill=(255, 226, 171, 232),
               stroke_width=2, stroke_fill=(18, 18, 22, 180))
        d.rounded_rectangle((54, 166, 1026, 173), radius=3, fill=(255, 246, 220, 64))
        d.rounded_rectangle((54, 166, 54 + max(7, round(972 * t / DURATION)), 173),
                            radius=3, fill=GOLD + (232,))
        for i in range(1, 5):
            x = 54 + round(972 * i / 5)
            d.rounded_rectangle((x - 1, 159, x + 1, 180), radius=1, fill=(10, 10, 14, 210))
        for i, (start, end, _, _) in enumerate(CAPTIONS):
            if not start <= t < end:
                continue
            art = self.captions[i]
            enter = min(1.0, (t - start) / 0.18)
            leave = min(1.0, max(0.0, (end - t) / 0.14))
            if leave <= 0:
                break
            a = round(255 * min(1.0, enter * 1.8, leave * 1.5))
            y = 1462
            for key in ("first", "second"):
                glyph = art[key]
                if a < 255:
                    glyph = glyph.copy()
                    glyph.putalpha(glyph.getchannel("A").point(lambda v: v * a // 255))
                im.paste(glyph, (34, y), glyph.getchannel("A"))
                y += glyph.height - 26
            break


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=round(FPS * DURATION))
    ap.add_argument("--segment", type=Path)
    args = ap.parse_args()

    import shutil
    ff = shutil.which("ffmpeg")
    if not ff:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()

    seg = args.segment or (BUILD / f"s25_{args.start:04d}.mp4")
    seg.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", str(seg)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    reel = Reel()
    try:
        assert proc.stdin is not None
        for n in range(args.start, args.end):
            proc.stdin.write(reel.frame(n / FPS).tobytes())
            if (n - args.start) % 24 == 0:
                print(f"frame {n}/{args.end}", flush=True)
        proc.stdin.close()
        assert proc.stderr is not None
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError(err)
    except BaseException:
        proc.kill()
        raise
    print(f"wrote {seg}")


if __name__ == "__main__":
    main()
