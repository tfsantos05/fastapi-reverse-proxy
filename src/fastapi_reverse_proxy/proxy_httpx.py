import httpx
from fastapi import FastAPI, Request

async def create_httpx_client(app: FastAPI):
    """Initializes the HTTP client and stores it in the app state."""
    app.state.http_proxy_client = httpx.AsyncClient()

async def close_httpx_client(app: FastAPI):
    """Closes the HTTP client stored in the app state."""
    if hasattr(app.state, "http_proxy_client"):
        await app.state.http_proxy_client.aclose() # close it

async def get_httpx_client(req: Request) -> httpx.AsyncClient:
    """Retrieves the HTTP client from the app state."""
    return req.app.state.http_proxy_client