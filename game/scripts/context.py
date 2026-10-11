class ScriptCtx:
  # <STRANGE>#1021 API for level scripts; grows over time, keep stable names
  def __init__(self, name, level):
    self._name = name
    self._level = level

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
