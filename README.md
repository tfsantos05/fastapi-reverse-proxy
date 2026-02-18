# FastAPI Reverse Proxy

A robust, streaming-capable reverse proxy for FastAPI including support for WebSockets and Server-Sent Events (SSE).

## Features

- **Streaming Support**: Efficiently handles large file uploads and downloads.
- **SSE Compatible**: Ready for Server-Sent Events (perfect for LLM applications like Open WebUI).
- **WebSocket Forwarding**: Bidirectional proxying of WebSocket connections.
- **Memory Efficient**: Uses `httpx` and FastAPI's streaming response to keep memory usage flat.
- **Connection Pooling**: Reuses client connections for maximum performance.

## Quick Start

### 1. Initialize the Client
In your FastAPI app, use the `lifespan` event to manage the connection pool:

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager
from proxy_httpx import create_httpx_client, close_httpx_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_httpx_client(app)
    yield
    await close_httpx_client(app)

app = FastAPI(lifespan=lifespan)
```

### 2. Setup the Proxy Route
```python
from fastapi import Request, WebSocket
from proxy_pass import proxy_pass, proxy_pass_websocket

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def http_proxy(request: Request, path: str):
    return await proxy_pass(request, "http://localhost:8080")

@app.websocket("/{path:path}")
async def ws_proxy(websocket: WebSocket, path: str):
    await proxy_pass_websocket(websocket, "ws://localhost:8080")
```

## Installation

```bash
pip install fastapi-reverse-proxy
```

## License
MIT
