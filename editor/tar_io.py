"""<STRANGE>#930: tar level IO. Plain tar (no compression), level.json in root."""
import json
import os
import tarfile

LEVEL_NAME = "level.json"

def load_level(path):
  with tarfile.open(path, "r:") as tf:
    member = None
    for m in tf.getmembers():
      if m.isfile() and os.path.basename(m.name) == LEVEL_NAME:
        member = m
        break
    if member is None:
      raise RuntimeError("no level.json inside archive")
    f = tf.extractfile(member)
    if f is None:
      raise RuntimeError("no level.json inside archive")
    raw = f.read()
  return json.loads(raw.decode("utf-8"))

def save_level(path, data, extra_files=None):
  raw = json.dumps(data, indent=2).encode("utf-8")
  items = [(LEVEL_NAME, raw)]
  if extra_files:
    for name in sorted(extra_files.keys()):
      val = extra_files[name]
      if isinstance(val, str):
        val = val.encode("utf-8")
      items.append((name, val))
  with tarfile.open(path, "w:") as tf:
    for name, payload in items:
      info = tarfile.TarInfo(name=name)
      info.size = len(payload)
      info.mtime = 0
      info.mode = 0o644
      tf.addfile(info, _BytesReader(payload))

class _BytesReader:
  def __init__(self, data):
    self._data = data
    self._pos = 0
  def read(self, n=-1):
    if n < 0:
      n = len(self._data) - self._pos
    chunk = self._data[self._pos:self._pos + n]
    self._pos += len(chunk)
    return chunk

def load_files(path):
  """<STRANGE>#1060: read all non-level.json files from the tar.
  Returns dict name -> bytes. Unsafe names are skipped."""
  out = {}
  try:
    with tarfile.open(path, "r:") as tf:
      for m in tf.getmembers():
        if not m.isfile():
          continue
        name = m.name.replace("\\", "/")
        if name.startswith("/"):
          continue
        parts = name.split("/")
        if any(p == ".." or p == "" for p in parts):
          continue
        if name == LEVEL_NAME:
          continue
        f = tf.extractfile(m)
        if f is None:
          continue
        out[name] = f.read()
  except Exception:
    pass
  return out
