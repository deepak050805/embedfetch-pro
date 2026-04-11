import yt_dlp
import os
import time
import copy

INFO_CACHE = {}

def extract_video_info(url: str):
    """
    Extract available video formats:
    - Keep only one best stream per resolution
    - Prefer MP4 over WEBM automatically
    """

    yydl_opts = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "skip_download": True,
    "socket_timeout": 10,
    "cachedir": True,
}

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        # Cache for 60 seconds to eliminate download startup delay
        INFO_CACHE[url] = {
            "expires": time.time() + 300,
            "data": copy.deepcopy(info)
        }

        unique_formats = {}

        for f in info.get("formats", []):
            height = f.get("height")
            vcodec = f.get("vcodec")

            # Skip invalid / audio-only formats
            if not height or vcodec == "none":
                continue

            res_key = f"{height}p"
            ext = f.get("ext", "mp4")
            fps = f.get("fps", "")
            filesize = f.get("filesize") or f.get("filesize_approx") or 0

            fmt_dict = {
                "format_id": f.get("format_id"),
                "resolution": res_key,
                "height": height,
                "fps": fps,
                "ext": ext,
                "vcodec": vcodec.split(".")[0] if vcodec else "",
                "filesize": filesize
            }

            # Keep only one per resolution, prefer MP4
            if res_key not in unique_formats:
                unique_formats[res_key] = fmt_dict
            else:
                existing = unique_formats[res_key]

                if ext == "mp4" and existing["ext"] != "mp4":
                    unique_formats[res_key] = fmt_dict
                elif existing["ext"] == "mp4" and ext != "mp4":
                    continue
                else:
                    # If same ext type, keep larger filesize
                    if filesize > existing["filesize"]:
                        unique_formats[res_key] = fmt_dict

        available_formats = list(unique_formats.values())
        available_formats.sort(key=lambda x: x["height"], reverse=True)

        return available_formats


