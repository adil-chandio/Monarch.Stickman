#!/usr/bin/env python3
"""
Audio engine v2 — cinematic music bed + procedural sound design + voice ducking.
All SFX are synthesized from scratch (no samples needed).
"""
import os, subprocess, math
import numpy as np
from scipy import signal

from timeline_v2 import BEATS, TOTAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "v2out")
os.makedirs(OUT, exist_ok=True)
FF = "/tmp/v/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
SR = 48000
rng = np.random.default_rng(20261024)


# ---------------------------------------------------------------- utils
def db(x):
    return 10 ** (x / 20.0)


def env_exp(n, attack=0.002, decay=0.3, curve=3.0):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    d = np.exp(-(t / max(decay, 1e-4)) * curve)
    return (a * d).astype(np.float32)


def lp(x, fc, order=2):
    b, a = signal.butter(order, min(0.99, fc / (SR / 2)), "low")
    return signal.lfilter(b, a, x).astype(np.float32)


def hp(x, fc, order=2):
    b, a = signal.butter(order, min(0.99, fc / (SR / 2)), "high")
    return signal.lfilter(b, a, x).astype(np.float32)


def bp(x, f1, f2, order=2):
    b, a = signal.butter(order, [min(0.99, f1 / (SR / 2)), min(0.99, f2 / (SR / 2))], "band")
    return signal.lfilter(b, a, x).astype(np.float32)


def noise(n):
    return rng.normal(0, 1, n).astype(np.float32)


def stereo(x, pan=0.0, width=0.0):
    """pan in [-1,1]; width adds tiny decorrelation."""
    l = x * min(1.0, 1.0 - pan * 0.5)
    r = x * min(1.0, 1.0 + pan * 0.5)
    if width > 0:
        l = l + np.roll(x, int(11 * width)) * 0.08 * width
        r = r + np.roll(x, int(23 * width)) * 0.08 * width
    return np.stack([l, r]).astype(np.float32)


def place(buf, sig, at, gain=1.0, pan=0.0, width=0.0):
    if sig.ndim == 1:
        sig = stereo(sig, pan, width)
    st = int(at * SR)
    n = sig.shape[1]
    if st < 0:
        sig = sig[:, -st:]
        n = sig.shape[1]
        st = 0
    end = min(buf.shape[1], st + n)
    if end <= st:
        return
    buf[:, st:end] += sig[:, : end - st] * gain


# ---------------------------------------------------------------- instruments
def kick(dur=0.34, f0=118, f1=44):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 9.5)
    click = noise(n) * np.exp(-t * 260) * 0.35
    return (body * 0.95 + click).astype(np.float32)


def hat(dur=0.055, bright=0.85):
    n = int(dur * SR)
    x = hp(noise(n), 7000) * env_exp(n, 0.0005, dur * 0.5, 5)
    return (x * bright).astype(np.float32)


def snare(dur=0.17):
    n = int(dur * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 26) * 0.35
    nz = bp(noise(n), 1200, 5200) * np.exp(-t * 19)
    return (nz * 0.8 + body).astype(np.float32)


def pluck(freq, dur=0.5, harm=(1.0, 0.35, 0.14, 0.06)):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    for i, a in enumerate(harm):
        s += a * np.sin(2 * np.pi * freq * (i + 1) * t) * np.exp(-t * (5.5 + i * 3.2))
    s *= np.clip(t / 0.004, 0, 1)
    return (s / max(1, len(harm))).astype(np.float32)


def pad(freqs, dur, bright=0.5, detune=0.15):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    for f in freqs:
        for d in (-detune, 0.0, detune):
            vib = 1 + 0.0022 * np.sin(2 * np.pi * 0.13 * t + f)
            for h, amp in ((1, 1.0), (2, 0.24 * bright), (3, 0.10 * bright)):
                s += (amp / (1 + 0.7 * (d != 0))) * np.sin(2 * np.pi * f * h * vib * (1 + d / 100) * t)
    s /= max(1, len(freqs) * 3)
    e = np.minimum(1, t / 0.35) * np.minimum(1, (dur - t) / 0.5)
    return (s * np.clip(e, 0, 1)).astype(np.float32)


