#!/usr/bin/env python3
"""
MonarchVoice — audio engine v3
--------------------------------------------------------------------
Premium score + sound design:
  * 10 synthesized instruments (piano, strings, 808, kick, snare, clap,
    hats, rim, drone, vinyl texture) with real arrangement sections
  * SFX library extracted from the reference packs (34 one-shots)
  * tape saturation, convolution reverb, stereo imaging, sidechain ducking
  * voice-first mix: narration leads, music breathes under it
"""
import os, json, math, subprocess, wave
import numpy as np
from scipy import signal
import soundfile as sf

from timeline_v4 import BEATS, TOTAL

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "v3out")
SFX_DIR = os.path.join(ROOT, "audio_v3", "sfx_raw")
os.makedirs(OUT, exist_ok=True)
FF = "/tmp/v/lib/python3.11/site-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
SR = 48000
rng = np.random.default_rng(777)

# ---------------------------------------------------------------- helpers
def T(sec): return int(round(sec * SR))

def nz(n): return rng.normal(0, 1, n).astype(np.float32)

def lp(x, fc, order=2):
    fc = np.clip(fc, 20, SR / 2 - 200)
    b, a = signal.butter(order, fc / (SR / 2), "low")
    return signal.lfilter(b, a, x).astype(np.float32)

def hp(x, fc, order=2):
    fc = np.clip(fc, 20, SR / 2 - 200)
    b, a = signal.butter(order, fc / (SR / 2), "high")
    return signal.lfilter(b, a, x).astype(np.float32)

def bp(x, f1, f2, order=2):
    f1 = max(20, f1); f2 = min(SR / 2 - 200, max(f1 + 50, f2))
    b, a = signal.butter(order, [f1 / (SR / 2), f2 / (SR / 2)], "band")
    return signal.lfilter(b, a, x).astype(np.float32)

def adsr(n, a=0.005, d=0.1, s=0.7, r=0.2):
    t = np.arange(n) / SR
    env = np.ones(n, dtype=np.float32) * s
    ai = min(n, max(1, T(a)))
    env[:ai] = np.linspace(0, 1, ai, dtype=np.float32) ** 1.2
    di = min(n - ai, max(1, T(d)))
    if di > 0:
        env[ai:ai + di] = np.linspace(1, s, di, dtype=np.float32)
    ri = min(n, max(1, T(r)))
    env[-ri:] *= np.linspace(1, 0, ri, dtype=np.float32)
    return env

def sat(x, drive=1.6, mix=0.35):
    y = np.tanh(x * drive) / np.tanh(drive)
    return (x * (1 - mix) + y * mix).astype(np.float32)

def pan_gains(p):
    """equal-power pan, p in [-1,1]"""
    a = (p + 1) * math.pi / 4
    return math.cos(a), math.sin(a)

def place(buf, sig, at, gain=1.0, pan=0.0, width=0.0, rev=None, rev_gain=0.0):
    """sig: mono or (n,2). at in seconds. buf: (n,2). all stereo buffers are frames-first"""
    if sig.ndim == 1:
        gl, gr = pan_gains(pan)
        L = sig * gl
        R = sig * gr
        if width > 0:
            d = int(11 * width)
            L = L + np.roll(sig, d) * 0.12 * width
            R = R + np.roll(sig, d * 2) * 0.12 * width
        sig = np.stack([L, R], axis=1)
    st = T(at)
    if st < 0:
        sig = sig[-st:]
        st = 0
    en = min(buf.shape[0], st + sig.shape[0])
    if en <= st:
        return
    buf[st:en, :] += sig[:en - st] * gain
    if rev is not None and rev_gain > 0:
        rev[st:en, :] += sig[:en - st] * gain * rev_gain

