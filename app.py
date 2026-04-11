import os
import asyncio

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# ✅ FIXED IMPORT
from downloader.ytdlp_handler import (
    extract_video_info,
    download_video,
    get_download_strategy
)

app = FastAPI(title="EmbedFetch Pro")

os.makedirs("downloads", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# =========================
# ASYNC HELPER
# =========================
async def run_blocking(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


# =========================
# MODEL
# =========================
class DownloadRequest(BaseModel):
    url: str
    format_id: str = "best"


# =========================
# ROUTES
# =========================
# =========================
# ROUTES
# =========================
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.get("/single")
async def single_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="single_video.html",
        context={}
    )


@app.post("/api/formats")
async def get_formats(data: DownloadRequest):
    try:
        formats = await run_blocking(extract_video_info, data.url)
        return {"status": "success", "formats": formats}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/download/single")
async def start_download(data: DownloadRequest):
    try:
        strategy = await run_blocking(
            get_download_strategy,
            data.url,
            data.format_id
        )

        # If the strategy provides a proxy url return it, otherwise fall back
        # to the default proxy endpoint.
        proxy_url = strategy.get("url") if isinstance(strategy, dict) else None
        if not proxy_url:
            proxy_url = f"/api/download/proxy?url={data.url}&format_id={data.format_id}"

        return {"status": "proxy", "proxy_url": proxy_url}

    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


@app.get("/api/download/proxy")
async def proxy_download(url: str, format_id: str = "best"):
    try:
        filepath = await run_blocking(
            download_video,
            url,
            "downloads",
            format_id
        )

        return FileResponse(filepath, filename=os.path.basename(filepath))

    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})