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
                ("t", ctypes.POINTER(ctypes.c_int32)),
                ("uv", ctypes.POINTER(ctypes.c_float)), ("m", ctypes.POINTER(ctypes.c_float)),
                ("nv", ctypes.c_int), ("nt", ctypes.c_int)]


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
                ("moon", ctypes.c_float * 3), ("shadow_strength", ctypes.c_float),
                ("light", ctypes.c_float * 3), ("light_colour", ctypes.c_float * 3),
                ("light_range", ctypes.c_float),
                ("light2", ctypes.c_float * 3), ("light2_colour", ctypes.c_float * 3),
                ("light2_range", ctypes.c_float),
                ("sky_hor", ctypes.c_float * 3), ("sky_top", ctypes.c_float * 3),
                ("cloud", ctypes.c_float), ("milky", ctypes.c_float),
                ("ao_strength", ctypes.c_float), ("bloom", ctypes.c_float),
                ("dof_focus", ctypes.c_float), ("dof_amt", ctypes.c_float),
                ("mist", ctypes.c_float * 3), ("mist_amount", ctypes.c_float),
                ("mist_height", ctypes.c_float)]


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
                    exposure=1.0, night=0, moon=(0, 0, 0), shadow=0.75,
                    light=None, light_colour=(0, 0, 0), light_range=4.0,
                    light2=None, light2_colour=(0, 0, 0), light2_range=3.0,
                    sky=None, cloud=0.0, milky=0.0, ao=0.62, bloom=0.55,
                    dof_focus=0.0, dof=0.0, mist=None, mist_amount=0.0,
                    mist_height=0.9) -> None:
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
        self.env.light = tuple(float(v) for v in (light or (0.0, -50.0, 0.0)))
        self.env.light_colour = tuple(float(v) for v in light_colour)
        self.env.light_range = float(light_range)
        self.env.light2 = tuple(float(v) for v in (light2 or (0.0, -50.0, 0.0)))
        self.env.light2_colour = tuple(float(v) for v in light2_colour)
        self.env.light2_range = float(light2_range)
        hor, top = sky if sky else ((0, 0, 0), (0, 0, 0))
        self.env.sky_hor = tuple(float(v) for v in hor)
        self.env.sky_top = tuple(float(v) for v in top)
        self.env.cloud = float(cloud)
        self.env.milky = float(milky)
        self.env.ao_strength = float(ao)
        self.env.bloom = float(bloom)
        self.env.dof_focus = float(dof_focus)
        self.env.dof_amt = float(dof)
        self.env.mist = tuple(float(v) for v in (mist or (0.0, 0.0, 0.0)))
        self.env.mist_amount = float(mist_amount)
        self.env.mist_height = float(mist_height)

    def render(self, meshes) -> np.ndarray:
        keep = []
        structs = (_Mesh * len(meshes))()
        for i, mesh in enumerate(meshes):
            v, n, c, e, t = mesh[:5]
            if len(t) == 0:
                continue
            uv = mesh[5] if len(mesh) > 5 else np.zeros((len(v), 2), np.float32)
            mm = mesh[6] if len(mesh) > 6 else np.zeros((len(v),), np.float32)
            v = np.ascontiguousarray(v, np.float32)
            n = np.ascontiguousarray(n, np.float32)
            c = np.ascontiguousarray(c, np.float32)
            e = np.ascontiguousarray(e, np.float32)
            t = np.ascontiguousarray(t, np.int32)
            uv = np.ascontiguousarray(uv, np.float32)
            mm = np.ascontiguousarray(mm, np.float32)
            keep.append((v, n, c, e, t, uv, mm))
            structs[i] = _Mesh(v.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                               n.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                               c.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                               e.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                               t.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
                               uv.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                               mm.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                               len(v), len(t))
        self.lib.render(structs, len(keep), ctypes.byref(self.cam), ctypes.byref(self.env),
                        self.out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
                        self.depth.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
                        self.normals.ctypes.data_as(ctypes.POINTER(ctypes.c_float)))
        return self.out.reshape(self.h, self.w, 3)
