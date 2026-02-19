import uvicorn
import asyncio
from fastapi import FastAPI, Request, WebSocket
from contextlib import asynccontextmanager

# Import your library components
# We import from the package root (__init__.py)
from __init__ import (
    proxy_pass, 
    proxy_pass_websocket, 
    HealthChecker, 
    LoadBalancer,
    create_httpx_client, 
    close_httpx_client
)

# 1. Configuration
# List of backends to load balance. 
# You can use a simple list of strings for standard round-robin.
BACKENDS = ["http://localhost:8081", "http://localhost:8082"]

# 2. Components Setup
# HealthChecker is the 'Active' component. It needs a lifecycle (async with).
# It will ping backends every 5 seconds to measure latency and health.
checker = HealthChecker(BACKENDS, interval=5)

# LoadBalancer is a 'Passive' utility. It just makes decisions based on its source.
smart_lb = LoadBalancer(checker)     # Health-aware: picks the fastest healthy backend
simple_lb = LoadBalancer(BACKENDS)   # Standard: cycles through backends regardless of health

# 3. Lifecycle Management
# This is the single place where background tasks and resources are managed.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize global HTTPX client for optimal performance
    await create_httpx_client(app)
    
    # We use 'async with' on the HealthChecker to start the monitoring loop
    # and ensure it stops cleanly when the server shuts down.
    async with checker:
        print("🚀 Gateway started. Monitoring backends...")
        print(f"Smart Targets: {checker.targets}")
        yield
    
    # Graceful shutdown of the global client
    await close_httpx_client(app)

app = FastAPI(lifespan=lifespan)

# --- ROUTE 1: Smart Load Balancing ---
@app.api_route("/smart/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def smart_proxy(request: Request, path: str):
    """
    Reroutes traffic to the FASTEST healthy backend.
    LoadBalancer automatically cleans up internal paths and appends yours.
    """
    return await smart_lb.proxy_pass(request, path=f"/{path}")

# --- ROUTE 2: Simple Round-Robin ---
@app.api_route("/simple/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def simple_proxy(request: Request, path: str):
    """Cycles through backends via standard Round-Robin."""
    return await simple_lb.proxy_pass(request, path=f"/{path}")

# --- ROUTE 3: Feature Showcase (Advanced Overrides) ---
@app.get("/override-test")
async def override_demo(request: Request):
    """
    Demonstrates injecting headers, changing methods, and overriding bodies.
    """
    # We can hit a specific backend directly with specialized settings
    target_api = f"{BACKENDS[0]}/api/process"
    
    return await proxy_pass(
        request, 
        target_api,
        method="POST",                   # Force a POST even if this was a GET
        additional_headers={
            "X-Proxy-Agent": "Antigravity",
            "X-Internal-Secret": "super-secret-key"
        },
        override_body=b'{"status": "proxied_demo_request"}' # Replace the body
    )

# --- ROUTE 4: WebSocket Tunneling ---
@app.websocket("/ws/{path:path}")
async def websocket_tunnel(websocket: WebSocket, path: str):
    """
    Websockets also benefit from load balancing.
    Subprotocols are negotiated automatically with the upstream.
    """
    # Use the smart balancer to find the best backend for this WS connection
    await smart_lb.proxy_pass_websocket(websocket, path=f"/{path}")


if __name__ == "__main__":
    print("FastAPI Reverse Proxy Example")
    print("----------------------------")
    print("Default target paths (if available):")
    for b in BACKENDS:
        print(f" - {b}")
    print("\nAPI Routes:")
    print(" [ANY] http://localhost:8000/smart/   -> Latency-based proxy")
    print(" [ANY] http://localhost:8000/simple/  -> Round-Robin proxy")
    print(" [GET] http://localhost:8000/override-test -> Custom overrides")
    print(" [WS ] ws://localhost:8000/ws/        -> WebSocket tunneling")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
