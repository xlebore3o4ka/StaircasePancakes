import argparse
import asyncio
import json
import websockets


_clients = {}  # name -> websocket


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
        name = msg.get("name") or f"anon-{id(ws)}"
        _clients[name] = ws
        print(f"+ {name} connected, total={len(_clients)}")
        # <STRANGE>#946 announce to everyone else so they can spawn a ghost immediately
        await _broadcast({"t": "joined", "name": name}, except_ws=ws)
      elif t == "state":
        if name is None:
          continue
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
  ap = argparse.ArgumentParser()
  ap.add_argument("--port", type=int, default=8765)
  args = ap.parse_args()
  try:
    asyncio.run(run(args.port))
  except KeyboardInterrupt:
    print("bye")


if __name__ == "__main__":
  main()
