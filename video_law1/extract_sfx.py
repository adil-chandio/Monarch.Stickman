#!/usr/bin/env python3
"""
Extract isolated one-shot SFX from the reference montage videos, trim them,
analyse + classify, and write a clean labelled library.
"""
import os, subprocess, json
import numpy as np
from scipy import signal
import soundfile as sf

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "assets_src")
OUT = os.path.join(ROOT, "audio_v3", "sfx_raw")
os.makedirs(OUT, exist_ok=True)
FF = "/tmp/v/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
SR = 48000


def load(path):
    raw = subprocess.run([FF, "-v", "error", "-i", path, "-f", "f32le", "-ac", "2",
                          "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def envelope_db(a, win=0.01):
    mono = np.abs(a).mean(axis=1)
    w = int(win * SR)
    n = len(mono) // w
    rms = np.sqrt((mono[:n * w].reshape(n, w) ** 2).mean(axis=1))
    return 20 * np.log10(rms + 1e-9), win


def detect_events(a):
    db, win = envelope_db(a)
    thr = db.max() - 30
    loud = db > thr
    events, i = [], 0
    while i < len(loud):
        if loud[i]:
            j = i
            while j < len(loud) and (loud[j] or (j + 3 < len(loud) and loud[j:j + 3].any())):
                j += 1
            t0 = max(0, (i - 3) * win)
            t1 = min(len(a) / SR, (j + 4) * win)
            if t1 - t0 > 0.04:
                events.append((t0, t1))
            i = j
        else:
            i += 1
    # merge events closer than 120 ms
    merged = []
    for e in events:
        if merged and e[0] - merged[-1][1] < 0.12:
            merged[-1] = (merged[-1][0], e[1])
        else:
            merged.append(list(e))
    return merged


def analyse(seg):
    mono = seg.mean(axis=1)
    n = len(mono)
    f, t, Z = signal.stft(mono, SR, nperseg=1024, noverlap=768)
    mag = np.abs(Z) + 1e-9
    cen = (f[:, None] * mag).sum(0) / mag.sum(0)
    centroid = float(np.median(cen))
    # centroid slope normalised
    k = max(1, len(cen) // 3)
    slope = float(cen[-k:].mean() - cen[:k].mean())
    # harmonicity: energy in peaks vs total
    peaks = np.sort(mag, axis=0)[-8:].sum(0)
    harm = float(np.median(peaks / mag.sum(0)))
    # attack / decay
    env = np.abs(mono)
    if env.max() > 0:
        thr = env.max() * 0.5
        atk = float(np.argmax(env > thr) / SR)
    else:
        atk = 0.0
    # stereo width (correlation)
    L, R = seg[:, 0], seg[:, 1]
    if L.std() > 1e-6 and R.std() > 1e-6:
        corr = float(np.corrcoef(L, R)[0, 1])
    else:
        corr = 1.0
    low = float(mag[f < 120].sum() / mag.sum())
    high = float(mag[f > 6000].sum() / mag.sum())
    return dict(dur=n / SR, centroid=centroid, slope=slope, harm=harm,
                atk=atk, corr=corr, low=low, high=high,
                peak=float(np.abs(seg).max()))


def classify(m):
    d, c = m["dur"], m["centroid"]
    if d < 0.16:
        return "click"
    if m["low"] > 0.25 and c < 700 and d < 1.4:
        return "impact"
    if c < 500 and d >= 1.0:
        return "boom"
    if m["slope"] > 900:
        return "riser"
    if m["slope"] < -700:
        return "downlifter"
    if m["harm"] > 0.55 and c > 700:
        return "tonal"
    if c > 2200 and m["high"] > 0.25:
        return "whoosh"
    if c > 1500:
        return "swoosh"
    return "texture"


def main():
    files = sorted(f for f in os.listdir(SRC) if f.lower().endswith((".mp4", ".wav", ".mp3")))
    meta = []
    idx = 0
    for fn in files:
        path = os.path.join(SRC, fn)
        a = load(path)
        evs = detect_events(a)
        print(f"{fn}: {len(evs)} events")
        for (t0, t1) in evs:
            seg = a[int(t0 * SR):int(t1 * SR)]
            if len(seg) < int(0.03 * SR):
                continue
            # trim edges to -50 dB
            env = np.abs(seg).mean(axis=1)
            pk = env.max()
            if pk <= 0:
                continue
            keep = np.where(env > pk * 0.004)[0]
            if len(keep) < 16:
                continue
            a0 = max(0, keep[0] - int(0.004 * SR))
            a1 = min(len(seg), keep[-1] + int(0.05 * SR))
            seg = seg[a0:a1]
            if len(seg) > 3.2 * SR:
                seg = seg[:int(3.2 * SR)]
            m = analyse(seg)
            if m["dur"] < 0.04 or m["peak"] < 0.004:
                continue
            kind = classify(m)
            # normalise peak to -3 dBFS
            seg = seg / max(m["peak"], 1e-6) * 0.71
            fades = int(0.004 * SR)
            if len(seg) > 2 * fades:
                seg[:fades] *= np.linspace(0, 1, fades)[:, None]
                seg[-fades:] *= np.linspace(1, 0, fades)[:, None]
            name = f"{kind}_{idx:03d}"
            sf.write(os.path.join(OUT, name + ".wav"), seg, SR, subtype="FLOAT")
            meta.append(dict(name=name, kind=kind, src=fn, t0=round(t0, 3),
                             **{k: round(v, 4) for k, v in m.items()}))
            idx += 1
    with open(os.path.join(OUT, "index.json"), "w") as f:
        json.dump(meta, f, indent=1)
    from collections import Counter
    print("\nclasses:", Counter(m["kind"] for m in meta))
    print("total:", len(meta))


if __name__ == "__main__":
    main()
