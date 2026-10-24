#!/usr/bin/env python3
"""
MonarchVoice — "Law 1: Never Outshine the Master" explainer
9:16 vertical (1080x1920) · whiteboard-cartoon style · Urdnglish narration

Renders PIL frames and pipes them into ffmpeg.
"""
import os, sys, math, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(ROOT, "assets")
FONTS = os.path.join(ROOT, "fonts")
AUDIO = os.path.join(ROOT, "audio")
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)

FF = "/tmp/venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"

W, H = 1080, 1920
FPS = 30

# ---------------- palette ----------------
PAPER     = (252, 251, 247)
INK       = (26, 26, 30)
INK_SOFT  = (58, 58, 66)
BLUE      = (19, 133, 229)
BLUE_DEEP = (13, 100, 177)
RED       = (196, 26, 45)
RED_DEEP  = (156, 18, 34)
GOLD      = (203, 158, 48)
GOLD_L    = (255, 214, 102)
CREAM     = (246, 241, 230)
WHITE_ISH = (255, 255, 255)

# ---------------- fonts ----------------
SERIF4 = os.path.join(FONTS, "PlayfairDisplay_400Regular.ttf")
SERIF7 = os.path.join(FONTS, "PlayfairDisplay_700Bold.ttf")
SERIF8 = os.path.join(FONTS, "PlayfairDisplay_800ExtraBold.ttf")
SERIF9 = os.path.join(FONTS, "PlayfairDisplay_900Black.ttf")
SERIF7I = os.path.join(FONTS, "PlayfairDisplay_700Bold_Italic.ttf")
SANS4 = os.path.join(FONTS, "Inter_400Regular.ttf")
SANS6 = os.path.join(FONTS, "Inter_600SemiBold.ttf")
SANS7 = os.path.join(FONTS, "Inter_700Bold.ttf")
SANS8 = os.path.join(FONTS, "Inter_800ExtraBold.ttf")
SANS9 = os.path.join(FONTS, "Inter_900Black.ttf")

_fc = {}
def F(path, size):
    k = (path, int(size))
    if k not in _fc:
        _fc[k] = ImageFont.truetype(path, int(size))
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

# ---------------- sprite helpers (art-bbox based) ----------------
_img_cache, _art_cache = {}, {}

def sprite(name, w):
    w = max(24, int(round(w / 4.0) * 4))
    key = (name, w)
    if key in _img_cache: return _img_cache[key]
    im = Image.open(os.path.join(ASSETS, name + ".png")).convert("RGB")
    h = max(1, int(im.height * w / im.width))
    im = im.resize((w, h), Image.LANCZOS)
    _img_cache[key] = im
    return im

def art_of(name):
    """cropped artwork (white margins removed) + its intrinsic aspect."""
    if name in _art_cache: return _art_cache[name]
    im = Image.open(os.path.join(ASSETS, name + ".png")).convert("RGB")
    a = np.asarray(im)
    mask = a.min(axis=2) < 243
    ys, xs = np.where(mask)
    if len(xs) == 0: xs, ys = np.array([0]), np.array([0])
    x0, x1 = max(0, xs.min() - 6), min(im.width, xs.max() + 7)
    y0, y1 = max(0, ys.min() - 6), min(im.height, ys.max() + 7)
    crop = im.crop((x0, y0, x1, y1))
    _art_cache[name] = crop
    return crop

def _scaled_art(name, w):
    art = art_of(name)
    w = max(8, int(round(w)))
    h = max(4, int(art.height * w / art.width))
    key = (name, w, h)
    if key in _img_cache: return _img_cache[key]
    im = art.resize((w, h), Image.LANCZOS)
    _img_cache[key] = im
    return im

def blit_art(base, im, x, y, opacity=1.0):
    x, y = int(round(x)), int(round(y))
    w, h = im.size
    if opacity <= .01: return
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(base.width, x + w), min(base.height, y + h)
    if x1 <= x0 or y1 <= y0: return
    crop = base.crop((x0, y0, x1, y1))
    sub = im.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    out = ImageChops.multiply(crop, sub)
    base.paste(out if opacity >= .99 else Image.blend(crop, out, opacity), (x0, y0))

