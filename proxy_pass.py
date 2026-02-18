from fastapi import Request, WebSocket, Response
from fastapi.responses import StreamingResponse
import httpx
import websockets
import asyncio
import logging
from typing import Optional
from proxy_httpx import get_httpx_client
from load_balance import LoadBalancer
from health_check import HealthChecker

logger = logging.getLogger("fastapi_reverse_proxy")

# Hop-by-hop headers that should typically not be forwarded by a proxy
# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/TE
EXCLUDED_HEADERS = {
    "connection", "keep-alive", "proxy-authenticate", 
    "proxy-authorization", "te", "trailers", "transfer-encoding", "upgrade"
}

async def proxy_pass(request: Request, target: str | LoadBalancer | HealthChecker, timeout: float = 60.0):
    """
    Forwards incoming HTTP requests to the target service using streaming.
    Robustly handles SSE (Server-Sent Events) and large payloads.
    """

    if isinstance(target, str): target_url = target
    elif isinstance(target, LoadBalancer): target_url = target.get()
    elif isinstance(target, HealthChecker): target_url = target.get_fastest()
    else: raise TypeError("Target must be a string, LoadBalancer, or HealthChecker")

    # If all servers are down, return a clean 503 instead of trying to hit "http://None/..."
    if target_url is None:
        logger.error("Proxy target is None (check LoadBalancer/HealthChecker status)")
        return Response("Service Unavailable: No healthy backends", status_code=503)

    url = f"{target_url.rstrip('/')}{request.url.path}"
    if request.query_params:
        url = f"{url}?{request.query_params}"

    # Prepare headers for the upstream request
    headers = dict(request.headers)
    
    # Identify the client's real IP and forward it
    client_host = request.client.host if request.client else "unknown"
    headers["X-Real-IP"] = client_host
    if "X-Forwarded-For" in headers:
        headers["X-Forwarded-For"] = f"{headers['X-Forwarded-For']}, {client_host}"
    else:
        headers["X-Forwarded-For"] = client_host
    
    headers["X-Forwarded-Proto"] = request.url.scheme
    headers["X-Forwarded-Host"] = headers.get("host", request.url.netloc)
    
    # Let httpx handle the host header and connection management
    headers.pop("host", None)
    headers.pop("connection", None)

    try:
        client = await get_httpx_client(request)
    except Exception:
        # Fallback for testing
        client = httpx.AsyncClient()

    # Stream the request body to the target (efficient for large uploads)
    async def request_generator():
        async for chunk in request.stream():
            yield chunk

    # Create the upstream request
    rp_req = client.build_request(
        method=request.method,
        url=url,
        headers=headers,
        content=request_generator() if request.method in ("POST", "PUT", "PATCH") else None,
        timeout=timeout
    )

    # Send the request and stream the response
    rp_resp = await client.send(rp_req, stream=True)

    # Filter response headers
    resp_headers = {}
    for k, v in rp_resp.headers.items():
        if k.lower() in EXCLUDED_HEADERS:
            continue
        # We let httpx decompress the response (default behavior),
        # so we must remove the Content-Encoding header to avoid double-decoding in the browser.
        if k.lower() == "content-encoding":
            continue
        # Content-Length is handled by StreamingResponse for chunked transfers
        if k.lower() == "content-length":
            continue
        resp_headers[k] = v
    
    # Optimization for SSE and real-time streaming: tell intermediate proxies not to buffer
    resp_headers["X-Accel-Buffering"] = "no"
    resp_headers["Cache-Control"] = "no-cache"

    return StreamingResponse(
        rp_resp.aiter_bytes(), # Use aiter_bytes() to get decompressed content
        status_code=rp_resp.status_code,
        headers=resp_headers,
        background=rp_resp.aclose # ALWAYS close the response stream
    )


async def proxy_pass_websocket(websocket: WebSocket, target: str | LoadBalancer | HealthChecker, subprotocols: Optional[list[str]] = None):
    """
    Forwards incoming WebSocket connections to the target service.
    'target' can be a string, LoadBalancer, or HealthChecker.
    """
    # Resolve target
    if isinstance(target, str): target_url = target
    elif isinstance(target, LoadBalancer): target_url = target.get()
    elif isinstance(target, HealthChecker): target_url = target.get_fastest()
    else: raise TypeError("Target must be a string, LoadBalancer, or HealthChecker")

    if target_url is None:
        await websocket.close(code=1011) # Internal Error
        return

    # Accept the incoming connection with the same subprotocol if requested
    client_subprotocol = websocket.headers.get("sec-websocket-protocol")
    await websocket.accept(subprotocol=client_subprotocol)
    
    path = websocket.url.path
    query = websocket.url.query

    # Ensure we use ws:// or wss://
    target_ws_base = target_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    target_ws_url = f"{target_ws_base}{path}"
    if query:
        target_ws_url += f"?{query}"

    client_host = websocket.client.host if websocket.client else "unknown"
    headers = {
        "X-Real-IP": client_host,
        "X-Forwarded-For": client_host,
        "X-Forwarded-Proto": websocket.url.scheme,
        "X-Forwarded-Host": websocket.headers.get("host", websocket.url.netloc)
    }

    # Handle different versions of the websockets library
    connect_params = {
        "subprotocols": subprotocols or websocket.scope.get("subprotocols")
    }

    try:
        # Try new API (websockets 12.0+)
        async with websockets.connect(target_ws_url, additional_headers=headers, **connect_params) as target_ws:
            await _handle_ws_bidirectional(websocket, target_ws)
    except TypeError as e:
        if "additional_headers" in str(e):
            # Fallback to legacy API
            async with websockets.connect(target_ws_url, extra_headers=headers, **connect_params) as target_ws:
                await _handle_ws_bidirectional(websocket, target_ws)
        else:
            logger.error(f"WebSocket Connect Error: {e}")
    except Exception as e:
        logger.error(f"WebSocket Proxy Error: {e}")
    finally:
        try:
            await websocket.close()
        except:
            pass

async def _handle_ws_bidirectional(websocket: WebSocket, target_ws):
    """Internal helper to manage bidirectional WS traffic."""
    async def client_to_target():
        try:
            while True:
                message = await websocket.receive()
                if "text" in message:
                    await target_ws.send(message["text"])
                elif "bytes" in message:
                    await target_ws.send(message["bytes"])
        except Exception:
            pass

    async def target_to_client():
        try:
            while True:
                message = await target_ws.recv()
                if isinstance(message, str):
                    await websocket.send_text(message)
                else:
                    await websocket.send_bytes(message)
        except Exception:
            pass

    # Run both tasks concurrently until one closes
    await asyncio.gather(client_to_target(), target_to_client())
