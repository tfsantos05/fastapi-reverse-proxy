# FastAPI Reverse Proxy

A robust, streaming-capable reverse proxy for FastAPI/Starlette with built-in **Latency-Based Load Balancing** and **Active Health Monitoring**.

## Features

- **Streaming Ready**: Efficiently handles SSE (Server-Sent Events) and large file uploads/downloads.
- **WebSocket Support**: Seamless bidirectional tunneling for real-time applications.
- **Unified Load Balancing**: Single class for both Round-Robin and Smart routing.
- **Latency-Based Routing**: Automatically routes traffic to the fastest healthy server (HEAD probe).
- **Graceful Failover**: Returns 503 Service Unavailable when no healthy backends are available.
- **Framework Agnostic**: Works with FastAPI and Starlette out of the box.

## Quick Start

```python
from fastapi import FastAPI, Request
from fastapi_reverse_proxy import proxy_pass, HealthChecker, LoadBalancer

app = FastAPI()

# 1. Setup health monitoring (Optional but recommended)
checker = HealthChecker(["http://localhost:8080", "http://localhost:8081"])
# 2. Setup the balancer
lb = LoadBalancer(checker)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def gateway(request: Request):
    # Pass the LoadBalancer directly!
    return await proxy_pass(request, lb)
```

## Core Components

### 1. HealthChecker
Monitors a list of target URLs in the background. It measures latency in milliseconds and tracks uptime.

- **Initialization**: `HealthChecker(targets, interval=10, timeout=10)`
- **`get_fastest()`**: Returns the URL with the lowest response time.
- **Lifecycle**: Use `async with checker:` or manual `start()`/`destroy()`.

### 2. LoadBalancer
The decision maker. It has two modes based on what you pass to the constructor:

- **Round-Robin Mode**: Pass a `list[str]`. It cycles through servers sequentially.
- **Latency Mode**: Pass a `HealthChecker` object. It always picks the fastest healthy target.

```python
lb = LoadBalancer(["http://a", "http://b"]) # Mode: Round-Robin
lb = LoadBalancer(checker)                  # Mode: Latency-Based
```

## Advanced Example

See `example.py` for a full implementation including:
- Proper `lifespan` management.
- Shared `httpx.AsyncClient` for performance.
- WebSocket proxying with load balancing.

## License

MIT
