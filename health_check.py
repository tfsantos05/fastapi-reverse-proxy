import asyncio
import httpx
import logging
import time
from typing import Optional, Union, Dict

logger = logging.getLogger("fastapi_reverse_proxy")

class HealthChecker:
    def __init__(self, targets: list, interval: int = 10, timeout: int = 10, autostart:bool = True, httpx_client: httpx.AsyncClient | None = None):
        if not targets: raise ValueError("Targets list cannot be empty")
        if interval < 1: raise ValueError("Interval must be at least 1")
        if timeout < 1: raise ValueError("Timeout must be at least 1")

        self.targets = targets
        self.interval = interval
        self.timeout = timeout
        # Stores latency in ms or False if down
        self.status: Dict[str, Union[float, bool]] = {target: 0.0 for target in targets}

        # Autostart: schedule the loop if a running event loop exists
        self._task = asyncio.create_task(self._loop()) if autostart and asyncio.get_event_loop().is_running() else None

        # Track if WE created the client so we know if we should close it
        self._owns_client = httpx_client is None
        self._client = httpx_client or httpx.AsyncClient(timeout=self.timeout)

    def __del__(self):
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self.destroy())
            # else: loop is gone, nothing we can do
        except RuntimeError:
            pass  # No event loop at all

    async def _check_target(self,  target):
        start_time = time.perf_counter()
        try:
            # We use a HEAD request because it's faster and uses less bandwidth
            response = await self._client.head(target)
            if response.status_code < 400:
                latency = (time.perf_counter() - start_time) * 1000
                self.status[target] = latency
            else:
                self.status[target] = False
        except Exception:
            self.status[target] = False
            logger.warning(f"Target {target} is DOWN")

    async def _loop(self):
        """The background loop."""
        while True:
            await self.check_all()
            await asyncio.sleep(self.interval)

    async def start(self):
        """Start the background health check loop. Can be called again after stop()."""
        if not self._task:
            self._task = asyncio.create_task(self._loop())

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.destroy()

    async def stop(self):
        """Stop the background loop. The client stays alive. Call start() to resume."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError: pass
            self._task = None

    async def destroy(self):
        """Stop the loop AND close the httpx client. Cannot be restarted after this."""
        await self.stop()
        if self._owns_client and self._client:
            await self._client.aclose()
            self._client = None

    async def check_all(self):
        """Pings all targets and updates their status."""
        tasks = [self._check_target(target) for target in self.targets]
        await asyncio.gather(*tasks)

    def get_healthy_targets(self):
        """Returns only the targets that are currently UP."""
        return [t for t in self.targets if self.status.get(t) is not False]

    def get_response_times(self) -> Dict[str, float]:
        """Returns a dict of {url: ms} for all healthy targets only."""
        return {t: float(v) for t, v in self.status.items() if v is not False}

    def get_fastest(self) -> str | None:
        """Returns the fastest healthy target, or None if all are down."""
        r = self.get_response_times()
        return min(r, key=lambda t: r[t]) if r else None


    def is_healthy(self, target: str) -> bool:
        """Returns True if the target is currently UP."""
        return self.status.get(target) is not False