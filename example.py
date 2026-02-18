import uvicorn
from fastapi import FastAPI, Request, WebSocket
from contextlib import asynccontextmanager

# Import your library components
from __init__ import (
    proxy_pass, 
    proxy_pass_websocket, 
    HealthChecker, 
    LoadBalancer,
    create_httpx_client, 
    close_httpx_client
)

# 1. Setup your backends
BACKENDS = ["http://localhost:8080", "http://localhost:8081"]

# 2. Initialize the "Brain" components
# We use autostart=False here because we'll start it inside the lifespan
checker = HealthChecker(BACKENDS, interval=5, autostart=False)
smart_lb = LoadBalancer(checker)     # Health-aware (picks fastest)
simple_lb = LoadBalancer(BACKENDS)   # Standard Round-Robin

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup global HTTPX client for the proxy
    await create_httpx_client(app)
    
    # Start the heatlh checker
    async with checker:
        print("🚀 Gateway started. Monitoring backends...")
        yield
    # destroy() is called automatically by 'async with' on shutdown
    await close_httpx_client(app)

app = FastAPI(lifespan=lifespan)

# --- ROUTE 1: Smart Load Balancing (Fastest Server) ---
@app.api_route("/smart/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def smart_proxy(request: Request):
    """Automatically routes to the fastest healthy backend."""
    return await proxy_pass(request, smart_lb)

# --- ROUTE 2: Simple Round-Robin ---
@app.api_route("/simple/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def simple_proxy(request: Request):
    """Cycles through servers regardless of health/speed."""
    return await proxy_pass(request, simple_lb)

# --- ROUTE 3: Single Target ---
@app.get("/direct/{path:path}")
async def direct_proxy(request: Request):
    """Directly hits a specific server."""
    return await proxy_pass(request, "http://localhost:8080")

# --- WEBSOCKETS ---
@app.websocket("/ws/{path:path}")
async def websocket_proxy(websocket: WebSocket, path: str):
    """Websocket proxying works with the LoadBalancer too!"""
    await proxy_pass_websocket(websocket, smart_lb)

if __name__ == "__main__":
    print("FastAPI Reverse Proxy Example")
    print("----------------------------")
    print("Test Smart (Fastest): http://localhost:8000/smart/")
    print("Test Simple (RR):      http://localhost:8000/simple/")
    uvicorn.run(app, host="0.0.0.0", port=8000)
