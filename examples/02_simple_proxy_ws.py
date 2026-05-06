from fastapi import FastAPI, Request, WebSocket
from contextlib import asynccontextmanager
from fastapi_reverse_proxy import Proxy, proxy_pass, proxy_pass_websocket

"""
Handling both HTTP and WebSocket traffic.

FastAPI treats HTTP and WebSockets as two different protocols.
To proxy both, you need both a standard route and a websocket route.

✅ This is the 'Transparent' setup:
- HTTP requests go to proxy_pass
- WS requests go to proxy_pass_websocket
- Both use the same target host.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with Proxy(app):
        yield

app = FastAPI(lifespan=lifespan)

# 1. HTTP Catch-all
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def http_gateway(request: Request, path: str):
    return await proxy_pass(request, "http://127.0.0.1:8080")

# 2. WebSocket Catch-all (from /ws)
@app.websocket("/{path:path}")
async def ws_gateway(websocket: WebSocket, path: str):
    # This handles the bidirectional tunnel and subprotocol negotiation
    await proxy_pass_websocket(websocket, "http://127.0.0.1:8080")

if __name__ == "__main__":
    import uvicorn
    print("Starting HTTP & WS proxy on http://127.0.0.1:8000")
    print("Proxies to http://127.0.0.1:8080")
    uvicorn.run(app, host="0.0.0.0", port=8000)
