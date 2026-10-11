import json
import queue
import threading
import asyncio
import websockets


class NetClient:
  # <STRANGE>#950 websocket runs in a background thread with its own asyncio loop; main thread only touches queues
  def __init__(self, url, name):
    self.url = url
    self.name = name
    self._in = queue.Queue()
    self._out = queue.Queue()
    self._stop = threading.Event()
    self._thread = None

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
        await ws.send(json.dumps({"t": "hello", "name": self.name}))
        await asyncio.gather(self._sender(ws), self._receiver(ws))
    except Exception as e:
      print(f"net: connect failed: {e}")
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
          self._in.put(json.loads(raw))
        except json.JSONDecodeError:
          continue
    except websockets.ConnectionClosed:
      print("net: connection closed")
      self._stop.set()
