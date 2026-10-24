#!/usr/bin/env python3
"""sfx_pack.py — curate a premium SFX pack from the CC0 wyzowl/sfx-kit library.

Source: https://github.com/wyzowl/sfx-kit (CC0 1.0 — no rights reserved).
Every entry carries its catalogue sync point, so the sound can be placed to
meet the exact frame it belongs to rather than just "some time near".

Writes audio_v4/sfx_gh/*.wav + index.json.
"""
import os, json, shutil
import numpy as np
import soundfile as sf

SRC = "/tmp/sfxkit/sfx-kit-main/sounds"
ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "audio_v4", "sfx_gh")
SR = 48000
os.makedirs(OUT, exist_ok=True)

# kind -> [(file, sync_seconds, note)]
CUR = {
    "slam": [
        ("cinematic-hits/cinematic-slam-big", .011, "heavy wooden door crashing shut"),
        ("cinematic-hits/cinematic-slam-massive", .084, "huge door slam, frame rattling"),
        ("cinematic-hits/cinematic-drum-big", .011, "giant drum: crack + deep boom"),
        ("cinematic-hits/cinematic-drum-massive", .034, "colossal drum hit"),
        ("cinematic-hits/cinematic-thunder-big", .011, "thunderclap + rolling rumble"),
        ("cinematic-hits/cinematic-thunder-massive", .012, "massive thunder overhead"),
        ("cinematic-hits/cinematic-metal-big", .030, "deep steel clang"),
    ],
    "impact": [
        ("impacts/impact-deep-hard", .010, "crisp crack over heavy rumble"),
        ("impacts/impact-deep-firm", .010, "big object landing on wood"),
        ("impacts/impact-deep-soft", .045, "bass thud, soft landing"),
        ("impacts/impact-heavy-hard", .010, "solid hit, crisp top"),
        ("impacts/impact-heavy-firm", .011, "weighty knock"),
        ("impacts/impact-medium-hard", .010, "crisp panel landing"),
        ("impacts/impact-medium-firm", .012, "solid knock"),
        ("impacts/impact-light-hard", .010, "light tick"),
        ("impacts/impact-light-firm", .011, "wooden tap"),
    ],
    "boom": [
        ("booms-and-bass/boom-drop-strong", .095, "huge sinking drop + roll"),
        ("booms-and-bass/boom-drop-medium", .052, "deep boom sinking"),
        ("booms-and-bass/boom-hit-strong", .047, "big deep boom, fills room"),
        ("booms-and-bass/boom-hit-medium", .038, "deep rounded boom, warm hall"),
        ("booms-and-bass/boom-hit-soft", .031, "soft deep boom"),
        ("booms-and-bass/bass-sub-drop-medium", .021, "sub drop, felt more than heard"),
        ("booms-and-bass/bass-sub-drop-long", .021, "long sub drop"),
        ("booms-and-bass/bass-sub-drop-short", .021, "short sub drop"),
        ("booms-and-bass/bass-808-medium", .011, "tuned 808 bass"),
        ("booms-and-bass/bass-808-short", .011, "short punchy 808"),
        ("booms-and-bass/bass-808-long", .011, "808 sliding down to F"),
        ("booms-and-bass/bass-rumble-medium", .017, "distant thunder, ground shaking"),
        ("booms-and-bass/bass-rumble-short", .003, "quick low rumble"),
        ("booms-and-bass/bass-rumble-long", .052, "long deep rumble"),
    ],
    "riser": [
        ("risers-and-fallers/riser-1s-strong", .984, "1s strong rise to a peak"),
        ("risers-and-fallers/riser-1s-soft", .982, "1s soft airy rise"),
        ("risers-and-fallers/riser-2s-strong", 1.978, "2s strong rise"),
        ("risers-and-fallers/riser-2s-soft", 1.994, "2s soft airy rise"),
        ("risers-and-fallers/riser-4s-strong", 3.977, "4s strong rise"),
        ("risers-and-fallers/riser-4s-soft", 3.945, "4s soft airy rise"),
    ],
    "faller": [
        ("risers-and-fallers/faller-1s-strong", .015, "1s bright fall, descending"),
        ("risers-and-fallers/faller-2s-strong", .034, "2s strong fall"),
        ("risers-and-fallers/faller-2s-soft", .011, "2s soft airy fall"),
        ("risers-and-fallers/faller-4s-strong", .010, "4s strong fall"),
        ("risers-and-fallers/faller-4s-soft", .070, "4s soft fall"),
    ],
    "whoosh": [
        ("whooshes/whoosh-fast-hard", .092, "fast crisp whip, bright edge"),
        ("whooshes/whoosh-fast-medium", .096, "quick clean swish"),
        ("whooshes/whoosh-fast-soft", .099, "quick gentle puff"),
        ("whooshes/whoosh-medium-hard", .201, "strong rush, bright crack"),
        ("whooshes/whoosh-medium-medium", .209, "balanced swish"),
        ("whooshes/whoosh-medium-soft", .229, "smooth gentle sweep"),
        ("whooshes/whoosh-slow-hard", .403, "big slow rush + tail"),
        ("whooshes/whoosh-slow-medium", .438, "slow full sweep"),
        ("whooshes/whoosh-slow-soft", .452, "long soft breath"),
    ],
    "reverse": [
        ("reverse-whooshes/reverse-whoosh-long-strong", 1.165, "air drawn in to a stop"),
        ("reverse-whooshes/reverse-whoosh-medium-strong", .682, "medium reverse whoosh"),
        ("reverse-whooshes/reverse-whoosh-short-strong", .340, "short reverse whoosh"),
        ("reverse-whooshes/reverse-whoosh-medium-soft", .679, "soft reverse whoosh"),
    ],
    "swish": [
        ("swishes-and-zips/swish-hard", .054, "fast sharp swish"),
        ("swishes-and-zips/swish-medium", .076, "quick clean swish + whistle"),
        ("swishes-and-zips/swish-soft", .085, "soft thin swish"),
        ("swishes-and-zips/zip-in-hard", .188, "bright zip that lands with a snap"),
        ("swishes-and-zips/zip-in-medium", .233, "zip rising to a stop"),
        ("swishes-and-zips/zip-in-soft", .294, "small thing zipping gently in"),
        ("swishes-and-zips/zip-out-hard", .011, "bright zip launched away"),
        ("swishes-and-zips/zip-out-medium", .023, "quick zip out"),
    ],
    "pop": [
        ("pops/pop-large-in", .011, "full round pop with puff"),
        ("pops/pop-large-bubble", .011, "deep round bubble bloop"),
        ("pops/pop-medium-in", .011, "round friendly pop"),
        ("pops/pop-medium-bubble", .011, "clean bubble plip"),
        ("pops/pop-small-in", .010, "tiny bright pop"),
        ("pops/pop-small-bubble", .010, "tiny water blip"),
        ("pops/pop-small-out", .011, "tiny soft pop dropping away"),
        ("appear-and-vanish/appear-burst", .010, "bursting apart, pieces scattering"),
        ("appear-and-vanish/appear-poof", .026, "vanishing in a puff of smoke"),
        ("appear-and-vanish/appear-materialise", .026, "particles gathering in"),
        ("appear-and-vanish/appear-flip-quick", .155, "card flipping over"),
    ],
    "click": [
        ("interface/click-button-firm", .009, "firm bright button click"),
        ("interface/click-button-medium", .009, "clean crisp button click"),
        ("interface/click-button-soft", .009, "gentle soft press"),
        ("interface/click-latch-firm", .021, "firm latch, metal tick"),
        ("interface/click-latch-medium", .021, "push button catching"),
        ("interface/click-snap-firm", .015, "sharp bright finger snap"),
        ("interface/click-snap-medium", .015, "clean finger snap"),
        ("interface/click-snap-soft", .015, "soft finger snap"),
        ("interface/click-hover-medium", .008, "tiny light tick"),
        ("interface/click-tap-firm", .009, "firm touchscreen tap"),
        ("interface/click-tap-medium", .009, "clear tap on glass"),
        ("interface/click-clap-firm", .009, "sharp bright hand clap"),
    ],
    "shimmer": [
        ("shimmers/shimmer-short-bright", .0, "short bright shimmer"),
        ("shimmers/shimmer-short-sparkle", .0, "short sparkle"),
        ("shimmers/shimmer-medium-bright", .0, "medium bright shimmer"),
        ("shimmers/shimmer-medium-sparkle", .0, "medium sparkle"),
        ("shimmers/shimmer-long-sparkle", .0, "long sparkle"),
        ("shimmers/shimmer-long-bright", .0, "long bright shimmer"),
    ],
    "tonal": [
        ("tones/tone-ding-high", .0, "high ding"),
        ("tones/tone-ding-mid", .0, "mid ding"),
        ("tones/tone-ding-low", .0, "low ding"),
        ("tones/tone-step-1", .0, "step 1"),
        ("tones/tone-step-2", .0, "step 2"),
        ("tones/tone-step-3", .0, "step 3"),
        ("tones/tone-step-4", .0, "step 4"),
        ("tones/tone-step-5", .0, "step 5"),
    ],
    "stinger": [
        ("logo-stings/sting-bold-short", .0, "bold short sting"),
        ("logo-stings/sting-bright-short", .0, "bright short sting"),
        ("logo-stings/sting-airy-short", .0, "airy short sting"),
        ("logo-stings/sting-tech-short", .0, "tech short sting"),
        ("logo-stings/sting-warm-short", .0, "warm short sting"),
        ("logo-stings/sting-minimal-short", .0, "minimal short sting"),
    ],
    "move": [
        ("bounce-spin-zoom/move-spring", 0.0, "coiled spring flicked"),
        ("bounce-spin-zoom/move-zoom-in", .489, "zooming in, air rushing nearer"),
        ("bounce-spin-zoom/move-zoom-out", 0.0, "zooming out, air falling away"),
        ("bounce-spin-zoom/move-bounce", .011, "rubber ball bouncing to rest"),
        ("bounce-spin-zoom/move-spin", .007, "something spinning fast"),
    ],
    "transform": [
        ("shape-changes/transform-grow", .003, "swell of air rising"),
        ("shape-changes/transform-shrink", 0.0, "air falling away, tucking in"),
        ("shape-changes/transform-morph", .002, "soft liquid morph"),
        ("shape-changes/transform-stretch", 0.0, "rubber stretching"),
        ("shape-changes/transform-fill", .003, "container filling up"),
    ],
    "celebrate": [
        ("celebration/celebration-applause-big", .0, "big crowd applause"),
        ("celebration/celebration-applause-small", .0, "small room applause"),
        ("celebration/celebration-confetti", .0, "confetti burst"),
        ("celebration/celebration-fireworks", .0, "fireworks"),
        ("celebration/celebration-popper", .0, "party popper"),
    ],
}

SKIP = {"celebration/celebration-cheer", "celebration/celebration-confetti"}


def main():
    idx = []
    for kind, items in CUR.items():
        for rel, sync, note in items:
            p = os.path.join(SRC, rel + ".wav")
            if not os.path.exists(p):
                continue
            try:
                x, sr = sf.read(p, dtype="float32")
            except Exception as e:
                print("skip", rel, e); continue
            if x.ndim == 1:
                x = np.stack([x, x], axis=1)
            if sr != SR:
                from scipy import signal as sg
                x = sg.resample(x, int(len(x) * SR / sr), axis=0).astype(np.float32)
            name = os.path.basename(rel)
            out = os.path.join(OUT, kind + "__" + name + ".wav")
            sf.write(out, x, SR, subtype="FLOAT")
            idx.append(dict(name=kind + "__" + name, kind=kind, file=name,
                            src=rel, dur=round(len(x) / SR, 3), sync=sync, note=note))
            print(f"{kind:10s} {name:34s} {len(x)/SR:5.2f}s sync {sync:.3f}")
    json.dump(idx, open(os.path.join(OUT, "index.json"), "w"), indent=1)
    print(f"\n{len(idx)} sounds in {OUT}")


if __name__ == "__main__":
    main()