# ---------------------------------------------------------------- instruments
def piano(freq, dur, bright=1.0, vel=1.0):
    n = T(dur)
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    # slightly inharmonic partials, decaying faster for higher partials
    for k, (mult, amp, dec) in enumerate([(1, 1.0, 1.9), (2, .42, 2.6), (3, .20, 3.4),
                                          (4, .11, 4.6), (5, .06, 6.0), (6.02, .035, 7.5),
                                          (8.1, .02, 9.0)]):
        f = freq * mult
        if f > SR / 2 - 500:
            continue
        s += (amp * bright ** (k * .34)) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) \
             * np.exp(-t * dec * 1.5)
    # hammer/attack noise
    atk = bp(nz(n), 1200, 7000) * np.exp(-t * 80) * 0.30
    s = (s * np.exp(-t * 0.55) + atk) * vel
    # body resonance
    s += lp(s, 1800) * 0.25 + hp(s, 2400) * 0.22
    return sat(s / max(1.0, np.abs(s).max()), 1.25, .18)

def strings(freqs, dur, bright=.55, attack=.5, release=.7, detune=6.0):
    """detuned band-limited saw stack (harmonic summation), slow swell"""
    n = T(dur)
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    for f in freqs:
        for d in (-detune, 0.0, detune):
            vib = 1 + 0.0032 * np.sin(2 * np.pi * float(rng.uniform(.12, .22)) * t + f * .01)
            ff = f * (1 + d / 1200) * vib
            for h in range(1, 9):
                if float(np.max(ff)) * h > 8000:
                    break
                s += (1.0 / (h ** 1.15)) * np.sin(2 * np.pi * ff * h * t + float(rng.uniform(0, 6.28)))
    s /= max(1, len(freqs) * 3)
    s = lp(s, 1200 + 4200 * bright)
    env = adsr(n, attack, .25, .82, release)
    return sat(s * env, 1.15, .2)


def sub808(freq, dur, glide=None, drive=2.4):
    n = T(dur)
    t = np.arange(n) / SR
    f = np.full(n, freq, dtype=np.float32)
    if glide:
        f = np.linspace(freq, glide, n).astype(np.float32) * 1.0
        f[:int(.02 * n)] = freq
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) + 0.16 * np.sin(2 * ph) + 0.05 * np.sin(3 * ph)
    env = adsr(n, .006, .1, .85, .22)
    return sat((s * env).astype(np.float32), drive, .5)

def kick(dur=.42, f0=128, f1=42, click=.35):
    n = T(dur)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 26)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 7.5)
    beak = bp(nz(n), 1500, 6000) * np.exp(-t * 190) * click
    s = body * 1.0 + beak * .5
    return sat(s.astype(np.float32), 1.9, .45)

def snare(dur=.26, tone=196):
    n = T(dur)
    t = np.arange(n) / SR
    body = (np.sin(2 * np.pi * tone * t) + .5 * np.sin(2 * np.pi * tone * 1.58 * t)) * np.exp(-t * 27)
    nz_ = bp(nz(n), 900, 7200) * np.exp(-t * 22)
    s = body * .55 + nz_ * .9
    return sat(s.astype(np.float32), 1.4, .3)

def clap(dur=.30):
    n = T(dur)
    s = np.zeros(n, dtype=np.float32)
    for k in range(4):
        off = int(k * 0.009 * SR)
        ln = min(n - off, T(.06))
        s[off:off + ln] += bp(nz(ln), 1100, 5200) * np.exp(-np.arange(ln) / (ln * .32))
    s *= np.exp(-np.arange(n) / (n * 1.6))
    return hp(s, 600) * .55

def hat(dur=.055, open_=False):
    d = .16 if open_ else dur
    n = T(d)
    s = hp(nz(n), 6500) * np.exp(-np.arange(n) / (n * (.55 if open_ else .3)))
    return s * .55

def rim(dur=.09):
    n = T(dur)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * 1750 * t) * .6 + np.sin(2 * np.pi * 2680 * t) * .3) * np.exp(-t * 70)
    return s + bp(nz(n), 2000, 8000) * np.exp(-t * 120) * .4