def put(base, name, cx=None, cy=None, max_w=None, max_h=None, scale=1.0, opacity=1.0,
        left=None, right=None, top=None, bottom=None, rot=0):
    """Draw artwork fitted inside a max_w x max_h box, anchored by its art bbox."""
    art = art_of(name)
    ar = art.width / art.height
    s = max(0.02, round(scale * 60) / 60.0)
    if max_w is not None and max_h is not None:
        w = min(max_w, max_h * ar)
    elif max_w is not None:
        w = max_w
    elif max_h is not None:
        w = max_h * ar
    else:
        w = 300
    im = _scaled_art(name, w * s)
    if rot:
        im = im.rotate(rot, expand=True, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    iw, ih = im.size
    if left is not None:     x = left
    elif right is not None:  x = right - iw
    else:                    x = (cx if cx is not None else W / 2) - iw / 2
    if top is not None:      y = top
    elif bottom is not None: y = bottom - ih
    else:                    y = (cy if cy is not None else H / 2) - ih / 2
    blit_art(base, im, x, y, opacity)
    return (x, y, iw, ih)


# ---------------- photo helpers ----------------
def cover(base, path, box, radius=0, opacity=1.0, focus_y=0.5, outline=None, ow=4):
    im = Image.open(path).convert("RGB")
    x0, y0, x1, y1 = [int(v) for v in box]
    bw, bh = x1 - x0, y1 - y0
    s = max(bw / im.width, bh / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    l = (im.width - bw) // 2
    t = int((im.height - bh) * focus_y)
    im = im.crop((l, t, l + bw, t + bh))
    if radius:
        mask = Image.new("L", (bw, bh), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, bw - 1, bh - 1], radius, fill=255)
        base.paste(im, (x0, y0), mask if opacity >= .99 else mask.point(lambda v: int(v * opacity)))
    else:
        base.paste(im, (x0, y0), None if opacity >= .99 else Image.new("L", (bw, bh), int(255 * opacity)))
    if outline:
        ImageDraw.Draw(base).rounded_rectangle([x0, y0, x1, y1], radius, outline=outline, width=ow)

def soft_shadow(base, box, radius, alpha=60, blur=20, dy=10):
    x0, y0, x1, y1 = [int(v) for v in box]
    pad = blur * 3
    sh = Image.new("RGBA", (x1 - x0 + pad * 2, y1 - y0 + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(sh)
    d.rounded_rectangle([pad, pad + dy, pad + (x1 - x0), pad + dy + (y1 - y0)], radius,
                        fill=(18, 20, 28, alpha))
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    base.paste(sh, (x0 - pad, y0 - pad), sh)

# ---------------- text helpers ----------------
def text_w(d, s, f):
    b = d.textbbox((0, 0), s, font=f)
    return b[2] - b[0]

def wrap(d, txt, f, max_w):
    words, lines, cur = txt.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if text_w(d, t, f) <= max_w or not cur: cur = t
        else: lines.append(cur); cur = wd
    if cur: lines.append(cur)
    return lines

def line_width(d, words, f):
    return sum(text_w(d, wd, f) for wd in words) + text_w(d, " ", f) * (len(words) - 1)

def draw_words(d, cx, baseline, words, f, colors, shown, shadow=True, alpha=1.0):
    x = cx - line_width(d, words, f) / 2
    sp = text_w(d, " ", f)
    for i, wd in enumerate(words):
        ww = text_w(d, wd, f)
        if i < shown:
            col = colors[i]
            if alpha >= .99:
                if shadow:
                    d.text((x, baseline + 4), wd, font=f, fill=(0, 0, 0, 60), anchor="ls")
                d.text((x, baseline), wd, font=f, fill=col, anchor="ls")
            else:
                a = int(255 * alpha)
                d.text((x, baseline), wd, font=f, fill=col + (a,), anchor="ls")
        x += ww + sp

def text_center(base, cx, cy, txt, f, fill=INK, alpha=1.0, anchor="mm", shadow=None, tracking=0):
    d = ImageDraw.Draw(base)
    if alpha >= .99:
        if shadow:
            d.text((cx + shadow[0], cy + shadow[1]), txt, font=f, fill=shadow[2], anchor=anchor)
        d.text((cx, cy), txt, font=f, fill=fill, anchor=anchor)
    else:
        a = int(255 * alpha)
        d.text((cx, cy), txt, font=f, fill=fill + (a,), anchor=anchor)

def pill(base, cx, cy, txt, fill=INK, fg=(255, 255, 255), size=38, scale=1.0, opacity=1.0,
         fpath=None, padx=28, pady=14, rot=0, border=None):
    if opacity <= .02 or scale <= .02: return
    fpath = fpath or SANS7
    fnt = F(fpath, size * scale)
    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    tw, th = text_w(tmp, txt, fnt), int(size * scale * 1.0)
    b = tmp.textbbox((0, 0), txt, font=fnt)
    th = b[3] - b[1]
    w = int(tw + padx * 2 * scale)
    h = int(th + pady * 2 * scale + size * scale * 0.34)
    layer = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([30, 30, 30 + w, 30 + h], h // 2, fill=fill + (int(255 * opacity),))
    if border:
        d.rounded_rectangle([30, 30, 30 + w, 30 + h], h // 2, outline=border + (int(255 * opacity),),
                            width=max(3, int(4 * scale)))
    d.text((30 + w / 2, 30 + h / 2), txt, font=fnt, fill=fg + (int(255 * opacity),), anchor="mm")
    if rot:
        layer = layer.rotate(rot, expand=True, resample=Image.BICUBIC)
    base.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)

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
    L, s = 30, 0.52
    d.polygon([b, (b[0] - L * math.cos(ang - s), b[1] - L * math.sin(ang - s)),
               (b[0] - L * math.cos(ang + s), b[1] - L * math.sin(ang + s))], fill=color)

def underline(base, x0, x1, y, color=RED, width=10, progress=1.0):
    if progress <= 0: return
    d = ImageDraw.Draw(base)
    xe = x0 + (x1 - x0) * cl(progress)
    d.line([(x0, y), (xe, y)], fill=color, width=width)
    d.line([(x0, y + 7), (x0 + (xe - x0) * .93, y + 7)], fill=color, width=3)

def sparkle(d, x, y, r, color=GOLD, width=5):
    d.line([(x - r, y), (x + r, y)], fill=color, width=width)
    d.line([(x, y - r), (x, y + r)], fill=color, width=width)

def stamp(base, cx, cy, txt, ang=-11, color=RED, size=86, scale=1.0, opacity=1.0):
    if opacity <= .02 or scale <= .02: return
    fnt = F(SANS9, size * scale)
    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    b = tmp.textbbox((0, 0), txt, font=fnt)
    tw, th = b[2] - b[0], b[3] - b[1]
    w, h = int(tw + 74), int(th + 50)
    layer = Image.new("RGBA", (w + 90, h + 90), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([45, 45, 45 + w, 45 + h], 16, outline=color + (int(255 * opacity),), width=10)
    d.rounded_rectangle([60, 60, 30 + w, 30 + h], 12, outline=color + (int(120 * opacity),), width=3)
    d.text((45 + w / 2, 45 + h / 2), txt, font=fnt, fill=color + (int(255 * opacity),), anchor="mm")
    layer = layer.rotate(ang, expand=True, resample=Image.BICUBIC)
    base.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)

def boss_silhouette(base, cx, bottom, w=700, opacity=.12):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    head_d = w * .52
    top = bottom - w * 1.75
    d.ellipse([cx - head_d / 2, top, cx + head_d / 2, top + head_d], fill=(38, 48, 64, 255))
    d.rounded_rectangle([cx - w * .62, top + head_d * .82, cx + w * .62, bottom],
                        int(w * .40), fill=(38, 48, 64, 255))
    a = layer.getchannel("A").point(lambda v: int(v * opacity))
    layer.putalpha(a)
    layer = layer.filter(ImageFilter.GaussianBlur(1.6))
    base.paste(layer, (0, 0), layer)

def bubble(base, cx, cy, w, h, fill=(255, 255, 255), outline=INK, lw=6, tail=None, opacity=1.0, radius=None):
    if opacity <= .02: return
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    r = radius if radius is not None else int(min(w, h) * .26)
    a = int(255 * opacity)
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], r,
                        fill=fill + (a,), outline=outline + (a,), width=lw)
    if tail:
        tx, ty = tail
        for i in range(4):
            rr = 20 - i * 4
            t = i / 3
            px = cx + (tx - cx) * .35 * t
            py = cy + h / 2 + 22 + (ty - (cy + h / 2)) * .55 * t
            d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=fill + (a,),
                      outline=outline + (a,), width=4)
    base.paste(layer, (0, 0), layer)

