import os
import sys
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn

app = FastAPI(title="Render Telegram Streaming Proxy")

TELEGRAM_API_BASE = "https://api.telegram.org"

@app.get("/health")
def health():
    return {"status": "healthy", "service": "render_telegram_streaming_proxy"}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def proxy_telegram(request: Request, path: str):
    """
    Transparent full-duplex streaming proxy for all Telegram Bot API requests,
    including webhook delivery, long-polling, text messages, audio, and heavy PDF downloads.
    """
    target_url = f"{TELEGRAM_API_BASE}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    body = await request.body()

    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0))
    try:
        req = client.build_request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body
        )
        resp = await client.send(req, stream=True)

        excluded_headers = {"content-encoding", "content-length", "transfer-encoding", "connection"}
        response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded_headers}

        async def stream_content():
            try:
                async for chunk in resp.aiter_raw():
                    yield chunk
            finally:
                await resp.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_content(),
            status_code=resp.status_code,
            headers=response_headers,
            media_type=resp.headers.get("content-type")
        )
    except Exception as e:
        await client.aclose()
        return JSONResponse(status_code=502, content={"ok": False, "error": str(e)})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    print(f"[*] Starting Render Telegram Streaming Proxy on 0.0.0.0:{port}...")
    uvicorn.run("proxy_server:app", host="0.0.0.0", port=port, log_level="info")
