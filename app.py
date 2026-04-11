import os
import uuid
import asyncio

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

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
# ASYNC HELPERS
# =========================
async def run_blocking(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


# =========================
# MODELS
# =========================
class DownloadRequest(BaseModel):
    url: str
    format_id: str = "best"


# =========================
# ROUTES
# =========================
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


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

        if strategy["type"] == "direct":
            return {
                "status": "success",
                "direct_url": strategy["url"]
            }

        return {
            "status": "proxy",
            "proxy_url": f"/api/download/proxy?url={data.url}&format_id={data.format_id}"
        }

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