from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi_reverse_proxy import Proxy, LoadBalancer

"""
Distributing traffic across multiple backends.

✅ Use this when you have a cluster of identical servers.
✅ Use this for simple scaling (Round-Robin).

Note: 
- This version uses a static list of backends.
- If one server goes down, the proxy will still try to send traffic to it.
- For automatic failover, use the HealthChecker (see example 05).
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with Proxy(app):
        yield

app = FastAPI(lifespan=lifespan)

# Define a list of backends to balance across
BACKENDS = ["http://127.0.0.1:8081", "http://127.0.0.1:8082", "http://127.0.0.1:8083"]

# LoadBalancer without a HealthChecker will use Round-Robin 
# based on the provided list.
lb = LoadBalancer(BACKENDS)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(request: Request, path: str):
    # The LoadBalancer decides which backend to use and calls proxy_pass internally
    return await lb.proxy_pass(request, path=f"/{path}")

if __name__ == "__main__":
    import uvicorn
    print(f"Starting Load Balanced proxy on http://127.0.0.1:8000")
    print(f"Balancing across: {BACKENDS}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
