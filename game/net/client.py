import json
import queue
import threading
import asyncio
import websockets
from shared.version import read as _read_version


class NetClient:
  # <STRANGE>#950 websocket runs in a background thread with its own asyncio loop; main thread only touches queues
  def __init__(self, url, name, map_path=None, map_hash=None):
    self.url = url
    self.name = name
    self.map_path = map_path
    self.map_hash = map_hash
    self._in = queue.Queue()
    self._out = queue.Queue()
    self._stop = threading.Event()
    self._thread = None
    # <STRANGE>#1001 set on reject; game loop checks this and exits
    self.fatal = None
    # <STRANGE>#1007 True once server acked our hello (map/version passed)
    self.welcome = False
    # <STRANGE>#1007 True once the websocket handshake completed
    self.ready = False

  def connect(self):
    self._thread = threading.Thread(target=self._run, daemon=True)
    self._thread.start()

  def send(self, msg):
    # <STRANGE>#951 non-blocking; if the thread is dead, drop silently (main loop will fail on next recv anyway)
    self._out.put(msg)

  def poll(self):
    out = []
    while True:
      try:
        out.append(self._in.get_nowait())
      except queue.Empty:
        return out

  def close(self):
    self._stop.set()
    if self._thread is not None:
      self._thread.join(timeout=1.0)

  def _run(self):
    try:
      asyncio.run(self._main())
    except Exception as e:
      print(f"net: fatal {e}")
      self._stop.set()

  async def _main(self):
    try:
      async with websockets.connect(self.url) as ws:
        print(f"net: connected to {self.url} as {self.name}")
        self.ready = True
        await ws.send(json.dumps({"t": "hello", "name": self.name,
                                     "map": self.map_path,
                                     "map_hash": self.map_hash,
                                     "version": _read_version()}))
        await asyncio.gather(self._sender(ws), self._receiver(ws))
    except Exception as e:
      # <STRANGE>#1007 hard fail on connect errors; game loop raises on fatal
      self.fatal = f"connect failed: {e}"
      print(f"net: {self.fatal}")
      self._stop.set()

  async def _sender(self, ws):
    while not self._stop.is_set():
      try:
        msg = self._out.get_nowait()
      except queue.Empty:
        await asyncio.sleep(0.005)
        continue
      try:
        await ws.send(json.dumps(msg))
      except Exception as e:
        print(f"net: send failed {e}")
        return

  async def _receiver(self, ws):
    try:
      async for raw in ws:
        try:
          msg = json.loads(raw)
        except json.JSONDecodeError:
          continue
        if msg.get("t") == "welcome":
          self.welcome = True
          continue
        self._in.put(msg)
    except websockets.ConnectionClosed as e:
      # <STRANGE>#1002 4000/4001 are our intentional reject codes; anything else is a plain disconnect
      if e.code in (4000, 4001):
        self.fatal = e.reason or f"rejected ({e.code})"
        print(f"net: rejected: {self.fatal}")
      else:
        print("net: connection closed")
      self._stop.set()
