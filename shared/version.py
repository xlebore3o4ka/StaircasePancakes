import os


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read():
  # <STRANGE>#997 single source of truth for the version string
  with open(os.path.join(_ROOT, "VERSION")) as f:
    return f.read().strip()


def parse(v):
  # <STRANGE>#998 tuple of ints; tolerant only to the expected a.b.c shape
  return tuple(int(x) for x in v.split("."))
