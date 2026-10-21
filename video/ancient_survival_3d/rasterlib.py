"""ctypes bridge to the software rasteriser in raster.c."""

from __future__ import annotations

import ctypes
import subprocess
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LIB_PATH = HERE / "libraster.so"


class _Mesh(ctypes.Structure):
    _fields_ = [("v", ctypes.POINTER(ctypes.c_float)), ("n", ctypes.POINTER(ctypes.c_float)),
                ("c", ctypes.POINTER(ctypes.c_float)), ("e", ctypes.POINTER(ctypes.c_float)),
                ("t", ctypes.POINTER(ctypes.c_int32)), ("nv", ctypes.c_int), ("nt", ctypes.c_int)]


class _Camera(ctypes.Structure):
    _fields_ = [("pos", ctypes.c_float * 3), ("target", ctypes.c_float * 3),
                ("up", ctypes.c_float * 3), ("fov", ctypes.c_float),
                ("nearz", ctypes.c_float), ("farz", ctypes.c_float),
                ("w", ctypes.c_int), ("h", ctypes.c_int)]


class _Env(ctypes.Structure):
    _fields_ = [("dir", ctypes.c_float * 3), ("colour", ctypes.c_float * 3),
                ("ambient", ctypes.c_float * 3), ("ground", ctypes.c_float * 3),
                ("fog", ctypes.c_float * 3), ("fog_density", ctypes.c_float),
                ("exposure", ctypes.c_float), ("night", ctypes.c_int),
                ("moon", ctypes.c_float * 3), ("shadow_strength", ctypes.c_float)]


def ensure_library(rebuild: bool = False) -> Path:
    if rebuild or not LIB_PATH.exists():
        subprocess.run(["gcc", "-O2", "-march=native", "-shared", "-fPIC",
                        "-o", str(LIB_PATH), str(HERE / "raster.c"), "-lm"], check=True)
    return LIB_PATH


class Raster:
    def __init__(self, width: int, height: int, fov: float = 0.80):
        lib = ctypes.CDLL(str(ensure_library()))
        lib.render.argtypes = [ctypes.POINTER(_Mesh), ctypes.c_int,
                               ctypes.POINTER(_Camera), ctypes.POINTER(_Env),
                               ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_float),
                               ctypes.POINTER(ctypes.c_float)]
        lib.render.restype = None
        self.lib = lib
        self.w, self.h = width, height
        self.cam = _Camera()
        self.cam.up = (0.0, 1.0, 0.0)
        self.cam.fov = fov
        self.cam.nearz = 0.06
        self.cam.farz = 400.0
        self.cam.w, self.cam.h = width, height
        self.env = _Env()
        self.out = np.zeros(height * width * 3, np.uint8)
        self.depth = np.zeros(height * width, np.float32)
        self.normals = np.zeros(height * width * 3, np.float32)

    def camera(self, pos, target, fov: float | None = None, up=(0.0, 1.0, 0.0)) -> None:
        self.cam.pos = tuple(float(v) for v in pos)
        self.cam.target = tuple(float(v) for v in target)
        self.cam.up = tuple(float(v) for v in up)
        if fov is not None:
            self.cam.fov = float(fov)

    def environment(self, sun_dir, sun_colour, ambient, ground, fog, fog_density,
                    exposure=1.0, night=0, moon=(0, 0, 0), shadow=0.75) -> None:
        self.env.dir = tuple(float(v) for v in sun_dir)
        self.env.colour = tuple(float(v) for v in sun_colour)
        self.env.ambient = tuple(float(v) for v in ambient)
        self.env.ground = tuple(float(v) for v in ground)
        self.env.fog = tuple(float(v) for v in fog)
        self.env.fog_density = float(fog_density)
        self.env.exposure = float(exposure)
        self.env.night = int(night)
        self.env.moon = tuple(float(v) for v in moon)
        self.env.shadow_strength = float(shadow)

    def render(self, meshes) -> np.ndarray:
        keep = []
        structs = (_Mesh * len(meshes))()
        for i, (v, n, c, e, t) in enumerate(meshes):
            if len(t) == 0:
                continue
            v = np.ascontiguousarray(v, np.float32)
            n = np.ascontiguousarray(n, np.float32)
            c = np.ascontiguousarray(c, np.float32)
            e = np.ascontiguousarray(e, np.float32)
            t = np.ascontiguousarray(t, np.int32)
            keep.append((v, n, c, e, t))
            structs[i] = _Mesh(v.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                               n.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                               c.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                               e.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                               t.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                               len(v), len(t))
        self.lib.render(structs, len(keep), ctypes.byref(self.cam), ctypes.byref(self.env),
                        self.out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
                        self.depth.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                        self.normals.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
        return self.out.reshape(self.h, self.w, 3)
