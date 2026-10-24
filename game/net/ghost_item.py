import math
import pygame
import pymunk
from shared.smooth import smooth
from shared.const import NET_TIMEOUT_SEC


_proto_cache = {}


def _proto(net_type):
  if net_type in _proto_cache:
    return _proto_cache[net_type]
  # <STRANGE>#966 lazy import to avoid circular dep with item module at load time
  from ..entities.item import CubeItem, SodaItem, RebarItem, PortablePegItem, BagItem, LanternItem
  cls = {"cube": CubeItem, "soda": SodaItem, "rebar": RebarItem,
         "peg": PortablePegItem, "bag": BagItem,
         "lantern": LanternItem}.get(net_type)
  if cls is None:
    print(f"ghost_item: unknown net_type {net_type!r}")
    _proto_cache[net_type] = None
    return None
  dummy = pymunk.Space()
  obj = cls(dummy, (0, 0))
  try:
    obj.destroy()
  except Exception:
    pass
  _proto_cache[net_type] = obj
  return obj


class GhostItems:
  # <STRANGE>#967 remote free items owned by other players; lerp to target, fade out on timeout
  ALPHA = 120
  LERP = 0.35

  def __init__(self):
    self.items = {}

  def apply(self, entries):
    for e in entries:
      nid = e.get("id")
      if not nid:
        continue
      it = self.items.get(nid)
      if it is None:
        self.items[nid] = {
          "type": e.get("type"),
          "x": float(e.get("x", 0)), "y": float(e.get("y", 0)),
          "tx": float(e.get("x", 0)), "ty": float(e.get("y", 0)),
          "angle": float(e.get("angle", 0)),
          "target_angle": float(e.get("angle", 0)),
          "owner": e.get("owner", ""),
          "last_seen": 0.0,
        }
      else:
        it["type"] = e.get("type", it["type"])
        it["tx"] = float(e.get("x", it["tx"]))
        it["ty"] = float(e.get("y", it["ty"]))
        it["target_angle"] = float(e.get("angle", it["target_angle"]))
        it["last_seen"] = 0.0

  def update(self, dt):
    k = smooth(self.LERP, dt)
    for it in self.items.values():
      it["x"] += (it["tx"] - it["x"]) * k
      it["y"] += (it["ty"] - it["y"]) * k
      da = (it["target_angle"] - it["angle"] + math.pi) % (2 * math.pi) - math.pi
      it["angle"] += da * k
      it["last_seen"] += dt
    stale = [nid for nid, it in self.items.items() if it["last_seen"] >= NET_TIMEOUT_SEC]
    for nid in stale:
      del self.items[nid]

  def draw(self, screen, cam):
    if not self.items:
      return
    surf = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    any_drawn = False
    for it in self.items.values():
      proto = _proto(it["type"])
      if proto is None:
        continue
      proto.draw_at(surf, cam, (it["x"], it["y"]), it["angle"], 255, 1.0)
      any_drawn = True
    if not any_drawn:
      return
    surf.set_alpha(self.ALPHA)
    screen.blit(surf, (0, 0))