def vertical_gradient_mask(w, h, strength, from_top=True):
    g = Image.new("L", (1, h))
    for i in range(h):
        t = i / max(1, h - 1)
        v = (1 - t) ** 1.5 if from_top else t ** 1.5
        g.putpixel((0, i), int(255 * strength * v))
    return g.resize((w, h))

# ---------------- paper background ----------------
_paper = None
def paper_bg():
    global _paper
    if _paper is not None: return _paper.copy()
    base = Image.new("RGB", (W, H), PAPER)
    rng = np.random.default_rng(11)
    grain = rng.normal(0, 2.6, (H // 3, W // 3)).astype(np.float32)
    g = np.array(Image.fromarray(np.uint8(np.clip(grain + 128, 0, 255)))
                 .resize((W, H), Image.BILINEAR)).astype(np.int16) - 128
    arr = np.array(base).astype(np.int16)
    for c in range(3):
        arr[:, :, c] = np.clip(arr[:, :, c] + g, 0, 255)
    base = Image.fromarray(arr.astype(np.uint8))
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * .30, -H * .18, W * 1.30, H * 1.18], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(150))
    edge = Image.new("RGB", (W, H), (238, 234, 224))
    base = Image.composite(base, Image.blend(base, edge, .5), vig)
    _paper = base
    return base.copy()

# ---------------- caption bar ----------------
CAP_W = 940
CAP_LEFT = (W - CAP_W) // 2
CAP_TOP = 126
CAP_FONT_SIZE = 54
CAP_LH = 70
CAP_PADX = 38
CAP_PADY = 30
_cap_cache = {}

KEYWORDS = {
    "WARNING", "SMART", "BOSS", "MASTER", "OUTSHINE", "LAW", "JALAN", "JAIL", "GIRAFTAR",
    "ROYAL", "INSECURE", "CREDIT", "TALENT", "BEIZZATI", "KAMYABI", "KING", "FOUQUET",
    "FRANCE", "POWER", "NEVER", "ONE", "XIV", "NICOLAS",
}

