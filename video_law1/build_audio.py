#!/usr/bin/env python3
"""
MonarchVoice — Law 1 explainer: audio assembly.
Places the 10 narration beats on the shared timeline, adds a soft synth music bed,
and renders a single mixed WAV ready for muxing.
"""
import os, subprocess, wave
import numpy as np
from timeline import BEATS, TOTAL

ROOT = os.path.dirname(os.path.abspath(__file__))
AUDIO = os.path.join(ROOT, "audio")
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)
FF = "/tmp/venv/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"

SR = 44100


def decode(path):
    raw = subprocess.run([FF, "-v", "error", "-i", path, "-f", "f32le", "-ac", "2",
                          "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def make_bed(total):
    """Slow, warm minor-key pad: Am - F - C - G, 8s per chord, very quiet."""
    n = int(total * SR)
    bed = np.zeros((n, 2), dtype=np.float32)

    chords = [
        [220.00, 261.63, 329.63],   # A minor
        [174.61, 220.00, 261.63],   # F major
        [130.81, 196.00, 261.63],   # C major
        [196.00, 246.94, 293.66],   # G major
    ]
    seg = 8.0
    t_axis = np.arange(int(seg * SR)) / SR
    for ci, freqs in enumerate(chords):
        start = int(ci * seg * SR)
        for k in range(20):
            st = start + int(k * seg * SR)
            if st >= n:
                break
            length = min(len(t_axis), n - st)
            env = np.minimum(1, np.minimum(t_axis[:length] / 1.6, (seg - t_axis[:length]) / 1.6))
            env = np.clip(env, 0, 1) ** 1.4
            sig = np.zeros(length, dtype=np.float32)
            for j, f in enumerate(freqs):
                vib = 1 + 0.0016 * np.sin(2 * np.pi * 0.18 * t_axis[:length] + j)
                for h, amp in ((1, 1.0), (2, 0.22), (3, 0.08)):
                    sig += (amp / (j + 1.4)) * np.sin(2 * np.pi * f * h * t_axis[:length] * vib)
            sig *= env
            # gentle stereo spread
            bed[st:st + length, 0] += sig * 0.9
            bed[st:st + length, 1] += np.roll(sig, 220) * 0.9
    # soft low pulse every 2s
    for k in range(int(total / 2) + 1):
        st = int(k * 2 * SR)
        ln = min(int(0.5 * SR), n - st)
        if ln <= 0:
            break
        tt = np.arange(ln) / SR
        thump = np.sin(2 * np.pi * 62 * tt) * np.exp(-tt * 8) * 0.5
        bed[st:st + ln, 0] += thump
        bed[st:st + ln, 1] += thump
    # low-pass-ish smoothing via moving average
    k = 9
    ker = np.ones(k, dtype=np.float32) / k
    for c in range(2):
        bed[:, c] = np.convolve(bed[:, c], ker, mode="same")
    peak = np.abs(bed).max()
    if peak > 0:
        bed = bed / peak * 0.16
    # fade in / out
    fi = int(1.5 * SR)
    bed[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    fo = int(2.0 * SR)
    bed[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
    return bed


def build():
    total_n = int((TOTAL + 0.2) * SR)
    mix = np.zeros((total_n, 2), dtype=np.float32)
    for b in BEATS:
        clip = decode(b["audio"])
        # trim leading/trailing near-silence
        env = np.abs(clip).max(axis=1)
        thr = env.max() * 0.008
        idx = np.where(env > thr)[0]
        if len(idx) > 2000:
            clip = clip[max(0, idx[0] - 400): idx[-1] + 1200]
        # tiny fades
        f = int(0.012 * SR)
        if len(clip) > 2 * f:
            clip[:f] *= np.linspace(0, 1, f, dtype=np.float32)[:, None]
            clip[-f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]
        st = int(b["start"] * SR)
        ln = min(len(clip), total_n - st)
        mix[st:st + ln] += clip[:ln] * 1.0

    # narration loudness target
    peak = np.abs(mix).max()
    mix = mix / max(peak, 1e-6) * 0.89

    bed = make_bed(TOTAL + 0.2)[:total_n]
    out = mix + bed * 0.55

    # soft limiter
    out = np.tanh(out * 1.05) * 0.98
    peak = np.abs(out).max()
    if peak > 0.99:
        out = out / peak * 0.99

    path = os.path.join(OUT, "mix.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    print("wrote", path, f"{total_n / SR:.2f}s")
    return path


if __name__ == "__main__":
    build()
