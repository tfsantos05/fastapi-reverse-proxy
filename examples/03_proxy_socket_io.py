from fastapi import FastAPI, Request, WebSocket
from contextlib import asynccontextmanager
from fastapi_reverse_proxy import Proxy, proxy_pass, proxy_pass_websocket

"""
Socket.IO has one more step than WebSocket.

You need an active HTTP endpoint on the same path.
Catch-all HTTP endpoints work too (as long as they cover /ws too)

✅ This works (cause it has a catch-all HTTP route)
@app.websocket("/ws/{path:path}")
@app.api_route("/{path:path}", methods=["GET","POST","PUT","DELETE"])

✅ This works too (cause /ws also has an HTTP route)
@app.websocket("/ws/{path:path}")
@app.api_route("/ws/{path:path}", methods=["GET","POST","PUT","DELETE"])

❌ This doesn't work (no HTTP route)
@app.websocket("/ws/{path:path}")

❌ This doesn't work either (HTTP endpoint doesn't catch /ws)
@app.websocket("/ws/{path:path}")
@app.api_route("/api/{path:path}", methods=["GET","POST","PUT","DELETE"])

Also, websocket always comes before HTTP endpoints
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with Proxy(app):
        yield
    
app = FastAPI(lifespan=lifespan)

# 1. The WebSocket comes first.
@app.websocket("/socket.io/{path:path}")
async def socketio_ws(websocket: WebSocket, path: str):
    await proxy_pass_websocket(websocket, "http://127.0.0.1:8080")


# 2. The HTTP route handles the initial handshake and long-polling.
@app.api_route("/socket.io/{path:path}", methods=["GET", "POST"])
async def socketio_http(request: Request, path: str):
    # Note: If using Socket.io, ensure the backend host is correct.
    return await proxy_pass(request, "http://127.0.0.1:8080")



if __name__ == "__main__":
    import uvicorn
    print("Starting Socket.io compatible proxy on http://127.0.0.1:8000")
    print("Proxying /socket.io/* to http://127.0.0.1:8080")
    print("\n💡 TIP: For best results with Socket.io, configure your client to use")
    print("transports: ['websocket'] to skip HTTP polling and connect directly.")
    uvicorn.run(app, host="0.0.0.0", port=8000)