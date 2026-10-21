"""Sprite-sheet rig for the Ancient Survival reel.

Each sheet is an illustration of one character in several poses on a uniform
white background. We split it into equal cells, key the white away, trim, and
scale every pose in a sheet with ONE shared factor so the character never
"breathes" in size. Placement is always anchored on the feet baseline, which is
what makes the generated walk cycles read as continuous movement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps

ASSETS = Path(__file__).resolve().parent / "assets"


@dataclass(frozen=True)
class Sheet:
    file: str
    names: tuple[str, ...]
    height: int          # height of the reference (first) pose on the plate
    reference: int = 0   # pose used to fix the shared scale


SHEETS = (
    Sheet("sheet_lookout.png", ("stand", "walkA", "walkB", "work"), 520),
    Sheet("sheet_woman.png", ("walkA", "walkB", "point", "bend"), 508),
    Sheet("sheet_pick.png", ("pickHigh", "pickLow"), 508),
    Sheet("sheet_elder.png", ("walkA", "walkB", "warm"), 486),
    Sheet("sheet_lookout_sit.png", ("sit", "tend"), 352),
    Sheet("sheet_woman_sit.png", ("turnA", "turnB"), 352),
)


def key_white(src: Image.Image) -> Image.Image:
    img = src.convert("RGB")
    r, g, b = img.split()
    low = ImageChops.darker(r, ImageChops.darker(g, b))
    high = ImageChops.lighter(r, ImageChops.lighter(g, b))
    dark = ImageOps.invert(low).point(
        [max(0, min(255, round((v - 13) * 255 / 18))) for v in range(256)])
    coloured = ImageChops.subtract(high, low).point(
        [max(0, min(255, round((v - 9) * 255 / 16))) for v in range(256)])
    alpha = ImageChops.lighter(dark, coloured)
    # Drop isolated specks that belong to a neighbouring cell, while thin
    # drawn lines (much denser locally) survive untouched.
    density = alpha.filter(ImageFilter.BoxBlur(4))
    alpha = Image.composite(alpha, Image.new("L", alpha.size, 0),
                            density.point(lambda v: 255 if v > 17 else 0))
    img.putalpha(alpha)
    box = alpha.getbbox()
    return img.crop(box) if box else img


def feet_anchor(cell: Image.Image) -> float:
    """Horizontal centre of the lowest band of visible pixels = support foot."""
    alpha = cell.getchannel("A")
    width, height = cell.size
    top = round(height * 0.88)
    band = alpha.crop((0, top, width, height))
    xs = [x for x in range(width) if band.crop((x, 0, x + 1, band.height)).getbbox()]
    if not xs:
        return width / 2
    return (xs[0] + xs[-1]) / 2


def split_sheet(sheet: Sheet) -> dict[str, Image.Image]:
    """Split, key, and re-centre every pose on the support foot.

    Re-centring on the foot anchor (not the alpha bounding box) stops the
    character from sliding sideways as limbs move between poses.
    """
    raw = Image.open(ASSETS / sheet.file)
    cells = []
    for i in range(len(sheet.names)):
        left = round(raw.width * i / len(sheet.names))
        right = round(raw.width * (i + 1) / len(sheet.names))
        cells.append(key_white(raw.crop((left, 0, right, raw.height))))
    scale = sheet.height / cells[sheet.reference].height
    out = {}
    for name, cell in zip(sheet.names, cells):
        anchor = feet_anchor(cell)
        half = math.ceil(max(anchor, cell.width - anchor)) + 2
        padded = Image.new("RGBA", (half * 2, cell.height), (0, 0, 0, 0))
        padded.paste(cell, (round(half - anchor), 0))
        size = (max(1, round(padded.width * scale)), max(1, round(padded.height * scale)))
        out[name] = padded.resize(size, Image.Resampling.LANCZOS)
    return out


WALKS = (
    ("lookout", "walk_lookout.png", 520),
    ("woman", "walk_woman.png", 508),
    ("elder", "walk_elder.png", 486),
)


def load_walks() -> dict[str, list[Image.Image]]:
    """Four-frame walk cycles: contact, passing, opposite contact, passing."""
    walks = {}
    for key, filename, height in WALKS:
        sheet = Sheet(filename, ("contactA", "passA", "contactB", "passB"), height)
        frames = split_sheet(sheet)
        walks[key] = [frames[name] for name in sheet.names]
    return walks


def load_rig() -> dict[str, dict[str, Image.Image]]:
    rig = {}
    for sheet in SHEETS:
        prefix = sheet.file.removeprefix("sheet_").removesuffix(".png")
        rig[prefix] = split_sheet(sheet)
    return rig


def shaded(sprite: Image.Image, colour: tuple[int, int, int], amount: float,
           warm: float = 0.0) -> Image.Image:
    """Night-grade a sprite while keeping its inked edges intact."""
    out = Image.blend(sprite.convert("RGB"),
                      Image.new("RGB", sprite.size, colour), amount)
    if warm:
        glow = Image.new("RGB", sprite.size, (255, 168, 92))
        out = Image.blend(out, glow, warm)
    out.putalpha(sprite.getchannel("A"))
    return out


def shadow(im: Image.Image, x: float, y: float, width: float, alpha: int = 62) -> None:
    from PIL import ImageDraw

    d = ImageDraw.Draw(im, "RGBA")
    d.ellipse((x - width / 2, y - width * 0.11, x + width / 2, y + width * 0.11),
              fill=(38, 27, 24, alpha))


def put(im: Image.Image, sprite: Image.Image, x: float, foot_y: float,
        angle: float = 0.0, scale: float = 1.0, alpha: int = 255,
        anchor: str = "foot") -> None:
    """Paste a sprite anchored on its baseline, optionally rotated in place."""
    s = sprite
    if scale != 1.0:
        s = s.resize((max(1, round(s.width * scale)), max(1, round(s.height * scale))),
                     Image.Resampling.LANCZOS)
    if angle:
        s = s.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    if alpha < 255:
        s = s.copy()
        s.putalpha(s.getchannel("A").point(lambda a: round(a * alpha / 255)))
    top = foot_y - s.height if anchor == "foot" else foot_y - s.height / 2
    im.paste(s, (round(x - s.width / 2), round(top)), s.getchannel("A"))
