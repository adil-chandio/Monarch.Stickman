#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
physics.py — tiny physical helpers used by the clip drivers.

Everything here works on scalar or vector state and is stepped with a fixed dt,
so the animation is deterministic no matter how frames are requested.

  Spring        : critically-ish damped spring, the workhorse for secondary motion
  Momentum      : chase a moving target with inertia (camera, head, hips)
  slosh         : a pendulum angle for the coffee in the cup
  contact_plant : keeps a stance foot nailed to the ground (no foot slide)
"""

import math

import numpy as np


class Spring:
    """x'' = k (target - x) - c x'"""

    def __init__(self, k=48.0, c=11.0, x=0.0, v=0.0):
        self.k, self.c, self.x, self.v = k, c, x, v

    def step(self, target, dt):
        a = self.k * (target - self.x) - self.c * self.v
        self.v += a * dt
        self.x += self.v * dt
        return self.x

    def settle(self, target, dt, eps=1e-4):
        for _ in range(600):
            self.step(target, dt)
            if abs(self.x - target) < eps and abs(self.v) < eps:
                break
        return self.x


class Momentum:
    """second order follower: position, velocity and a little overshoot"""

    def __init__(self, k=26.0, c=9.0):
        self.s = Spring(k, c)
        self.prev = 0.0

    def step(self, target, dt):
        self.prev = self.s.x
        return self.s.step(target, dt)

    @property
    def vel(self):
        return self.s.v


def ease(t):
    t = max(0.0, min(1.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def ease_out(t, p=2.0):
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** p


def ease_in(t, p=2.0):
    t = max(0.0, min(1.0, t))
    return t ** p


def anticipate(t, a=0.14):
    """rise, dip slightly before the move, then go — classic anticipation"""
    t = max(0.0, min(1.0, t))
    if t < 0.18:
        return -a * math.sin(math.pi * t / 0.18)
    return ease((t - 0.18) / 0.82)


def overshoot(t, s=0.12):
    """ease with a small overshoot at the end, settles by t=1"""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3 * math.cos(3.0 * t) * (1.0 - s) - s * t


class Slosh:
    """the coffee surface inside the cup, driven by hand acceleration"""

    def __init__(self, k=230.0, c=7.0):
        self.s = Spring(k, c)
        self.last_v = 0.0

    def step(self, hand_x, hand_y, dt):
        # angular impulse from the hand's acceleration, clamped to a sane range
        if dt <= 0:
            return 0.0
        vx = hand_x
        ay = (vx - self.last_v) / dt
        self.last_v = vx
        target = max(-9.0, min(9.0, -ay * 0.55))
        a = self.s.step(target, dt)
        self.s.step(0.0, dt)          # always pulls back to level
        return max(-11.0, min(11.0, a))


class Plant:
    """no-slip feet: the stance foot stays where it landed"""

    def __init__(self):
        self.x = None
        self.stance = None

    def update(self, stance, foot_local_x, body_x):
        if self.x is None or stance != self.stance:
            # a new foot just landed -> nail it where it is right now
            self.x = body_x + foot_local_x
            self.stance = stance
        return self.x - foot_local_x


def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return max(lo, min(hi, v))
