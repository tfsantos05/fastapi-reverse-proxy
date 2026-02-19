from health_check import HealthChecker
from fastapi import Request
from urllib.parse import urlparse

class LoadBalancer:
    """
    Give it a list of URLs and it will act as round-robin
    Give it a HealthCheck object and it will act as "fastest to respond"
    """
    
    def __init__(self, servers: list | HealthChecker):
        self.servers = servers
        self.__index = 0
        self.__healthMode: bool = isinstance(servers, HealthChecker)
    
    def peek(self) -> str | None:
        if self.__healthMode:
            return self.servers.get_fastest()
        else:
            if not self.servers: return None
            return self.servers[self.__index]
    
    def get(self) -> str | None:
        if self.__healthMode: return self.servers.get_fastest()
        else:
            if not self.servers: return None
            try:
                return self.servers[self.__index]
            finally:
                self.__index = (self.__index + 1) % len(self.servers)
        
    def get_all(self) -> list:
        if self.__healthMode: return self.servers.targets
        else: return self.servers

    def set_index(self, index: int) -> None:
        if self.__healthMode:
            raise RuntimeError("set_index() is not supported in health mode")
        if index < 0 or (self.servers and index >= len(self.servers)):
            raise IndexError("Index out of range")
        self.__index = index

    async def proxy_pass(self, req: Request, timeout: float = 60.0):
        """
        Smart proxying: takes a resolved target (which might have a health-check path),
        strips it to the origin (scheme://host), and forwards the request.
        """
        from proxy_pass import proxy_pass as _proxy_pass  # Late import to avoid circular dependency
        
        target = self.get()
        if not target:
            from fastapi import Response
            return Response("Service Unavailable: No healthy backends", status_code=503)
            
        # Strip to origin (e.g. http://server/ping -> http://server)
        u = urlparse(target)
        origin = f"{u.scheme}://{u.netloc}"
        
        return await _proxy_pass(req, origin, timeout=timeout)

    async def proxy_pass_websocket(self, websocket, subprotocols: list[str] | None = None):
        """
        Smart WebSocket proxying: takes a resolved target,
        strips it to the origin, and forwards the connection.
        """
        from proxy_pass import proxy_pass_websocket as _proxy_pass_ws  # Late import
        
        target = self.get()
        if not target:
            await websocket.close(code=1011)
            return

        u = urlparse(target)
        origin = f"{u.scheme}://{u.netloc}"
        
        return await _proxy_pass_ws(websocket, origin, subprotocols=subprotocols)

   