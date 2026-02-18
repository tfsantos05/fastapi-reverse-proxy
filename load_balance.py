from health_check import HealthChecker

class LoadBalancer:
    """
    Give it a list of URLs and it will act as round-robin
    Give it a HealthCheck object and it will act as "fastest to respond"
    """
    
    def __init__(self, servers: list| HealthChecker):
        self.servers = servers
        self.__index = 0
        self.__healthMode: bool = isinstance(servers, HealthChecker)
    
    def peek(self) -> str | None:
        if self.__healthMode:
            return self.servers.get_fastest()
        else:
            return self.servers[self.__index]
    
    def get(self) -> str | None:
        if self.__healthMode: return self.servers.get_fastest()
        else:
            try:
                return self.servers[self.__index]
            finally:
                self.__index = (self.__index + 1) % len(self.servers)
        
    def get_all(self) -> list:
        if self.__healthMode: return self.servers.targets # HealthChecker.servers 
        else: return self.servers

    def set_index(self, index: int) -> None:
        if self.__healthMode:
            raise RuntimeError("set_index() is not supported in health mode")
        if index < 0 or index >= len(self.servers):
            raise IndexError("Index out of range")
        self.__index = index

   