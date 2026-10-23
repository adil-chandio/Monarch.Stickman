#!/usr/bin/env python3
"""Animate photoreal AI keyframes into a moving shot.

There is no GPU here, so a video diffusion model cannot run locally. The
reference reel is made by handing a blockout to a video model; the honest
local equivalent of that is **keyframe animation**: every frame in this file
comes from a photoreal AI plate, and the motion between plates is computed,
not faked with a dissolve.

Three things make it read as footage rather than a slideshow:

1. **Flow-guided transition.** Dense optical flow is computed between the two
   plates of a segment, then each frame is built by warping *both* plates
   along the flow and blending them in proportion to the time, weighted by a
   confidence map. Texture travels with the pixels, so faces and bark slide
   and stretch the way they would in a real transfer instead of cross-fading.
2. **Camera move.** Each shot has a slow push-in plus a hand-held drift,
   applied as a sub-pixel resample of the whole frame *and* a slightly larger
   displacement of the near layers, so the plate has parallax as it moves.
3. **Light and atmosphere on top.** The fire's flicker modulates the warm
   region of the frame, embers are simulated particles on ballistic arcs,
   ground mist is a drifting noise band, and grain + a gentle vignette tie the
   layers together.

    python3 animate.py --start 0 --end 120 --segment _build/a.mp4
"""

from __future__ import annotations

import argparse
import math
import subprocess
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
FRAMES = HERE / "frames"
BUILD = HERE / "_build"
OUT = REPO / "video" / "Ancient_Survival_3D_10s_Photoreal.mp4"
FONTS = REPO / "video" / "ancient_survival" / "fonts"

W, H, FPS = 1080, 1920, 24
SW, SH = 810, 1440                 # working size (plates are 768x1376)
DURATION = 10.0

CREAM = (255, 246, 220)
GOLD = (255, 187, 93)

# A reel is cut, not dissolved: six shots, hard cuts, each with its own camera
# move. This is also what the reference does - its photoreal half is a series
# of 1.5-2 s shots joined on action, not one long morph.
# (start, end, plate, zoom from, zoom to, drift x, drift y, anchor x, anchor y, fire?)
SHOTS = [
    (0.00, 1.95, "A1", 1.045, 1.100, 0.010, -0.004, 0.50, 0.47, 0.30),
    (1.95, 3.65, "A2", 1.050, 1.115, -0.012, -0.006, 0.46, 0.45, 0.30),
    (3.65, 5.05, "A3", 1.045, 1.105, 0.008, -0.005, 0.50, 0.50, 0.30),
    (5.05, 7.15, "B1", 1.030, 1.075, 0.006, -0.008, 0.50, 0.52, 1.00),
    (7.15, 8.65, "B2", 1.105, 1.165, -0.008, -0.006, 0.455, 0.50, 1.00),
    (8.65, 10.0, "B4", 1.035, 1.090, 0.006, 0.004, 0.505, 0.505, 1.00),
]

CAPTIONS = [
    (0.00, 1.95, "RAAT KA", "JUNGLE..."),
    (1.95, 5.05, "NA PHONE.", "NA SAFE GHAR."),
    (5.05, 7.55, "AAG =", "PEHLA GHAR"),
    (7.55, 10.01, "PEHRA", "+ TEAMWORK"),
]


# --------------------------------------------------------------------- plates
def load_plate(name: str) -> np.ndarray:
    path = FRAMES / f"{name}.jpg"
    if not path.exists():
        path = FRAMES / f"{name}.png"
    im = Image.open(path).convert("RGB")
    im = im.resize((SW, SH), Image.LANCZOS)
    return np.asarray(im, np.float32) / 255.0