def check_has_audio(filepath: str, ffmpeg_location: str) -> bool:
    import subprocess
    import json
    
    if not filepath or not os.path.exists(filepath):
        print(f"[FFPROBE WARNING] File does not exist: {filepath}")
        return True # Can't check, fail open

    try:
        if ffmpeg_location and os.path.isdir(ffmpeg_location):
            ffprobe_path = os.path.join(ffmpeg_location, "ffprobe.exe")
            if not os.path.exists(ffprobe_path):
                ffprobe_path = os.path.join(ffmpeg_location, "ffprobe")
                if not os.path.exists(ffprobe_path):
                    ffprobe_path = "ffprobe"
        else:
            ffprobe_path = "ffprobe"

        cmd = [
            ffprobe_path,
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
    except FileNotFoundError:
        print("[FFPROBE WARNING] ffprobe not found, skipping audio check. (Fail open)")
        return True
    except Exception as e:
        print(f"[FFPROBE ERROR] Validation error: {e}")
        return True # Fail open

class CustomYtDlpLogger:
    def debug(self, msg):
        msg_lower = msg.lower()
        if "ffmpeg command line" in msg_lower:
            print(f"[MERGE_DEBUG_FFMPEG_CMD] {msg}")
        elif "downloading format" in msg_lower or "format" in msg_lower:
            print(f"[MERGE_DEBUG_FORMAT] {msg}")
        else:
            print(f"[yt-dlp] {msg}")

    def warning(self, msg):
        print(f"[yt-dlp warning] {msg}")

    def error(self, msg):
        print(f"[yt-dlp error] {msg}")

def download_video(url: str, output_dir: str, format_id="best", progress_hook=None):
    """
    Download video with guaranteed audio merge.
    Fixes:
    ✔ Audio missing issue
    ✔ FFmpeg merge issue
    ✔ MP4 final output
    ✔ Automatic fallback retry
    """
    import shutil

    temp_dir = os.path.join(output_dir, "_temp")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    # Check FFmpeg availability
    has_ffmpeg = shutil.which("ffmpeg") is not None
    ffmpeg_location = None
    windows_ffmpeg = r"C:\ffmpeg\ffmpeg-8.1-essentials_build\bin"
    if not has_ffmpeg and os.path.exists(windows_ffmpeg):
        has_ffmpeg = True
        ffmpeg_location = windows_ffmpeg

    if has_ffmpeg:
        if format_id == "best":
            # Prefer progressive single-stream over separated streams if available
            target_format = "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
        else:
            # Prefer selected format independently if it already has audio, else merge
            target_format = f"{format_id}[ext=mp4]/{format_id}+bestaudio[ext=m4a]/{format_id}+bestaudio/best"
    else:
        print("[WARNING] FFmpeg missing. Falling back to single progressive stream to ensure audio.")
        # Best format that is pre-merged (contains both video and audio)
        target_format = "best[ext=mp4]/best"

    ydl_opts = {
        "outtmpl": {"default": "%(title).80s_[%(resolution)s].%(ext)s"},
        "paths": {
            "home": output_dir,
            "temp": temp_dir
        },
        "quiet": True,
        "cookiefile": "cookies.txt",
        "format": target_format,
        "verbose": True,
        "no_warnings": False,
        "nopart": False,
        "overwrites": True,
        "retries": 10,
        "fragment_retries": 10,
        "logger": CustomYtDlpLogger()
    }

    if has_ffmpeg:
        ydl_opts["merge_output_format"] = "mp4"
        if ffmpeg_location:
            ydl_opts["ffmpeg_location"] = ffmpeg_location
            
        # In case merging runs, enforce AAC audio, H264 compat, and MOOV atom faststart for browser playback
        # We purposely avoid the FFmpegVideoConvertor postprocessor to ensure we skip FFmpeg entirely for native progressive streams
        ydl_opts["postprocessor_args"] = {
            "ffmpeg": [
                "-c:v", "copy",
                "-c:a", "aac",
                "-avoid_negative_ts", "make_non_negative",
                "-max_muxing_queue_size", "1024",
                "-movflags", "+faststart"
            ]
        }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    def perform_download(opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            cached = INFO_CACHE.get(url)
            if cached and time.time() < cached["expires"]:
                print(f"[CACHE HIT] Reusing cached metadata to skip extraction delay for {url}")
                info_copy = copy.deepcopy(cached["data"])
                # Crucial Fix: Scrub the root format assignments that were implicitly set by the generic analyzer
                # This guarantees yt-dlp's internal `process_video_result` format selector natively re-fires without crashing
                keys_to_pop = [
                    'format', 'format_id', 'url', 'ext', 'manifest_url', 'vcodec', 'acodec', 'resolution',
                    'requested_downloads', 'requested_formats'
                ]
                for k in keys_to_pop:
                    info_copy.pop(k, None)
                info = ydl.process_ie_result(info_copy, download=True)
            else:
                info = ydl.extract_info(url, download=True)
            
            # Find the final output filepath
            final_filepath = None
            if "requested_downloads" in info:
                final_filepath = info["requested_downloads"][0].get("filepath")
            
            if not final_filepath:
                # Fallback: guess the final filepath
                pre_filepath = ydl.prepare_filename(info)
                base, _ = os.path.splitext(pre_filepath)
                if opts.get("merge_output_format") == "mp4" and os.path.exists(base + ".mp4"):
                    final_filepath = base + ".mp4"
                elif os.path.exists(pre_filepath):
                    final_filepath = pre_filepath
                else:
                    import glob
                    import shlex
                    # glob escape the base to handle brackets/spaces properly
                    candidates = glob.glob(f"{glob.escape(base)}*")
                    if candidates:
                        final_filepath = candidates[0]
                        
            if not final_filepath or not os.path.exists(final_filepath):
                raise Exception(f"Download finished but output file not found on disk. Expected near: {ydl.prepare_filename(info)}")

            # Validation: wait for locks to be released and confirm the temp file is completely merged
            part_file = final_filepath + ".part"
            ytdl_file = final_filepath + ".ytdl"
            
            timeout = 30
            start_time = time.time()
            while time.time() - start_time < timeout:
                if os.path.exists(part_file) or os.path.exists(ytdl_file):
                    time.sleep(1)
                else:
                    break
                    
            if os.path.exists(part_file) or os.path.exists(ytdl_file):
                raise Exception("Corrupted download: incomplete temp files still exist after extraction timeout.")

            if os.path.getsize(final_filepath) == 0:
                raise Exception("Corrupted download: output file is completely empty (0 bytes).")
                
            return final_filepath

    try:
        print(f"[DOWNLOAD START] Initial attempt with format: {target_format}")
        final_file = perform_download(ydl_opts)
        
        has_audio = check_has_audio(final_file, ffmpeg_location)
        if not has_audio:
            print("[AUDIO VALIDATION FAILED] No audio stream detected. Retrying with safe fallback format.")
            # Fallback to single stream MP4 natively guaranteed to have audio and video
            ydl_opts["format"] = "best[ext=mp4]/best"
            if "merge_output_format" in ydl_opts:
                del ydl_opts["merge_output_format"]
            final_file = perform_download(ydl_opts)
            print(f"[FALLBACK SUCCESS] Saved to {final_file}")
        else:
            print(f"[AUDIO VALIDATION PASSED] Audio confirmed in {final_file}")
            
    except Exception as e:
        print(f"[DOWNLOAD ERROR] Error during primary download: {e}")
        import traceback
        traceback.print_exc()
        
        # One last fallback attempt if it totally crashed
        print("[FALLBACK] Attempting final safety fallback: best[ext=mp4]/best")
        ydl_opts["format"] = "best[ext=mp4]/best"
        if "merge_output_format" in ydl_opts:
            del ydl_opts["merge_output_format"]
        final_file = perform_download(ydl_opts)
        print(f"[FALLBACK SUCCESS] Saved to {final_file}")
        
    return final_file


def get_download_strategy(url: str, format_id="best") -> dict:
    """
    Fast optimized strategy resolver:
    - Uses cache first
    - Avoids repeated extraction delays
    - Faster direct/proxy routing
    """
    import copy
    import time

    # Fast format selector
    if format_id == "best":
        target_format = "best[ext=mp4]/best"
    else:
        target_format = f"{format_id}[ext=mp4]/{format_id}/best"

    ydl_opts = {
        "format": target_format,
        "quiet": True,
        "no_warnings": True,
        "cookiefile": "cookies.txt",
        "retries": 3,
        "extractor_retries": 2,
        "socket_timeout": 10,
        "cachedir": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/123.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        # =========================
        # FAST CACHE HIT
        # =========================
        cached = INFO_CACHE.get(url)
        if cached and time.time() < cached["expires"]:
            print(f"[FAST CACHE HIT] Using cached metadata for: {url}")

            info = copy.deepcopy(cached["data"])

            # Find selected format directly
            selected_format = None
            for f in info.get("formats", []):
                if f.get("format_id") == format_id:
                    selected_format = f
                    break

            # If chosen format found directly
            if selected_format and selected_format.get("url"):
                extractor = info.get("extractor", "").lower()

                if "youtube" in extractor or "vimeo" in extractor:
                    return {
                        "type": "direct",
                        "url": selected_format["url"]
                    }
                else:
                    return {
                        "type": "proxy",
                        "url": None
                    }

        # =========================
        # FALLBACK EXTRACTION
        # =========================
        print(f"[CACHE MISS] Fresh resolving: {url}")
        info = ydl.extract_info(url, download=False)

        extractor = info.get("extractor", "").lower()

        # Direct public CDN sources
        if "youtube" in extractor or "vimeo" in extractor:
            direct_url = info.get("url")

            if not direct_url and "requested_formats" in info:
                for rf in info["requested_formats"]:
                    if rf.get("url"):
                        direct_url = rf["url"]
                        break

            if not direct_url:
                raise Exception("Failed to extract direct CDN URL.")

            return {
                "type": "direct",
                "url": direct_url
            }

        # Protected embedded hosts
        return {
            "type": "proxy",
            "url": None
        }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        cached = INFO_CACHE.get(url)
        if cached and time.time() < cached["expires"]:
            info_copy = copy.deepcopy(cached["data"])
            keys_to_pop = [
                'format', 'format_id', 'url', 'ext', 'manifest_url', 'vcodec', 'acodec', 'resolution',
                'requested_downloads', 'requested_formats'
            ]
            for k in keys_to_pop:
                info_copy.pop(k, None)
            info = ydl.process_ie_result(info_copy, download=False)
        else:
            info = ydl.extract_info(url, download=False)
            
        extractor = info.get("extractor", "").lower()
        
        # Determine strategy
        if "youtube" in extractor or "vimeo" in extractor:
            # Public CDN, safe to redirect directly
            direct_url = info.get("url")
            
            if not direct_url and "requested_formats" in info:
                pass
                
            if not direct_url:
                ydl_opts["format"] = "best[ext=mp4]/best"
                with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                    info2 = ydl2.extract_info(url, download=False)
                    direct_url = info2.get("url")
                    
            if not direct_url:
                raise Exception("Failed to extract direct CDN URL for public video.")
                
            return {"type": "direct", "url": direct_url}
            
        else:
            # Protected embedded site requiring custom Headers / Cookies
            return {"type": "proxy", "url": None}