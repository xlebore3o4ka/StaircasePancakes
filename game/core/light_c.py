import ctypes
import math
import os
import weakref
import pygame
from ..entities.light import LightBase, SunLight, LampLight, SpotLight

_lib = None
_Cam = None
_Light = None
_Occ = None

def _load():
    global _lib, _Cam, _Light, _Occ
    if _lib is not None:
        return _lib
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    name = "light.dll" if os.name == "nt" else "light.so"
    candidates = [
        os.path.join(root, "libraries", name),
        os.path.join(root, name),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), name),
    ]
    path = next((c for c in candidates if os.path.exists(c)), None)
    if path is None:
        raise FileNotFoundError(
            f"light_c: {name} not found (searched: {candidates})")
    _lib = ctypes.CDLL(path)

    class _CamStruct(ctypes.Structure):
        _fields_ = [
            ("x", ctypes.c_float), ("y", ctypes.c_float),
            ("w", ctypes.c_float), ("h", ctypes.c_float),
            ("scale", ctypes.c_float), ("lerp_t", ctypes.c_float),
            ("shake_t", ctypes.c_float), ("shake_dur", ctypes.c_float),
            ("shake_amp", ctypes.c_float), ("shake_freq", ctypes.c_float),
            ("ox", ctypes.c_float), ("oy", ctypes.c_float),
        ]
    _Cam = _CamStruct

    class _LightStruct(ctypes.Structure):
        _fields_ = [
            ("kind", ctypes.c_int),
            ("x", ctypes.c_float), ("y", ctypes.c_float),
            ("color", ctypes.c_ubyte * 3),
            ("intensity", ctypes.c_float),
            ("radius", ctypes.c_float),
            ("angle", ctypes.c_float), ("length", ctypes.c_float), ("cone", ctypes.c_float),
            ("scratch", ctypes.c_void_p),
            ("scratch_w", ctypes.c_int), ("scratch_h", ctypes.c_int),
            ("grad", ctypes.c_void_p),
            ("grad_w", ctypes.c_int), ("grad_h", ctypes.c_int),
            ("grad_radius", ctypes.c_float), ("grad_intensity", ctypes.c_float),
            ("grad_color", ctypes.c_ubyte * 3),
            ("grad_bgr", ctypes.c_int),
        ]
    _Light = _LightStruct

    class _OccStruct(ctypes.Structure):
        _fields_ = [
            ("min_x", ctypes.c_float), ("min_y", ctypes.c_float),
            ("max_x", ctypes.c_float), ("max_y", ctypes.c_float),
            ("n_edges", ctypes.c_int),
            ("edges", ctypes.POINTER(ctypes.c_float)),
            ("n_points", ctypes.c_int),
            ("points", ctypes.POINTER(ctypes.c_float)),
            ("absorption", ctypes.c_float),
        ]
    _Occ = _OccStruct

    _lib.light_init_sun.argtypes = [ctypes.POINTER(_Light), ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_float]
    _lib.light_init_lamp.argtypes = [ctypes.POINTER(_Light), ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_float]
    _lib.light_init_spot.argtypes = [ctypes.POINTER(_Light), ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_float]
    _lib.light_free.argtypes = [ctypes.POINTER(_Light)]
    _lib.light_contribute.argtypes = [ctypes.POINTER(_Light), ctypes.POINTER(ctypes.c_ubyte), ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(_Cam), ctypes.POINTER(_Occ), ctypes.c_int]
    return _lib

_occ_cache_key = None
_occ_array = None
_occ_buffers = []
_debug_printed = False

