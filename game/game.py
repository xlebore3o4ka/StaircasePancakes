import pygame
from .core.window import Window
from .core.physics import make_space
from .entities.player import Player, BODY_R
from .core.camera import Camera
from .level import Level
from .entities.floor import FloorFill
from .core.sound import SoundManager
from .entities.hud_info import HudInfo
from .net.remote_player import RemotePlayer
from .net.client import NetClient
from .net.player_state import to_wire, from_wire
from .net.ghost_item import GhostItems
from shared.const import NET_TIMEOUT_SEC

LOGICAL_W = 1920
LOGICAL_H = 1080
NET_TICK_HZ = 20


class Game:
  def __init__(self, cheats=False, map_path="levels/test.json", debugview=False,
               name=None, server=None):
    self.cheats = cheats
    self.map_path = map_path
    self.debugview = debugview
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
      level = Level(space, self.map_path, sound=sound, cheats=self.cheats)
      player.level = level
      # <STRANGE>#942 remote ghosts: name -> RemotePlayer
      remotes = {}
      # <STRANGE>#967 ghost items owned by other players
      ghost_items = GhostItems()

      # <STRANGE>#955 net is optional; without --server the rest of the loop is untouched
      net = None
      if self.server_url:
        net = NetClient(self.server_url, self.name or "anon", map_path=self.map_path)
        net.connect()
        # <STRANGE>#1007 block until server welcomes us or fails; better to crash early than drop into single
        t0 = pygame.time.get_ticks()
        while not net.welcome and net.fatal is None:
          if pygame.time.get_ticks() - t0 > 3000:
            raise RuntimeError("server did not answer hello (timeout)")
          pygame.time.wait(20)
        if net.fatal:
          raise RuntimeError(net.fatal)
        # <STRANGE>#983 broadcast local sfx with emitter position; receiver culls offscreen
        # <STRANGE>#989 field is "snd" because the server overwrites "name" with the sender name
        sound.on_play = lambda n, v: net.send({
          "t": "sound", "snd": n, "vol": v,
          "x": player.body.position.x, "y": player.body.position.y,
        })
      net_accum = 0.0

      floor_fill = FloorFill()
      hud_info = HudInfo()
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
        # <STRANGE>#377 sub-step long frames: 1/30 broken into two 1/60 steps reduces penetration and phantom bounces
        substeps = 2 if dt > 1/45 else 1
        for e in pygame.event.get():
          if e.type == pygame.QUIT:
            running = False
          elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running = False
          player.handle_event(e)
        player.update(cam, level.grabbables(), level.items, dt, level.backgrounds)
        level.update_triggers(dt, (player.body.position.x, player.body.position.y))
        level.update_movers(dt)
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
        for _ in range(substeps):
          player.record_pre_step()
          space.step(dt / substeps)
          # <STRANGE>#525 rebar sticking is checked after physics so arbiter list is fresh
          level.post_step(player, cam)
          # <STRANGE>#657 player bias clamp runs after every substep
          player.post_step(dt)
        cam.follow(player.body.position, dt)
        w.screen.fill((89, 95, 102))
        # <NOTE>#445 single sorted pass: backgrounds -> floor -> platforms/pegs -> items -> player
        drawables = level.drawables() + [floor_fill, player]
        drawables.sort(key=lambda o: o.layer)
        for d in drawables:
          d.draw(w.screen, cam)
        ghost_items.update(dt)
        ghost_items.draw(w.screen, cam)
        for rp in remotes.values():
          rp.draw(w.screen, cam)
        if self.debugview:
          level.draw_debug(w.screen, cam, player.body.position)
        player.draw_hud(w.screen, cam)
        hud_info.update(dt)
        # <STRANGE>#620 height is distance from spawn, not absolute y
        hud_info.draw(w.screen, player.body.position.y - spawn_y)
        w.flip()

      level.unload()
      if net is not None:
        net.close()