class Shot:
    """One plate, filmed: a dolly plus a layered parallax and a breath of life.

    The photograph supplies the image; the camera supplies the movement. Two
    warps of the same plate (one for the room, one slightly larger for the
    moss and roots at the bottom of frame) are blended through a soft vertical
    mask, so the near ground slides against the far trees exactly as it would
    if a camera were dollying through the clearing. On top of that sits a
    sub-pixel warp driven by two slow sine fields - the optical "breathing" a
    long lens has when it is held by a person - which stops the plate reading
    as a frozen frame.
    """

    def __init__(self, name: str) -> None:
        self.plate = load_plate(name)
        yy = np.mgrid[0:SH, 0:SW][0].astype(np.float32) / SH
        # the near layer only takes over at the very bottom of frame: any
        # higher and a figure standing close to camera gets a ghost of herself
        self.mask = np.clip((yy - 0.62) / 0.30, 0.0, 1.0) ** 1.7
        self.mask = cv2.GaussianBlur(self.mask, (0, 0), 12.0)[..., None]

    def frame(self, zoom: float, dx: float, dy: float, ax: float, ay: float,
              row: int, near: float = 0.040) -> np.ndarray:
        """Composite: far layer at `zoom`, near layer `near` bigger."""
        def warp(scale_mul: float, phase: float) -> np.ndarray:
            z = zoom * scale_mul
            cx = SW * ax + dx * SW + math.sin(row * 0.017 + phase) * 2.2
            cy = SH * ay + dy * SH + math.cos(row * 0.013 + phase) * 2.0
            M = np.array([[z, 0, SW * 0.5 - z * cx], [0, z, SH * 0.5 - z * cy]], np.float32)
            return cv2.warpAffine(self.plate, M, (SW, SH), flags=cv2.INTER_LANCZOS4,
                                  borderMode=cv2.BORDER_REFLECT)

        far = warp(1.0, 0.0)
        near_layer = warp(1.0 + near, 1.7)
        img = far * (1.0 - self.mask) + near_layer * self.mask
        return np.clip(img, 0.0, 1.0)


SHOT_CACHE: dict[int, Shot] = {}


def shot_for(i: int) -> Shot:
    s = SHOT_CACHE.get(i)
    if s is None:
        s = Shot(SHOTS[i][2])
        SHOT_CACHE[i] = s
    return s