def _c_contribute(self, light_surf, cam, occluders):
    global _occ_cache_key, _occ_array, _occ_buffers, _debug_printed
    if light_surf.get_bytesize() != 3:
        raise RuntimeError("light_surf must be 24-bit RGB (call .convert(24))")
    if not _debug_printed:
        print(f"light_c: surface shifts={light_surf.get_shifts()}, masks={light_surf.get_masks()}")
        _debug_printed = True

    w, h = light_surf.get_size()
    c = self._c_light
    c.x = self.pos[0]
    c.y = self.pos[1]
    c.intensity = self.intensity
    if hasattr(self, "radius"):
        c.radius = self.radius
    if hasattr(self, "angle"):
        c.angle = self.angle
        c.length = self.length
        c.cone = self.cone

    cam_struct = _Cam(
        cam.x, cam.y, cam.w, cam.h, cam.scale,
        getattr(cam, "lerp_t", 0.0),
        0.0, 0.0, 0.0, 0.0,
        getattr(cam, "_ox", 0.0), getattr(cam, "_oy", 0.0),
    )

    key = (id(occluders), len(occluders))
    if key != _occ_cache_key:
        _occ_cache_key = key
        n_occ = len(occluders)
        _occ_array = (_Occ * n_occ)()
        _occ_buffers = []
        for i, o in enumerate(occluders):
            bbox = o["bbox"]
            edges = o["edges"]
            _occ_array[i].min_x = bbox[0]
            _occ_array[i].min_y = bbox[1]
            _occ_array[i].max_x = bbox[2]
            _occ_array[i].max_y = bbox[3]
            n_edges = len(edges)
            _occ_array[i].n_edges = n_edges
            flat = []
            for e in edges:
                flat.extend(e)
            buf = (ctypes.c_float * len(flat))(*flat)
            _occ_buffers.append(buf)
            _occ_array[i].edges = ctypes.cast(buf, ctypes.POINTER(ctypes.c_float))

            pts = o.get("points", [])
            _occ_array[i].n_points = len(pts)
            flat_pts = []
            for p in pts:
                flat_pts.extend(p)
            buf_pts = (ctypes.c_float * len(flat_pts))(*flat_pts)
            _occ_buffers.append(buf_pts)
            _occ_array[i].points = ctypes.cast(buf_pts, ctypes.POINTER(ctypes.c_float))
            _occ_array[i].absorption = o.get("absorption", 0.5)
    n_occ = len(occluders)

    bgr = 1 if light_surf.get_shifts()[0] == 16 else 0

    mv = memoryview(light_surf.get_buffer())
    try:
        buf_ptr = (ctypes.c_ubyte * len(mv)).from_buffer(mv)
        _lib.light_contribute(self._c_light_ptr, buf_ptr, w, h, bgr, ctypes.byref(cam_struct), _occ_array, n_occ)
    finally:
        del buf_ptr
        mv.release()

def install():
    global _lib
    _lib = _load()
    
    _orig_lamp_init = LampLight.__init__
    def _lamp_init(self, pos, radius=300, color=(255, 200, 120), intensity=1.0):
        _orig_lamp_init(self, pos, radius, color, intensity)
        col = (ctypes.c_ubyte * 3)(*color)
        self._c_light = _Light()
        self._c_light_ptr = ctypes.pointer(self._c_light)
        _lib.light_init_lamp(self._c_light_ptr, pos[0], pos[1], radius, col, intensity)
        weakref.finalize(self, _lib.light_free, self._c_light_ptr)
    LampLight.__init__ = _lamp_init
    LampLight.contribute = _c_contribute

    _orig_sun_init = SunLight.__init__
    def _sun_init(self, color=(200, 210, 240), intensity=0.5, direction=(0.5, 1.0), shadow_length=1000.0, gradient_length=100.0):
        _orig_sun_init(self, color, intensity, direction, shadow_length, gradient_length)
        col = (ctypes.c_ubyte * 3)(*color)
        self._c_light = _Light()
        self._c_light_ptr = ctypes.pointer(self._c_light)
        _lib.light_init_sun(self._c_light_ptr, direction[0], direction[1], shadow_length, gradient_length, col, intensity)
        weakref.finalize(self, _lib.light_free, self._c_light_ptr)
    SunLight.__init__ = _sun_init
    SunLight.contribute = _c_contribute

    _orig_spot_init = SpotLight.__init__
    def _spot_init(self, pos, angle=0.0, length=500, cone=math.radians(60), color=(255, 240, 200), intensity=1.0):
        _orig_spot_init(self, pos, angle, length, cone, color, intensity)
        col = (ctypes.c_ubyte * 3)(*color)
        self._c_light = _Light()
        self._c_light_ptr = ctypes.pointer(self._c_light)
        _lib.light_init_spot(self._c_light_ptr, pos[0], pos[1], angle, length, cone, col, intensity)
        weakref.finalize(self, _lib.light_free, self._c_light_ptr)
    SpotLight.__init__ = _spot_init
    SpotLight.contribute = _c_contribute
