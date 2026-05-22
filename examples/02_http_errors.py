from fastapi import FastAPI, Request, HTTPException
from fastapi_reverse_proxy import proxy_pass, Proxy
import uvicorn
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with Proxy(app):
        yield

app = FastAPI(title="Proxy Error Handling Example", lifespan=lifespan)

# We define two backends to demonstrate failover
PRIMARY_BACKEND = "http://127.0.0.1:8081"
BACKUP_BACKEND = "http://127.0.0.1:8082"

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def smart_proxy(request: Request):
    """
    This route demonstrates how to use the injected HTTPExceptions
    to implement a simple failover mechanism.
    """
    try:
        # Try the primary backend first
        # We use a short timeout here to trigger failover quickly for the demo
        return await proxy_pass(
            request, 
            PRIMARY_BACKEND,  
            timeout=5.0 
        )
    except HTTPException as e:
        # 504 = Gateway Timeout (Backend took too long)
        # 502 = Bad Gateway (Backend is down/refused connection)
        if e.status_code in (502, 504):
            print(f"Primary backend failed ({e.status_code}). Switching to backup...")
            try:
                return await proxy_pass(
                    request, 
                    BACKUP_BACKEND,
                    timeout=10.0
                )
            except HTTPException as backup_e:
                # If the backup also fails, we finally let the error bubble up to the client
                raise backup_e
        
        # If it's another error (like 404 from the backend), just raise it
        else: raise e

if __name__ == "__main__":
    print("Running Proxy with Failover Logic...")
    print(f"Primary: {PRIMARY_BACKEND} -> Backup: {BACKUP_BACKEND}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
