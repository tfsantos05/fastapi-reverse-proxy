# FastAPI Reverse Proxy

A robust, streaming-capable reverse proxy for FastAPI/Starlette with built-in **Latency-Based Load Balancing** and **Active Health Monitoring**.

## Features

- **Streaming Ready**: Efficiently handles SSE (Server-Sent Events) and large file uploads/downloads.
- **WebSocket Support**: Seamless bidirectional tunneling with automated subprotocol negotiation.
- **Unified Load Balancing**: Standard Round-Robin or Smart routing using a single utility.
- **Latency-Based Routing**: Automatically routes traffic to the fastest healthy server (HEAD probe).
- **Advanced Overrides**: Granular control over headers, body, and HTTP methods.
- **Robust Cancellation**: Specialized handling for `asyncio.CancelledError` to prevent resource leaks.
- **Version Agnostic**: Automatically handles `websockets` library version differences (12.0+ vs Legacy).

## Quick Start (Best Practice)

The recommended way to use the library is within a FastAPI **lifespan** handler. This ensures all background monitoring tasks and HTTP clients start and stop cleanly.

```python
from fastapi import FastAPI, Request, WebSocket
from contextlib import asynccontextmanager

from fastapi_reverse_proxy import (
     HealthChecker, LoadBalancer, 
     create_httpx_client, close_httpx_client
)

# 1. Setup health monitoring and load balancing
checker = HealthChecker(["http://localhost:8080", "http://localhost:8081"])
lb = LoadBalancer(checker)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize global resources
    await create_httpx_client(app)
    async with checker: # Starts background health loop
        yield
    await close_httpx_client(app)

app = FastAPI(lifespan=lifespan)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(request: Request, path: str):
    # Route to the fastest healthy backend
    return await lb.proxy_pass(request, path=f"/{path}")

@app.websocket("/ws/{path:path}")
async def ws_tunnel(websocket: WebSocket, path: str):
    # Automatic subprotocol negotiation + Tunneling
    await lb.proxy_pass_websocket(websocket, path=f"/{path}")
```

## Advanced Proxying

The `proxy_pass` function and `LoadBalancer.proxy_pass` provide deep customization for upstream requests:

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `method` | `str` | Force a specific HTTP method (e.g., `"POST"`). |
| `override_body` | `bytes` | Send custom data instead of the incoming request body. |
| `additional_headers` | `dict` | Append custom headers to the proxied request. |
| `override_headers` | `dict` | Use these headers *instead* of original request headers. |
| `forward_query` | `bool` | Whether to append the incoming query string (Default: `True`). |

## Monitoring & Configuration

### HealthChecker (The Loop Owner)
The **proactive** component. It owns an internal `asyncio` background task that monitors backends.
- **Immediate Start**: When you enter the `async with` block (or call `start()`), the checker performs an **immediate** check of all backends. This eliminates the "cold-start" window where backends are unknown.
- **Configuration Modes**:
  - **Standard**: `HealthChecker(["http://a", "http://b"], ping_path="/health")`
  - **Personalized**: Pass a list of dictionaries for per-host settings:
    ```python
    checker = HealthChecker([
        {"host": "http://api-1", "pingpath": "/v1/status", "maxrequests": 100},
        {"host": "http://api-2", "pingpath": "/health"}
    ])
    ```
- **Properties**:
  - `ping_path`: Get or set the global health check path (default: `"/"`).

### LoadBalancer (The Decision Utility)
A **normal Python object** that makes routing decisions based on its source.
- **Stateful**: While it has no background loop, it **does track state** (request counts for rate-limiting and the last time it pulled data from the health checker).
- **No Lifecycle Needed**: It relies on the `HealthChecker` (or a static list) for data and doesn't need explicit `start`/`stop` calls.

## WebSocket Refinements

The library implements "deferred negotiation" for WebSockets:
1. The proxy receives the client's supported subprotocols from `scope`.
2. It establishes an upstream connection first.
3. Once the upstream accepts a protocol, the proxy calls `websocket.accept(subprotocol=...)` back to the client.
4. This ensures the entire tunnel (Client <-> Proxy <-> Upstream) uses the same negotiated protocol.

## Robustness & Safety

- **Termination Safety**: Resource cleanup (closing `httpx` clients and sockets) is triggered even on task cancellation (`BaseException`).
- **Introspection-Based Compatibility**: Uses `inspect.signature` to automatically detect version-specific parameters in the `websockets` library.
