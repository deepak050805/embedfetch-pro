print("[DEBUG STARTUP] app.py loading started")

import os
import uuid
import re
import asyncio
import time
from typing import Dict, Any

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from downloader.ytdlp_handler import extract_video_info, download_video
from downloader.playlist_manager import fetch_playlist
from downloader.selenium_extractor import extract_embedded_urls
from utils import check_ffmpeg_installed

print("[DEBUG STARTUP] fastAPI components loaded")

app = FastAPI(title="EmbedFetch Pro MVP")

# Ensure folders exist
os.makedirs("downloads", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

download_tasks: Dict[str, Any] = {}


# =========================
# Request Models
# =========================
class DownloadRequest(BaseModel):
    url: str
    format_id: str = "best"


# =========================
# Page Routes
# =========================
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.get("/single")
async def single_video(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="single_video.html",
        context={}
    )


@app.get("/playlist")
async def playlist(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="playlist.html",
        context={}
    )


# =========================
# API Routes
# =========================
@app.get("/api/system_status")
async def system_status():
    return {
        "ffmpeg_installed": check_ffmpeg_installed(),
        "debug": False
    }


@app.post("/api/formats")
async def get_formats(data: DownloadRequest):
    """
    Analyze video and return available quality formats.
    """
    try:
        formats = extract_video_info(data.url)

        return {
            "status": "success",
            "formats": formats
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/api/extract_embed")
async def extract_embed(data: DownloadRequest):
    """
    Extract embedded video URLs from protected pages.
    """
    try:
        urls = extract_embedded_urls(data.url)
        return {"urls": urls}

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/api/download/single")
async def start_single_download(
    data: DownloadRequest,
    background_tasks: BackgroundTasks
):
    """
    Start single video download.
    """
    try:
        task_id = str(uuid.uuid4())

        download_tasks[task_id] = {
            "status": "downloading",
            "progress": "0%",
            "speed": "0 MB/s",
            "eta": "--",
            "file": None
        }

        def progress_hook(d):
            if d["status"] == "downloading":
                percent = d.get("_percent_str", "0%").strip()
                speed = d.get("_speed_str", "0 MB/s")
                eta = d.get("_eta_str", "--")

                ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
                percent = ansi_escape.sub('', percent)
                speed = ansi_escape.sub('', str(speed))
                eta = ansi_escape.sub('', str(eta))

                download_tasks[task_id]["progress"] = percent
                download_tasks[task_id]["speed"] = speed
                download_tasks[task_id]["eta"] = eta

            elif d["status"] == "finished":
                download_tasks[task_id]["status"] = "completed"

        def run_download():
            try:
                download_video(
                    url=data.url,
                    output_dir="downloads",
                    format_id=data.format_id,
                    progress_hook=progress_hook
                )
                download_tasks[task_id]["status"] = "completed"

            except Exception as e:
                download_tasks[task_id]["status"] = "error"
                download_tasks[task_id]["error"] = str(e)

        background_tasks.add_task(run_download)

        return {
            "status": "success",
            "task_id": task_id
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )


@app.get("/api/download_status/{task_id}")
async def get_download_status(task_id: str):
    if task_id in download_tasks:
        return download_tasks[task_id]

    return JSONResponse(
        status_code=404,
        content={"detail": "Task not found"}
    )


@app.post("/api/playlist/extract")
async def extract_playlist(data: DownloadRequest):
    """
    Extract playlist metadata.
    """
    try:
        videos = fetch_playlist(data.url)

        return {
            "status": "success",
            "videos": videos
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/api/download/playlist")
async def start_playlist_download(
    data: DownloadRequest,
    background_tasks: BackgroundTasks
):
    return {
        "status": "info",
        "message": "Playlist bulk download feature coming next."
    }


print("[DEBUG STARTUP] app.py loading completed!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8001)