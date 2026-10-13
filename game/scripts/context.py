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
