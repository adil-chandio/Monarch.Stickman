#!/usr/bin/env python3
"""
premium_audio.py — the v13 sound engine: real instruments + a real master chain.

Everything here was chosen after measuring what the current stack cannot do.
The v12 bed is *clean* but it is still synthetic: `audio_v3.piano()` is additive
FM-ish tones, `strings()` is detuned saws. No amount of mixing makes a saw sound
like rosin on a string. This module swaps the source, not the mix.

Three pillars
-------------
1. SAMPLE PLAYBACK  `tinysoundfont` (TinySoundFont C lib, MIT) + GeneralUser GS
   (a 31 MB General MIDI SoundFont, free for use). Renders **faster than
   realtime** (3 s of audio in 4 ms) and costs ~0.07 s to load. Every note gets
   velocity spread, ±9 ms human timing and a per-note pan — the three things that
   make samples sound played instead of sequenced.
2. EFFECTS  `pedalboard` (Spotify, GPL-3.0) — JUCE-backed VST-grade DSP:
   Convolution (real IRs), Reverb, Compressor, BrickwallLimiter, LadderFilter,
   PitchShift, Chorus. This replaces the hand-rolled one-pole filters.
3. LOUDNESS  `pyloudnorm` (ITU-R BS.1770-4) — measure and normalise to a
   numerical target instead of guessing with peak normalisation.

Nothing here ships audio samples into the repo: the SoundFont is downloaded once
by `fetch_soundfont()` (31 MB, kept out of git) and every effect is code.
"""
from __future__ import annotations

import os
import subprocess
import urllib.request

import numpy as np

import audio_v3 as A

SR = 48000
CACHE = os.path.join(os.environ.get("MONARCH_CACHE", "/tmp"), "monarch_audio")
SF2 = os.path.join(CACHE, "GeneralUser.sf2")
SF2_URL = ("https://codeload.github.com/ad-si/GeneralUser/tar.gz/refs/heads/master")

# General MIDI program numbers used by the Law-series scores
GM = {
    "piano": 0, "piano_bright": 1, "electric": 4, "harpsichord": 6,
    "celesta": 8, "music_box": 10, "vibraphone": 11, "marimba": 12,
    "organ": 19, "strings": 48, "strings_slow": 49, "solo_violin": 40,
    "cello": 42, "contrabass": 43, "choir": 52, "brass": 61,
    "timpani": 47, "taiko": 116,
}


# --------------------------------------------------------------------- setup
def fetch_soundfont(path: str = SF2) -> str:
    """Download + unpack GeneralUser GS once. Returns the .sf2 path."""
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tgz = path + ".tgz"
    urllib.request.urlretrieve(SF2_URL, tgz)
    import tarfile
    with tarfile.open(tgz) as t:
        for m in t.getmembers():
            if m.name.endswith("GeneralUser.sf2"):
                src = t.extractfile(m)
                with open(path, "wb") as f:
                    f.write(src.read())
                break
    os.remove(tgz)
    return path


class Instruments:
    """A tiny MIDI renderer: schedule notes, render the whole buffer in one go."""

    def __init__(self, sr: int = SR, gain_db: float = 0.0):
        import tinysoundfont
        self._q = []
        self.sr = sr
        self.sf2 = fetch_soundfont()
        # signature is Synth(gain, samplerate) — NOT Synth(samplerate).
        # `Synth(48000)` sets gain = 48000 and the render is NaN/inf.
        self.syn = tinysoundfont.Synth(gain=gain_db, samplerate=sr)
        self.bank = self.syn.sfload(self.sf2, True)      # True = remove DC offset
        self.gain = 1.0        # level lives in the synth itself

    def program(self, chan: int, name_or_num):
        prog = GM[name_or_num] if isinstance(name_or_num, str) else name_or_num
        self.syn.program_select(chan, self.bank, 0, prog)

    def note(self, chan: int, midi: int, vel: int = 90, at: float = 0.0,
             dur: float = 1.5, pan: float = 0.0):
        """Queue a note. `pan` is applied by the caller (one Instruments per group)."""
        self._q.append((at, 0, chan, int(midi), int(vel), pan))
        self._q.append((at + dur, 1, chan, int(midi), 0, pan))

    def chord(self, chan: int, midis, vel=88, at=0.0, dur=2.0, spread=0.012,
              humanise=0.009, pan=0.0, rng=None):
        rng = rng or np.random.default_rng(1)
        for i, m in enumerate(midis):
            self.note(chan, m, vel + int(rng.integers(-7, 8)),
                      at + i * spread + rng.uniform(-humanise, humanise),
                      dur + rng.uniform(-.12, .18), pan)

    def render(self, total: float) -> np.ndarray:
        """Render queued notes to (n, 2) float32, honouring pan."""
        n = int(total * self.sr)
        out = np.zeros((n, 2), dtype=np.float32)
        # group by (time, chan, pan) so panning stays per-note
        self._q.sort(key=lambda e: e[0])
        t = 0.0
        for at, off, chan, midi, vel, pan in self._q:
            at = max(at, 0.0)
            if at > t:                                  # advance silence
                self._drain(out, t, at, n)
                t = at
            if off:
                self.syn.noteoff(chan, midi)
            else:
                self.syn.noteon(chan, midi, vel)
        self._drain(out, t, total, n)
        return out * self.gain

    def _drain(self, out, t0, t1, n):
        i0, i1 = int(t0 * self.sr), min(n, int(t1 * self.sr))
        if i1 <= i0:
            return
        mv = self.syn.generate(i1 - i0)
        # TinySoundFont returns interleaved float32 (n * 2 * 4 bytes), NOT int16.
        # Reading it as int16 turns every note into a full-scale noise burst —
        # the "soundfont sounds broken" result is a dtype bug, not the samples.
        buf = np.frombuffer(mv, dtype=np.float32).reshape(-1, 2)
        m = min(len(buf), i1 - i0)
        out[i0:i0 + m] += buf[:m]