def drone(freqs, dur, bright=.3):
    n = T(dur)
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    for f in freqs:
        for d in (-3, 3):
            s += np.sin(2 * np.pi * f * (1 + d / 1200) * t) * .5
            s += np.sin(2 * np.pi * f * 2 * (1 + d / 1200) * t) * .16
    s = lp(s, 300 + 900 * bright)
    env = adsr(n, 1.2, .4, .9, 1.6)
    return s * env

def reverse_swell(src, dur=None):
    d = dur or (len(src) / SR)
    n = T(d)
    s = np.resize(src, n) if len(src) < n else src[:n]
    return s[::-1] * np.linspace(0, 1, n, dtype=np.float32) ** 1.5

# ---------------------------------------------------------------- fx
class Reverb:
    def __init__(self, dur=2.6, decay=2.6, predelay=0.02, damp=5200, seed=5):
        r = np.random.default_rng(seed)
        n = T(dur)
        t = np.arange(n) / SR
        ir = r.normal(0, 1, n).astype(np.float32) * np.exp(-t * decay)
        ir = lp(ir, damp)
        ir[:T(predelay)] = 0
        ir = ir / np.abs(ir).max()
        self.ir = ir

    def __call__(self, x):
        if x.ndim == 1:
            return signal.fftconvolve(x, self.ir, mode="same").astype(np.float32)
        return np.stack([signal.fftconvolve(x[:, c], self.ir, mode="same") for c in range(x.shape[1])],
                        axis=1).astype(np.float32)

VERB = Reverb(1.6, 3.8, 0.014, 5200, 11)
PLATE = Reverb(1.5, 4.2, 0.008, 8200, 23)

def tape(x, drive=1.25, hiss=0.0012, wow=0.00018):
    """tape-ish saturation + wow + hiss"""
    y = np.tanh(x * drive) / np.tanh(drive)
    n = y.shape[0]
    t = np.arange(n) / SR
    drift = 1 + wow * np.sin(2 * np.pi * 0.31 * t) + 0.5 * wow * np.sin(2 * np.pi * 0.07 * t)
    idx = np.clip(np.cumsum(drift) - 1, 0, n - 1)
    if y.ndim == 1:
        y = np.interp(idx, np.arange(n), y)
    else:
        for c in range(y.shape[1]):
            y[:, c] = np.interp(idx, np.arange(n), y[:, c])
    y = lp(y, 15500)
    if hiss:
        h = nz(n).astype(np.float32)
        y = y + (h if y.ndim == 1 else h[:, None]) * hiss
    return y.astype(np.float32)

def widen(x, amount=.35):
    """mid/side widening"""
    L, R = x[:, 0], x[:, 1]
    mid = (L + R) / 2
    side = (L - R) / 2
    side *= (1 + amount)
    return np.stack([mid + side, mid - side], axis=1).astype(np.float32)

# ---------------------------------------------------------------- music
NOTE = {}
_A4 = 440.0
_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
for octv in range(0, 9):
    for i, nm in enumerate(_NAMES):
        NOTE[f"{nm}{octv}"] = _A4 * 2 ** ((octv - 4) + (i - 9) / 12)

CHORDS = {
    "Am": ["A2", "E3", "A3", "C4", "E4"],
    "F":  ["F2", "C3", "F3", "A3", "C4"],
    "C":  ["C2", "G2", "C3", "E3", "G3"],
    "G":  ["G2", "D3", "G3", "B3", "D4"],
    "Dm": ["D2", "A2", "D3", "F3", "A3"],
    "Em": ["E2", "B2", "E3", "G3", "B3"],
}
ROOT = {"Am": "A1", "F": "F1", "C": "C1", "G": "G1", "Dm": "D1", "Em": "E1"}

# emotional hook motif (scale degrees per chord)
MOTIF = [(0, 0.0), (2, 0.75), (4, 1.5), (3, 2.25)]      # indices into chord tones

