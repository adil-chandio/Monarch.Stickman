#!/usr/bin/env python3
"""Shared timeline for the Law 1 explainer (used by render.py and build_audio.py)."""
import os, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(ROOT, "audio")
FF = "/tmp/venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"

LEAD = 0.35
GAP = 0.32
TAIL = 0.85

BEATS = [
    dict(n=1, cues=["Agar aap apne boss se", "zyada SMART hain...", "to yeh video",
                    "aapke liye ek WARNING hai."]),
    dict(n=2, cues=["The 48 Laws of Power", "\u2014 Law No. 1 \u2014", "NEVER OUTSHINE",
                    "THE MASTER.", "Apne master ko kabhi", "neecha mat dikhao."]),
    dict(n=3, cues=["FRANCE, 1661.", "Nicolas Fouquet ne", "King Louis XIV ke liye",
                    "ek aisa palace banwaya..."]),
    dict(n=4, cues=["...ke har mehman ne kaha:", "\u201cYeh to KING se bhi",
                    "zyada ROYAL hai!\u201d"]),
    dict(n=5, cues=["King ne muskura kar", "tareef ki...", "lekin andar hi andar",
                    "JALAN ne janam liya."]),
    dict(n=6, cues=["Kuch hafton baad,", "Fouquet GIRAFTAR tha.", "Aur baaki saari zindagi",
                    "JAIL mein."]),
    dict(n=7, cues=["Law No. 1:", "apne MASTER ko", "kabhi INSECURE mat karo.",
                    "Usay lagta hai tumhari kamyabi", "uska inaam hai."]),
    dict(n=8, cues=["SMART raho...", "lekin CREDIT master ko do.", "Talent chhupana nahi \u2014",
                    "bas usay neecha mat dikhao."]),
    dict(n=9, cues=["Log KAMYABI", "bhool jate hain.", "Lekin apni BEIZZATI", "kabhi nahi."]),
    dict(n=10, cues=["Yeh thi LAW ONE.", "Agli law mein milte hain.", "Follow karna mat bhoolna."]),
]


def audio_duration(path):
    err = subprocess.run([FF, "-hide_banner", "-i", path], capture_output=True, text=True).stderr
    for line in err.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
    raise RuntimeError("no duration " + path)


def build():
    starts, durs = [], []
    t = LEAD
    for b in BEATS:
        ap = os.path.join(AUDIO, f"beat{b['n']:02d}.mp3")
        dur = audio_duration(ap)
        b["dur"], b["start"], b["audio"] = dur, t, ap
        weights = [max(7, len(c.replace(" ", ""))) for c in b["cues"]]
        tot = sum(weights)
        acc, cues = 0.0, []
        for c, wg in zip(b["cues"], weights):
            cues.append((c, 0.06 + acc / tot * max(0.35, dur - 0.10)))
            acc += wg
        b["cue_times"] = cues
        starts.append(t)
        durs.append(dur)
        t += dur + GAP
    total = (t - GAP) + TAIL
    return total, starts, durs


TOTAL, STARTS, DURS = build()