# ---------------------------------------------------------------- SFX
def whoosh(dur=0.62, f1=280, f2=5200, rev=True):
    n = int(dur * SR)
    x = noise(n)
    t = np.linspace(0, 1, n)
    out = np.zeros(n, dtype=np.float32)
    # sweep band-pass in a few chunks for a real "movement" feel
    chunks = 14
    for i in range(chunks):
        a, b = i / chunks, (i + 1) / chunks
        seg = x[int(a * n):int(b * n)]
        if len(seg) < 32:
            continue
        fc = f1 * (f2 / f1) ** a
        y = bp(seg, max(60, fc * 0.6), min(SR / 2 - 200, fc * 1.7))
        out[int(a * n):int(a * n) + len(y)] = y
    e = np.sin(np.pi * np.clip(t, 0, 1)) ** 1.5
    if rev:
        e = e ** 0.8
    return (out * e * 0.7).astype(np.float32)


def boom(gain=1.0, dur=1.1):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 32 + 68 * np.exp(-t * 12)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    thump = bp(noise(n), 60, 260) * np.exp(-t * 12) * 0.5
    crack = noise(n) * np.exp(-t * 90) * 0.25
    return ((sub + thump + crack) * gain).astype(np.float32)


def riser(dur=1.4, f0=300, f1=6000):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = noise(n)
    y = np.zeros(n, dtype=np.float32)
    chunks = 20
    for i in range(chunks):
        a, b = i / chunks, (i + 1) / chunks
        seg = x[int(a * n):int(b * n)]
        if len(seg) < 32:
            continue
        fc = f0 * (f1 / f0) ** a
        y[int(a * n):int(a * n) + len(seg)] = bp(seg, max(80, fc * 0.7), min(SR / 2 - 300, fc * 1.4))
    sweep = np.sin(2 * np.pi * np.cumsum(160 * (6 ** (t / dur))) / SR) * 0.15
    e = (t / dur) ** 2.2
    return ((y * 0.9 + sweep) * e).astype(np.float32)