def build_music(total):
    """Cinematic orchestral bed — strings, cello, felt piano, taiko, heartbeat.
    No trap drums, no harsh synths: warmth and space instead of noise."""
    n = T(total)
    music = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)

    bpm = 84.0
    beat = 60.0 / bpm
    bar = beat * 4
    prog = ["Am", "F", "C", "G"]

    def section(at):
        sec = [b for b in BEATS if at >= b["start"]]
        return sec[-1] if sec else BEATS[0]

    def energy(at):
        b = section(at)
        base = {"hook": .30, "title": .48, "story": .55, "danger": .72,
                "shock": .12, "teach": .70, "bright": .85, "quote": .22,
                "end": .82}[b["kind"]]
        local = at - b["start"]
        return base * (0.80 + 0.20 * min(1.0, local / 1.4))

    nb = int(total / bar) + 2
    for bi in range(nb):
        t0 = bi * bar
        if t0 >= total:
            break
        ch = prog[bi % 4]
        tones = CHORDS[ch]
        en = energy(t0)

        # ---------------- cello: root, sustained, the floor of the cue
        root = NOTE[ROOT[ch]]
        cel = strings([root, root * 2], bar * 1.25, bright=.26 + .18 * en,
                      attack=1.2, release=1.8, detune=4.0)
        place(music, nr(cel, .026 * (0.55 + .65 * en)), t0, gain=1.0,
              width=.25, rev=send, rev_gain=.22)

        if en < .2:
            continue                        # shock / silence: let the voice own it

        # ---------------- strings pad: mid chord, slow swell
        pad = strings([NOTE[x] for x in tones[1:4]], bar * 1.18,
                      bright=.32 + .34 * en, attack=.85, release=1.4)
        place(music, nr(pad, .036 * (0.55 + .8 * en)), t0, gain=1.0,
              width=.55, rev=send, rev_gain=.55)

        # ---------------- felt piano: the motif people remember
        if en < .6:
            pat = [(0, 0.0), (2, 1.0), (3, 2.0), (4, 3.0)]
        else:
            pat = [(0, 0.0), (2, .5), (4, 1.0), (3, 1.5), (2, 2.0), (3, 2.5), (4, 3.0), (3, 3.5)]
        for k, pos in pat:
            f = NOTE[tones[min(k, len(tones) - 1)]] * 2
            p = piano(f, 1.7, bright=.92 + .22 * en, vel=1.0)
            place(music, nr(p, .038 * (0.6 + .75 * en)), t0 + pos * beat, gain=1.0,
                  pan=float(rng.uniform(-.18, .18)), rev=send, rev_gain=.6)

        # ---------------- glass bell: one high sparkle per bar
        if en > .62:
            f = NOTE[tones[-1]] * 4
            g = piano(f, 2.4, bright=1.45, vel=.6)
            place(music, nr(g, .009 * en), t0 + 2 * beat, gain=1.0,
                  pan=float(rng.uniform(-.4, .4)), rev=send, rev_gain=.95)

        # ---------------- heartbeat: two soft low thumps, tension only
        if en > .45:
            for k, g in ((0, 1.0), (0.30, .62)):
                hb = npk(lp(kick(.55, 92, 48, .03), 190), .085 * en * g)
                place(music, hb, t0 + k * beat / 1.0, gain=1.0, pan=-.06,
                      rev=send, rev_gain=.15)

        # ---------------- taiko: section weight, every other bar at full energy
        if en > .74 and bi % 2 == 0:
            tk = npk(lp(kick(1.25, 88, 38, .07), 240), .20 * en)
            place(music, tk, t0, gain=1.0, width=.15, rev=send, rev_gain=.45)

    # ---------------- shimmer: soft air band, keeps the bed open on phone speakers
    sh = bp(nz(n), 3200, 7600) * np.linspace(0, 1, n, dtype=np.float32) ** .5
    k = T(1.4)
    env = np.convolve(np.abs(sh), np.ones(k, dtype=np.float32) / k, mode="same")
    a = fade_env(n)
    sh = sh * a / max(np.abs(sh * a).max(), 1e-9)
    L = sh; Rr = np.roll(sh, T(.011))
    shim = np.stack([L, Rr], axis=1) * .010
    shim = shim * (0.35 + .65 * np.clip(shimmer_env(n), 0, 1))[:, None]
    music = music + shim

    # ---------------- transitions: reverse swell into every section
    for b in BEATS[1:]:
        sw = R.sfx("riser", 1.6)
        if np.abs(sw).max() < 1e-5:
            continue
        sw = hl(sw)
        place(music, nr(sw, .012), b["start"] - 1.55, gain=1.0, width=.7,
              rev=send, rev_gain=.45)

    music = hp(music, 34)
    music = tape(music, 1.05, 0.0007)
    wet = VERB(music)
    music = (music * .94 + wet * .06).astype(np.float32)
    # gentle tonal shaping for phone speakers
    music = music + hp(music, 1800) * .55 + hp(music, 3600) * .75 - lp(music, 95) * .30
    music = widen(music, .26)
    return music


