import yt_dlp
import os
import time
import copy
import shutil
import subprocess
import json

# =========================
# CACHE SYSTEM (LRU STYLE)
# =========================
INFO_CACHE = {}
MAX_CACHE = 100
CACHE_TTL = 300  # 5 min


def set_cache(url, data):
    if len(INFO_CACHE) > MAX_CACHE:
        oldest = next(iter(INFO_CACHE))
        del INFO_CACHE[oldest]

    INFO_CACHE[url] = {
        "expires": time.time() + CACHE_TTL,
        "data": copy.deepcopy(data)
    }


def get_cache(url):
    cached = INFO_CACHE.get(url)
    if cached and time.time() < cached["expires"]:
        return copy.deepcopy(cached["data"])
    return None


# =========================
# EXTRACT VIDEO INFO
# =========================
def extract_video_info(url: str):

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": 10,
        "cachedir": True,
        "cookiefile": "cookies.txt",
        "http_headers": {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        set_cache(url, info)

        unique_formats = {}

        for f in info.get("formats", []):
            height = f.get("height")
            vcodec = f.get("vcodec")

            if not height or vcodec == "none":
                continue

            res_key = f"{height}p"
            ext = f.get("ext", "mp4")
            filesize = f.get("filesize") or f.get("filesize_approx") or 0

            fmt = {
                "format_id": f.get("format_id"),
                "resolution": res_key,
                "height": height,
                "ext": ext,
                "filesize": filesize
            }

            if res_key not in unique_formats:
                unique_formats[res_key] = fmt
            else:
                existing = unique_formats[res_key]

                if ext == "mp4" and existing["ext"] != "mp4":
                    unique_formats[res_key] = fmt
                elif filesize > existing["filesize"]:
                    unique_formats[res_key] = fmt

        formats = sorted(unique_formats.values(), key=lambda x: x["height"], reverse=True)
        return formats


# =========================
# AUDIO CHECK
# =========================
def check_has_audio(filepath: str) -> bool:
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                return True
        return False
    except:
        return True


# =========================
# DOWNLOAD VIDEO
# =========================
def download_video(url: str, output_dir: str, format_id="best", progress_hook=None):

    os.makedirs(output_dir, exist_ok=True)

    target_format = (
        "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best"
        if format_id == "best"
        else f"{format_id}+bestaudio/best"
    )

    ydl_opts = {
        "outtmpl": "%(title).80s.%(ext)s",
        "quiet": True,
        "format": target_format,
        "cookiefile": "cookies.txt",
        "retries": 10,
        "concurrent_fragment_downloads": 5,
        "restrictfilenames": True,
        "merge_output_format": "mp4",
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        },
        "postprocessor_args": {
            "ffmpeg": [
                "-c:v", "copy",
                "-c:a", "aac",
                "-profile:v", "main",
                "-level", "3.1",
                "-movflags", "+faststart"
            ]
        }
    }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        cached = get_cache(url)

        if cached:
            info = ydl.process_ie_result(cached, download=True)
        else:
            info = ydl.extract_info(url, download=True)

        filepath = ydl.prepare_filename(info)

        if not filepath.endswith(".mp4"):
            base, _ = os.path.splitext(filepath)
            filepath = base + ".mp4"

        if not check_has_audio(filepath):
            # fallback
            ydl_opts["format"] = "best[ext=mp4]/best"
            with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                info = ydl2.extract_info(url, download=True)
                filepath = ydl2.prepare_filename(info)

        return filepath


# =========================
# DOWNLOAD STRATEGY
# =========================
def get_download_strategy(url: str, format_id="best") -> dict:

    ydl_opts = {
        "quiet": True,
        "cookiefile": "cookies.txt",
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        cached = get_cache(url)

        if cached:
            info = cached
        else:
            info = ydl.extract_info(url, download=False)
            set_cache(url, info)

        extractor = info.get("extractor", "").lower()

        if "youtube" in extractor or "vimeo" in extractor:
            return {
                "type": "direct",
                "url": info.get("url")
            }

        return {
            "type": "proxy",
            "url": None
        }