def clang(dur=1.3, base=190.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    for r, a, d in ((1.0, 1.0, 2.6), (2.41, 0.55, 3.4), (3.87, 0.34, 4.2),
                    (5.71, 0.2, 5.0), (8.1, 0.12, 6.0)):
        s += a * np.sin(2 * np.pi * base * r * t + rng.uniform(0, 6)) * np.exp(-t * d)
    s += noise(n) * np.exp(-t * 140) * 0.5
    return (s * 0.45).astype(np.float32)


def chains(dur=1.5, nclicks=9):
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    for i in range(nclicks):
        at = rng.uniform(0, dur * 0.8)
        c = clang(dur=0.28, base=rng.uniform(320, 640)) * rng.uniform(0.25, 0.6)
        st = int(at * SR)
        e = min(n, st + len(c))
        out[st:e] += c[:e - st]
    return out


def fire(dur=2.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    base = lp(noise(n), 900) * 0.35
    pops = np.zeros(n, dtype=np.float32)
    for i in range(34):
        at = int(rng.uniform(0, dur) * SR)
        ln = min(n - at, int(rng.uniform(0.006, 0.028) * SR))
        if ln <= 0:
            continue
        pops[at:at + ln] += noise(ln) * np.exp(-np.arange(ln) / (ln * 0.35)) * rng.uniform(0.3, 0.9)
    pops = hp(pops, 900)
    sw = (0.7 + 0.3 * np.sin(2 * np.pi * 1.7 * t)) * (1 - np.exp(-t * 3))
    return ((base + pops * 0.8) * sw * 0.5).astype(np.float32)


def heartbeat(dur=1.0):
    n = int(dur * SR)
    out = np.zeros(n, dtype=np.float32)
    for at, g in ((0.0, 1.0), (0.24, 0.62)):
        st = int(at * SR)
        k = kick(0.26, 92, 38) * g
        e = min(n, st + len(k))
        out[st:e] += k[:e - st]
    return (lp(out, 220) * 0.9).astype(np.float32)


def ding(dur=0.9, f=1568.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    for r, a, d in ((1, 1.0, 4.5), (1.5, 0.5, 6.0), (2.0, 0.35, 7.0), (2.66, 0.2, 8.0)):
        s += a * np.sin(2 * np.pi * f * r * t) * np.exp(-t * d)
    return (s * 0.3).astype(np.float32)


def coin(dur=0.5):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    for f, a in ((2093, 1.0), (2637, 0.7), (3136, 0.5), (4186, 0.3)):
        s += a * np.sin(2 * np.pi * f * t) * np.exp(-t * rng.uniform(9, 15))
    return (s * 0.16).astype(np.float32)


def tick(dur=0.07, f=2400):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) * np.exp(-t * 90)
    s += noise(n) * np.exp(-t * 300) * 0.5
    return (s * 0.5).astype(np.float32)


def pop(f=520, dur=0.12):
    n = int(dur * SR)
    t = np.arange(n) / SR
    fq = f * (1 + 0.7 * np.exp(-t * 45))
    s = np.sin(2 * np.pi * np.cumsum(fq) / SR) * np.exp(-t * 32)
    return (s * 0.5).astype(np.float32)


def reverb_ir(dur=1.7, decay=3.2):
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = rng.normal(0, 1, n).astype(np.float32) * np.exp(-t * decay)
    ir = lp(ir, 5200)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
    return ir / np.abs(ir).max()


def apply_reverb(buf, wet=0.22):
    ir = reverb_ir()
    out = buf.copy()
    for c in range(2):
        y = signal.fftconvolve(buf[c], ir, mode="same")
        out[c] = buf[c] * (1 - wet) + y * wet * 0.5
    return out


# ---------------------------------------------------------------- music
def build_music(total):
    n = int(total * SR)
    music = np.zeros((2, n), dtype=np.float32)
    fx = np.zeros((2, n), dtype=np.float32)

    bpm = 84.0
    beat = 60.0 / bpm
    bar = beat * 4

    # chord plan per bar: Am, Am, F, F, C, C, G, G ... (loop)
    prog = [
        (110.00, [220.00, 261.63, 329.63]),   # Am
        (98.00, [196.00, 246.94, 293.66]),    # G
        (87.31, [174.61, 220.00, 261.63]),    # F
        (130.81, [261.63, 329.63, 392.00]),   # C
    ]

    # intensity map (section energy 0..1)
    def energy(at):
        # energy ramps: quiet under voice, spikes at beat starts
        e = 0.42
        for b in BEATS:
            d = at - b["start"]
            if -0.2 < d < 0.9:
                e = max(e, 0.42 + 0.18 * math.exp(-max(0, d) * 3))
            if d >= 0:
                e = max(e, 0.40 if b["kind"] in ("story", "quote") else 0.55)
        if at > BEATS[5]["start"] and at < BEATS[5]["start"] + BEATS[5]["dur"]:
            e = min(1.0, e + 0.14)
        if at > BEATS[-1]["start"]:
            e = min(1.0, e + 0.18)
        return e

    nb = int(total / bar) + 2
    for bi in range(nb):
        t0 = bi * bar
        if t0 >= total:
            break
        root, chord = prog[bi % len(prog)]
        en = energy(t0)
        # ---- pad (full bar, long)
        p = pad(chord, bar * 1.05, bright=0.35 + 0.4 * en)
        place(music, p, t0, gain=0.30 * (0.65 + 0.55 * en), width=0.6)
        # ---- sub bass on beats 1 and 3
        for k in (0, 2):
            b = pluck(root, 0.85, harm=(1.0, 0.25))
            place(music, lp(b, 220), t0 + k * beat, gain=0.34 * (0.7 + 0.5 * en))
        # ---- kick pattern (4 on floor for high energy, else 1 & 3)
        kicks = [0, 1, 2, 3] if en > 0.5 else [0, 2]
        for k in kicks:
            g = 0.30 if k in (0, 2) else 0.16
            place(music, kick(), t0 + k * beat, gain=g * (0.55 + 0.7 * en))
        # ---- hats 8ths when energetic
        if en > 0.36:
            for k in range(8):
                if k % 2 == 1 or en > 0.55:
                    place(music, hat(), t0 + k * beat / 2, gain=(0.055 if k % 2 else 0.09) * en,
                          pan=0.25 if k % 2 else -0.2)
        # ---- snare on 3 when high energy
        if en > 0.52:
            place(music, snare(), t0 + 2 * beat, gain=0.10 * en)
        # ---- arp plucks (8 notes per bar)
        scale = chord + [chord[0] * 2]
        for k in range(8):
            f = scale[(k * 3 + bi) % len(scale)] * (2 if (k % 4 == 3) else 1)
            if en > 0.3:
                place(music, pluck(f, 0.42), t0 + k * beat / 2,
                      gain=0.055 * (0.5 + en), pan=(-0.45 if k % 2 else 0.45), width=0.4)

    # ---- global music sidechain-ish ducking handled later with voice env
    # ---- swell into beat 2, 6, 10
    for b in (BEATS[1], BEATS[5], BEATS[9]):
        place(music, riser(1.5), b["start"] - 1.55, gain=0.20, width=0.8)
        place(music, boom(0.9), b["start"], gain=0.78)
    place(music, boom(1.1), 0.0, gain=0.85)

    # ---- end fade
    fade = int(1.6 * SR)
    music[:, -fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
    return music, fx


def build_sfx(total):
    n = int(total * SR)
    sfx = np.zeros((2, n), dtype=np.float32)

    for i, b in enumerate(BEATS):
        st = b["start"]
        # transition whoosh just before each beat (except the first)
        if i > 0:
            place(sfx, whoosh(0.55, 240, 4800), st - 0.34, gain=0.30, width=0.9)
        # cue ticks / pops
        for j, c in enumerate(b["cue_times"]):
            g = 0.16 if j == 0 else 0.075
            place(sfx, pop(560 if j % 2 == 0 else 700), st + c["t"], gain=g, pan=-0.15)
            if c["kw"]:
                place(sfx, tick(0.05, 3100), st + c["t"], gain=0.10, pan=0.25)

    # 1 — hook: alarm-ish double hit + sub drop
    place(sfx, boom(1.0), 0.0, gain=0.95)
    place(sfx, clang(0.9, 260), 0.05, gain=0.16, pan=0.3)
    place(sfx, whoosh(0.5, 300, 5200), 0.55, gain=0.28)

    # 2 — crown ding
    place(sfx, ding(1.1), BEATS[1]["start"] + 0.25, gain=0.24, pan=0.1)

    # 4 — nobles murmur: soft filtered noise swell
    place(sfx, whoosh(1.0, 400, 1400), BEATS[3]["start"] + 0.9, gain=0.12)

    # 5 — fire crackle + rising heat
    b5 = BEATS[4]
    place(sfx, fire(b5["dur"] * 0.9), b5["start"] + 0.5, gain=0.30, pan=-0.2)
    place(sfx, riser(1.3, 220, 3400), b5["start"] + b5["dur"] - 1.2, gain=0.16)

    # 6 — slam: bars down, clang, chain, heartbeat
    b6 = BEATS[5]
    place(sfx, whoosh(0.4, 160, 2600), b6["start"] - 0.05, gain=0.34)
    place(sfx, boom(1.0), b6["start"] + 0.02, gain=0.7)
    place(sfx, chains(1.6), b6["start"] + 0.15, gain=0.22, pan=0.2)
    for k in range(3):
        place(sfx, heartbeat(1.0), b6["start"] + 1.2 + k * 1.5, gain=0.20)

    # 7 — spotlight swell
    place(sfx, riser(1.0, 500, 2500), BEATS[6]["start"] + 0.1, gain=0.11)
    place(sfx, ding(0.8, 880), BEATS[6]["start"] + 0.3, gain=0.12)

    # 8 — coins / credit sparkle
    b8 = BEATS[7]
    for k in range(7):
        place(sfx, coin(0.5), b8["start"] + 1.9 + k * 0.16, gain=0.12, pan=rng.uniform(-0.6, 0.6))
    place(sfx, ding(1.0, 1318), b8["start"] + 2.0, gain=0.16)

    # 9 — clock ticking under the quote
    b9 = BEATS[8]
    for k in range(int(b9["dur"] / 0.5)):
        place(sfx, tick(0.03, 1700), b9["start"] + 0.2 + k * 0.5, gain=0.075, pan=(0.35 if k % 2 else -0.35))

    # 10 — end: riser, boom, chain, low drone
    b10 = BEATS[9]
    place(sfx, riser(1.8, 180, 7000), b10["start"] - 0.2, gain=0.26)
    place(sfx, boom(1.2), b10["start"] + 0.9, gain=0.9)
    place(sfx, chains(2.2, 12), b10["start"] + 0.3, gain=0.2, pan=-0.2)
    drone = pad([55.0, 82.5], 3.4, bright=0.2)
    place(sfx, drone, b10["start"] + 0.9, gain=0.35)

    return apply_reverb(sfx, wet=0.24)


# ---------------------------------------------------------------- voice
def decode(path):
    raw = subprocess.run([FF, "-v", "error", "-i", path, "-f", "f32le", "-ac", "2",
                          "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def build_voice(total):
    n = int(total * SR)
    v = np.zeros((2, n), dtype=np.float32)
    for b in BEATS:
        clip = decode(b["audio"])
        mono = clip.mean(axis=1)
        e = np.abs(mono)
        thr = max(1e-4, e.max() * 0.006)
        idx = np.where(e > thr)[0]
        if len(idx) > 2000:
            clip = clip[max(0, idx[0] - 500): idx[-1] + 1500]
            mono = clip.mean(axis=1)
        # gentle compression
        env = np.abs(mono)
        env = np.convolve(env, np.ones(2048, dtype=np.float32) / 2048, mode="same")
        gain = np.where(env > 0.08, 0.08 / np.maximum(env, 1e-6), 1.0)
        gain = np.clip(gain, 0.35, 1.0)
        clip = clip * gain[:, None]
        # air / presence boost
        hi = hp(mono, 5200) * 0.22
        clip = clip + np.stack([hi, hi]).T
        clip = lp(clip, 15500)
        f = int(0.01 * SR)
        if len(clip) > 2 * f:
            clip[:f] *= np.linspace(0, 1, f, dtype=np.float32)[:, None]
            clip[-f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]
        place(v, clip.astype(np.float32).T, b["start"], gain=1.0)
    return v


def norm_peak(x, db):
    p = np.abs(x).max()
    if p <= 0:
        return x
    return x / p * (10 ** (db / 20.0))


def compress(x, thr_db=-18.0, ratio=3.2, atk_ms=4.0, rel_ms=140.0, makeup_db=0.0):
    """Simple stereo-linked feed-forward compressor."""
    env = np.abs(x).max(axis=0).astype(np.float32)
    k = max(2, int(SR * rel_ms / 1000))
    env = np.convolve(env, np.ones(k, dtype=np.float32) / k, mode="same")
    thr = 10 ** (thr_db / 20.0)
    g = np.ones_like(env)
    over = env > thr
    g[over] = (thr / env[over]) ** (1.0 - 1.0 / ratio)
    # attack smoothing (fast)
    ka = max(2, int(SR * atk_ms / 1000))
    g = np.minimum(g, np.convolve(g, np.ones(ka, dtype=np.float32) / ka, mode="same") + 0.02)
    g = np.clip(g, 0.05, 1.0)
    y = x * g[None, :] * (10 ** (makeup_db / 20.0))
    return y.astype(np.float32)


def smooth_var(x, sr=SR, ms=180.0):
    k = max(3, int(sr * ms / 1000))
    ker = np.hanning(k).astype(np.float32)
    ker /= ker.sum()
    return np.convolve(x, ker, mode="same")


def build():
    total = TOTAL + 0.25
    n = int(total * SR)
    print("voice...")
    voice = build_voice(total)
    print("music...")
    music, _ = build_music(total)
    print("sfx...")
    sfx = build_sfx(total)

    # ---- normalize each bus to sane targets
    voice = voice[:, :n]
    voice = norm_peak(voice, -1.6)
    voice = compress(voice, thr_db=-16, ratio=2.4, makeup_db=2.0)
    voice = norm_peak(voice, -1.6)

    music = music[:, :n]
    music = norm_peak(music, -7.0)
    music = compress(music, thr_db=-24, ratio=3.0, makeup_db=0.0)
    music_rms = np.sqrt((music ** 2).mean())
    music = music * (10 ** (-25.5 / 20.0) / max(music_rms, 1e-9))

    sfx = sfx[:, :n]
    sfx = norm_peak(sfx, -4.0)
    sfx = compress(sfx, thr_db=-16, ratio=4.0, makeup_db=0.0)
    sfx = norm_peak(sfx, -4.5)

    # ---- duck music + sfx under voice
    venv = np.abs(voice).max(axis=0)
    venv = smooth_var(venv, ms=240)
    venv = np.clip(venv / max(venv.max(), 1e-6) * 2.0, 0, 1)
    duck = 1.0 - 0.60 * venv
    music = music * duck
    sfx = sfx * (1.0 - 0.30 * venv)

    mix = voice * 1.0 + music * 1.05 + sfx * 0.95

    # master: soft-knee compression + limiter
    mix = compress(mix, thr_db=-12, ratio=3.5, makeup_db=0.0)
    mix = np.tanh(mix * 1.05) * 0.97
    peak = np.abs(mix).max()
    if peak > 0.95:
        mix = mix / peak * 0.95

    # intro/outro
    fi = int(0.02 * SR)
    mix[:, :fi] *= np.linspace(0, 1, fi, dtype=np.float32)[None, :]
    fo = int(1.6 * SR)
    mix[:, -fo:] *= np.linspace(1, 0, fo, dtype=np.float32)[None, :]

    path = os.path.join(OUT, "mix_v2.wav")
    import wave
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(mix, -1, 1) * 32767).astype(np.int16).T.tobytes())
    print("wrote", path, f"{n / SR:.2f}s")
    return path


if __name__ == "__main__":
    build()