def fade_env(n):
    """slow breathing envelope so the shimmer never sits static"""
    t = np.arange(n) / SR
    e = .55 + .45 * np.sin(2 * np.pi * .055 * t) * np.sin(2 * np.pi * .017 * t + 1.1)
    k = T(.8)
    return np.convolve(np.clip(e, .15, 1.0), np.ones(k) / k, mode="same").astype(np.float32)


def shimmer_env(n):
    """section-driven intensity for the shimmer layer"""
    e = np.zeros(n, dtype=np.float32)
    for b in BEATS:
        g = {"hook": .30, "title": .5, "story": .55, "danger": .8, "shock": .1,
             "teach": .7, "bright": .9, "quote": .25, "end": .85}[b["kind"]]
        st = T(b["start"]); en = min(n, st + T(b["dur"]))
        e[st:en] = g
    k = T(.35)
    return np.clip(np.convolve(e, np.ones(k) / k, mode="same"), 0, 1)


def hl(x):
    """make a reversed swell out of a one-shot"""
    y = x[::-1].copy()
    e = np.linspace(0, 1, len(y), dtype=np.float32) ** 2.2
    return (y * e).astype(np.float32)


# ---------------------------------------------------------------- sfx polish
def polish_sfx(s, kind):
    """turn raw one-shots from the reference packs into smooth, premium accents:
    darken the harsh 3-6 kHz noise, add weight, soften the edges."""
    s = s.astype(np.float32)
    s = s - float(s.mean())
    if kind in ("whoosh", "riser"):
        fc, depth, pitch = 3000.0, .55, .84
    elif kind == "downlifter":
        fc, depth, pitch = 4200.0, .5, .80
    elif kind == "click":
        fc, depth, pitch = 5600.0, .45, .92
    elif kind == "impact":
        fc, depth, pitch = 6500.0, .25, .94
    else:
        fc, depth, pitch = 7000.0, .2, 1.0

    y = lp(s, fc) * .92 + lp(s, fc * 2.4) * .22
    y = y - bp(s, 2800, 5200) * depth
    y = hp(y, 40)
    if pitch != 1.0:
        y = signal.resample(y, max(16, int(len(y) / pitch))).astype(np.float32)
        y = np.tanh(y * 1.0)
    y = y / max(np.abs(y).max(), 1e-6)
    f = min(T(.004), len(y) // 4)
    if f > 2:
        y[:f] *= np.linspace(0, 1, f).astype(np.float32)
        y[-f:] *= np.linspace(1, 0, f).astype(np.float32)
    return y.astype(np.float32)

# ---------------------------------------------------------------- SFX library
class SFXLib:
    def __init__(self, folder):
        self.by_kind = {}
        self.idx = json.load(open(os.path.join(folder, "index.json")))
        for x in self.idx:
            p = os.path.join(folder, x["name"] + ".wav")
            if not os.path.exists(p):
                continue
            a, sr = sf.read(p, dtype="float32")
            if a.ndim == 1:
                a = np.stack([a, a], axis=1)
            if sr != SR:
                a = signal.resample(a, int(len(a) * SR / sr), axis=0).astype(np.float32)
            self.by_kind.setdefault(x["kind"], []).append((x["name"], a))

    def sfx(self, kind, dur=None):
        pool = self.by_kind.get(kind) or []
        if not pool:
            return np.zeros(T(dur or .3), dtype=np.float32)
        name, a = pool[rng.integers(0, len(pool))]
        s = polish_sfx(a.mean(axis=1), kind)
        if dur:
            n = T(dur)
            s = s[:n] if len(s) >= n else np.pad(s, (0, n - len(s)))
        return s.copy()

    def has(self, k):
        return bool(self.by_kind.get(k))

R = SFXLib(SFX_DIR)

def build_sfx(total):
    """Editorial sound design — sparse, purposeful, quiet."""
    n = T(total)
    buf = np.zeros((n, 2), dtype=np.float32)
    send = np.zeros((n, 2), dtype=np.float32)

    def hit(kind, at, gain=.4, pan=0.0, dur=None, rev=.25, width=.2):
        s = R.sfx(kind, dur)
        if np.abs(s).max() < 1e-5:
            return
        s = s / np.abs(s).max()
        place(buf, s, at, gain=gain, pan=pan, rev=send, rev_gain=rev, width=width)

    # --- beat 1: hook. one deep boom + a "whoosh" into the warning icon
    b1 = BEATS[0]
    hit("impact", b1["start"] + .02, .42, 0, 1.1, .18)
    hit("whoosh", b1["start"] + .30, .22, -.2)
    hit("click", b1["start"] + .95, .16, .25, .12)
    hit("downlifter", b1["start"] + 4.2, .18, .1)

    # --- beat 2: title. riser into crown + tonal ding
    b2 = BEATS[1]
    hit("riser", b2["start"] - .55, .30, 0, 1.2, .3)
    hit("impact", b2["start"] + .05, .34, 0, 1.0, .2)
    hit("tonal", b2["start"] + .62, .22, .15)

    # --- beat 3: story. soft whoosh for the king entrance
    b3 = BEATS[2]
    hit("whoosh", b3["start"] + .18, .18, -.15)
    hit("downlifter", b3["start"] + 1.95, .16, .2)

    # --- beat 4: nobles murmur
    b4 = BEATS[3]
    hit("whoosh", b4["start"] + .05, .16, .2)
    hit("click", b4["start"] + 1.02, .13, -.2, .1)

    # --- beat 5: fire — design crackle by re-pitching clicks
    b5 = BEATS[4]
    hit("whoosh", b5["start"] + .02, .14, -.25)
    for i in range(10):
        at = b5["start"] + .55 + i * .26 + rng.uniform(-.05, .05)
        hit("click", at, .05 + .04 * rng.random(), rng.uniform(-.5, .5), .07, .1, .1)
    hit("riser", b5["start"] + b5["dur"] - 1.5, .20, 0, 1.4, .25)

    # --- beat 6: jail slam
    b6 = BEATS[5]
    hit("impact", b6["start"], .50, 0, 1.2, .22)
    hit("downlifter", b6["start"] + .02, .22, -.15)
    hit("whoosh", b6["start"] + 1.78, .26, .2)
    hit("impact", b6["start"] + 1.80, .30, 0, .9, .25)
    hit("click", b6["start"] + 2.85, .10, .2, .1)

    # --- beat 7: teaching — clean, minimal
    b7 = BEATS[6]
    hit("whoosh", b7["start"] - .1, .14, 0)
    hit("tonal", b7["start"] + 1.15, .14, -.1)
    hit("click", b7["start"] + 3.75, .09, .25, .1)

    # --- beat 8: bright — sparkle clicks
    b8 = BEATS[7]
    hit("whoosh", b8["start"] + .02, .13, .2)
    for i in range(6):
        hit("click", b8["start"] + 1.9 + i * .17, .045 + .02 * rng.random(),
            rng.uniform(-.6, .6), .07, .12, .05)
    hit("tonal", b8["start"] + 2.0, .16, .1)

    # --- beat 9: quote — ticking + underline accent
    b9 = BEATS[8]
    for i in range(int(b9["dur"] / .5)):
        hit("click", b9["start"] + .25 + i * .5, .05, .3 if i % 2 else -.3, .05, .05, .05)
    hit("downlifter", b9["start"] + 2.2, .12, 0)

    # --- beat 10: end — riser + huge impact + tail
    b10 = BEATS[9]
    hit("riser", b10["start"] - 1.2, .30, 0, 2.0, .3)
    hit("impact", b10["start"] + .82, .55, 0, 1.5, .35)
    hit("downlifter", b10["start"] + 1.05, .20, -.2)
    hit("whoosh", b10["start"] + 3.0, .16, .2)

    wet = VERB(buf)
    buf = (buf * .96 + wet * .04).astype(np.float32)
    return widen(buf, .22)


# ---------------------------------------------------------------- voice
def decode(path):
    raw = subprocess.run([FF, "-v", "error", "-i", path, "-f", "f32le", "-ac", "2",
                          "-ar", str(SR), "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()


def deess(x, amount=0.55):
    mono = x.mean(axis=1)
    hi = bp(mono, 5200, 9500)
    env = np.abs(hi)
    k = T(.004)
    env = np.convolve(env, np.ones(k, dtype=np.float32) / k, mode="same")
    thr = np.percentile(env, 88) + 1e-6
    g = np.ones_like(env)
    m = env > thr
    g[m] = (thr / env[m]) ** amount
    return x * g[:, None]


def compress(x, thr_db=-20, ratio=3.0, atk=.006, rel=.2, makeup=0.0):
    """stereo-linked compressor with exponential attack/release"""
    env = np.abs(x).max(axis=1).astype(np.float32)
    ca = math.exp(-1.0 / max(1, T(atk)))
    cr = math.exp(-1.0 / max(1, T(rel)))
    sm = np.empty_like(env)
    prev = 0.0
    for i in range(len(env)):
        e = env[i]
        prev = ca * prev + (1 - ca) * e if e > prev else cr * prev + (1 - cr) * e
        sm[i] = prev
    thr = 10 ** (thr_db / 20)
    g = np.ones_like(sm)
    over = sm > thr
    g[over] = (thr / sm[over]) ** (1 - 1 / ratio)
    g = np.clip(g, .1, 1.0)
    return (x * g[:, None] * (10 ** (makeup / 20))).astype(np.float32)


def build_voice(total):
    n = T(total)
    v = np.zeros((n, 2), dtype=np.float32)
    env_for_duck = np.zeros(n, dtype=np.float32)
    for b in BEATS:
        clip = decode(b["audio"])
        mono = clip.mean(axis=1)
        e = np.abs(mono)
        thr = max(1e-4, e.max() * .006)
        idx = np.where(e > thr)[0]
        if len(idx) > 2000:
            clip = clip[max(0, idx[0] - T(.01)): idx[-1] + T(.03)]
            mono = clip.mean(axis=1)
        # EQ: remove rumble, add presence
        m = hp(mono, 88)
        m = m - bp(m, 170, 430) * 0.32
        pres = bp(m, 2200, 5200) * 0.46
        air = hp(m, 8200) * 0.16
        m = m + pres + air
        m = lp(m, 16000)
        clip = np.stack([m, m], axis=1)
        clip = deess(clip, .5)
        clip = compress(clip, -18, 3.0, .005, .18, 1.5)
        # voice stays 100% dry - no plate, no slap, nothing that reads as echo
        f = T(.012)
        if len(clip) > 2 * f:
            clip[:f] *= np.linspace(0, 1, f)[:, None].astype(np.float32)
            clip[-f:] *= np.linspace(1, 0, f)[:, None].astype(np.float32)
        place(v, clip, b["start"], 1.0)
        st = T(b["start"])
        en = min(n, st + len(clip))
        env_for_duck[st:en] = np.maximum(env_for_duck[st:en],
                                         np.abs(clip[:en - st]).max(axis=1))
    # normalise voice
    pk = np.abs(v).max()
    if pk > 0:
        v = v / pk * 0.89
    v = compress(v, -14, 2.2, .004, .16, 1.0)
    pk = np.abs(v).max()
    v = v / max(pk, 1e-9) * 0.91
    return v, env_for_duck


def smooth(x, ms):
    k = max(3, T(ms / 1000))
    ker = np.hanning(k).astype(np.float32); ker /= ker.sum()
    return np.convolve(x, ker, mode="same")


def nr(x, target=.05):
    r = float(np.sqrt((x ** 2).mean()))
    return (x * (target / max(r, 1e-9))).astype(np.float32)


def npk(x, target=.4):
    return (x * (target / max(float(np.abs(x).max()), 1e-9))).astype(np.float32)


def rms_db(x):
    r = np.sqrt((x ** 2).mean())
    return 20 * np.log10(max(r, 1e-9))


def build():
    total = TOTAL + .25
    print("voice…"); voice, venv = build_voice(total)
    print("music…"); music = build_music(total)
    print("sfx…");   sfx = build_sfx(total)
    n = T(total)
    voice, music, sfx = voice[:n], music[:n], sfx[:n]

    # ---- loudness staging: voice is the reference, everything else is placed under it
    voice = voice / max(np.abs(voice).max(), 1e-9) * 10 ** (-1.5 / 20)
    vr = rms_db(voice)

    # music: set so that (after ducking) it sits ~18 dB under the voice
    music = music / max(np.abs(music).max(), 1e-9)
    music = music * (10 ** ((vr - 11.5) / 20) / max(rms_db(music), -90) if False else 1.0)
    m_r = rms_db(music)
    music = music * 10 ** ((vr - 10.0 - m_r) / 20)

    # sfx: accents peak just under the voice, never over it
    sfx = sfx / max(np.abs(sfx).max(), 1e-9) * 10 ** (-7.5 / 20)

    # duck
    d = smooth(venv[:n], 260)
    d = np.clip(d / max(d.max(), 1e-9) * 2.2, 0, 1)
    duck_music = 1 - 0.52 * d
    duck_sfx = 1 - 0.30 * d

    music = music * duck_music[:, None]
    sfx = sfx * duck_sfx[:, None]
    mix = voice + music + sfx

    mix = tape(mix, 1.1, 0.0)
    mix = compress(mix, -11, 2.4, .004, .18, 0.0)
    mix = mix * (10 ** (3.8 / 20))
    mix = np.tanh(mix * 0.98) / 0.98
    pk = np.abs(mix).max()
    if pk > .89:
        mix = mix / pk * .89
    fi = T(.02); fo = T(1.4)
    mix[:fi, :] *= np.linspace(0, 1, fi)[:, None].astype(np.float32)
    mix[-fo:, :] *= np.linspace(1, 0, fo)[:, None].astype(np.float32)

    for nm, bus in (("stem_voice", voice), ("stem_music", music), ("stem_sfx", sfx)):
        sf.write(os.path.join(OUT, nm + ".wav"), bus.astype(np.float32), SR, subtype="FLOAT")
    path = os.path.join(OUT, "mix_v3.wav")
    sf.write(path, mix.astype(np.float32), SR, subtype="FLOAT")
    print("wrote", path, f"{n / SR:.2f}s",
          f"| voice {rms_db(voice):.1f} music {rms_db(music):.1f} sfx {rms_db(sfx):.1f} dB RMS"
          f"| peaks v {20*np.log10(max(np.abs(voice).max(),1e-9)):.1f} m {20*np.log10(max(np.abs(music).max(),1e-9)):.1f} s {20*np.log10(max(np.abs(sfx).max(),1e-9)):.1f} mix {20*np.log10(max(np.abs(mix).max(),1e-9)):.1f}")
    return path


if __name__ == "__main__":
    build()
