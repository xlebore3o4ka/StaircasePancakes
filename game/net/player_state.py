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
  angle: float = 0.0
  jumped: bool = False
