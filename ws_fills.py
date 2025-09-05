import json, time, threading
import websockets, asyncio

class FillsWS:
    def __init__(self, url, headers=None, out_path="ws_fills.json"):
        self.url = url
        self.headers = headers or {}
        self.out_path = out_path
        self._stop = threading.Event()
        self._thread = None

    async def _run(self):
        while not self._stop.is_set():
            try:
                async with websockets.connect(self.url, extra_headers=self.headers, ping_interval=20) as ws:
                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                        except Exception:
                            continue
                        fills = []
                        if isinstance(data, dict) and "fills" in data:
                            fills = data["fills"]
                        elif isinstance(data, dict):
                            fills = [data]
                        if fills:
                            payload = {"ts": time.time(), "fills": fills}
                            with open(self.out_path,"w") as f:
                                json.dump(payload, f, indent=2)
            except Exception:
                await asyncio.sleep(1.0)

    def start(self):
        if self._thread and self._thread.is_alive(): return
        def _bg():
            asyncio.run(self._run())
        self._thread = threading.Thread(target=_bg, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
