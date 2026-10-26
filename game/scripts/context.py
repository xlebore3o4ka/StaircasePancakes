import random
import zlib


class ScriptCtx:
  # <STRANGE>#1021 API for level scripts; grows over time, keep stable names
  def __init__(self, name, level, script_seed):
    self._name = name
    self._level = level
    # <STRANGE>#1148 deterministic per-trigger RNG; same at both clients if script_seed matches
    self.random = random.Random(script_seed ^ zlib.crc32(name.encode()))

  def log(self, msg):
    print(f"[{self._name}] {msg}")

  def by_id(self, oid):
    # <STRANGE>#1037 returns the raw object; trust scripts since they ship inside the level archive
    return self._level.by_id.get(oid)

  def move_to(self, oid, x=None, y=None, dur=0.5, ease="out"):
    # <STRANGE>#1043 eases: "linear", "in", "out", "inout". Overlapping moves on same object cancel
    return self._level.move_to(oid, x=x, y=y, dur=dur, ease=ease)

  def cancel_move(self, oid):
    self._level.cancel_move(oid)

  def shake(self, dur, amp, freq=0.0):
    # <STRANGE>#1195 screen shake; freq=0 means random jitter, >0 means smooth oscillation
    self._level.shake(dur, amp, freq)

  def sound(self, name, volume=1.0):
    # <STRANGE>#1310 fire a local sound; volume scales SOUND_VOLUME
    if self._level.sound is not None:
      self._level.sound.play(name, volume)

  def text(self, msg, x, y, dur=2.0, size=32, color=(255, 255, 255)):
    # <STRANGE>#1311 world-space floating text; size is in logical px (scaled by cam)
    return self._level.add_text(msg, x, y, dur=dur, size=size, color=color)

  def toast(self, content, dur=2.0, color=(235, 225, 210), w=1200, h=40):
    # <STRANGE>#1312 bottom-center transient message; text, shape list, or draw callback
    return self._level.add_toast(content, dur=dur, color=color, w=w, h=h)

  def flash(self, dur, color=(255, 255, 255), alpha=120):
    # <STRANGE>#1313 full-screen colour flash; alpha fades to 0 over dur
    return self._level.flash(dur, color=color, alpha=alpha)

  def set_light(self, oid, color=None, intensity=None, radius=None,
                angle=None, length=None, cone=None):
    # <STRANGE>#4000: ???????????? ?????????????????? ???????????????????? ??????????
    obj = self._level.by_id.get(oid)
    if obj is None:
      self.log(f"set_light: id '{oid}' not found")
      return False
    from ..entities.light import LightBase
    if not isinstance(obj, LightBase):
      self.log(f"set_light: '{oid}' is not a light")
      return False

    if color is not None:
      obj.color = tuple(color)
    if intensity is not None:
      obj.intensity = max(0.0, float(intensity))
    if radius is not None and hasattr(obj, "radius"):
      obj.radius = float(radius)
    if angle is not None and hasattr(obj, "angle"):
      obj.angle = float(angle)
    if length is not None and hasattr(obj, "length"):
      obj.length = float(length)
    if cone is not None and hasattr(obj, "cone"):
      obj.cone = float(cone)

    # ???????????????????? ???????????? ?????????????????????? ?????????? ??????????
    self._level._occ_cache = None
    self._level.cam = self._level.cam
    return True

  def fade_light(self, oid, intensity, dur=1.0):
    # <STRANGE>#4001: ?????????????? ?????????????? ??????????????????????????
    obj = self._level.by_id.get(oid)
    if obj is None:
      self.log(f"fade_light: id '{oid}' not found")
      return False
    from ..entities.light import LightBase
    if not isinstance(obj, LightBase):
      self.log(f"fade_light: '{oid}' is not a light")
      return False
    self._level.add_mover_light(obj, target_intensity=float(intensity), dur=dur)
    return True

  def toggle_light(self, oid, on=None):
    # <STRANGE>#4002: ????????????????/?????????????????? (???? ?????????????????? - ??????????????????????)
    obj = self._level.by_id.get(oid)
    if obj is None:
      self.log(f"toggle_light: id '{oid}' not found")
      return False
    from ..entities.light import LightBase
    if not isinstance(obj, LightBase):
      self.log(f"toggle_light: '{oid}' is not a light")
      return False
    if on is None:
      on = (obj.intensity <= 0.01)
    obj.intensity = 1.0 if on else 0.0
    self._level._occ_cache = None
    return True
