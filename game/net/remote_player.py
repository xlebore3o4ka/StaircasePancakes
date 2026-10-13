import pygame
import pymunk
from shared.const import ARM_R, ITEM_OFFSET
from shared.smooth import smooth
from ..entities.player import STAMINA_MAX, draw_player_body
from ..entities.item import CubeItem, SodaItem, RebarItem, PortablePegItem, BagItem


# <STRANGE>#935 minimal field holders so draw_player_body can read body.position/arms[i].position uniformly
class _FakeBody:
  def __init__(self):
    self.position = (0.0, 0.0)


class _FakeArm:
  def __init__(self):
    self.position = (0.0, 0.0)


_NET_CLASSES = {
  "cube": CubeItem,
  "soda": SodaItem,
  "rebar": RebarItem,
  "peg": PortablePegItem,
  "bag": BagItem,
}

# <STRANGE>#936 prototypes for draw_at: instantiated once, body destroyed, kept only for rendering
_proto_cache = {}


def _proto(net_type):
  if net_type not in _NET_CLASSES:
    print(f"remote_player: unknown net_type {net_type!r}")
    return None
  if net_type not in _proto_cache:
    dummy = pymunk.Space()
    obj = _NET_CLASSES[net_type](dummy, (0, 0))
    try:
      obj.destroy()
    except Exception:
      pass
    _proto_cache[net_type] = obj
  return _proto_cache[net_type]


class RemotePlayer:
  # <STRANGE>#937 ghost of another player; holds current & target state, lerps in update, draws via shared renderer
  def __init__(self, name):
    self.name = name
    self.body = _FakeBody()
    self.arms = [_FakeArm(), _FakeArm()]
    self.stamina = [float(STAMINA_MAX), float(STAMINA_MAX)]
    # <STRANGE>#1166 default full hp for remote ghosts; synced later
    self.hp = 100.0
    self.arm_r = [float(ARM_R), float(ARM_R)]
    self.held = [None, None]
    self._target_pos = (0.0, 0.0)
    self._target_arms = [(0.0, 0.0), (0.0, 0.0)]
    self._target_stamina = [float(STAMINA_MAX), float(STAMINA_MAX)]
    self._target_hp = 100.0
    self._target_held = [None, None]
    self.lerp_t = 0.35
    self.last_seen = 0.0
    # <STRANGE>#981 on first state, snap position instead of lerping from origin
    self._received_once = False
    self._font = None

  def apply_state(self, st):
    self.name = st.name or self.name
    self._target_pos = st.pos
    self._target_arms = list(st.arms)
    self._target_stamina = list(st.stamina)
    self._target_hp = float(st.hp)
    self._target_held = list(st.held)
    # <STRANGE>#981 reset timeout so ghost doesn't get pruned while states keep arriving
    self.last_seen = 0.0
    if not self._received_once:
      # <STRANGE>#982 first state after creation: jump to target, no lerp from origin
      self._received_once = True
      self.body.position = st.pos
      for i in range(2):
        self.arms[i].position = st.arms[i]
      self.stamina = list(st.stamina)
      self.hp = float(st.hp)

  def update(self, dt):
    k = smooth(self.lerp_t, dt)
    p = self.body.position
    tp = self._target_pos
    self.body.position = (p[0] + (tp[0] - p[0]) * k,
                          p[1] + (tp[1] - p[1]) * k)
    for i in range(2):
      a = self.arms[i].position
      t = self._target_arms[i]
      self.arms[i].position = (a[0] + (t[0] - a[0]) * k,
                               a[1] + (t[1] - a[1]) * k)
      self.stamina[i] += (self._target_stamina[i] - self.stamina[i]) * k
      self.held[i] = self._target_held[i]
    # <STRANGE>#1193 hp lerps too: body colour smooths as remote takes damage
    self.hp += (self._target_hp - self.hp) * k
    self.last_seen += dt

  GHOST_ALPHA = 140
  NAME_ALPHA = 180

  def draw(self, screen, cam):
    # <STRANGE>#957 remote ghost drawn onto an alpha surface, then blitted with global alpha; per-shape alpha would need SRCALPHA draws everywhere
    surf = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    for i in range(2):
      t = self.held[i]
      if t is None:
        continue
      proto = _proto(t)
      if proto is None:
        continue
      hx, hy = self.arms[i].position
      ox = hx + ITEM_OFFSET * (-1 if i == 0 else 1)
      proto.draw_at(surf, cam, (ox, hy), 0.0, 255, 1.0)
    draw_player_body(surf, cam, self, is_local=False)
    surf.set_alpha(self.GHOST_ALPHA)
    screen.blit(surf, (0, 0))

    # <STRANGE>#958 nickname above head
    if self.name:
      if self._font is None:
        self._font = pygame.font.SysFont(None, 26)
      tx, ty = cam.to_screen(self.body.position[0], self.body.position[1])
      label = self._font.render(self.name, True, (255, 255, 255))
      label.set_alpha(self.NAME_ALPHA)
      screen.blit(label, label.get_rect(center=(int(tx), int(ty - 60 * cam.scale))))
