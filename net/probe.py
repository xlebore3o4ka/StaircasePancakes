import argparse
import asyncio
import json
import websockets


async def run(url, name):
  async with websockets.connect(url) as ws:
    await ws.send(json.dumps({"t": "hello", "name": name}))
    print(f"[{name}] connected to {url}")

    async def sender():
      i = 0
      while True:
        await asyncio.sleep(0.5)
        i += 1
        await ws.send(json.dumps({
          "t": "state",
          "pos": [i, i * 2],
          "arms": [[0, 0], [0, 0]],
          "arm_dirs": [[0, 0], [0, 0]],
          "held": [None, None],
          "grabbed": [False, False],
          "stamina": [100.0, 100.0],
          "angle": 0.0,
        }))

    async def receiver():
      async for raw in ws:
        msg = json.loads(raw)
        print(f"[{name}] <- {msg}")

    await asyncio.gather(sender(), receiver())


def main():
  ap = argparse.ArgumentParser()
  ap.add_argument("--url", default="ws://127.0.0.1:8765")
  ap.add_argument("--name", required=True)
  args = ap.parse_args()
  try:
    asyncio.run(run(args.url, args.name))
  except KeyboardInterrupt:
    print(f"[{args.name}] bye")


if __name__ == "__main__":
    main()