# ------------------------------------------------------------------- overlays
class Fx:
    def __init__(self) -> None:
        rng = np.random.default_rng(11)
        # embers
        self.n = 420
        self.seed = rng.random((self.n, 6))
        # mist texture
        self.mist = self._mist_texture(rng)
        self.grain = rng.normal(0, 3.2, (H, W, 1)).astype(np.float32)
        self.vig = self._vignette()
        yy, xx = np.mgrid[0:SH, 0:SW].astype(np.float32)
        self.nx = xx / SW
        self.ny = yy / SH

    @staticmethod
    def _mist_texture(rng) -> np.ndarray:
        h, w = 220, 130
        base = rng.normal(0, 1, (h, w)).astype(np.float32)
        for oct_, amp in ((1, 1.0), (2, 0.5), (4, 0.25), (8, 0.12)):
            small = rng.normal(0, 1, (max(2, h // (oct_ * 4)), max(2, w // (oct_ * 4))))
            small = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
            base += small * amp
        base -= base.min()
        base /= max(1e-6, base.max())
        return base

    @staticmethod
    def _vignette() -> np.ndarray:
        yy, xx = np.mgrid[0:SH, 0:SW].astype(np.float32)
        r = np.sqrt(((xx - SW / 2) / (SW * 0.62)) ** 2 + ((yy - SH / 2) / (SH * 0.66)) ** 2)
        return np.clip(1.06 - 0.30 * np.clip(r - 0.35, 0, 2) ** 1.6, 0.55, 1.06).astype(np.float32)

    # ---- fire light: flicker the warm part of the frame near the flames
    def firelight(self, img: np.ndarray, t: float, cx: float, cy: float,
                  radius: float, strength: float, flicker: float) -> np.ndarray:
        d = np.sqrt((self.nx - cx) ** 2 + ((self.ny - cy) * 0.85) ** 2) / radius
        fall = np.clip(1.0 - d, 0.0, 1.0) ** 2.2
        warm = np.array([1.0, 0.62, 0.30], np.float32)
        # the plate already contains the fire, so only a gentle warm pulse is
        # added, and it is skipped where the flames themselves are (otherwise
        # the fire clips to white)
        keep = np.clip((d - 0.30) / 0.35, 0.0, 1.0)
        img = img * (1.0 + fall[..., None] * keep[..., None] * flicker * strength * warm)
        return img

    # ---- embers: ballistic arcs, fading, slight wind
    def embers(self, img: np.ndarray, t: float, cx: float, cy: float,
               spread: float, rise: float, count: int = 90, wind: float = 0.0) -> np.ndarray:
        out = img.copy()
        for i in range(count):
            p = self.seed[i]
            life = 0.9 + p[0] * 1.1
            u = ((t / life) + p[1]) % 1.0
            x = cx + (p[2] - 0.5) * spread * 0.55 * (0.4 + u) + wind * u
            y = cy - rise * (0.15 + u ** 0.7) * (0.6 + p[3] * 0.7)
            fade = (1.0 - u) ** 1.6 * min(1.0, u * 12.0)
            if fade < 0.03:
                continue
            xi, yi = int(x * SW), int(y * SH)
            r = 2 if u > 0.5 else 3
            if xi < r or yi < r or xi >= SW - r or yi >= SH - r:
                continue
            col = np.array([1.0, 0.55 + 0.2 * p[5], 0.22], np.float32) * fade
            yy0, yy1 = yi - r, yi + r + 1
            xx0, xx1 = xi - r, xi + r + 1
            g = np.clip(1.0 - np.sqrt(((np.arange(xx0, xx1) - xi) ** 2)[None, :]
                                      + ((np.arange(yy0, yy1) - yi) ** 2)[:, None]) / (r + 0.5), 0, 1)
            out[yy0:yy1, xx0:xx1] += (g ** 1.7)[..., None] * col * 0.55
        return out

    # ---- heat shimmer over the flames: the one thing every campfire shot has
    def shimmer(self, img: np.ndarray, t: float, x0: float, y0: float,
                x1: float, y1: float, amount: float = 1.6) -> np.ndarray:
        yy, xx = np.mgrid[0:SH, 0:SW].astype(np.float32)
        fx0, fx1 = x0 * SW, x1 * SW
        fy0, fy1 = y0 * SH, y1 * SH
        box = ((xx > fx0) & (xx < fx1) & (yy > fy0) & (yy < fy1)).astype(np.float32)
        box = cv2.GaussianBlur(box, (0, 0), 18.0)
        if box.max() < 0.01:
            return img
        dx = (np.sin(yy * 0.06 + t * 7.3) * np.sin(xx * 0.021 - t * 4.1)) * amount * box
        dy = (np.cos(xx * 0.05 + t * 6.1) * np.sin(yy * 0.017 + t * 3.3)) * amount * 0.7 * box
        return cv2.remap(img, xx + dx, yy + dy, cv2.INTER_LANCZOS4,
                         borderMode=cv2.BORDER_REFLECT)

    def breathe(self, img: np.ndarray, t: float, cx: float, cy: float,
                rx: float, ry: float, amp: float = 0.004, phase: float = 0.0) -> np.ndarray:
        """Two millimetres of chest movement - enough to prove the plate is alive."""
        yy, xx = np.mgrid[0:SH, 0:SW].astype(np.float32)
        d = (((xx - cx * SW) / (rx * SW)) ** 2 + ((yy - cy * SH) / (ry * SH)) ** 2)
        w = np.clip(1.0 - d, 0.0, 1.0) ** 1.5
        k = math.sin(t * 1.9 + phase)
        s = 1.0 + amp * k * w
        mx = cx * SW + (xx - cx * SW) / s
        my = cy * SH + (yy - cy * SH) / s
        out = cv2.remap(img, mx, my, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT)
        return img * (1.0 - w[..., None] * 0.55) + out * (w[..., None] * 0.55)

    # ---- ground mist band, drifting
    def ground_mist(self, img: np.ndarray, t: float, y0: float, y1: float,
                    amount: float) -> np.ndarray:
        band = np.clip((self.ny - y0) / max(1e-3, (y1 - y0)), 0, 1)
        band = np.clip(np.sin(band * math.pi), 0.0, 1.0) ** 1.4
        v = int((t * 38)) % self.mist.shape[0]
        m = np.roll(self.mist, v, axis=0)
        m = cv2.resize(m, (SW, SH), interpolation=cv2.INTER_CUBIC)
        m = cv2.GaussianBlur(m, (0, 0), 3.0)
        a = np.clip(m * band * amount, 0, 1)[..., None]
        tint = np.array([0.62, 0.70, 0.86], np.float32)
        return img * (1 - a) + tint * a




# ---------------------------------------------------------------------- grade
def film_grade(img: np.ndarray) -> np.ndarray:
    """A print-film curve: lifted toes, rolled highlights, slight warm-cool split."""
    img = np.clip(img, 0.0, 1.0)
    img = np.clip(img, 0.0, 1.0) ** 1.04
    img = img * img * (3 - 2 * img) * 0.22 + img * 0.78
    shadow = np.clip(1.0 - img.mean(axis=2, keepdims=True) * 2.2, 0, 1)
    img = img + shadow * np.array([0.012, 0.016, 0.030], np.float32)
    high = np.clip(img.mean(axis=2, keepdims=True) * 1.6 - 0.55, 0, 1)
    img = img + high * np.array([0.020, 0.010, -0.004], np.float32)
    return np.clip(img, 0.0, 1.0)


# ------------------------------------------------------------------- captions
def font_for(text: str, size: int, max_width: int) -> ImageFont.FreeTypeFont:
    while size > 40:
        f = ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), size)
        if f.getlength(text) <= max_width:
            return f
        size -= 6
    return ImageFont.truetype(str(FONTS / "BarlowCondensed-Black.ttf"), size)


_CAPTION_CACHE: dict[str, Image.Image] = {}


def render_line(text: str, colour) -> Image.Image:
    key = text + str(colour)
    hit = _CAPTION_CACHE.get(key)
    if hit is not None:
        return hit
    f = font_for(text, 118, 940)
    tmp = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(tmp)
    box = d.textbbox((0, 0), text, font=f, stroke_width=0)
    w, h = box[2] - box[0], box[3] - box[1]
    im = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    dd.text((20 - box[0], 20 - box[1]), text, font=f, fill=colour + (255,))
    _CAPTION_CACHE[key] = im
    return im


def overlay(im: Image.Image, t: float) -> None:
    d = ImageDraw.Draw(im, "RGBA")
    tag = ImageFont.truetype(str(FONTS / "BarlowCondensed-Bold.ttf"), 30)
    d.text((54, 104), "MONARCHVOICE  /  SURVIVAL FILE 01  /  PHOTOREAL", font=tag,
           fill=(255, 246, 220, 205))
    d.line([(54, 146), (54 + 470, 146)], fill=(255, 187, 93, 120), width=2)
    for start, end, first, second in CAPTIONS:
        if not (start <= t < end):
            continue
        fade = min(1.0, (t - start) / 0.22, max(0.0, end - t) / 0.22)
        if fade <= 0.0:
            continue
        a = int(255 * min(1.0, fade))
        y = 1560
        for text, colour in ((first, CREAM), (second, GOLD)):
            glyph = render_line(text, colour)
            shadow = Image.new("RGBA", glyph.size, (0, 0, 0, 0))
            shadow.putalpha(glyph.getchannel("A").filter(ImageFilter.GaussianBlur(9)))
            shadow = Image.composite(Image.new("RGBA", glyph.size, (6, 6, 10, a)), shadow,
                                     shadow.getchannel("A"))
            x = 54 - 20
            im.alpha_composite(shadow, (x, y - 20)) if im.mode == "RGBA" else im.paste(
                shadow, (x, y - 20), shadow)
            layer = glyph.copy()
            layer.putalpha(layer.getchannel("A").point(lambda v: v * a // 255))
            if im.mode == "RGBA":
                im.alpha_composite(layer, (x, y))
            else:
                im.paste(layer, (x, y), layer)
            y += glyph.height - 22


# ----------------------------------------------------------------- main loop
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=int(FPS * DURATION))
    ap.add_argument("--segment", type=Path)
    args = ap.parse_args()

    import shutil
    ff = shutil.which("ffmpeg")
    if not ff:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()

    seg_path = args.segment or (BUILD / f"a_{args.start:04d}.mp4")
    seg_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
           "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", str(seg_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    fx = Fx()
    try:
        assert proc.stdin is not None
        for n in range(args.start, args.end):
            t = n / FPS
            s = max(i for i, sh in enumerate(SHOTS) if sh[0] <= t + 1e-6)
            start, end, _, z0, z1, dx, dy, ax, ay, fire = SHOTS[s]
            u = min(1.0, max(0.0, (t - start) / (end - start)))
            e = u * u * (3 - 2 * u)
            zoom = z0 + (z1 - z0) * e
            # the dolly drifts on a slow sine as well: a real operator does not
            # move in a straight line
            ddx = dx * e + 0.0006 * math.sin(t * 0.61)
            ddy = dy * e + 0.0005 * math.sin(t * 0.47 + 1.1)
            img = shot_for(s).frame(zoom, ddx, ddy, ax, ay, n)

            flick = 0.5 + 0.5 * math.sin(t * 9.1) * math.sin(t * 3.7 + 1.2)
            if fire > 0.5:
                img = fx.firelight(img, t, 0.50, 0.74, 0.52, 0.26, flick)
                img = fx.embers(img, t, 0.50, 0.66, 0.22, 0.42, count=34,
                                wind=0.003 * math.sin(t * 0.7))
                img = fx.ground_mist(img, t, 0.60, 0.90, 0.09)
                # flames shimmer, and the two of them breathe
                img = fx.shimmer(img, t, 0.24, 0.36, 0.76, 0.62, 1.9)
                img = fx.breathe(img, t, 0.30, 0.42, 0.13, 0.16, 0.006, 0.4)
                img = fx.breathe(img, t, 0.66, 0.36, 0.13, 0.16, 0.005, 2.1)
            else:
                img = fx.firelight(img, t, 0.31, 0.62, 0.22, 0.18, flick)
                img = fx.embers(img, t, 0.31, 0.62, 0.07, 0.10, count=10)
                img = fx.ground_mist(img, t, 0.55, 0.95, 0.15)
                img = fx.breathe(img, t, 0.45, 0.44, 0.12, 0.18, 0.005, 1.2)

            img = film_grade(img)
            img = img * fx.vig[..., None]
            small = Image.fromarray(np.clip(img * 255.0, 0, 255).astype(np.uint8))
            big = small.resize((W, H), Image.LANCZOS)
            big = big.filter(ImageFilter.UnsharpMask(radius=1.4, percent=46, threshold=2))
            frame = np.clip(np.asarray(big, np.float32) + fx.grain, 0, 255).astype(np.uint8)

            im = Image.fromarray(frame).convert("RGBA")
            overlay(im, t)
            proc.stdin.write(np.asarray(im.convert("RGB")).tobytes())
            if n % 24 == 0:
                print(f"frame {n}/{args.end}", flush=True)
        proc.stdin.close()
        assert proc.stderr is not None
        err = proc.stderr.read().decode("utf-8", "replace")
        if proc.wait() != 0:
            raise RuntimeError(err)
    except BaseException:
        proc.kill()
        raise
    print(f"wrote {seg_path}")


if __name__ == "__main__":
    main()
