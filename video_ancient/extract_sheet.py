#!/usr/bin/env python3
"""
extract_sheet.py — turn a generated sheet into individual transparent PNGs.

The art is generated as contact sheets (one image, many items on white). The film
needs sprites:  each item cut out, alpha-masked, trimmed, and saved with a name.

  python extract_sheet.py            # all sheets -> assets_an/<name>/<idx>_<slug>.png
  python extract_sheet.py --contact  # also writes a numbered contact sheet to check
"""
from __future__ import annotations

import glob
import json
import os
import shutil

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = os.path.dirname(os.path.abspath(__file__))
SHEETS = os.path.join(ROOT, "sheet")
OUT = os.path.join(ROOT, "assets_an")

# which sheet is which, and the names of its items in reading order
SHEET_MAP = {
    "01_host_character_sheet": ["host_idle", "host_point", "host_think", "host_cheer"],
    # the sheet's 2nd row draws two hunters together, so they cut as one sprite
    "02_ancient_human_poses": ["human_idle", "human_pair", "human_crouch",
                               "human_kneel", "human_kneel2", "human_triumph"],
    "03_fire_elements": ["fire_candle", "fire_camp", "fire_bonfire", "embers",
                         "sparks", "torch", "fire_ring", "smoke_curl", "flame_core"],
    "04_stone_tools_props": ["hammer_stone", "spear", "knife", "pot_lid", "bow",
                             "flint_core", "hide_cloak", "bone_tool", "basket", "pot"],
    "05_environment": ["env_cave", "env_cave_inside", "env_hills", "env_forest",
                       "env_field", "env_night", "env_river", "env_plain"],
    "06_animals": ["mammoth", "sabertooth", "wolf", "deer", "vulture", "boar", "rabbit"],
    "07_effects_ui_shapes": ["ui_panel", "ui_outline", "ui_stamp_frame", "ui_ribbon",
                             "ui_arrow_curve", "ui_arrow", "ui_burst_ring", "ui_speedlines",
                             "ui_dust", "ui_sparkle", "ui_streaks", "ui_spotlight"],
    "08_small_props_nature": ["wheat", "sprout", "seeds", "rocks_small", "boulder",
                              "moon", "sun", "stars", "smoke", "droplets", "footprints",
                              "firewood"],
}


