import pygame
from .core.window import Window
from .core.physics import make_space
from .entities.player import Player, BODY_R
from .core.camera import Camera
from .level import Level
from .entities.floor import FloorFill
from .core.sound import SoundManager
from .entities.hud_info import HudInfo
from .debug_info import DebugInfo
from .net.remote_player import RemotePlayer
from .net.client import NetClient
from .net.player_state import to_wire, from_wire
from .net.ghost_item import GhostItems
from shared.const import NET_TIMEOUT_SEC

LOGICAL_W = 1920
LOGICAL_H = 1080
NET_TICK_HZ = 20


try:
    from .core import light_c
    light_c.install()
    print("light_c: C renderer enabled")
except Exception as e:
    print(f"light_c: not installed ({e}); using Python")

def _visible_obj(d, cam, screen_size):
  # <STRANGE>#5010 viewport cull: skip drawables whose bbox is entirely off-screen
  body = getattr(d, "body", None)
  vw, vh = screen_size
  if body is not None:
    px, py = body.position.x, body.position.y
    w = getattr(d, "w", 0) or 0
    h = getattr(d, "h", 0) or 0
    r = getattr(d, "r", None)
    if r is not None:
      w = h = r * 2
    pts = getattr(d, "points", None)
    if pts:
      xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
      if len(xs) > 1 and len(ys) > 1:
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
    rr = max(w, h) * 0.5 * cam.scale + 96
    sx, sy = cam.to_screen(px, py)
    return -rr <= sx <= vw + rr and -rr <= sy <= vh + rr
  x = getattr(d, "x", None)
  y = getattr(d, "y", None)
  if x is None or y is None:
    return True
  pts = getattr(d, "points", None)
  if pts:
    xs = [x + q[0] for q in pts]
    ys = [y + q[1] for q in pts]
    l, r_, b, t = min(xs), max(xs), min(ys), max(ys)
  else:
    w = getattr(d, "w", 0)
    h = getattr(d, "h", 0)
    l, r_, b, t = x - w / 2, x + w / 2, y - h / 2, y + h / 2
  sx0, sy0 = cam.to_screen(l, t)
  sx1, sy1 = cam.to_screen(r_, b)
  lo_x, hi_x = (sx0, sx1) if sx0 < sx1 else (sx1, sx0)
  lo_y, hi_y = (sy0, sy1) if sy0 < sy1 else (sy1, sy0)
  return hi_x >= 0 and lo_x <= vw and hi_y >= 0 and lo_y <= vh


