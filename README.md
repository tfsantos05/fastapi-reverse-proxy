# FastAPI Reverse Proxy

A robust, streaming-capable reverse proxy for FastAPI/Starlette with built-in **Latency-Based Load Balancing** and **Active Health Monitoring**.

## Features

- **Async**: Async by default.
- **Httpx Pool**: Async HTTPX Pool for proxying.
- **Streaming Ready**: Handles SSE (Server-Sent Events) and large payloads (such as big files) while keeping RAM usage low.
- **WebSocket Support**: Seamless bidirectional tunneling with automated subprotocol negotiation.
- **Unified Load Balancing**: Standard Round-Robin or Smart routing using a single utility.
- **Latency-Based Routing**: Automatically routes traffic to the fastest healthy server (HEAD probe).
- **Advanced Overrides**: Granular control over headers, body, and HTTP methods.
- **Smart Error Mapping**: Automatically converts upstream connection failures into standard HTTP 502 (Bad Gateway) and 504 (Gateway Timeout) responses.
- **Resilient Handshakes**: Customizable `open_timeout` for WebSockets to prevent proxy hangs during backend connection attempts.
- **Version Agnostic**: Automatically handles `websockets` library version differences (12.0+ vs Legacy).

## Quick Start

Use the **lifespan** handler as shown for an easy launch.

The simplest way to use the proxy is to use **proxy_pass** and/or **proxy_pass_websocket** on the endpoints.

```python
from fastapi import FastAPI, Request, WebSocket
from contextlib import asynccontextmanager

from fastapi_reverse_proxy import Proxy, proxy_pass, proxy_pass_websocket

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with Proxy(app):
        yield

app = FastAPI(lifespan=lifespan)

# catch-all route. recommended for a reverse proxy
@app.api_route("/{path:path}", methods=["GET","POST","PUT","DELETE"]) # don't forget to add the methods.
async def index(req: Request):
    """
    You always need to pass the "Request" object and to specify the host
    If you don't add a path, it will be the same as the original (/login --> http://127.0.0.1/login)
    """
    return await proxy_pass(req, "http://127.0.0.1:8080")

```

## 🛡️ Resilience & Error Handling

Error Handlingfastapi-reverse-proxy transforms upstream crashes into meaningful HTTPException responses (e.g., 502 Bad Gateway or 504 Gateway Timeout). 

This allows you to implement custom failover logic, retry mechanisms, or specific error pages.

For a full implementation of a primary-to-backup failover system, see the [example](https://github.com/tfsantos05/fastapi-reverse-proxy/tree/main/examples/02_http_errors.py).

## Advanced Examples:

Check [examples](https://github.com/tfsantos05/fastapi-reverse-proxy/tree/main/examples) for full examples, including:
- **Websocket Proxy**
- **Socket.IO Proxy** 
- **Error Handling & Failover** (`examples/error_handling_example.py`)

## Advanced Proxying

The `proxy_pass` function and `LoadBalancer.proxy_pass` provide deep customization for upstream requests:

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `timeout` | `float` | Total request timeout in seconds (Default: `60.0`). |
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
5. **Handshake Timeout**: Supports a customizable `timeout` parameter (default `10.0s`) to prevent hangs if the backend is unresponsive.

## Robustness & Safety

- **Termination Safety**: Resource cleanup (closing `httpx` clients and sockets) is triggered even on task cancellation (`BaseException`).
- **Introspection-Based Compatibility**: Uses `inspect.signature` to automatically detect version-specific parameters in the `websockets` library.
