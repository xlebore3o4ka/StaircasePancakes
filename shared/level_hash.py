import hashlib
import json
import os
import tarfile


def _canon_json(data):
  # <STRANGE>#1203 canonical json: sorted keys, no spaces, stable across writers
  return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def _hash_json_file(path):
  with open(path) as f:
    return hashlib.sha1(_canon_json(json.load(f))).hexdigest()


def hash_level(path):
  # <STRANGE>#1203 hash the content (json + scripts), not the file bytes: tar mtimes/owner/order differ between copies
  if not path.endswith(".tar"):
    return _hash_json_file(path)
  parts = []
  with tarfile.open(path, "r") as tf:
    names = sorted(m.name for m in tf.getmembers() if m.isfile())
    for name in names:
      f = tf.extractfile(name)
      if f is None:
        continue
      data = f.read()
      if name == "level.json":
        try:
          data = _canon_json(json.loads(data))
        except Exception:
          pass
      h = hashlib.sha1(data).hexdigest()
      parts.append(f"{name}:{h}")
  return hashlib.sha1("\n".join(parts).encode()).hexdigest()
