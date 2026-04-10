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
from fastapi.responses import JSONResponse, FileResponse
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


# =========================
# FIXED DOWNLOAD ROUTE
# Browser downloads directly to user PC
# =========================
@app.post("/api/download/single")
async def start_single_download(data: DownloadRequest):
    """
    Download single video directly to browser.
    """
    try:
        file_path = download_video(
            url=data.url,
            output_dir="downloads",
            format_id=data.format_id
        )

        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type="application/octet-stream"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Download failed: {str(e)}"}
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
    import zipfile
    import shutil
    try:
        videos = fetch_playlist(data.url)
        if not videos:
            raise Exception("No videos found in playlist configuration.")

        playlist_id = str(uuid.uuid4())[:8]
        playlist_dir = os.path.join("downloads", f"playlist_{playlist_id}")
        os.makedirs(playlist_dir, exist_ok=True)

        for video in videos:
            try:
                print(f"[PLAYLIST INFO] Downloading video in playlist: {video['title']}")
                download_video(url=video['url'], output_dir=playlist_dir, format_id=data.format_id)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"[PLAYLIST ERROR] Gracefully handling failed download for {video['url']}: {e}")

        zip_path = os.path.join("downloads", f"playlist_{playlist_id}.zip")
        # Ensure we don't zip the _temp directory or anything weird inside the output. We just grab the files.
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(playlist_dir):
                if "_temp" in root: 
                    continue
                for file in files:
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, os.path.basename(file_path))

        return FileResponse(
            path=zip_path,
            filename=f"playlist_{playlist_id}.zip",
            media_type="application/zip"
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Playlist download failed: {str(e)}"}
        )


print("[DEBUG STARTUP] app.py loading completed!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8001)