#!/usr/bin/env python3
"""Compose an ORIGINAL 30-second stereo score, foley and narrated mix.

No stock music or third-party sound effects are used. Requires the approved
`narration.wav` in this folder and NumPy. The mix is deliberately ducked under
speech; intro and outro are allowed to swell without covering the narrator.
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RATE = 48000
LENGTH = 30.0
SAMPLES = round(RATE * LENGTH)
RNG = np.random.default_rng(480)


def add(sound: np.ndarray, track: np.ndarray, when: float, pan: float = 0.0) -> None:
    begin = round(when * RATE)
    if begin < 0:
        sound = sound[-begin:]
        begin = 0
    if begin >= SAMPLES or len(sound) == 0:
        return
    sound = sound[: SAMPLES - begin]
    left = math.cos((pan + 1) * math.pi / 4)
    right = math.sin((pan + 1) * math.pi / 4)
    track[begin:begin + len(sound), 0] += sound * left
    track[begin:begin + len(sound), 1] += sound * right


def note(freq: float, duration: float, amp: float, attack: float, release: float,
         kind: str = "pad") -> np.ndarray:
    t = np.arange(round(duration * RATE), dtype=np.float32) / RATE
    if len(t) == 0:
        return np.empty(0, dtype=np.float32)
    if kind == "wood":
        # A soft woody mallet, rather than a pure electronic sine tone.
        signal = (np.sin(2 * np.pi * freq * t) +
                  0.32 * np.sin(2 * np.pi * freq * 2.01 * t) +
                  0.12 * np.sin(2 * np.pi * freq * 3.97 * t))
        env = (1 - np.exp(-t / max(attack, 0.002))) * np.exp(-t / 0.31)
    else:
        drift = 0.006 * np.sin(2 * np.pi * 0.28 * t)
        signal = (np.sin(2 * np.pi * freq * t + drift) +
                  0.16 * np.sin(2 * np.pi * (2 * freq + 0.6) * t))
        env = np.minimum(1, t / max(attack, 0.002)) * np.minimum(
            1, np.maximum(0, duration - t) / max(release, 0.002))
    return (signal * env * amp).astype(np.float32)


def filtered_noise(count: int, smooth: int) -> np.ndarray:
    noise = RNG.normal(0, 1, count + smooth).astype(np.float32)
    # O(n) sliding boxcar: attenuates harsh white noise without SciPy.
    sums = np.cumsum(noise, dtype=np.float64)
    return ((sums[smooth:] - sums[:-smooth]) / smooth).astype(np.float32)


def kick() -> np.ndarray:
    t = np.arange(round(0.49 * RATE), dtype=np.float32) / RATE
    phase = 2 * np.pi * (47 * t + 4.9 * (1 - np.exp(-13 * t)))
    body = np.sin(phase) * np.exp(-t * 11)
    click = RNG.normal(0, 1, len(t)) * np.exp(-t * 120) * 0.085
    return ((body + click) * 0.085).astype(np.float32)


def wood_tap() -> np.ndarray:
    t = np.arange(round(0.17 * RATE), dtype=np.float32) / RATE
    body = np.sin(2 * np.pi * (195 - 50 * t) * t) * np.exp(-t * 35)
    splinter = RNG.normal(0, 1, len(t)) * np.exp(-t * 84)
    return ((body * 0.034 + splinter * 0.016)).astype(np.float32)


def whoosh(duration: float = 0.5) -> np.ndarray:
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    raw = filtered_noise(n, 11)
    env = np.sin(np.pi * np.minimum(1, t / duration)) ** 1.8
    shimmer = np.sin(2 * np.pi * (410 * t + 1000 * t * t)) * 0.18
    return ((raw + shimmer) * env * 0.070).astype(np.float32)


def stone_chip() -> np.ndarray:
    n = round(0.14 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    bright = np.sin(2 * np.pi * (1900 * t - 1200 * t * t)) * np.exp(-t * 70)
    grit = RNG.normal(0, 1, n) * np.exp(-t * 105)
    return ((bright * 0.04 + grit * 0.029)).astype(np.float32)


def rustle(duration: float = 0.36) -> np.ndarray:
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    env = np.sin(np.pi * t / duration) ** 2
    raw = filtered_noise(n, 5)
    return (raw * env * 0.066).astype(np.float32)


def fire_pop() -> np.ndarray:
    n = round(0.055 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    return (RNG.normal(0, 1, n) * np.exp(-t * 165) * 0.037).astype(np.float32)


def footstep(weight: float = 1.0) -> np.ndarray:
    n = round(0.22 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    thud = np.sin(2 * np.pi * (72 - 26 * t) * t) * np.exp(-t * 26)
    grit = filtered_noise(n, 3) * np.exp(-t * 42) * 0.5
    return ((thud * 0.055 + grit * 0.035) * weight).astype(np.float32)


def riser(duration: float = 1.1, gain: float = 1.0) -> np.ndarray:
    n = round(duration * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    env = (t / duration) ** 2
    sweep = np.sin(2 * np.pi * (220 + 520 * (t / duration) ** 1.6) * t)
    air = filtered_noise(n, 6) * 0.5
    return ((sweep * 0.020 + air * 0.030) * env * gain).astype(np.float32)


def impact(gain: float = 1.0) -> np.ndarray:
    n = round(0.75 * RATE)
    t = np.arange(n, dtype=np.float32) / RATE
    sub = np.sin(2 * np.pi * (54 - 10 * t) * t) * np.exp(-t * 5.2)
    snap = RNG.normal(0, 1, n) * np.exp(-t * 38) * 0.22
    return ((sub * 0.10 + snap * 0.05) * gain).astype(np.float32)


def chirp(freq: float) -> np.ndarray:
    t = np.arange(round(0.22 * RATE), dtype=np.float32) / RATE
    sweep = np.sin(2 * np.pi * (freq * t + 650 * t * t))
    return (sweep * np.sin(np.pi * t / t[-1]) ** 2 * 0.012).astype(np.float32)


def score_and_foley() -> tuple[np.ndarray, np.ndarray]:
    music = np.zeros((SAMPLES, 2), dtype=np.float32)
    foley = np.zeros_like(music)

    # D minor to warm B-flat, G minor and A, resolving at the final reveal.
    chords = [
        (0.00, 6.40, (146.83, 174.61, 220.00)),
        (6.40, 11.50, (116.54, 146.83, 174.61)),
        (11.50, 14.92, (98.00, 116.54, 146.83)),
        (14.92, 18.48, (146.83, 174.61, 220.00)),
        (18.48, 22.67, (116.54, 146.83, 174.61)),
        (22.67, 25.50, (98.00, 116.54, 146.83)),
        (25.50, 27.65, (110.00, 138.59, 164.81)),
        (27.65, 30.00, (146.83, 174.61, 220.00)),
    ]
    for start, end, freqs in chords:
        for j, freq in enumerate(freqs):
            add(note(freq, end - start, 0.0125, 0.44, 0.54), music, start,
                pan=(-0.46, 0.0, 0.46)[j])
            add(note(freq * 0.5006, end - start, 0.0065, 0.7, 0.6), music,
                start, pan=(0.34, -0.25, 0.15)[j])

    bpm_beat = 60 / 100
    for idx, moment in enumerate(np.arange(6.40, 29.85, bpm_beat)):
        if idx % 2 == 0 or moment >= 22.67:
            add(kick(), music, float(moment), pan=-0.02)
        else:
            add(wood_tap(), music, float(moment), pan=0.20)
        if moment >= 8.2:
            # A gentle shaker on off-beats adds momentum without muddying VO.
            for offset in (0.3,):
                add(rustle(0.075) * 0.33, music, float(moment + offset), pan=0.42)
    melody = (293.66, 440.00, 349.23, 440.00, 466.16, 349.23, 293.66, 523.25)
    for i, moment in enumerate(np.arange(8.4, 29.8, 0.6)):
        intensity = 0.010 if moment < 14.8 else 0.014
        if moment >= 27.6:
            intensity = 0.021
        add(note(melody[i % len(melody)], 0.75, intensity, 0.003, 0.1,
                 kind="wood"), music, float(moment), pan=-0.32 if i % 2 else 0.32)

    # Wide low wind bed for the first six seconds and gentle ambience later.
    wind = filtered_noise(SAMPLES, 480)
    wind_t = np.arange(SAMPLES, dtype=np.float32) / RATE
    swell = 0.65 + 0.35 * np.sin(2 * np.pi * 0.105 * wind_t) ** 2
    music[:, 0] += wind * swell * 0.032
    music[:, 1] += np.roll(wind, 1100) * swell * 0.027
    # Faint forest birds when the group is gathering; no stock recordings.
    for j, moment in enumerate((8.7, 9.45, 10.7, 19.1, 21.4)):
        add(chirp(950 + j * 90), foley, moment, pan=0.68 if j % 2 else -0.63)

    for j, moment in enumerate((0.04, 6.32, 11.42, 13.27, 14.84, 18.40, 22.59, 25.43, 27.57)):
        add(whoosh(0.48), foley, moment - 0.24, pan=-0.68 if j % 2 else 0.68)
    # Story beats: tense low booms, a group reveal, then a final resolved hit.
    for moment, gain in ((0.18, 0.7), (6.40, 0.65), (14.92, 0.55), (22.67, 0.6), (27.66, 0.9)):
        add(kick() * gain, foley, moment, pan=0)
    for moment in (2.1, 2.65, 4.5, 8.5, 10.0, 19.0, 19.65, 20.3, 21.1):
        add(rustle(), foley, moment, pan=-0.3 if moment < 10 else 0.3)
    for j, moment in enumerate((11.63, 12.02, 12.55, 12.96, 13.81, 14.31)):
        add(stone_chip(), foley, moment, pan=(-0.35, 0.35)[j % 2])
    for j, moment in enumerate(np.arange(15.08, 18.38, 0.18)):
        add(fire_pop(), foley, float(moment + RNG.uniform(-0.07, 0.07)),
            pan=RNG.uniform(-0.36, 0.36))
    for j, moment in enumerate(np.arange(18.7, 22.35, 0.47)):
        add(wood_tap() * 0.6 + rustle(0.17) * 0.44, foley, float(moment),
            pan=-0.35 if j % 2 else 0.35)

    # Footsteps land on the painted stride contacts of each walk cycle.
    for base, rate, span, pans in ((7.35, 1.75, 4.1, (-0.2, 0.1, 0.35)),
                                   (18.5, 1.9, 3.9, (-0.1, 0.15, 0.4)),
                                   (25.55, 1.9, 2.0, (-0.1, 0.15, 0.4))):
        for k, pan in enumerate(pans):
            phase = (0.33 * k) % 1.0
            moment = base + phase / rate
            while moment < base + span:
                add(footstep(0.7 if k else 1.0), foley, moment, pan=pan)
                moment += 1.0 / rate
    # Whooshes pushed slightly earlier sell each camera punch; risers lead the
    # two biggest reveals, and impacts land exactly on the cuts.
    for moment in (10.98, 12.90, 14.45, 18.00, 22.20, 25.05, 27.20):
        add(riser(0.9, 0.8), foley, moment, pan=0.15 if moment % 2 else -0.15)
    for moment, gain in ((0.0, 0.9), (6.40, 0.75), (11.50, 0.6), (13.35, 0.55),
                         (14.92, 0.7), (18.48, 0.6), (22.67, 0.75), (25.50, 0.6),
                         (27.65, 1.0)):
        add(impact(gain), foley, moment, pan=0)
    return music, foley


def narration_at_48k() -> np.ndarray:
    with wave.open(str(HERE / "narration.wav"), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("Expected the selected narrator's 16-bit mono WAV")
        rate = source.getframerate()
        voice = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
    voice = voice.astype(np.float32) / 32768
    indices = np.arange(SAMPLES, dtype=np.float32) * (rate / RATE)
    resampled = np.interp(indices, np.arange(len(voice)), voice,
                          left=0, right=0).astype(np.float32)
    # Gentle 2.2:1 crest control, followed by makeup gain.
    magnitude = np.abs(resampled)
    compressed = np.where(magnitude <= 0.17, magnitude,
                          0.17 + (magnitude - 0.17) / 2.2)
    return np.sign(resampled) * compressed * 1.16


def create_mix(path: Path | None = None) -> Path:
    path = path or HERE / "_build" / "final_mix.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    music, foley = score_and_foley()
    voice = narration_at_48k()

    # RMS envelope drives a smooth sidechain-style volume dip beneath each word.
    samples = np.abs(voice).astype(np.float64)
    cumulative = np.concatenate(([0.0], np.cumsum(samples)))
    window = round(0.100 * RATE)
    smoothed = (cumulative[window:] - cumulative[:-window]) / window
    activity = np.pad(smoothed, (window // 2, SAMPLES - len(smoothed) - window // 2),
                      mode="edge").astype(np.float32)
    duck = np.clip(activity / 0.035, 0, 1)
    # Broad 90ms attack/release envelope rather than chattery per-sample pumping.
    response = round(0.090 * RATE)
    gain_curve = np.cumsum(np.pad(duck, (response, 0)), dtype=np.float64)
    duck_smooth = ((gain_curve[response:] - gain_curve[:-response]) / response)[:SAMPLES]
    music_gain = 1.65 - 0.52 * duck_smooth.astype(np.float32)
    outro = np.clip((np.arange(SAMPLES) / RATE - 27.7) / 1.4, 0, 1)
    music_gain += outro.astype(np.float32) * 0.45

    mix = (music * music_gain[:, None] + foley * 1.08 + voice[:, None]) * 1.48
    peak = float(np.max(np.abs(mix)))
    if peak > 0.92:
        mix *= 0.92 / peak
    pcm = (np.clip(mix, -0.999, 0.999) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(pcm.tobytes())
    print(f"Mixed {LENGTH:.0f}s stereo audio: {path}, peak {np.max(np.abs(mix)):.3f}, "
          f"RMS {np.sqrt(np.mean(mix ** 2)):.3f}")
    return path


if __name__ == "__main__":
    create_mix()
