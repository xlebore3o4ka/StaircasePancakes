import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "settings.json")
_DATA = None


def _load():
  global _DATA
  if _DATA is not None:
    return _DATA
  try:
    with open(_PATH, "r", encoding="utf-8") as f:
      _DATA = json.load(f)
  except Exception:
    _DATA = {}
  return _DATA


def get_panel_size(kind):
  """kind: 'platform' | 'background'. ???????????????????? (w, h) ?????? None."""
  d = _load().get("panel_size", {})
  v = d.get(kind)
  if not v:
    return None
  try:
    return (int(v[0]), int(v[1]))
  except Exception:
    return None


def set_panel_size(kind, w, h):
  d = _load()
  ps = d.setdefault("panel_size", {})
  ps[kind] = [int(w), int(h)]
  try:
    with open(_PATH, "w", encoding="utf-8") as f:
      json.dump(d, f, indent=2)
  except Exception:
    pass


def get_level_version(default=None):
  """<STRANGE>#800: version string the editor writes into level JSON."""
  d = _load()
  v = d.get("level_version")
  if v is None:
    return default
  return str(v)


def set_level_version(v):
  """<STRANGE>#801: persist editor level version to settings.json."""
  d = _load()
  d["level_version"] = str(v)
  try:
    with open(_PATH, "w", encoding="utf-8", newline="\n") as f:
      json.dump(d, f, indent=2)
  except Exception:
    pass
