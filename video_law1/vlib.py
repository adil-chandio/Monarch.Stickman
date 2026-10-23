#!/usr/bin/env python3
"""vlib — drawing, camera, particles, transitions and post-FX helpers for the v2 explainer."""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageEnhance

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")
FONTS = os.path.join(ROOT, "fonts")

W, H = 1080, 1920
FPS = 30

# ---------------- palette ----------------
PAPER     = (252, 251, 247)
INK       = (24, 24, 28)
INK_SOFT  = (60, 60, 68)
BLUE      = (19, 133, 229)
BLUE_DEEP = (12, 96, 172)
RED       = (198, 24, 44)
RED_DEEP  = (140, 12, 26)
GOLD      = (201, 155, 44)
GOLD_L    = (255, 213, 96)
CREAM     = (246, 241, 230)
NIGHT     = (5, 7, 11)
WHITE     = (255, 255, 255)

# ---------------- fonts ----------------
S4  = os.path.join(FONTS, "PlayfairDisplay_400Regular.ttf")
S7  = os.path.join(FONTS, "PlayfairDisplay_700Bold.ttf")
S8  = os.path.join(FONTS, "PlayfairDisplay_800ExtraBold.ttf")
S9  = os.path.join(FONTS, "PlayfairDisplay_900Black.ttf")
S7I = os.path.join(FONTS, "PlayfairDisplay_700Bold_Italic.ttf")
N4  = os.path.join(FONTS, "Inter_400Regular.ttf")
N6  = os.path.join(FONTS, "Inter_600SemiBold.ttf")
N7  = os.path.join(FONTS, "Inter_700Bold.ttf")
N8  = os.path.join(FONTS, "Inter_800ExtraBold.ttf")
N9  = os.path.join(FONTS, "Inter_900Black.ttf")

_fc = {}
def F(path, size):
    k = (path, int(max(6, size)))
    if k not in _fc:
        _fc[k] = ImageFont.truetype(path, int(max(6, size)))
    return _fc[k]

# ---------------- easing ----------------
def cl(x, a=0.0, b=1.0): return a if x < a else (b if x > b else x)
def eo(t):  t = cl(t); return 1 - (1 - t) ** 3
def ei(t):  t = cl(t); return t * t * t
def eio(t): t = cl(t); return 3 * t * t - 2 * t * t * t
def eob(t, s=1.7):
    t = cl(t) - 1
    return 1 + t * t * ((s + 1) * t + s)
def sg(t, start, dur): return cl((t - start) / max(dur, 1e-6))
def lerp(a, b, t): return a + (b - a) * cl(t)

# ---------------- sprites ----------------
_img_cache, _art_cache = {}, {}

def art_of(name):
    if name in _art_cache:
        return _art_cache[name]
    im = Image.open(os.path.join(ASSETS, name + ".png")).convert("RGB")
    a = np.asarray(im)
    mask = a.min(axis=2) < 243
    ys, xs = np.where(mask)
    if len(xs) == 0:
        xs, ys = np.array([0]), np.array([0])
    x0, x1 = max(0, xs.min() - 6), min(im.width, xs.max() + 7)
    y0, y1 = max(0, ys.min() - 6), min(im.height, ys.max() + 7)
    crop = im.crop((x0, y0, x1, y1))
    _art_cache[name] = crop
    return crop

def _scaled(name, w):
    art = art_of(name)
    w = max(8, int(round(w / 2.0) * 2))
    h = max(4, int(art.height * w / art.width))
    key = (name, w, h)
    if key in _img_cache:
        return _img_cache[key]
    im = art.resize((w, h), Image.LANCZOS)
    _img_cache[key] = im
    return im