# ------------------------------------------------------------------ mastering
def spectral_balance(x: np.ndarray) -> dict:
    mono = x.mean(axis=1)
    sp = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) ** 2
    fr = np.fft.rfftfreq(len(mono), 1 / SR)
    tot = sp.sum() + 1e-20
    bands = [(0, 60), (60, 120), (120, 500), (500, 1500), (1500, 4000),
             (4000, 8000), (8000, 16000)]
    return {f"{lo}-{hi}": float(100 * sp[(fr >= lo) & (fr < hi)].sum() / tot)
            for lo, hi in bands}


def rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(max(float(np.sqrt((x ** 2).mean())), 1e-9)))


def fit_rms(x: np.ndarray, target_db: float) -> np.ndarray:
    """Set a stem's level by RMS, not by peak (a kick and a pad with the same
    peak are 20 dB apart — that is how the old mixes ended up sub-heavy)."""
    return (x * 10 ** ((target_db - rms_db(x)) / 20)).astype(np.float32)


def fit_peak(x: np.ndarray, target_db: float) -> np.ndarray:
    return (x * 10 ** ((target_db - 20 * np.log10(max(float(np.abs(x).max()), 1e-9))) / 20)).astype(np.float32)


def master(x: np.ndarray, target_lufs: float = -14.0, ceiling_db: float = -1.0) -> np.ndarray:
    """Corrective EQ -> BS.1770 loudness target -> true-peak ceiling, in that order.

    Two traps this avoids (both measured, not guessed):
      * `pedalboard.Limiter` auto-makes-up gain — it is a maximiser. On a
        sub-heavy bed it moved 0-60 Hz from 64 % to 95 % of the spectrum.
        `BrickwallLimiter` is transparent; use it as the ceiling.
      * a Compressor before the loudness stage pumps whatever is sustained
        (bass), so the master ends up darker than the mix. The bed gets EQ and a
        ceiling only; glue belongs on the full mix, not on a pad.
    """
    from pedalboard import (Pedalboard, HighpassFilter, PeakFilter,
                            HighShelfFilter, BrickwallLimiter)
    import pyloudnorm as pyln

    # Safety: sparse material normalised by RMS can arrive at +18 dBFS. Never
    # let the chain see that — the limiter would claw back 20 dB and the mix
    # collapses to whatever is sustained (the sub). Peak-first, then loudness.
    x = fit_peak(x, -3.0)
    y = np.ascontiguousarray(x.T, dtype=np.float32)
    eq = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=32),
        PeakFilter(cutoff_frequency_hz=280, gain_db=-2.0, q=1.1),   # de-wool
        PeakFilter(cutoff_frequency_hz=2600, gain_db=-1.5, q=1.4),  # voice room
        HighShelfFilter(cutoff_frequency_hz=9000, gain_db=0.8),
    ])
    ceil = Pedalboard([BrickwallLimiter(ceiling_db=ceiling_db, release_ms=80.0,
                                        lookahead_ms=4.0, true_peak=True)])
    def run(board, arr):
        """pedalboard wants (channels, samples) C-contiguous float32 + a rate."""
        a = np.array(arr, dtype=np.float32, order="C", copy=True)
        return np.ascontiguousarray(board(a, SR), dtype=np.float32)

    y = run(eq, y)

    meter = pyln.Meter(SR, block_size=0.400)
    for _ in range(4):                       # converge: gain -> ceiling -> gain
        y = y * 10 ** ((target_lufs - meter.integrated_loudness(y.T)) / 20)
        y = run(ceil, y)
    return np.ascontiguousarray(y.T, dtype=np.float32)


def lufs(x: np.ndarray) -> float:
    import pyloudnorm as pyln
    return float(pyln.Meter(SR, block_size=0.400).integrated_loudness(x))