def cut(img: Image.Image, white_thr: int = 232, min_area: int = 1200, join: int = 0):
    """Remove the sheet background *only where it touches the border*.

    A naive "all near-white pixels are background" rule also deletes the white
    inside the art (tusks, eyes, flame cores), which made every sprite look
    milky. Flood-filling from the border keeps interior whites intact.
    """
    rgb = img.convert("RGB")
    arr = np.asarray(rgb)
    cand = arr.min(axis=2) > white_thr                       # near-white
    seed = np.zeros_like(cand)
    seed[0, :] = seed[-1, :] = True
    seed[:, 0] = seed[:, -1] = True
    seed &= cand
    bg = ndimage.binary_propagation(seed, mask=cand)          # white reachable from outside
    # grow the background mask by 1 px so the anti-aliased halo goes too
    bg = ndimage.binary_dilation(bg, np.ones((3, 3)))
    # the anti-aliased rim between ink and paper is near-white too: killing it
    # stops a pale halo showing around every sprite on the paper background
    rim = ndimage.binary_dilation(bg, np.ones((3, 3)), iterations=2)
    rim &= ~bg
    pale = arr.min(axis=2) > 226
    bg = bg | (rim & pale)
    alpha = np.where(bg, 0, 255).astype(np.uint8)
    lab, n = ndimage.label(alpha > 0)
    # --- merge pieces that belong to one drawing -------------------------
    # A multi-stroke glyph (speed lines, a sparkle cluster, a handful of seeds)
    # comes out as several components. Union anything whose boxes are within
    # `join` pixels so one drawing stays one sprite.
    boxes = ndimage.find_objects(lab)
    parent = list(range(n + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a in range(1, n + 1):
        if boxes[a - 1] is None:
            continue
        ya, xa = boxes[a - 1]
        for b in range(a + 1, n + 1):
            if boxes[b - 1] is None:
                continue
            yb, xb = boxes[b - 1]
            if (ya.start - join <= yb.stop and yb.start - join <= ya.stop and
                    xa.start - join <= xb.stop and xb.start - join <= xa.stop):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[rb] = ra
    groups = {}
    for i in range(1, n + 1):
        if (lab == i).sum() == 0:
            continue
        groups.setdefault(find(i), []).append(i)

    out = []
    for root, members in groups.items():
        m = np.isin(lab, members)
        if m.sum() < min_area:
            continue
        ys, xs = np.where(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        pad = 6
        y0, x0 = max(0, y0 - pad), max(0, x0 - pad)
        y1 = min(alpha.shape[0], y1 + pad)
        x1 = min(alpha.shape[1], x1 + pad)
        a_loc = np.where(m[y0:y1, x0:x1], 255, 0).astype(np.uint8)   # only this component
        sub = np.dstack([arr[y0:y1, x0:x1], a_loc]).astype(np.uint8)
        out.append((x0, y0, Image.fromarray(sub, "RGBA"), int(m.sum())))
    return out


# how close two strokes must be to count as one drawing
JOIN = {"03_fire_elements": 26, "07_effects_ui_shapes": 26, "08_small_props_nature": 26}


def reading_order(items):
    """Sort into rows (by y) then left-to-right."""
    if not items:
        return []
    items = sorted(items, key=lambda t: t[1])
    rows, cur = [], [items[0]]
    for it in items[1:]:
        if abs(it[1] - cur[-1][1]) < 90:
            cur.append(it)
        else:
            rows.append(sorted(cur, key=lambda t: t[0]))
            cur = [it]
    rows.append(sorted(cur, key=lambda t: t[0]))
    return [it for row in rows for it in row]


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = {}
    for path in sorted(glob.glob(os.path.join(SHEETS, "*.png"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        names = SHEET_MAP.get(stem)
        if not names:
            print(f"  ! no name map for {stem}")
            continue
        img = Image.open(path)
        items = reading_order(cut(img, join=JOIN.get(stem, 0)))
        d = os.path.join(OUT, stem.split("_", 1)[1])
        if os.path.isdir(d):                     # drop sprites from an older run
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        for i, (_, _, im, area) in enumerate(items):
            nm = names[i] if i < len(names) else f"extra{i:02d}"
            im.save(os.path.join(d, f"{i:02d}_{nm}.png"))
        manifest[stem] = [names[i] if i < len(names) else f"extra{i:02d}"
                          for i in range(len(items))]
        extra = len(items) - len(names)
        print(f"  {stem:34s} {len(items):2d} sprites  ({'+' + str(extra) if extra > 0 else 'ok'})")

    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)

    # contact sheet to eyeball the order/names
    tiles = []
    for path in sorted(glob.glob(os.path.join(SHEETS, "*.png"))):
        stem = os.path.splitext(os.path.basename(path))[0]
        for i, (_, _, im, _) in enumerate(reading_order(cut(Image.open(path), join=JOIN.get(stem, 0)))):
            t = Image.new("RGB", (240, 200), (255, 255, 255))
            k = min(220 / im.width, 150 / im.height)
            r = im.resize((max(1, int(im.width * k)), max(1, int(im.height * k))))
            t.paste(r, ((240 - r.width) // 2, 30 + (150 - r.height) // 2), r)
            ImageDraw.Draw(t).text((6, 6), f"{stem[:2]}-{i:02d}", fill=(200, 20, 40))
            tiles.append(t)
    cols = 8
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 240, rows * 200), (255, 255, 255))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * 240, (i // cols) * 200))
    sheet.save(os.path.join(OUT, "_contact.png"))
    print(f"wrote {OUT}/_contact.png  ({len(tiles)} sprites)")


if __name__ == "__main__":
    main()
