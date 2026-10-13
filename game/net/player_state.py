from dataclasses import dataclass, field


@dataclass
class PlayerState:
  # <STRANGE>#922 minimal snapshot of a player sent over the wire; no physics, no refs to live objects
  name: str = ""
  pos: tuple[float, float] = (0.0, 0.0)
  arms: list[tuple[float, float]] = field(
    default_factory=lambda: [(0.0, 0.0), (0.0, 0.0)])
  arm_dirs: list[tuple[float, float]] = field(
    default_factory=lambda: [(0.0, 0.0), (0.0, 0.0)])
  # <NOTE>#923 type names only; remote side decides how to render them
  held: list[str | None] = field(default_factory=lambda: [None, None])
  grabbed: list[bool] = field(default_factory=lambda: [False, False])
  stamina: list[float] = field(default_factory=lambda: [0.0, 0.0])
  hp: float = 100.0
  angle: float = 0.0
  jumped: bool = False
  # <STRANGE>#964 free items touched by this player; list of {id, type, x, y, angle}
  items: list[dict] = field(default_factory=list)


def to_wire(st):
  # <STRANGE>#954 compact wire format; floats kept as-is, client/server cast to num/str on parse
  return {
    "t": "state",
    "pos": [st.pos[0], st.pos[1]],
    "arms": [[st.arms[0][0], st.arms[0][1]], [st.arms[1][0], st.arms[1][1]]],
    "arm_dirs": [[st.arm_dirs[0][0], st.arm_dirs[0][1]],
                 [st.arm_dirs[1][0], st.arm_dirs[1][1]]],
    "held": [st.held[0], st.held[1]],
    "grabbed": [bool(st.grabbed[0]), bool(st.grabbed[1])],
    "stamina": [float(st.stamina[0]), float(st.stamina[1])],
    "hp": float(st.hp),
    "angle": float(st.angle),
    "items": st.items,
  }


def from_wire(msg):
  st = PlayerState()
  st.name = msg.get("name", "")
  p = msg.get("pos", [0, 0])
  st.pos = (float(p[0]), float(p[1]))
  a = msg.get("arms", [[0, 0], [0, 0]])
  st.arms = [(float(a[0][0]), float(a[0][1])), (float(a[1][0]), float(a[1][1]))]
  d = msg.get("arm_dirs", [[0, 0], [0, 0]])
  st.arm_dirs = [(float(d[0][0]), float(d[0][1])), (float(d[1][0]), float(d[1][1]))]
  h = msg.get("held", [None, None])
  st.held = [h[0], h[1]]
  g = msg.get("grabbed", [False, False])
  st.grabbed = [bool(g[0]), bool(g[1])]
  st_g = msg.get("stamina", [100.0, 100.0])
  st.stamina = [float(st_g[0]), float(st_g[1])]
  st.hp = float(msg.get("hp", 100.0))
  st.angle = float(msg.get("angle", 0.0))
  st.items = list(msg.get("items", []))
  return st
