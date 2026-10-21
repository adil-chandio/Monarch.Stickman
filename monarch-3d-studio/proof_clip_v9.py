#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
proof_clip_v9 — the character sheet's character, moved with physics.

Shot 1  0.0 - 4.4   cafe: seated, reach, pick up, sip (anticipation + overshoot,
                    head-lead, coffee slosh), lower
Shot 2  4.4 - 7.8   street: walk cycle driven by a no-slip foot plant, the body
                    rides the stance leg (real COM bob), arm swing lags 6 frames,
                    the camera chases with momentum
Shot 3  7.8 - 10.0  cafe wide: standing sip, slow push-in

1920x1080, 24 fps, 10.00 s -> proof_cozy_v9.mp4
"""

import math

import numpy as np
import cv2

import char_v9 as CH
import physics as PH
import proof_clip_v7 as P7

FPS = 24
DUR = 10.0
N = int(FPS * DUR)
OUT = "proof_cozy_v9.mp4"
W, H = 1920, 1080

# ---------------------------------------------------------------- shot 1 set
SEAT_X, FLOOR_Y, R = 900.0, 985.0, 100.0
GY = FLOOR_Y
MUG_X, MUG_Y = 1156.0, 641.0
SIP_SH, SIP_EL = 88.0, 130.0

# ---------------------------------------------------------------- shot 2 set
WALK_GROUND = 1000.0
WALK_SCALE = 82.0
WALK_START = 620.0
CYCLE = 1.06                 # seconds for a full two-step cycle
A_HIP = 21.0
DUTY = 0.62


def ease(t):
    return PH.ease(t)


# ============================================================ walk mechanics
def leg_state(ph):
    """hip / knee / foot angles for one leg at cycle phase ph (0..1)."""
    ph = ph % 1.0
    if ph < DUTY:                                   # ---- stance
        u = ph / DUTY
        hip = A_HIP * (1.0 - 2.0 * u)
        knee = -7.0 - 13.0 * math.sin(math.pi * u)
        foot = -13.0 + 34.0 * u
    else:                                           # ---- swing
        u = (ph - DUTY) / (1.0 - DUTY)
        hip = -A_HIP + 2.0 * A_HIP * PH.ease(u)
        knee = -16.0 - 54.0 * math.sin(math.pi * u) ** 0.9
        foot = 20.0 - 28.0 * u
    return hip, knee, foot


def walk_pose(phase, carry=True):
    hl, kl, fl = leg_state(phase)
    hr, kr, fr = leg_state(phase + 0.5)
    p = dict(lean=4.5, hipL=hl, knL=kl, hipR=hr, knR=kr,
             footL=fl, footR=fr, py=0.0)
    # far arm counter-swings the far leg, with a lag baked into the phase
    p["shL"] = 0.62 * leg_state(phase + 0.5 + 0.10)[0] - 6.0
    p["elL"] = -22.0 - 10.0 * math.sin(2 * math.pi * (phase + 0.10))
    p["shR"], p["elR"] = -34.0, 62.0                # the carry arm
    # contact squash: two strikes per cycle
    d = min(abs((phase % 0.5) / 0.5), abs((phase % 0.5 - 0.5) / 0.5))
    p["squash"] = 1.0 - 0.030 * math.exp(-(d / 0.20) ** 2)
    return p


class Sim:
    """stateful simulation; seek(t) steps forward, and rewinds on stills"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.i = 0
        self.pose = None

    def seek(self, t):
        n = int(round(t * FPS))
        if n < self.i:
            self.reset()
        while self.i < n:
            self.i += 1
            self.step(self.i / FPS, 1.0 / FPS)
        if self.pose is None:                 # frame 0
            self.step(max(t, 1.0 / FPS), 1.0 / FPS)
        return self.pose


class WalkSim(Sim):
    def reset(self):
        super().reset()
        self.plant = PH.Plant()
        self.tilt = PH.Spring(70, 13)
        self.slosh = PH.Slosh()
        self.cam = PH.Momentum(20, 9)
        self.body_x = WALK_START
        self.cam_x = 960.0
        self.hand = (0.0, 0.0)

    def step(self, t, dt):
        phase = (t / CYCLE) % 1.0
        p = walk_pose(phase)
        J = CH.fk(p, 1)
        stance, key = (("L", "anL") if J["anL"][1] >= J["anR"][1]
                       else ("R", "anR"))
        self.body_x = self.plant.update(stance,
                                        float(J[key][0]) * WALK_SCALE,
                                        self.body_x)
        # head lag: the head keeps travelling a beat after the body
        bob = (J["pelvis"][1] + 0.0) * WALK_SCALE / 100.0
        p["tilt"] = self.tilt.step(4.0 + bob * 0.5, dt)
        hx = float(J["haR"][0])
        p["cup_tilt"] = -9.0 + self.slosh.step(hx, 0.0, dt)
        self.cam_x = self.cam.step(960.0 + 0.12 * (self.body_x - 960.0),
                                   dt)
        self.hand = (float(J["haR"][0]), float(J["haR"][1]))
        self.pose = p


# ============================================================ shot 1: seated
def seated_timeline(t):
    """returns (k, tilt_target, sip_lean) — k 0 = on the table, 1 = at the lips"""
    # reach from 0.55 to 1.30, then an anticipatory dip before the lift
    lift = PH.anticipate((t - 1.30) / 1.05, a=0.13)
    lift = max(0.0, lift)
    if t > 2.35:                       # small overshoot as the cup arrives
        lift = 1.0 + 0.035 * math.exp(-((t - 2.45) / 0.16) ** 2)
    down = PH.ease((t - 3.30) / 0.75)
    k = max(0.0, min(1.06, lift)) * (1.0 - down)
    return k