def blit(base, im, x, y, opacity=1.0):
    x, y = int(round(x)), int(round(y))
    w, h = im.size
    if opacity <= .01:
        return
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(base.width, x + w), min(base.height, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    crop = base.crop((x0, y0, x1, y1))
    sub = im.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    out = ImageChops.multiply(crop, sub)
    base.paste(out if opacity >= .99 else Image.blend(crop, out, opacity), (x0, y0))

def put(base, name, cx=None, cy=None, max_w=None, max_h=None, scale=1.0, opacity=1.0,
        left=None, right=None, top=None, bottom=None, rot=0):
    art = art_of(name)
    ar = art.width / art.height
    s = max(0.02, round(scale * 80) / 80.0)
    if max_w is not None and max_h is not None: w = min(max_w, max_h * ar)
    elif max_w is not None: w = max_w
    elif max_h is not None: w = max_h * ar
    else: w = 300
    im = _scaled(name, w * s)
    if rot:
        im = im.rotate(rot, expand=True, resample=Image.BICUBIC, fillcolor=WHITE)
    iw, ih = im.size
    x = left if left is not None else (right - iw if right is not None else
                                       (cx if cx is not None else W / 2) - iw / 2)
    y = top if top is not None else (bottom - ih if bottom is not None else
                                     (cy if cy is not None else H / 2) - ih / 2)
    blit(base, im, x, y, opacity)
    return (x, y, iw, ih)

# ---------------- text ----------------
def tw(d, s, f):
    b = d.textbbox((0, 0), s, font=f)
    return b[2] - b[0]

def wrap(d, txt, f, max_w):
    words, lines, cur = txt.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if tw(d, t, f) <= max_w or not cur: cur = t
        else: lines.append(cur); cur = wd
    if cur: lines.append(cur)
    return lines

def T(base, xy, txt, f, fill=INK, anchor="mm", alpha=1.0, shadow=None, stroke=0, stroke_fill=None):
    d = ImageDraw.Draw(base)
    a = int(255 * cl(alpha))
    if a <= 3: return
    x, y = xy
    if shadow and alpha > .99:
        d.text((x + shadow[0], y + shadow[1]), txt, font=f, fill=shadow[2], anchor=anchor)
    d.text((x, y), txt, font=f, fill=fill if alpha >= .99 else fill + (a,), anchor=anchor,
           stroke_width=stroke, stroke_fill=stroke_fill or fill)

def T_track(base, cx, y, txt, f, fill=INK, track=4, alpha=1.0, shadow=None):
    """Letter-spaced centered text."""
    d = ImageDraw.Draw(base)
    widths = [tw(d, ch, f) for ch in txt]
    total = sum(widths) + track * (len(txt) - 1)
    x = cx - total / 2
    a = int(255 * cl(alpha))
    if a <= 3: return
    for ch, wd in zip(txt, widths):
        if ch != " ":
            if shadow and alpha > .99:
                d.text((x + shadow[0], y + shadow[1]), ch, font=f, fill=shadow[2], anchor="lm")
            d.text((x, y), ch, font=f, fill=fill if alpha >= .99 else fill + (a,), anchor="lm")
        x += wd + track

def rgba_text(text, f, color, alpha=255):
    tmp = Image.new("RGBA", (4, 4))
    d = ImageDraw.Draw(tmp)
    b = d.textbbox((0, 0), text, font=f)
    img = Image.new("RGBA", (b[2] + 8, b[3] + 12), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((4 - b[0], 4 - b[1]), text, font=f, fill=color + (alpha,))
    return img

def put_text_scaled(base, text, f, color, cx, cy, scale=1.0, alpha=1.0, anchor_mm=True):
    if alpha <= .02 or scale <= .05: return 0
    img = rgba_text(text, f, color, int(255 * cl(alpha)))
    if abs(scale - 1) > .01:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                         Image.BICUBIC)
    base.paste(img, (int(cx - img.width / 2), int(cy - img.height / 2)), img)
    return img.height

# ---------------- shapes ----------------
def halo(base, cx, cy, r, color=(232, 228, 218), opacity=1.0, falloff=0.8):
    size = int(r * 2)
    if size < 8: return
    half = size / 2.0
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    d = np.sqrt((xx - half) ** 2 + (yy - half) ** 2) / half
    a = np.clip(1 - d, 0, 1) ** falloff
    layer = Image.new("RGBA", (size, size), color + (255,))
    layer.putalpha(Image.fromarray((a * 255 * opacity).astype(np.uint8)))
    base.paste(layer, (int(cx - r), int(cy - r)), layer)

def glow_ring(base, cx, cy, r, width=6, color=RED, alpha=.8):
    if r <= 2 or alpha <= .02: return
    size = int(r * 2 + width * 4)
    lay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    c = size / 2
    d.ellipse([c - r, c - r, c + r, c + r], outline=color + (int(255 * cl(alpha)),), width=width)
    lay = lay.filter(ImageFilter.GaussianBlur(width * .8))
    base.paste(lay, (int(cx - c), int(cy - c)), lay)

def shadow_rr(base, box, radius, alpha=62, blur=20, dy=12, fill=None):
    x0, y0, x1, y1 = [int(v) for v in box]
    pad = blur * 3
    sh = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad + dy, pad + (x1 - x0), pad + dy + (y1 - y0)],
                                         radius, fill=(14, 16, 24, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    base.paste(sh, (x0 - pad, y0 - pad), sh)
    if fill:
        ImageDraw.Draw(base).rounded_rectangle([x0, y0, x1, y1], radius, fill=fill)

def pill(base, cx, cy, txt, fill=INK, fg=WHITE, size=36, scale=1.0, opacity=1.0,
         fpath=None, padx=28, pady=13, rot=0, border=None, track=0):
    if opacity <= .02 or scale <= .02: return
    fpath = fpath or N7
    s = max(0.1, scale)
    fnt = F(fpath, size * s)
    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    b = tmp.textbbox((0, 0), txt, font=fnt)
    tw_, th_ = b[2] - b[0], b[3] - b[1]
    w = int(tw_ + padx * 2 * s + track * (len(txt) - 1) * s)
    h = int(th_ + pady * 2 * s + size * s * 0.42)
    lay = Image.new("RGBA", (w + 70, h + 70), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([35, 35, 35 + w, 35 + h], h // 2, fill=fill + (int(255 * opacity),))
    if border:
        d.rounded_rectangle([35, 35, 35 + w, 35 + h], h // 2, outline=border + (int(255 * opacity),),
                            width=max(2, int(4 * s)))
    if track:
        T_track(lay, 35 + w / 2, 35 + h / 2 + 2, txt, fnt, fg, track * s, opacity)
    else:
        d.text((35 + w / 2, 35 + h / 2 + 1), txt, font=fnt, fill=fg + (int(255 * opacity),), anchor="mm")
    if rot:
        lay = lay.rotate(rot, expand=True, resample=Image.BICUBIC)
    base.paste(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)), lay)

def arrow(base, pts, color=INK, width=7, progress=1.0):
    if progress <= 0: return
    d = ImageDraw.Draw(base)
    lens = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(lens) * cl(progress)
    p, acc = [pts[0]], 0.0
    for i, l in enumerate(lens):
        if acc + l <= total:
            p.append(pts[i + 1]); acc += l
        else:
            r = (total - acc) / max(l, 1e-6)
            a, b = pts[i], pts[i + 1]
            p.append((a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r)); break
    if len(p) < 2: return
    d.line([tuple(map(int, q)) for q in p], fill=color, width=width, joint="curve")
    a, b = p[-2], p[-1]
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    L, s = width * 4.2, 0.52
    d.polygon([b, (b[0] - L * math.cos(ang - s), b[1] - L * math.sin(ang - s)),
               (b[0] - L * math.cos(ang + s), b[1] - L * math.sin(ang + s))], fill=color)

def underline(base, x0, x1, y, color=RED, width=10, progress=1.0):
    if progress <= 0: return
    d = ImageDraw.Draw(base)
    xe = x0 + (x1 - x0) * cl(progress)
    d.line([(x0, y), (xe, y)], fill=color, width=width)
    d.line([(x0, y + width * .7), (x0 + (xe - x0) * .92, y + width * .7)], fill=color, width=max(2, width // 3))

def sparkle(d, x, y, r, color=GOLD, width=5, rot=0):
    if r <= 0.4: return
    for a in (0, math.pi / 2):
        dx, dy = math.cos(a + rot) * r, math.sin(a + rot) * r
        d.line([(x - dx, y - dy), (x + dx, y + dy)], fill=color, width=width)

def star4(base, x, y, r, color=GOLD_L, alpha=1.0):
    if r <= 1 or alpha <= .02: return
    size = int(r * 2.6)
    lay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    c = size / 2
    d.polygon([(c, c - r), (c + r * .22, c - r * .22), (c + r, c), (c + r * .22, c + r * .22),
               (c, c + r), (c - r * .22, c + r * .22), (c - r, c), (c - r * .22, c - r * .22)],
              fill=color + (int(255 * alpha),))
    lay = lay.filter(ImageFilter.GaussianBlur(max(0.4, r * .12)))
    base.paste(lay, (int(x - c), int(y - c)), lay)

def bubble(base, cx, cy, w, h, fill=WHITE, outline=INK, lw=6, tail=None, opacity=1.0, radius=None):
    if opacity <= .02: return
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    r = radius if radius is not None else int(min(w, h) * .26)
    a = int(255 * opacity)
    if tail:
        tx, ty = tail
        d.polygon([(cx - 55, cy + h / 2 - 6), (cx + 55, cy + h / 2 - 6), (tx, ty)],
                  fill=fill + (a,), outline=outline + (a,))
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], r,
                        fill=fill + (a,), outline=outline + (a,), width=lw)
    base.paste(lay, (0, 0), lay)

def stamp(base, cx, cy, txt, ang=-9, color=RED, size=84, scale=1.0, opacity=1.0):
    if opacity <= .02 or scale <= .02: return
    fnt = F(N9, size * scale)
    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    b = tmp.textbbox((0, 0), txt, font=fnt)
    w, h = int(b[2] - b[0] + 76), int(b[3] - b[1] + 52)
    lay = Image.new("RGBA", (w + 110, h + 110), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    a = int(255 * cl(opacity))
    d.rounded_rectangle([55, 55, 55 + w, 55 + h], 14, outline=color + (a,), width=11)
    d.rounded_rectangle([74, 74, 36 + w, 36 + h], 10, outline=color + (int(a * .45),), width=3)
    d.text((55 + w / 2, 55 + h / 2 + 2), txt, font=fnt, fill=color + (a,), anchor="mm")
    lay = lay.rotate(ang, expand=True, resample=Image.BICUBIC)
    base.paste(lay, (int(cx - lay.width / 2), int(cy - lay.height / 2)), lay)

def cover(base, path, box, radius=0, opacity=1.0, focus_y=0.5, zoom=1.0, focus_x=0.5, outline=None, ow=4):
    im = Image.open(path).convert("RGB")
    x0, y0, x1, y1 = [int(v) for v in box]
    bw, bh = x1 - x0, y1 - y0
    s = max(bw / im.width, bh / im.height) * zoom
    im = im.resize((max(2, int(im.width * s) + 1), max(2, int(im.height * s) + 1)), Image.LANCZOS)
    l = int((im.width - bw) * cl(focus_x))
    t = int((im.height - bh) * cl(focus_y))
    im = im.crop((l, t, l + bw, t + bh))
    if radius:
        mask = Image.new("L", (bw, bh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, bw - 1, bh - 1], radius, fill=255)
        base.paste(im, (x0, y0), mask if opacity >= .99 else mask.point(lambda v: int(v * opacity)))
    else:
        base.paste(im, (x0, y0), None if opacity >= .99 else Image.new("L", (bw, bh), int(255 * opacity)))
    if outline:
        ImageDraw.Draw(base).rounded_rectangle([x0, y0, x1, y1], radius, outline=outline, width=ow)

def boss_sil(base, cx, bottom, w=700, opacity=.16, blur=2.0):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    hd = w * .5
    top = bottom - w * 1.72
    d.ellipse([cx - hd / 2, top, cx + hd / 2, top + hd], fill=(36, 46, 62, 255))
    d.rounded_rectangle([cx - w * .60, top + hd * .84, cx + w * .60, bottom],
                        int(w * .38), fill=(36, 46, 62, 255))
    lay.putalpha(lay.getchannel("A").point(lambda v: int(v * opacity)))
    lay = lay.filter(ImageFilter.GaussianBlur(blur))
    base.paste(lay, (0, 0), lay)

# ---------------- paper bg ----------------
_paper = None
def paper_bg():
    global _paper
    if _paper is not None: return _paper.copy()
    base = Image.new("RGB", (W, H), PAPER)
    rng = np.random.default_rng(11)
    grain = rng.normal(0, 2.4, (H // 3, W // 3)).astype(np.float32)
    g = np.array(Image.fromarray(np.uint8(np.clip(grain + 128, 0, 255)))
                 .resize((W, H), Image.BILINEAR)).astype(np.int16) - 128
    arr = np.array(base).astype(np.int16)
    for c in range(3):
        arr[:, :, c] = np.clip(arr[:, :, c] + g, 0, 255)
    base = Image.fromarray(arr.astype(np.uint8))
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * .28, -H * .16, W * 1.28, H * 1.16], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(150))
    edge = Image.new("RGB", (W, H), (236, 232, 222))
    base = Image.composite(base, Image.blend(base, edge, .55), vig)
    _paper = base
    return base.copy()

# ---------------- camera ----------------
def apply_camera(img, zoom=1.0, fx=0.5, fy=0.5, shake=(0, 0), rot=0.0):
    if abs(zoom - 1) < .002 and shake == (0, 0) and abs(rot) < .01:
        return img
    z = max(1.0, zoom)
    big = img.resize((int(W * z), int(H * z)), Image.BICUBIC)
    if abs(rot) > .01:
        big = big.rotate(rot, resample=Image.BICUBIC, center=(big.width / 2, big.height / 2),
                         fillcolor=WHITE)
        big = big.crop(((big.width - int(W * z)) // 2, (big.height - int(H * z)) // 2,
                        (big.width + int(W * z)) // 2, (big.height + int(H * z)) // 2))
    cx = cl(fx, 0, 1) * big.width + shake[0]
    cy = cl(fy, 0, 1) * big.height + shake[1]
    left = int(cl(cx - W / 2, 0, big.width - W))
    top = int(cl(cy - H / 2, 0, big.height - H))
    return big.crop((left, top, left + W, top + H))

# ---------------- particles ----------------
def make_particles(kind, n, seed):
    r = np.random.default_rng(seed)
    P = []
    for i in range(n):
        P.append(dict(
            x=r.uniform(-30, W + 30), y=r.uniform(-40, H + 40),
            vx=r.uniform(-18, 18), vy=r.uniform(-70, 70),
            s=r.uniform(2.2, 7.0), ph=r.uniform(0, 6.28), sp=r.uniform(.6, 2.0),
            col=None, life=r.uniform(.6, 1.0),
        ))
    if kind == "ember":
        for p in P:
            p["vy"] = -r.uniform(55, 150); p["vx"] = r.uniform(-22, 22); p["s"] = r.uniform(2, 6)
    elif kind == "confetti":
        for p in P:
            p["vy"] = r.uniform(90, 230); p["vx"] = r.uniform(-40, 40); p["s"] = r.uniform(5, 11)
    elif kind == "dust":
        for p in P:
            p["vy"] = r.uniform(-16, 16); p["s"] = r.uniform(2, 5)
    elif kind == "spark":
        for p in P:
            p["vy"] = r.uniform(-95, 95); p["s"] = r.uniform(2, 5)
    return P

CONF_COLORS = [RED, BLUE, GOLD, GOLD_L, (60, 160, 110), (240, 120, 60)]

def draw_particles(base, P, t, kind, density=1.0, tint=None, y_min=0):
    if not P or density <= .02: return
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for i, p in enumerate(P):
        if i / len(P) > density: continue
        x = (p["x"] + p["vx"] * t + math.sin(t * p["sp"] + p["ph"]) * 18) % (W + 120) - 60
        y = (p["y"] + p["vy"] * t) % (H + 120) - 60
        if y < y_min:
            continue
        s = p["s"]
        flick = .55 + .45 * math.sin(t * p["sp"] * 3.1 + p["ph"])
        if kind == "ember":
            col = tint or (255, int(120 + 90 * flick), int(30 + 40 * flick))
            a = int(200 * flick)
            d.ellipse([x - s, y - s * 1.3, x + s, y + s * 1.3], fill=col + (a,))
            d.ellipse([x - s * 2.6, y - s * 2.6, x + s * 2.6, y + s * 2.6], fill=col + (int(a * .12),))
        elif kind == "confetti":
            col = CONF_COLORS[i % len(CONF_COLORS)]
            a = int(220 * min(1, density * 1.2))
            ang = t * p["sp"] * 2 + p["ph"]
            dx, dy = math.cos(ang) * s, math.sin(ang) * s * .6
            d.polygon([(x - dx, y - dy), (x + dy, y - dx), (x + dx, y + dy), (x - dy, y + dx)],
                      fill=col + (a,))
        elif kind == "dust":
            col = tint or (176, 168, 150)
            a = int(70 * flick)
            d.ellipse([x - s * .8, y - s * .8, x + s * .8, y + s * .8], fill=col + (a,))
        else:  # spark
            col = tint or (255, 80, 80)
            a = int(210 * flick)
            d.line([(x - s * 2, y), (x + s * 2, y)], fill=col + (a,), width=2)
            d.line([(x, y - s * 2), (x, y + s * 2)], fill=col + (a,), width=2)
    base.paste(lay, (0, 0), lay)

# ---------------- post fx ----------------
VIGNETTE = None
def vignette_mask(strength=.20):
    global VIGNETTE
    if VIGNETTE is None:
        m = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(m)
        d.rectangle([0, 0, W, H], fill=0)
        d.ellipse([-W * .34, -H * .22, W * 1.34, H * 1.22], fill=255)
        m = m.filter(ImageFilter.GaussianBlur(170))
        VIGNETTE = m
    return VIGNETTE.point(lambda v: int((255 - v) * strength))

def apply_vignette(img, strength=.22):
    m = vignette_mask(strength)
    black = Image.new("RGB", (W, H), (6, 8, 12))
    return Image.composite(black, img, m)

GRAINS = []
def grain_tiles():
    if GRAINS: return GRAINS
    for k in range(6):
        r = np.random.default_rng(100 + k)
        n = r.normal(0, 12, (H // 2, W // 2)).astype(np.float32)
        a = np.clip(128 + n, 0, 255).astype(np.uint8)
        g = Image.fromarray(a).resize((W, H), Image.BILINEAR).convert("RGB")
        GRAINS.append(g)
    return GRAINS

def apply_grain(img, idx, amt=0.055):
    g = grain_tiles()[idx % len(GRAINS)]
    return Image.blend(img, ImageChops.multiply(img, ImageEnhance.Brightness(g).enhance(1.06)), amt)

def grade(img, tint=None, amt=0.0, contrast=1.0, brightness=1.0, saturation=1.0):
    out = img
    if abs(brightness - 1) > .01:
        out = ImageEnhance.Brightness(out).enhance(brightness)
    if abs(contrast - 1) > .01:
        out = ImageEnhance.Contrast(out).enhance(contrast)
    if abs(saturation - 1) > .01:
        out = ImageEnhance.Color(out).enhance(saturation)
    if tint and amt > 0.001:
        out = Image.blend(out, Image.new("RGB", (W, H), tint), amt)
    return out

def flash(img, color=(255, 255, 255), amt=0.0):
    if amt <= .003: return img
    return Image.blend(img, Image.new("RGB", (W, H), color), cl(amt) * .9)

def glitch(img, t, amount=0.0):
    if amount <= .02: return img
    r = np.random.default_rng(int(t * 1000) % 9973)
    out = img.copy()
    for _ in range(int(4 + 8 * amount)):
        y = int(r.uniform(0, H - 80))
        h = int(r.uniform(6, 60))
        dx = int(r.uniform(-40, 40) * amount)
        strip = img.crop((0, y, W, y + h))
        out.paste(strip, (dx, y))
    return out

# ---------------- transitions ----------------
def tr_mask(kind, p, w=W, h=H):
    p = cl(p)
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if kind == "slide":
        # incoming comes up from bottom
        y = int(h * (1 - eo(p)))
        d.rectangle([0, y, w, h], fill=255)
        for i in range(24):  # soft edge
            yy = y - i
            d.rectangle([0, yy, w, yy + 1], fill=int(255 * (1 - i / 24) ** 2))
    elif kind == "wipe":
        x = int(w * eo(p))
        d.rectangle([0, 0, x, h], fill=255)
        for i in range(30):
            xx = x - i
            d.rectangle([xx, 0, xx + 1, h], fill=int(255 * (1 - i / 30) ** 2))
    elif kind == "slam":
        s = 1.25 - .25 * eo(p)
        ww, hh = int(w * s), int(h * s)
        d.rounded_rectangle([(w - ww) // 2, (h - hh) // 2, (w + ww) // 2, (h + hh) // 2],
                            int(40 * s), fill=255)
    elif kind == "iris":
        r = eo(p) * (w * .78)
        d.ellipse([w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r], fill=255)
    else:  # punch / flash → simple crossfade
        d.rectangle([0, 0, w, h], fill=int(255 * p))
    return m.filter(ImageFilter.GaussianBlur(3 if kind in ("slide", "wipe") else 1))


def transition(a, b, kind, p):
    p = cl(p)
    if kind in ("punch", "flash"):
        out = Image.blend(a, b, eo(p))
        if kind == "punch":
            out = apply_camera(out, 1.0 + .10 * math.sin(math.pi * p))
        return out
    m = tr_mask(kind, p)
    out = b.copy()
    out.paste(a, (0, 0), ImageChops.invert(m))
    return out
