import argparse
import asyncio
import json
import websockets
from shared.version import read as _read_version, parse as _parse_version


_clients = {}  # name -> websocket
_map_path = None


async def handler(ws):
  name = None
  try:
    async for raw in ws:
      try:
        msg = json.loads(raw)
      except json.JSONDecodeError:
        continue
      t = msg.get("t")
      if t == "hello":
        # <STRANGE>#1000 versions must share major.minor; patch may differ
        req_ver = msg.get("version")
        cur_ver = _read_version()
        if req_ver is None or _parse_version(req_ver)[:2] != _parse_version(cur_ver)[:2]:
          print(f"! reject {msg.get('name')}: version {req_ver!r} vs {cur_ver!r}")
          await ws.close(code=4001, reason="version mismatch")
          return
        req_map = msg.get("map")
        # <STRANGE>#995 reject mismatched map before registering; close the socket so client sees the failure
        if _map_path is not None and req_map != _map_path:
          print(f"! reject {msg.get('name')}: map {req_map!r} != {_map_path!r}")
          await ws.close(code=4000, reason="map mismatch")
          return
        name = msg.get("name") or f"anon-{id(ws)}"
        _clients[name] = ws
        print(f"+ {name} connected, total={len(_clients)}")
        # <STRANGE>#1007 ack to the joiner so it knows it passed map+version checks
        await ws.send(json.dumps({"t": "welcome"}))
        # <STRANGE>#946 announce to everyone else so they can spawn a ghost immediately
        await _broadcast({"t": "joined", "name": name}, except_ws=ws)
      elif name is not None:
        # <STRANGE>#980 relay any non-hello message as-is; the server shouldn't need to know about every event type
        out = dict(msg)
        out["name"] = name
        await _broadcast(out, except_ws=ws)
  except websockets.ConnectionClosed:
    pass
  finally:
    if name is not None and _clients.get(name) is ws:
      del _clients[name]
      print(f"- {name} disconnected, total={len(_clients)}")
      await _broadcast({"t": "left", "name": name}, except_ws=ws)


async def _broadcast(msg, except_ws=None):
  raw = json.dumps(msg)
  targets = [w for w in _clients.values() if w is not except_ws]
  if not targets:
    return
  await asyncio.gather(*(w.send(raw) for w in targets), return_exceptions=True)


async def run(port):
  # <STRANGE>#947 ping_interval None: we do our own liveness via client-side timeout, don't want ws to kill idle conns
  async with websockets.serve(handler, "0.0.0.0", port, ping_interval=None):
    print(f"server on 0.0.0.0:{port}")
    await asyncio.Future()


def main():
  global _map_path
  ap = argparse.ArgumentParser()
  ap.add_argument("--port", type=int, default=8765)
  ap.add_argument("--map", default="levels/test.json",
                  help="level json every client must be using")
  args = ap.parse_args()
  _map_path = args.map
  print(f"map: {_map_path}")
  try:
    asyncio.run(run(args.port))
  except KeyboardInterrupt:
    print("bye")


if __name__ == "__main__":
  main()