class Game:
  def __init__(self, cheats=False, map_path="levels/test.json", debugview=False,
               debuginfo=False, name=None, server=None):
    self.cheats = cheats
    self.map_path = map_path
    self.debugview = debugview
    self.debuginfo = debuginfo
    self.name = name
    self.server_url = server

  def run(self):
    with Window() as w:
      space = make_space()
      sound = SoundManager()
      sound.report()
      # <STRANGE>#158 spawn at world origin on the floor; cam starts synced so it doesn't fly in
      player = Player(space, (0, BODY_R), cheats=self.cheats, sound=sound)
      if self.name:
        player.state.name = self.name
      spawn_y = BODY_R
      # <STRANGE>#189 camera viewport is always LOGICAL_W x LOGICAL_H; scale only affects rendering, not world size
      cam = Camera(0, BODY_R, LOGICAL_W, LOGICAL_H, w.scale)
      # <STRANGE>#1144 level is created before the net client so we can hash its content
      # <STRANGE>#1205 with --server the map comes from the server, local --map is ignored
      net = None
      script_seed = None
      map_path = self.map_path
      if self.server_url:
        net = NetClient(self.server_url, self.name or "anon")
        net.connect()
        t0 = pygame.time.get_ticks()
        while not net.welcome and net.fatal is None:
          if pygame.time.get_ticks() - t0 > 5000:
            raise RuntimeError("server did not answer hello (timeout)")
          pygame.time.wait(20)
        if net.fatal:
          raise RuntimeError(net.fatal)
        if net.map_bytes is None:
          raise RuntimeError("server did not ship a map")
        script_seed = net.script_seed
        # <STRANGE>#1205 persist to a temp file so Level can tar-extract / read normally
        import tempfile
        suffix = ".tar" if (net.map_name or "").endswith(".tar") else ".json"
        tf = tempfile.NamedTemporaryFile(prefix="map_", suffix=suffix, delete=False)
        tf.write(net.map_bytes)
        tf.close()
        map_path = tf.name

      level = Level(space, map_path, sound=sound, cheats=self.cheats,
                    script_seed=script_seed)
      level.cam = cam
      level.cam = cam
      player.level = level
      player._all_buttons = level.buttons
      # <STRANGE>#942 remote ghosts: name -> RemotePlayer
      remotes = {}
      # <STRANGE>#967 ghost items owned by other players
      ghost_items = GhostItems()

      if net is not None:
        # <STRANGE>#983 broadcast local sfx with emitter position; receiver culls offscreen
        # <STRANGE>#989 field is "snd" because the server overwrites "name" with the sender name
        sound.on_play = lambda n, v: net.send({
          "t": "sound", "snd": n, "vol": v,
          "x": player.body.position.x, "y": player.body.position.y,
        })
      net_accum = 0.0
      # <STRANGE>#1520 rolling FPS over 0.5s windows
      fps_accum = 0.0
      fps_frames = 0
      fps_value = 0.0

      floor_fill = FloorFill()
      hud_info = HudInfo()
      debug_info = DebugInfo()
      clock = pygame.time.Clock()
      running = True
      while running:
        # <STRANGE>#1003 network rejection (version/map) aborts the whole run
        if net is not None and net.fatal:
          print(f"net: {net.fatal}")
          running = False
          break
        # <STRANGE>#341 dt clamped to 1/30 so a lag spike doesn't explode pymunk with one huge step
        dt = min(clock.tick() / 1000.0, 1 / 30)
        if dt <= 0:
          dt = 1 / 60
        fps_value = clock.get_fps()
        # <STRANGE>#377 sub-step long frames: 1/30 broken into two 1/60 steps reduces penetration and phantom bounces
        substeps = 2 if dt > 1/45 else 1
        events = pygame.event.get()
        for e in events:
          if e.type == pygame.QUIT:
            running = False
          elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if getattr(level, "note_ui", None):
              level.close_note_ui()
            else:
              running = False
          player.handle_event(e)
        old_hp = player.hp
        player.update(cam, level.grabbables(), level.items, dt, level.backgrounds)
        if player.hp < old_hp and getattr(level, "note_ui", None):
          level.close_note_ui()
        level.update_lanterns(player, cam, dt)
        level.update_buttons(dt, player)
        level.update_triggers(dt, (player.body.position.x, player.body.position.y), player.events)
        player.events.clear()
        level.update_notes(dt, events)
        level.update_movers(dt)
        level.update_light_movers(dt)
        level.update_overlays(dt)
        for rp in remotes.values():
          rp.update(dt)
        # <STRANGE>#963 drop remotes that stopped sending; covers server death and ghost of a disconnected peer
        stale = [n for n, rp in remotes.items() if rp.last_seen >= NET_TIMEOUT_SEC]
        for n in stale:
          del remotes[n]

        # <STRANGE>#956 throttle state sends to NET_TICK_HZ; poll drains queue each frame
        if net is not None:
          net_accum += dt
          if net_accum >= 1.0 / NET_TICK_HZ:
            net_accum = 0.0
            net.send(to_wire(player.state))
          # <STRANGE>#973 drain one-shot world events (peg placement, rebar stick)
          for ev in level.net_events:
            net.send(ev)
          level.net_events.clear()
          # <STRANGE>#991 drain player events (item removals)
          for ev in player.net_events:
            net.send(ev)
          player.net_events.clear()
          for ev in net.poll():
            t = ev.get("t")
            if t == "joined":
              n = ev.get("name")
              if n and n != player.state.name:
                remotes[n] = RemotePlayer(n)
            elif t == "left":
              remotes.pop(ev.get("name"), None)
            elif t == "state":
              n = ev.get("name")
              if not n or n == player.state.name:
                continue
              rp = remotes.get(n)
              if rp is None:
                rp = RemotePlayer(n)
                remotes[n] = rp
              st = from_wire(ev)
              rp.apply_state(st)
              ghost_items.apply(st.items)
            elif t == "place_peg":
              # <STRANGE>#973 remote peg; _from_net stops us from re-broadcasting
              level.spawn_item((float(ev["x"]), float(ev["y"])),
                               {"type": "peg_static", "_from_net": True})
            elif t == "item_gone":
              # <STRANGE>#991 peer picked up or consumed an item; drop ghost immediately
              ghost_items.items.pop(ev.get("id"), None)
            elif t == "sound":
              # <STRANGE>#983 remote sfx at half volume; play only when emitter is on our screen
              n = ev.get("snd")
              v = float(ev.get("vol", 1.0))
              if n:
                ex = float(ev.get("x", 0))
                ey = float(ev.get("y", 0))
                sx, sy = cam.to_screen(ex, ey)
                sw, sh = w.screen.get_size()
                # <STRANGE>#987 100px margin so near-edge sounds aren't cut abruptly
                m = 100
                if -m <= sx <= sw + m and -m <= sy <= sh + m:
                  sound.play(n, volume=v * 0.5, _from_net=True)
            elif t == "place_rebar":
              # <STRANGE>#974 remote stuck rebar: spawn a rebar, angle it, force it into stuck state
              spec = {"x": float(ev["x"]), "y": float(ev["y"]), "type": "rebar"}
              it = level.spawn_item((float(ev["x"]), float(ev["y"])), spec)
              it.body.angle = float(ev.get("angle", 0.0))
              it.stick(cam=None)
              # <STRANGE>#975 kill the lingering ghost of this item if it was in flight on our side
              gid = ev.get("id")
              if gid:
                ghost_items.items.pop(gid, None)

        # <STRANGE>#300 drain spawn queue after player update so items appear next frame with no mid-frame physics surprises
        if player.spawn_queue:
          for pos, spec, vel in player.spawn_queue:
            result = level.spawn_item(pos, spec, vel)
            # <STRANGE>#964 tag freshly spawned item so it can be ghosted by other clients
            if result is not None and hasattr(result, "net_id"):
              player.tag_item(result)
            # <STRANGE>#795 if the spawned entity is grabbable, tell Player to latch the source hand
            if result is not None and not hasattr(result, "net_id"):
              player.pending_grab = (result, pos)
          player.spawn_queue.clear()
        # <STRANGE>#1179 capture pre-step velocity once, before all substeps; per-substep capture loses the impact speed
        player.record_pre_step()
        for _ in range(substeps):
          space.step(dt / substeps)
          # <STRANGE>#525 rebar sticking is checked after physics so arbiter list is fresh
          level.post_step(player, cam)
          # <STRANGE>#657 player bias clamp runs after every substep
          player.post_step(dt)
        cam.follow(player.body.position, dt)
        cam.update(dt)
        cam.update(dt)
        if w.world is not None:
          from .core.gpu_render import WorldCtx
          w.world.begin()
          target = WorldCtx(w.world, cam)
        else:
          w.screen.fill((89, 95, 102))
          target = w.screen
        # <NOTE>#445 single sorted pass: backgrounds -> floor -> platforms/pegs -> items -> player
        drawables = level.drawables() + [floor_fill, player]
        drawables.sort(key=lambda o: o.layer)
        for d in drawables:
          if not _visible_obj(d, cam, w.size):
            continue
          d.draw(target, cam)
        ghost_items.update(dt)
        ghost_items.draw(target, cam)
        for rp in remotes.values():
          rp.draw(target, cam)
        if w.world is not None:
          w.world.flush()
        if self.debugview:
          level.draw_debug(target, cam, player.body.position)
        # <STRANGE>#1330 lighting: scene * light, then HUD composited on top
        if level.lighting_config is not None:
          _occ = level.occluders()
          w.lighting.setup(level.lighting_config, level.lights, cam, _occ)
        else:
          w.lighting.gain = 1.0
          w.lighting.begin((255, 255, 255))
        # <STRANGE>#1331 HUD in a separate renderer so it stays unlit
        w.hud.begin()
        player.draw_hud(w.hud, cam)
        hud_info.update(dt)
        # <STRANGE>#620 height is distance from spawn, not absolute y
        hud_info.draw(w.hud, player.body.position.y - spawn_y)
        level.draw_overlays(w.hud, cam)
        level.draw_notes(w.hud, cam)
        # <STRANGE>#1521 FPS in bottom-left corner
        _sh = w.hud.get_size()[1]
        w.hud.text(f"FPS {fps_value:.0f}", 12, _sh - 36, 24,
                   (200, 200, 200), 180, anchor="topleft")
        if self.debuginfo:
          debug_info.update(dt, player)
          debug_info.draw(w.hud)
        w.flip()

      level.unload()
      if net is not None:
        net.close()
