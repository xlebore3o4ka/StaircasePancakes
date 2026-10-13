import argparse
import asyncio
import hashlib
import json
import os
import random
import tarfile
import websockets
from shared.version import read as _read_version, parse as _parse_version


_clients = {}  # name -> websocket
_map_path = None
_map_hash = None
_script_seed = None


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
        req_hash = msg.get("map_hash")
        # <STRANGE>#1144 compare content hashes, not paths; path may differ but bytes must match
        if _map_hash is not None and req_hash != _map_hash:
          print(f"! reject {msg.get('name')}: map hash {req_hash!r} != {_map_hash!r}")
          await ws.close(code=4000, reason="map mismatch")
          return
        name = msg.get("name") or f"anon-{id(ws)}"
        _clients[name] = ws
        print(f"+ {name} connected, total={len(_clients)}")
        # <STRANGE>#1007 ack to the joiner; also ship the deterministic script seed
        await ws.send(json.dumps({"t": "welcome", "script_seed": _script_seed}))
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


def _read_seed(path):
  # <STRANGE>#1148 server only needs the seed from the level; parse enough for json and tar
  try:
    if path.endswith(".tar"):
      with tarfile.open(path, "r") as tf:
        f = tf.extractfile("level.json")
        if f is None:
          return None
        data = json.loads(f.read())
    else:
      with open(path) as f:
        data = json.load(f)
  except Exception:
    return None
  return data.get("seed")


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
  global _map_path, _map_hash
  ap = argparse.ArgumentParser()
  ap.add_argument("--port", type=int, default=8765)
  ap.add_argument("--map", default="levels/test.json",
                  help="level file every client must match (content-hashed)")
  args = ap.parse_args()
  _map_path = args.map
  with open(_map_path, "rb") as f:
    _map_hash = hashlib.sha1(f.read()).hexdigest()
  seed = _read_seed(_map_path)
  if seed is None:
    seed = random.randint(0, 2**31)
  _script_seed = seed
  print(f"map: {_map_path} (sha1 {_map_hash[:8]}) script seed {_script_seed}")
  try:
    asyncio.run(run(args.port))
  except KeyboardInterrupt:
    print("bye")


if __name__ == "__main__":
  main()
