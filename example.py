import uvicorn
import asyncio
from fastapi import FastAPI, Request, WebSocket
from contextlib import asynccontextmanager

# Import your library components
# We import from the package root (__init__.py)
#from __init__ import (
#    proxy_pass, 
#   proxy_pass_websocket, 
#    HealthChecker, 
#    LoadBalancer,
#    create_httpx_client, 
#    close_httpx_client
#)
import fastapi_reverse_proxy as fproxy

# 1. Configuration
# List of backends to load balance. 
SIMPLE_BACKENDS = ["http://localhost:8081", "http://localhost:8082"]

# Personalized backends with custom ping paths and request limits
# This is a 'Manual' configuration for the HealthChecker
PERSONALIZED_BACKENDS = [
    {"host": "http://localhost:8083", "pingpath": "/", "maxrequests": 50},
    {"host": "http://localhost:8084", "pingpath": "/", "maxrequests": 100},
]

# 2. Components Setup

# --- Health-Aware (Smart) Balancer ---
# HealthChecker is the 'Active' component. It needs a lifecycle (async with).
# It will ping backends every 10 seconds to measure latency and health.
smart_checker = fproxy.HealthChecker(PERSONALIZED_BACKENDS, interval=10)

# LoadBalancer is a 'Passive' utility. It picks the fastest healthy backend.
# Because smart_checker uses personalized dicts, limits (maxrequests) are automatic.
smart_lb = fproxy.LoadBalancer(smart_checker)

# --- Standard Round-Robin Balancer ---
# No background tasks needed for simple list-based balancing.
simple_lb = fproxy.LoadBalancer(SIMPLE_BACKENDS)


# 3. Lifecycle Management
# This is the single place where background tasks and resources are managed.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize global HTTPX client for optimal performance across all proxy calls
    await fproxy.create_httpx_client(app)
    
    # We use 'async with' on the HealthChecker to start the monitoring loop
    # and ensure it stops cleanly when the server shuts down.
    async with smart_checker:
        print("🚀 Gateway started. Monitoring personalized backends...")
        print(f"Smart Targets: {smart_checker.targets}")
        yield
    
    # Graceful shutdown of the global client
    await fproxy.close_httpx_client(app)

app = FastAPI(
    title="FastAPI Reverse Proxy Gateway",
    description="A comprehensive example showing load balancing, health checks, and WS tunneling.",
    lifespan=lifespan
)

# --- ROUTE 1: Smart Load Balancing (Latency-Based) ---
@app.api_route("/smart/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def smart_proxy(request: Request, path: str):
    """
    Reroutes traffic to the FASTEST healthy backend from the personalized list.
    Automatically respects 'maxrequests' limits defined in PERSONALIZED_BACKENDS.
    """
    return await smart_lb.proxy_pass(request, path=f"/{path}")

# --- ROUTE 2: Simple Round-Robin ---
@app.api_route("/simple/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def simple_proxy(request: Request, path: str):
    """
    Cycles through a simple list of strings via standard Round-Robin.
    No health monitoring or latency tracking is performed for this list.
    """
    return await simple_lb.proxy_pass(request, path=f"/{path}")

# --- ROUTE 3: Feature Showcase (Advanced Overrides) ---
@app.get("/override-test")
async def override_demo(request: Request):
    """
    Demonstrates injecting headers, changing methods, and overriding bodies
    without using a LoadBalancer (hitting a specific target directly).
    """
    target_api = "http://localhost:8081/api/process"
    
    return await fproxy.proxy_pass(
        request, 
        target_api,
        method="POST",                   # Force a POST even if this was a GET
        additional_headers={
            "X-Proxy-Agent": "FastAPI-Reverse-Proxy-Example",
            "X-Internal-Secret": "super-secret-key"
        },
        override_body=b'{"status": "proxied_demo_request", "action": "override"}' # Replace the body
    )

# --- ROUTE 4: WebSocket Tunneling ---
@app.websocket("/ws/{path:path}")
async def websocket_tunnel(websocket: WebSocket, path: str):
    """
    Websockets also benefit from load balancing.
    Subprotocols are negotiated automatically with the upstream.
    This uses the smart balancer to find the best backend.
    """
    await smart_lb.proxy_pass_websocket(websocket, path=f"/{path}")


if __name__ == "__main__":
    print("FastAPI Reverse Proxy Example")
    print("----------------------------")
    print("\nAPI Routes:")
    print(" [ANY] http://localhost:8000/smart/   -> Latency-based proxy (with limits)")
    print(" [ANY] http://localhost:8000/simple/  -> Round-Robin proxy")
    print(" [GET] http://localhost:8000/override-test -> Custom overrides showcase")
    print(" [WS ] ws://localhost:8000/ws/        -> WebSocket tunneling")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