class SeatedSim(Sim):
    def reset(self):
        super().reset()
        self.tilt = PH.Spring(60, 12)
        self.slosh = PH.Slosh()

    def step(self, t, dt):
        base = CH.pose_seated(t, lean=18)
        reach = CH.arm_to(base, ((MUG_X - SEAT_X) / R, (MUG_Y - GY) / R))
        k = seated_timeline(t)
        p = dict(reach)
        el1 = SIP_EL
        while el1 - reach["elR"] > 180:
            el1 -= 360
        while el1 - reach["elR"] < -180:
            el1 += 360
        p["shR"] = reach["shR"] + (SIP_SH - reach["shR"]) * k
        p["elR"] = reach["elR"] + (el1 - reach["elR"]) * k
        p["lean"] = 18 + 7.0 * k
        p["tilt"] = self.tilt.step(5.0 * min(1.0, max(0.0, (k - 0.15) / 0.8)),
                                   dt)
        J = CH.fk(p, 1)
        hx, hy = float(J["haR"][0]), float(J["haR"][1])
        p["cup_tilt"] = -9.0 + self.slosh.step(hx, hy, dt) * 1.4
        p["_k"] = k
        p["_hand"] = (SEAT_X + hx * R, GY + hy * R)
        self.pose = p


# ============================================================ frame renderer
def frame(fi):
    t = fi / FPS

    # ---------------- shot 1
    if t < 4.4:
        tl = t / 4.4
        push = ease((t - 2.05) / 0.55) - ease((t - 3.25) / 0.60)
        push = max(0.0, min(1.0, push))
        z = 1.40 + 0.10 * ease(tl) + 0.15 * push
        cxc = 1000.0 + 22.0 * push
        cyc = 635.0 - 70.0 * push
        img, c = P7.cam(P7.load("cafe_table5"), z, cxc, cyc)
        sx, sy = P7.w2s(SEAT_X, GY, c)
        Rp = R * z
        P7._chair(img, sx, sy, Rp)
        p = SEATED.seek(t)
        k = p["_k"]
        held = k > 0.05
        if not held:
            mx, my = P7.w2s(MUG_X, MUG_Y, c)
            P7._mug_stand(img, (mx, my), Rp)
        CH.draw(img, sy, sx, Rp, p, t=t, mood="sip" if k > 0.75 else "happy",
                blink_at=1.9, cup=held, front_arm=held)
        if k > 0.55:                     # steam off the cup
            _steam(img, P7.w2s(*p["_hand"], c), Rp * (k - 0.55), t)
        return P7.grade(img)

    # ---------------- shot 2
    if t < 7.8:
        tt = t - 4.4
        sim = WALK
        sim.seek(tt)
        img, c = P7.cam(P7.load("street_walk"), 1.22, sim.cam_x, 560.0)
        sx, sy = P7.w2s(sim.body_x, WALK_GROUND, c)
        CH.draw(img, sy, sx, WALK_SCALE * c[0], sim.pose, t=t, mood="happy",
                blink_at=2.4, cup=True)
        return P7.grade(img)

    # ---------------- shot 3
    tl = (t - 7.8) / 2.2
    z = 1.20 + 0.09 * ease(tl)
    img, c = P7.cam(P7.load("cafe_table5"), z, 1055.0, 630.0)
    sx, sy = P7.w2s(1010.0, 985.0, c)
    Rp = 78 * z
    k = ease((t - 8.3) / 0.9)
    base = CH.pose_idle(t)
    sip_base = dict(base)
    sip_base["lean"] = 14.0
    sip_base["tilt"] = 14.0
    head = CH.fk(sip_base, 1)["head"]
    sip = CH.arm_to(sip_base, (float(head[0]) + 0.30, float(head[1]) + 0.70))
    p = dict(base)
    p["lean"] = 2.0 + 12.0 * k
    p["tilt"] = 14.0 * k
    p["shR"] = base["shR"] + (sip["shR"] - base["shR"]) * k
    p["elR"] = base["elR"] + (sip["elR"] - base["elR"]) * k
    p["cup_tilt"] = -9.0 - 11.0 * k
    CH.draw(img, sy, sx, Rp, p, t=t, mood="sip" if k > 0.6 else "happy",
            blink_at=0.9, cup=True, front_arm=k > 0.25)
    return P7.grade(img)


def _steam(img, p, amt, t):
    if amt <= 0:
        return
    for j, off in enumerate((-0.10, 0.10)):
        pts = []
        for i in range(5):
            a = i / 4.0
            x = p[0] + off * 60 + math.sin(a * 5.0 + t * 4.0 + j) * 7 * a
            y = p[1] - 30 - a * 70 * (0.5 + amt)
            pts.append((int(x), int(y)))
        ov = img.copy()
        for a, b in zip(pts[:-1], pts[1:]):
            cv2.line(ov, a, b, (250, 250, 248), 3, cv2.LINE_AA)
        cv2.addWeighted(cv2.GaussianBlur(ov, (0, 0), 3), min(0.55, 0.30 * amt),
                        img, 1 - min(0.55, 0.30 * amt), 0, img)


SEATED = SeatedSim()
WALK = WalkSim()


def main():
    import subprocess
    import time
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ff = "ffmpeg"
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "bgr24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    t0 = time.time()
    for i in range(N):
        f = frame(i)
        p.stdin.write(np.ascontiguousarray(f).tobytes())
        if i % 24 == 0:
            print(f"frame {i}/{N} {time.time() - t0:.1f}s", flush=True)
    p.stdin.close()
    p.wait()
    print("DONE", OUT)


if __name__ == "__main__":
    main()
