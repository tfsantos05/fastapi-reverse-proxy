from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi_reverse_proxy import Proxy, proxy_pass

"""
The simplest way to proxy a request.

Important: 
- Always use the Proxy lifespan manager
- Without Proxy(app), it won't work.
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the HTTPX connection pool via the Proxy manager
    async with Proxy(app):
        yield

app = FastAPI(lifespan=lifespan)

# A catch-all route that proxies all traffic to a single backend
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
async def gateway(request: Request, path: str):
    # Proxies request to the target host. 
    # Path is automatically handled (e.g., /api/user -> http://backend:8080/api/user)
    return await proxy_pass(request, "http://127.0.0.1:8080")

if __name__ == "__main__":
    import uvicorn
    print("Starting simple proxy on http://127.0.0.1:8000")
    print("Proxies all requests to http://127.0.0.1:8080")
    uvicorn.run(app, host="0.0.0.0", port=8000)
