from fastapi import FastAPI, Request, WebSocket
from contextlib import asynccontextmanager
from fastapi_reverse_proxy import Proxy, HealthChecker, LoadBalancer

"""
The Production-Ready Setup: Health Monitoring + Load Balancing.

✅ This is the most robust way to deploy the proxy.
✅ Automatically detects dead servers and removes them from the pool.
✅ Routes traffic to the fastest responding server (Latency-Based).

Key Components:
- Proxy: Manages the HTTPX pool.
- HealthChecker: Background loop that pings backends.
- LoadBalancer: Makes the routing decision based on health/speed.
"""

# 1. Configure the health checker with backends
# It will proactively monitor these URLs.
checker = HealthChecker([
    "http://127.0.0.1:8081", 
    "http://127.0.0.1:8082"
])

# 2. The LoadBalancer uses the HealthChecker to route to the FASTEST healthy server
lb = LoadBalancer(checker)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Use the Proxy context manager to manage the HTTPX connection pool
    async with Proxy(app):
        # Start the background health monitoring loop
        async with checker:
            yield

app = FastAPI(lifespan=lifespan)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(request: Request, path: str):
    # Routes to the healthiest/fastest backend
    return await lb.proxy_pass(request, path=f"/{path}")

@app.websocket("/{path:path}")
async def ws_tunnel(websocket: WebSocket, path: str):
    # Also applies load balancing to WebSockets
    await lb.proxy_pass_websocket(websocket, path=f"/{path}")

if __name__ == "__main__":
    import uvicorn
    print("Starting Production-Ready Proxy with Health Monitoring on http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