def caption_layout(cue):
    f = F(SERIF7, CAP_FONT_SIZE)
    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    lines = wrap(tmp, cue, f, CAP_W - CAP_PADX * 2 - 10)
    n_lines = len(lines)
    h = n_lines * CAP_LH + CAP_PADY * 2
    return lines, h, f

def caption_bar(cue, shown, pop=1.0):
    key = (cue, shown, round(pop, 3))
    if key in _cap_cache: return _cap_cache[key]
    lines, h, f = caption_layout(cue)
    layer = Image.new("RGBA", (CAP_W + 90, h + 110), (0, 0, 0, 0))
    ox, oy = 45, 40
    # drop shadow
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([ox + 2, oy + 10, ox + CAP_W + 2, oy + h + 10], 26,
                                         fill=(12, 16, 24, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(14))
    layer = Image.alpha_composite(layer, sh)
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([ox, oy, ox + CAP_W, oy + h], 26, fill=BLUE + (255,))
    # subtle bottom shade (paper-like depth, reference style)
    gloss = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    dg = ImageDraw.Draw(gloss)
    gh = int(h * .55)
    grad = Image.new("L", (1, gh))
    for i in range(gh):
        grad.putpixel((0, i), int(26 * (1 - i / max(1, gh - 1)) ** 1.6))
    grad = grad.resize((CAP_W - 4, gh))
    dg.rectangle([ox + 2, oy + 2, ox + CAP_W - 2, oy + 2 + gh], fill=(255, 255, 255, 255))
    gloss = Image.composite(Image.new("RGBA", layer.size, (255, 255, 255, 0)),
                            Image.new("RGBA", layer.size, (255, 255, 255, 255)),
                            Image.new("L", layer.size, 0))
    # apply gradient by pasting a white layer through the mask
    white = Image.new("RGBA", (CAP_W - 4, gh), (255, 255, 255, 255))
    white.putalpha(grad)
    gloss = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    gloss.paste(white, (ox + 2, oy + 2), white)
    gloss.putalpha(gloss.getchannel("A").point(lambda v: int(v * .16)))
    layer = Image.alpha_composite(layer, gloss)
    d = ImageDraw.Draw(layer)
    # words
    words = cue.split()
    # rebuild per-line word lists respecting wrap
    idx = 0
    asc, desc = f.getmetrics()
    for li, line in enumerate(lines):
        lwords = line.split()
        n = len(lwords)
        baseline = oy + CAP_PADY + li * CAP_LH + CAP_LH / 2 + (asc - desc) / 2
        colors = []
        for wd in lwords:
            core = wd.strip('.,!?"\u201c\u201d\u2026:;').upper()
            colors.append(GOLD_L if core in KEYWORDS else (255, 255, 255))
        draw_words(d, ox + CAP_W / 2, baseline, lwords, f, colors,
                   max(0, min(n, shown - idx)))
        idx += n
    _cap_cache[key] = layer
    return layer

def draw_caption(base, b, tl):
    cues = b["cue_times"]
    cur_i = 0
    for i, (c, st) in enumerate(cues):
        if tl >= st: cur_i = i
    cue, st = cues[cur_i]
    words = cue.split()
    age = tl - st
    n = len(words) if age > 0.12 * len(words) + .1 else min(len(words), int(age / 0.12) + 1)
    n = max(1, n)
    pop = 0.90 + 0.10 * eob(cl(age / 0.26))
    layer = caption_bar(cue, n, 1.0)
    lw, lh = layer.size
    if pop < .999:
        layer = layer.resize((int(lw * pop), int(lh * pop)), Image.BILINEAR)
        lw, lh = layer.size
    base.paste(layer, (int((W - lw) / 2), int(CAP_TOP - 24)), layer)

# =====================================================================
#  SCENES
# =====================================================================
def halo(base, cx, cy, r, color=(232, 228, 218), opacity=.55, falloff=1.9):
    size = int(r * 2)
    if size < 8: return
    rad = Image.new("L", (size, size), 0)
    px = rad.load()
    for y in range(size):
        dy = (y - size / 2) / (size / 2)
        for x in range(0, size):
            dx = (x - size / 2) / (size / 2)
            d = math.sqrt(dx * dx + dy * dy)
            px[x, y] = 0 if d >= 1 else int(255 * (1 - d) ** falloff)
    layer = Image.new("RGBA", (size, size), color + (255,))
    layer.putalpha(rad.point(lambda v: int(v * opacity)))
    base.paste(layer, (int(cx - r), int(cy - r)), layer)


def s1(base, t, dur):
    halo(base, 315, 1160, 500, (230, 227, 216), 1.0, falloff=.75)
    halo(base, 812, 900, 300, (248, 226, 218), .95, falloff=.8)
    boss_silhouette(base, 812, 1310, w=430, opacity=.16)
    p = eob(sg(t, .3, .55))
    if p > .02:
        shake = math.sin(t * 48) * 9 * (1 - cl(sg(t, 1.0, .9)))
        put(base, "icon_warning", cx=815 + shake, cy=880, max_w=300,
            scale=.55 + .45 * p, opacity=cl(sg(t, .3, .22) * 1.6))
        d = ImageDraw.Draw(base)
        for i, (sx, sy) in enumerate([(600, 640), (1010, 700), (990, 1080)]):
            if t > .9 + i * .12:
                sparkle(d, sx, sy, 16 * eo(sg(t, .9 + i * .12, .25)), RED)
    a = eo(sg(t, .0, .35))
    if a > 0:
        text_center(base, 815, 660, "WARNING", F(SANS9, 30), RED, a * cl(sg(t, .5, .4)))
    q = eo(sg(t, 0, .5))
    put(base, "char_worried", cx=340, bottom=1840, max_h=800 + (1 - q) * 30,
        opacity=cl(sg(t, 0, .18)))
    if t > 1.1:
        a2 = eo(sg(t, 1.1, .4))
        pill(base, 315, 900, "AAP", fill=(40, 51, 68), size=32, opacity=a2,
             scale=.9 + .1 * a2)
        if t > 1.9:
            a3 = eo(sg(t, 1.9, .4))
            pill(base, 812, 1300, "AAPKA BOSS", fill=(255, 255, 255), fg=INK, size=28,
                 opacity=a3, border=(120, 118, 112), scale=.94 + .06 * a3)


def s2(base, t, dur):
    halo(base, 540, 452, 300, (250, 236, 197), .9)
    p = eob(sg(t, .05, .55))
    if p > .02:
        put(base, "icon_crown", cx=540, cy=452, max_w=230, max_h=210,
            scale=.6 + .4 * p, opacity=cl(sg(t, .05, .18) * 1.8))
        d = ImageDraw.Draw(base)
        for i, (sx, sy) in enumerate([(390, 340), (700, 360), (545, 300)]):
            if t > .5 + i * .1:
                sparkle(d, sx, sy, 14 * eo(sg(t, .5 + i * .1, .25)), GOLD)
    if t > .28:
        a = eo(sg(t, .28, .3))
        s = .86 + .14 * eob(sg(t, .28, .45))
        text_center(base, 540, 760, "LAW", F(SERIF8, 118 * s), INK, a)
        text_center(base, 540, 900, "ONE", F(SERIF9, 156 * s), RED, a)
    pr = eio(sg(t, .7, .5))
    if pr > 0:
        ImageDraw.Draw(base).rounded_rectangle([540 - 290 * pr, 1022, 540 + 290 * pr, 1034],
                                               6, fill=GOLD)
    if t > 1.15:
        a = cl(sg(t, 1.15, .35))
        text_center(base, 540, 1112, "NEVER OUTSHINE", F(SERIF7, 74), INK, a)
        text_center(base, 540, 1200, "THE MASTER", F(SERIF7, 74), RED, a)
    if t > 2.6:
        a = eo(sg(t, 2.6, .45))
        put(base, "char_think", right=1050, bottom=1870, max_h=470, opacity=a * .96)


def s3(base, t, dur):
    a = eo(sg(t, .08, .35))
    pill(base, 540, 452, "FRANCE  \u00b7  1661", fill=INK, size=36, opacity=a,
         scale=.92 + .08 * eob(sg(t, .08, .4)))
    q = eo(sg(t, .25, .6))
    if q > .02:
        put(base, "king_throne", cx=540, cy=980, max_w=770, max_h=760,
            scale=.9 + .1 * eob(sg(t, .25, .7)), opacity=q)
    if t > 1.45:
        a2 = eo(sg(t, 1.45, .4))
        pill(base, 540, 1500, "KING LOUIS XIV", fill=GOLD, fg=INK, size=36, opacity=a2,
             scale=.94 + .06 * a2, padx=34)
    if t > 2.15:
        a3 = eo(sg(t, 2.15, .45))
        text_center(base, 540, 1610, "KA NAUKAR:", F(SANS7, 28), (128, 124, 116), a3)
        text_center(base, 540, 1690, "Nicolas Fouquet", F(SERIF8, 62), RED, a3)
        if t > 2.75:
            text_center(base, 540, 1770, "finance minister", F(SERIF7I, 40), INK_SOFT,
                        cl(sg(t, 2.75, .45)))


def s4(base, t, dur):
    q = eo(sg(t, .05, .55))
    bx0, by0, bx1, by1 = 96, 430, 984, 940
    if q > .02:
        soft_shadow(base, (bx0, by0, bx1, by1), 24, alpha=62, blur=20, dy=12)
        cover(base, os.path.join(ASSETS, "palace_party.png"), (bx0, by0, bx1, by1),
              radius=24, opacity=q, focus_y=.45)
        ImageDraw.Draw(base).rounded_rectangle([bx0, by0, bx1, by1], 24, outline=INK, width=4)
        if t > .4:
            a0 = eo(sg(t, .4, .4))
            text_center(base, 540, 1000, "Vaux-le-Vicomte  \u2014  Fouquet ka palace", F(SERIF4, 32),
                        INK_SOFT, a0)
    if t > 1.0:
        a = cl(sg(t, 1.0, .3))
        s = .9 + .1 * eob(sg(t, 1.0, .4))
        bubble(base, 540, 1215, 850 * s, 225 * s, opacity=a)
        f = F(SERIF7, 54)
        text_center(base, 540, 1162, "\u201cYeh to KING se bhi", f, INK, a)
        d = ImageDraw.Draw(base)
        parts = [("zyada ", INK), ("ROYAL", RED), (" hai!\u201d", INK)]
        tot = sum(text_w(d, p_, f) for p_, _ in parts)
        x = 540 - tot / 2
        for txt, col in parts:
            d.text((x, 1245), txt, font=f, fill=col + (int(255 * a),), anchor="ls")
            x += text_w(d, txt, f)
    if t > 2.3:
        a = eo(sg(t, 2.3, .45))
        put(base, "char_happy", left=40, bottom=1855, max_h=430, opacity=a)
        text_center(base, 700, 1720, "Sab ko farq dikh raha tha...", F(SERIF4, 40), INK_SOFT, a)


def s5(base, t, dur):
    q = eo(sg(t, 0, .45))
    if q > .02:
        put(base, "king_throne", cx=280, bottom=1245, max_h=470, scale=.95 + .05 * q, opacity=q)
    if t > .25:
        pill(base, 280, 1320, "KING", fill=INK, size=28, opacity=eo(sg(t, .25, .4)))
    g = eio(sg(t, .45, 2.6))
    if g > 0:
        put(base, "icon_flame", cx=800, cy=860, max_w=340, max_h=340,
            scale=.42 + .95 * g, opacity=cl(g * 2.4))
        d = ImageDraw.Draw(base)
        for i, (sx, sy) in enumerate([(640, 660), (975, 700), (930, 1060)]):
            if g > .5 + i * .12:
                sparkle(d, sx, sy, 13, RED)
    if t > 1.5:
        a = eo(sg(t, 1.5, .4))
        text_center(base, 800, 1180, "JALAN", F(SERIF9, 96 * (.9 + .1 * a)), RED, a)
        text_center(base, 800, 1252, "JEALOUSY", F(SANS7, 24), (92, 90, 86), a)
        if t > 2.1:
            a2 = eo(sg(t, 2.1, .45))
            put(base, "char_think", cx=540, bottom=1870, max_h=540, opacity=a2 * .97)


def s6(base, t, dur):
    halo(base, 540, 1150, 460, (235, 232, 224), 1.0, falloff=.85)
    q = eo(sg(t, .05, .5))
    if q > .02:
        put(base, "icon_jail", cx=540, top=470, max_w=180, opacity=q * .95)
    q2 = eo(sg(t, .35, .55))
    if q2 > .02:
        put(base, "char_worried", cx=540, bottom=1720, max_h=760, opacity=q2 * .95)
    if t > .55:
        a = cl(sg(t, .55, .45))
        bars = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        db = ImageDraw.Draw(bars)
        for i in range(7):
            x = 96 + i * 148
            db.rectangle([x, 620, x + 22, 1900], fill=(38, 40, 47, int(96 * a)))
        for i in range(2):
            y = 860 + i * 560
            db.rectangle([0, y, W, y + 18], fill=(38, 40, 47, int(62 * a)))
        base.paste(bars, (0, 0), bars)
    if t > 1.8:
        sp = eob(sg(t, 1.8, .45))
        stamp(base, 545, 700, "GIRAFTAR!", ang=-9, color=RED, size=84,
              scale=.55 + .45 * sp, opacity=cl(sp * 1.7))
    if t > 2.9:
        a = eo(sg(t, 2.9, .45))
        pill(base, 540, 1790, "1661 \u2192 1680  \u00b7  QAID", fill=INK, size=28, opacity=a)


def s7(base, t, dur):
    sp = eo(sg(t, .05, .6))
    if sp > 0:
        cone = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(cone).polygon([(430, 330), (650, 330), (960, 940), (120, 940)],
                                     fill=(255, 231, 168, int(78 * sp)))
        cone = cone.filter(ImageFilter.GaussianBlur(22))
        base.paste(cone, (0, 0), cone)
    if t > .2:
        a = cl(sg(t, .2, .35))
        s = .86 + .14 * eob(sg(t, .2, .45))
        text_center(base, 540, 560, "MASTER", F(SERIF9, 134 * s), INK, a)
    if t > .65:
        pr = eio(sg(t, .65, .5))
        ImageDraw.Draw(base).rounded_rectangle([540 - 250 * pr, 665, 540 + 250 * pr, 675], 5, fill=RED)
        put(base, "icon_crown", cx=540, cy=418, max_w=118, opacity=eo(sg(t, .7, .3)))
    if t > 1.3:
        a = cl(sg(t, 1.3, .4))
        text_center(base, 540, 810, "INSECURE", F(SERIF7, 80), RED, a)
        text_center(base, 540, 894, "MAT KARO", F(SERIF7, 80), INK, a)
    if t > 1.95:
        a = eo(sg(t, 1.95, .5))
        put(base, "char_think", cx=300, bottom=1880, max_h=620, opacity=a)
    if t > 4.5:
        a = eo(sg(t, 4.5, .45))
        text_center(base, 762, 1330, "tumhari kamyabi", F(SERIF4, 40), INK_SOFT, a)
        text_center(base, 762, 1392, "= uska inaam", F(SERIF7, 52), BLUE_DEEP, a)


def s8(base, t, dur):
    if t > .05:
        a = cl(sg(t, .05, .35))
        text_center(base, 540, 500, "SMART RAHO...", F(SERIF7, 78), INK, a)
    q = eob(sg(t, .45, .55))
    if q > .02:
        put(base, "icon_scale", cx=540, cy=880, max_w=430, max_h=330,
            scale=.72 + .28 * q, opacity=cl(q * 2))
    if t > 1.25:
        a = eo(sg(t, 1.25, .4))
        pill(base, 350, 1150, "TALENT", fill=BLUE, size=34, opacity=a, scale=.9 + .1 * a)
        pill(base, 740, 1150, "CREDIT", fill=GOLD, fg=INK, size=34, opacity=a, scale=.9 + .1 * a)
    if t > 2.0:
        arrow(base, [(415, 1235), (540, 1310), (676, 1235)], color=RED, width=8,
              progress=eio(sg(t, 2.0, .75)))
        a = eo(sg(t, 2.35, .4))
        pill(base, 540, 1350, "CREDIT MASTER KO DO", fill=RED, size=33, opacity=a)
    if t > 3.1:
        a = eo(sg(t, 3.1, .5))
        put(base, "char_happy", cx=872, bottom=1876, max_h=460, opacity=a)


def s9(base, t, dur):
    q = eo(sg(t, .05, .5))
    if q > .02:
        s = .93 + .07 * eob(sg(t, .05, .5))
        w, h = 852 * s, 800 * s
        cx, cy = 540, 1010
        box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        soft_shadow(base, box, 30, alpha=72, blur=24, dy=14)
        d = ImageDraw.Draw(base)
        d.rounded_rectangle(box, 30, fill=(255, 255, 255), outline=INK, width=4)
        d.text((box[0] + 30, box[1] + 4), "\u201c", font=F(SERIF9, 150), fill=GOLD)
        if t > .4:
            a1 = cl(sg(t, .4, .4))
            text_center(base, cx, cy - 185, "Log kamyabi", F(SERIF7, 70), INK, a1)
            text_center(base, cx, cy - 96, "bhool jate hain...", F(SERIF7, 70), INK, a1)
        if t > 1.8:
            a2 = cl(sg(t, 1.8, .4))
            text_center(base, cx, cy + 55, "lekin apni", F(SERIF7, 70), INK, a2)
            text_center(base, cx, cy + 155, "BEIZZATI", F(SERIF9, 94), RED, a2)
            underline(base, cx - 205, cx + 205, cy + 232, RED, 11, eio(sg(t, 2.4, .6)))
            text_center(base, cx, cy + 312, "kabhi nahi.", F(SERIF7, 70), INK, a2)
    if t > 3.0:
        a = eo(sg(t, 3.0, .5))
        put(base, "char_worried", cx=900, bottom=1870, max_h=380, opacity=a)


def s10(base, t, dur):
    base.paste(Image.new("RGB", (W, H), (5, 7, 11)), (0, 0))
    im = Image.open(os.path.join(ASSETS, "chained_hand.png")).convert("RGB")
    s = max(W / im.width, H / im.height) * (1.0 + .05 * cl(t / max(dur, .1)))
    nw, nh = int(im.width * s), int(im.height * s)
    im = im.resize((nw, nh), Image.LANCZOS)
    l, tp = (nw - W) // 2, int((nh - H) * .40)
    base.paste(im.crop((l, tp, l + W, tp + H)), (0, 0))
    base.paste(Image.new("RGB", (W, 880), (4, 5, 9)), (0, 0),
               vertical_gradient_mask(W, 880, .9, True))
    base.paste(Image.new("RGB", (W, 760), (2, 3, 6)), (0, H - 760),
               vertical_gradient_mask(W, 760, .97, False))
    d = ImageDraw.Draw(base)
    a = cl(sg(t, .18, .5))
    text_center(base, 540, 1418, "YEH THI", F(SANS6, 38), (236, 232, 223), a)
    text_center(base, 540, 1526, "LAW ONE", F(SERIF9, 116), (255, 255, 255), a,
                shadow=(0, 6, (0, 0, 0)))
    if t > .65:
        pr = eio(sg(t, .65, .5))
        a2 = cl(sg(t, .65, .25))
        d.rounded_rectangle([540 - 200 * pr, 1600, 540 + 200 * pr, 1610], 5,
                            fill=GOLD + (int(255 * a2),))
    if t > 1.0:
        a3 = cl(sg(t, 1.0, .45))
        text_center(base, 540, 1668, "Fouquet ki zindagi qaid mein khatam hui.",
                    F(SERIF4, 36), (228, 223, 214), a3)
        text_center(base, 540, 1726, "Apne master ko kabhi neecha mat dikhao.",
                    F(SERIF7, 37), (255, 214, 112), a3)
    if t > 1.6:
        a4 = cl(sg(t, 1.6, .5))
        text_center(base, 540, 1800, "AGLI LAW MEIN MILTE HAIN", F(SANS7, 28),
                    (255, 255, 255), a4)
        text_center(base, 540, 1844, "FOLLOW  @MONARCHVOICE", F(SANS6, 23),
                    (255, 214, 112), a4)


SCENES = {1: s1, 2: s2, 3: s3, 4: s4, 5: s5, 6: s6, 7: s7, 8: s8, 9: s9, 10: s10}

# ---------------- overlay ----------------
def overlay(base, t_global, total, beat_no):
    d = ImageDraw.Draw(base)
    dark = beat_no == 10
    brand_col = (250, 246, 236) if dark else (126, 122, 114)
    chip_col = (238, 233, 222) if dark else (152, 148, 141)
    acc = GOLD_L if dark else GOLD
    d.polygon([(50, 80), (54, 54), (68, 68), (80, 50), (92, 68), (106, 54), (110, 80)],
              fill=acc)
    d.rectangle([50, 80, 110, 87], fill=acc)
    d.ellipse([50, 48, 58, 56], fill=acc)
    d.ellipse([76, 44, 84, 52], fill=acc)
    d.ellipse([102, 48, 110, 56], fill=acc)
    d.text((124, 68), "MONARCHVOICE", font=F(SANS7, 24), fill=brand_col)
    d.text((W - 54, 68), "LAW 01 / 48", font=F(SANS6, 24), fill=chip_col, anchor="ra")
    # progress line
    pw = int((W - 108) * cl(t_global / max(total, .001)))
    d.rounded_rectangle([54, H - 26, W - 54, H - 22], 2, fill=(220, 216, 208) if not dark else (40, 42, 48))
    d.rounded_rectangle([54, H - 26, 54 + pw, H - 22], 2, fill=acc)

# =====================================================================
#  TIMELINE (shared)
# =====================================================================
from timeline import BEATS, TOTAL, STARTS, DURS, LEAD, GAP

def render_frame(t_global):
    b = BEATS[-1]
    for bb in BEATS:
        if t_global >= bb["start"] - 1e-6: b = bb
    tl = t_global - b["start"]
    base = Image.new("RGB", (W, H), (5, 7, 11)) if b["n"] == 10 else paper_bg()
    SCENES[b["n"]](base, tl, b["dur"])
    if b["n"] != 10:
        draw_caption(base, b, tl)
    overlay(base, t_global, TOTAL, b["n"])
    if t_global < 0.22:
        k = 1 - t_global / 0.22
        base = Image.blend(Image.new("RGB", (W, H), (255, 255, 255)), base, 1 - k * .85)
    return base

# ---------------- audio bed ----------------
def build_audio(out_path):
    silent_video = None
    return silent_video

def render_video(with_audio=True):
    total_frames = int(round(TOTAL * FPS))
    silent = os.path.join(OUT, "video_silent.mp4")
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
           "-x264-params", "keyint=60:min-keyint=30", "-movflags", "+faststart", silent]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(total_frames):
        proc.stdin.write(render_frame(i / FPS).tobytes())
        if i % 90 == 0: print(f"  frame {i}/{total_frames}", flush=True)
    proc.stdin.close()
    proc.wait()
    return silent, total_frames

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "render"
    if mode == "stills":
        for ts in [float(x) for x in sys.argv[2:]]:
            p = os.path.join(OUT, f"still_{ts:06.2f}.png")
            render_frame(ts).save(p)
            print("saved", p)
    elif mode == "timeline":
        print(f"TOTAL {TOTAL:.2f}s")
        for b in BEATS:
            print(f"  beat {b['n']:2d} start {b['start']:6.2f}  dur {b['dur']:5.2f}")
    elif mode == "full":
        import build_audio
        print(f"TOTAL {TOTAL:.2f}s  frames {int(TOTAL*FPS)}")
        p, n = render_video()
        print("silent video:", p, n)
        wav = build_audio.build()
        final = os.path.join(OUT, "MonarchVoice_Law1_Never_Outshine_The_Master_9x16.mp4")
        subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                        "-i", p, "-i", wav,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                        "-af", "loudnorm=I=-14:TP=-1.2:LRA=9",
                        "-shortest", "-movflags", "+faststart", final], check=True)
        print("FINAL:", final)
    else:
        print(f"TOTAL {TOTAL:.2f}s  frames {int(TOTAL*FPS)}")
        p, n = render_video()
        print("video:", p, n)
