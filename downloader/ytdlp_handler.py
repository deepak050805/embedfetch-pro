import yt_dlp
import os
import time
import copy
import subprocess
import json

# =========================
# CACHE SYSTEM
# =========================
INFO_CACHE = {}
MAX_CACHE = 100
CACHE_TTL = 300


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
        "skip_download": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0",
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []

    for f in info.get("formats", []):
        height = f.get("height")
        vcodec = f.get("vcodec")
        acodec = f.get("acodec")

        if (
            height and
            vcodec != "none" and
            f.get("ext") in ["mp4", "webm"] and
            height >= 144
        ):
            formats.append({
                "format_id": f.get("format_id"),
                "resolution": f"{height}p",
                "height": height,
                "ext": f.get("ext"),
                "filesize": f.get("filesize") or f.get("filesize_approx") or 0,
                "vcodec": vcodec,
                "acodec": acodec,
                "fps": int(f.get("fps") or 0)
            })

    # ✅ REMOVE DUPLICATES
    unique = {}

    for f in formats:
        res = f["resolution"]

        if res not in unique:
            unique[res] = f
        else:
            if f["ext"] == "mp4" and f["acodec"] != "none":
                unique[res] = f

    return sorted(unique.values(), key=lambda x: x["height"], reverse=True)


# =========================
# AUDIO CHECK
# =========================
def check_has_audio(filepath: str) -> bool:
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams", filepath
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        return any(s.get("codec_type") == "audio" for s in data.get("streams", []))
    except:
        return True


# =========================
# DOWNLOAD VIDEO
# =========================
def download_video(url: str, output_dir: str, format_id="best", progress_hook=None):

    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "%(title).80s.%(ext)s"),

        # stable + fast
        "format": "best[ext=mp4]/best",

        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },

        "http_headers": {
            "User-Agent": "Mozilla/5.0",
        },

        "ffmpeg_location": "C:\\ffmpeg\\ffmpeg-8.1-essentials_build\\bin",
        "merge_output_format": "mp4",

        "retries": 10,
        "concurrent_fragment_downloads": 5,
    }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

        filepath = ydl.prepare_filename(info)

        # remove .fxxx
        base, _ = os.path.splitext(filepath)
        if ".f" in base:
            base = base.split(".f")[0]

        filepath = base + ".mp4"

        if not os.path.exists(filepath):
            raise Exception(f"File not found: {filepath}")

        if not check_has_audio(filepath):
            print("Retrying with fallback...")
            ydl_opts["format"] = "best"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                info = ydl2.extract_info(url, download=True)
                filepath = ydl2.prepare_filename(info)

        return filepath


# =========================
# DOWNLOAD STRATEGY
# =========================
def get_download_strategy(url: str, format_id="best") -> dict:
    return {
        "type": "proxy",
        "url": None
    }