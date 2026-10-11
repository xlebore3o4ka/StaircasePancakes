import importlib.util
import os
import traceback


def load(path, name):
  # <STRANGE>#1022 load module under a stable synthetic name so files with same basename don't clash
  if not os.path.exists(path):
    print(f"script: not found {path}")
    return None
  try:
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
  except Exception as e:
    _err(path, e)
    return None


def call(mod, path, handler, ctx, *extra):
  # <STRANGE>#1023 missing handler is silent; exception is logged and swallowed so level keeps running
  if mod is None:
    return
  fn = getattr(mod, handler, None)
  if fn is None:
    return
  try:
    fn(ctx, *extra)
  except Exception as e:
    _err(path, e)


def _err(path, e):
  # <STRANGE>#1024 print in "path(line,col) Error: msg" form so it can be located quickly
  tb = traceback.extract_tb(e.__traceback__)
  if tb:
    last = tb[-1]
    col = getattr(last, "colno", 0) or 0
    print(f"{path}({last.lineno},{col}) {type(e).__name__}: {e}")
  else:
    print(f"{path} {type(e).__name__}: {e}")