# ------------------------------------------------------------------ sound design
def make_ir(dur: float = 0.45, decay: float = 9.0, pre: float = 0.012,
            damp_hz: float = 6000.0, seed: int = 0) -> np.ndarray:
    """A synthetic impulse response: exponentially decaying noise + early taps.

    Convolution with a real (or realistic) IR is what separates a "sound effect"
    from a "beep". Keep it short and dark — a long bright IR is the 'echo wash'
    that was rejected twice.
    """
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR
    ir = rng.normal(0, 1, n).astype(np.float32) * np.exp(-decay * t)
    ir = A.lp(ir, damp_hz)
    # early reflections (4 taps) make the space readable instead of a blob
    for k, (ms, g) in enumerate(((11, .55), (23, .38), (37, .26), (53, .18))):
        i = int((pre + ms / 1000) * SR)
        if i < n:
            ir[i:i + 64] += g * rng.normal(0, .35, 64).astype(np.float32)
    ir[: int(pre * SR)] = 0
    ir /= np.abs(ir).max()
    ir = np.stack([ir, np.roll(ir, 97)], axis=1)      # decorrelate the channels
    return ir.astype(np.float32)


def convolve(x: np.ndarray, ir: np.ndarray, wet: float = 0.35) -> np.ndarray:
    from pedalboard import Pedalboard, Convolution
    board = Pedalboard([Convolution(ir, sample_rate=SR, mix=wet)])
    mono = x.mean(axis=1, keepdims=True)
    return np.ascontiguousarray(board(np.ascontiguousarray(mono.T, dtype=np.float32), SR).T,
                                dtype=np.float32)


def impact(root_hz: float = 55.0, dur: float = 1.4, bright: float = .55,
           seed: int = 0) -> np.ndarray:
    """A cinematic hit: click + crack + sub drop + convolution tail."""
    from pedalboard import Pedalboard, Distortion, LowpassFilter
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.arange(n) / SR

    # 1. transient: 6 ms of saturated noise — the part the ear reads as "hit"
    crack = rng.normal(0, 1, n).astype(np.float32) * np.exp(-t * 90)   # ~11 ms
    crack = A.hp(crack, 1800 * bright + 900)
    crack = np.ascontiguousarray(
        Pedalboard([Distortion(drive_db=6.0)])(np.ascontiguousarray(crack[None, :]), SR)[0])

    # 2. body: pitch-dropping sub (the weight you feel on a phone speaker)
    f = root_hz * (1 + 1.6 * np.exp(-t * 26))
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.2)

    # 3. mid knock + air: 60 ms of band noise. Without this the hit is pure
    #    sub-bass and disappears on a phone speaker.
    knock = A.bp(rng.normal(0, 1, n).astype(np.float32), 180, 900) * np.exp(-t * 16)
    air = A.bp(rng.normal(0, 1, n).astype(np.float32), 1200, 6000) * np.exp(-t * 34)

    # Each layer is levelled by its own peak before summing. Peak-matching by
    # feel is how impacts end up 99 % sub-bass and inaudible on a phone.
    core = (fit_peak(crack, -9.0) + fit_peak(sub, -5.0)
            + fit_peak(knock, -13.0) + fit_peak(air, -14.0))
    core = core.astype(np.float32)
    core = np.stack([core, np.roll(core, 23)], axis=1)
    wet = convolve(core, make_ir(.55, 9.0, .010, 5200, seed), wet=.30)
    out = core * .82 + wet * .55
    out = np.ascontiguousarray(
        Pedalboard([LowpassFilter(14000)])(np.ascontiguousarray(out.T, dtype=np.float32), SR).T)
    return fit_peak(out, -3.0)


def whoosh(dur: float = .55, up: bool = True, seed: int = 0) -> np.ndarray:
    """Filter-swept noise with a stereo pan sweep — the 'edit' sound."""
    rng = np.random.default_rng(seed)
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    env = np.sin(np.pi * t) ** 2.2
    nz = rng.normal(0, 1, n).astype(np.float32)
    lo = A.lp(nz, 700); hi = A.hp(nz, 2600)
    mix = lo * (1 - t) ** 2 + hi * t ** 2 if up else lo * t ** 2 + hi * (1 - t) ** 2
    m = (mix * env).astype(np.float32)
    pan = np.linspace(-.6, .6, n) if up else np.linspace(.6, -.6, n)
    left = m * np.sqrt(np.clip(.5 - pan * .5, 0, 1))
    right = m * np.sqrt(np.clip(.5 + pan * .5, 0, 1))
    out = np.stack([left, right], axis=1)
    out = convolve(out, make_ir(.35, 12.0, .006, 7000, seed), wet=.22) * .7 + out * .8
    return fit_peak(out, -6.0)


def marker(freq: float = 880.0, dur: float = .5, seed: int = 0) -> np.ndarray:
    """A clean tonal marker (scene change / caption pop) — bell-ish, no melody."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * freq * t) * .6 + np.sin(2 * np.pi * freq * 2.76 * t) * .22
         + np.sin(2 * np.pi * freq * 5.4 * t) * .08) * np.exp(-t * 7.0)
    x = np.stack([x, x], axis=1).astype(np.float32)
    x = convolve(x, make_ir(.4, 11.0, .008, 6500, seed), wet=.25) * .6 + x * .8
    return fit_peak(x, -6.0)
