#!/usr/bin/env python3
"""
MonarchVoice Library Builder
============================

Scans the audiobook assets in this repository, reads the Easy Urdnglish guide,
and generates `library.js` — a single, dependency-free data file consumed by
`index.html`.

Why a generated JS file instead of JSON + fetch()?
  * It works when the player is opened directly from disk (file://), where
    fetch() of a local JSON file is blocked by browsers.
  * Still works perfectly when served over HTTP (GitHub Pages, a local server).

Run:
    python3 build_library.py
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GUIDE = ROOT / "The_48_Laws_of_Power_Easy_Urdnglish_Guide.md"
OUT = ROOT / "library.js"

# ---------------------------------------------------------------------------
# MP3 duration (no external dependencies)
# ---------------------------------------------------------------------------

_BITRATE_V1_L3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
_BITRATE_V2_L3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
_SAMPLE_RATES = {
    3: [44100, 48000, 32000],  # MPEG-1
    2: [22050, 24000, 16000],  # MPEG-2
    0: [11025, 12000, 8000],   # MPEG-2.5
}


def mp3_duration(path: Path) -> float:
    """Return the exact duration of a CBR/VBR MPEG Layer III file in seconds."""
    data = path.read_bytes()
    pos = 0

    if data[:3] == b"ID3":
        size = (
            ((data[6] & 0x7F) << 21)
            | ((data[7] & 0x7F) << 14)
            | ((data[8] & 0x7F) << 7)
            | (data[9] & 0x7F)
        )
        pos = 10 + size

    total = 0.0
    n = len(data)
    while pos + 4 <= n:
        if data[pos] != 0xFF or (data[pos + 1] & 0xE0) != 0xE0:
            pos += 1
            continue

        b1, b2, b3 = data[pos + 1], data[pos + 2], data[pos + 3]
        version = (b1 >> 3) & 3          # 3 = MPEG-1, 2 = MPEG-2, 0 = MPEG-2.5
        layer = (b1 >> 1) & 3            # 1 = Layer III
        bitrate_idx = (b2 >> 4) & 15
        sample_idx = (b2 >> 2) & 3
        padding = (b2 >> 1) & 1

        if version == 1 or layer != 1 or bitrate_idx in (0, 15) or sample_idx == 3:
            pos += 1
            continue

        bitrate = (_BITRATE_V1_L3 if version == 3 else _BITRATE_V2_L3)[bitrate_idx] * 1000
        sample_rate = _SAMPLE_RATES[version][sample_idx]
        samples_per_frame = 1152 if version == 3 else 576
        frame_len = (144 if version == 3 else 72) * bitrate // sample_rate + padding

        if frame_len <= 4:
            pos += 1
            continue

        total += samples_per_frame / sample_rate
        pos += frame_len

    return round(total, 1)


# ---------------------------------------------------------------------------
# Guide parsing
# ---------------------------------------------------------------------------

LAW_HEADING = re.compile(r"^###\s+Law\s+(\d+)\s*:\s*(.+?)\s*$", re.M)
MEANING = re.compile(r"^-\s+\*\*Easy Meaning:\*\*\s*(.+?)\s*$", re.M)
EXPLANATION = re.compile(r"^-\s+\*\*Explanation:\*\*\s*(.+?)\s*$", re.M)


def parse_guide() -> dict[int, dict]:
    text = GUIDE.read_text(encoding="utf-8")
    headings = list(LAW_HEADING.finditer(text))
    laws: dict[int, dict] = {}

    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        block = text[match.end():end]
        meaning = MEANING.search(block)
        explanation = EXPLANATION.search(block)
        laws[int(match.group(1))] = {
            "number": int(match.group(1)),
            "title": match.group(2).strip(),
            "meaning": meaning.group(1).strip() if meaning else "",
            "explanation": explanation.group(1).strip() if explanation else "",
        }

    return laws


# ---------------------------------------------------------------------------
# Track discovery
# ---------------------------------------------------------------------------

def slug(path: str) -> str:
    return os.path.basename(path).replace(".mp3", "")


def build_tracks(laws: dict[int, dict]) -> dict:
    deep_files = sorted((ROOT / "deep_audio").glob("Law_*.mp3"))
    tracks: list[dict] = []

    # 1. Master compilation -------------------------------------------------
    master = ROOT / "The_48_Laws_of_Power_Master_Deep_Audiobook.mp3"
    tracks.append({
        "id": "master",
        "kind": "master",
        "title": "Complete Master Audiobook",
        "subtitle": "Preface + all 48 Laws + Grand Finale",
        "src": master.name,
        "duration": mp3_duration(master),
        "laws": list(range(0, 50)),
    })

    # 2. Individual deep episodes (Law_00 ... Law_49) ------------------------
    for path in deep_files:
        num = int(re.match(r"Law_(\d+)_", path.name).group(1))
        if num == 0:
            title = "Book Preface & Core Philosophy"
            subtitle = "Start here — the mindset behind all 48 Laws"
        elif num == 49:
            title = "Grand Finale: Master Takeaways"
            subtitle = "The 5 golden rules that tie the book together"
        else:
            law = laws.get(num, {})
            title = law.get("title") or path.stem.split("_", 2)[2].replace("_", " ")
            subtitle = law.get("meaning", "")[:95]
        tracks.append({
            "id": f"law-{num:02d}",
            "kind": "preface" if num == 0 else ("finale" if num == 49 else "episode"),
            "law": num,
            "title": title,
            "subtitle": subtitle,
            "src": f"deep_audio/{path.name}",
            "duration": mp3_duration(path),
        })

    # 3. Volumes ------------------------------------------------------------
    for path in sorted(ROOT.glob("Volume_*.mp3")):
        m = re.match(r"Volume_(\d+)_Laws_(\d+)_to_(\d+)", path.name)
        if not m:
            continue
        vol, first, last = int(m.group(1)), int(m.group(2)), int(m.group(3))
        final = " + Grand Finale" if vol == 5 else ""
        tracks.append({
            "id": f"volume-{vol}",
            "kind": "volume",
            "title": f"Volume {vol}: Laws {first}–{last}{final}",
            "subtitle": f"Deep storytelling · {last - first + 1} laws",
            "src": path.name,
            "duration": mp3_duration(path),
            "laws": list(range(first, last + 1)),
        })

    # 4. Quick summary edition ---------------------------------------------
    parts = sorted((ROOT / "audio").glob("Part_*.mp3"))
    for path in parts:
        m = re.match(r"Part_(\d+)_Laws_(\d+)_to_(\d+)(.*)", path.name)
        if not m:
            continue
        part, first, last = int(m.group(1)), int(m.group(2)), int(m.group(3))
        suffix = " + Conclusion" if "Conclusion" in m.group(4) else ""
        tracks.append({
            "id": f"part-{part:02d}",
            "kind": "part",
            "title": f"Part {part}: Laws {first}–{last}{suffix}",
            "subtitle": "Quick summary edition",
            "src": f"audio/{path.name}",
            "duration": mp3_duration(path),
            "laws": list(range(first, last + 1)),
        })

    # -----------------------------------------------------------------------
    # Law index -> primary episode
    # -----------------------------------------------------------------------
    episodes = {t["law"]: t for t in tracks if t["kind"] in ("episode", "preface", "finale")}
    law_index = []
    for num, law in sorted(laws.items()):
        primary = episodes.get(num)
        law_index.append({
            "number": num,
            "title": law["title"],
            "meaning": law["meaning"],
            "explanation": law["explanation"],
            "track": primary["id"] if primary else "master",
            "duration": primary["duration"] if primary else 0,
            "src": primary["src"] if primary else "",
        })

    return {
        "generatedBy": "build_library.py",
        "book": "The 48 Laws of Power",
        "author": "Robert Greene",
        "language": "Easy Urdnglish (Roman Urdu + English)",
        "tracks": tracks,
        "laws": law_index,
    }


def main() -> None:
    laws = parse_guide()
    if len(laws) != 48:
        raise SystemExit(f"Expected 48 laws in the guide, found {len(laws)}")

    library = build_tracks(laws)
    payload = json.dumps(library, ensure_ascii=False, indent=2)
    OUT.write_text(
        "/* Auto-generated by build_library.py — do not edit by hand. */\n"
        f"window.MONARCH_LIBRARY = {payload};\n",
        encoding="utf-8",
    )

    counts: dict[str, int] = {}
    for track in library["tracks"]:
        counts[track["kind"]] = counts.get(track["kind"], 0) + 1
    total = sum(t["duration"] for t in library["tracks"] if t["kind"] == "episode")

    print(f"Wrote {OUT.name} ({OUT.stat().st_size:,} bytes)")
    print(f"  tracks: {dict(sorted(counts.items()))}")
    print(f"  laws: {len(library['laws'])} | law episodes: {total / 60:.1f} min")


if __name__ == "__main__":
    main()
