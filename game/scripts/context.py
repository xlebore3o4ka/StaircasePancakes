class ScriptCtx:
  # <STRANGE>#1021 minimal API for level scripts; grows later, currently only log
  def __init__(self, name):
    self._name = name

  def log(self, msg):
    print(f"[{self._name}] {msg}")
