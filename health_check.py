import asyncio
import httpx
import logging
import time
from typing import Optional, Union, Dict
from urllib.parse import urlparse

logger = logging.getLogger("fastapi_reverse_proxy")


class HealthChecker:
    def __init__(self, targets: list[str] | list[dict], interval: int = 10, timeout: int = 10, autostart: bool = True, httpx_client: httpx.AsyncClient | None = None):
        if not targets:
            raise ValueError("Targets list cannot be empty")
        if interval < 1:
            raise ValueError("Interval must be at least 1")
        if timeout < 1:
            raise ValueError("Timeout must be at least 1")

        self.interval = interval
        self.timeout = timeout
        
        # Internal storage: {host_origin: pingpath}
        self._targets_map: Dict[str, str] = {}
        
        # Determine and enforce strict type (no mixing)
        first_type = type(targets[0])
        if first_type not in (str, dict):
             raise TypeError("Targets must be a list of strings or a list of dictionaries")
        
        self._is_personalized = (first_type is dict)
        self._global_ping_path = "/"

        for idx, t in enumerate(targets):
            if not isinstance(t, first_type):
                raise TypeError(f"Mixed types in targets at index {idx}. Total list must be same type.")
            
            if self._is_personalized:
                if "host" not in t:
                    raise KeyError(f"Target dictionary at index {idx} missing required 'host' key")
                u = urlparse(t["host"])
                host = f"{u.scheme}://{u.netloc}"
                path = t.get("pingpath", "/")
                self._targets_map[host] = path
            else:
                u = urlparse(t)
                host = f"{u.scheme}://{u.netloc}"
                self._targets_map[host] = self._global_ping_path

        self.targets = list(self._targets_map.keys())
        # Stores latency in ms or False if down
        self.status: Dict[str, Union[float, bool]] = {host: 0.0 for host in self.targets}

        # Autostart: schedule the loop if a running event loop exists
        self._task: Optional[asyncio.Task] = None
        if autostart:
            try:
                self._task = asyncio.create_task(self._loop())
            except RuntimeError:
                pass  # No running event loop yet — call start() manually

        # Track if WE created the client so we know if we should close it
        self._owns_client = httpx_client is None
        self._client = httpx_client or httpx.AsyncClient(timeout=self.timeout)

    @property
    def ping_path(self) -> str:
        if self._is_personalized:
            raise RuntimeError("Global ping_path is not supported when using personalized hosts")
        return self._global_ping_path

    @ping_path.setter
    def ping_path(self, value: str):
        if self._is_personalized:
            raise RuntimeError("Global ping_path is not supported when using personalized hosts")
        self._global_ping_path = value
        # Update all targets in map since we are in global mode
        for host in self._targets_map:
            self._targets_map[host] = value

    def __del__(self):
        """
        Class-built function for deletion
        
        WARNING: This one is last resort! Consider using .destroy() before exiting instead !
        Complete GC of this class is NOT guaranteed
        """
        if self._client is not None: # the client was NOT destroyed
            try:
                logger.warning("You did not call .destroy() . Attempting cleanup via __del__ ... \n(Don't forget to add .destroy() at the end of your program)")
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    loop.create_task(self.destroy())
                # else: loop is gone, nothing we can do
            except RuntimeError:
                pass  # No event loop at all

    async def _check_target(self, host: str):
        path = self._targets_map[host] if self._is_personalized else self._global_ping_path
        # Construct absolute probe URL
        url = f"{host.rstrip('/')}/{path.lstrip('/')}"
        
        start_time = time.perf_counter()
        try:
            # We use a HEAD request because it's faster and uses less bandwidth
            response = await self._client.head(url)
            if response.status_code < 400:
                latency = (time.perf_counter() - start_time) * 1000
                self.status[host] = latency
            else:
                self.status[host] = False
        except Exception:
            self.status[host] = False
            logger.warning(f"Target {host} is DOWN")

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
        tasks = [self._check_target(host) for host in self.targets]
        await asyncio.gather(*tasks)

    def get_healthy_targets(self):
        """Returns only the hosts that are currently UP."""
        return [h for h in self.targets if self.status.get(h) is not False]

    def get_response_times(self) -> Dict[str, float]:
        """Returns a dict of {url: ms} for all healthy targets only."""
        return {t: float(v) for t, v in self.status.items() if v is not False}

    def get_fastest(self) -> str | None:
        """Returns the fastest healthy target, or None if all are down."""
        r = self.get_response_times()
        return min(r, key=lambda t: r[t]) if r else None


    def is_healthy(self, target: str) -> bool:
        """Returns True if the target is currently UP."""
        u = urlparse(target)
        host = f"{u.scheme}://{u.netloc}"
        status = self.status.get(host)
        return status is not False and status is not None