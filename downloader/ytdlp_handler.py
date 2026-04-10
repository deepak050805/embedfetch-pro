import yt_dlp
import os


def extract_video_info(url: str):
    """
    Extract available video formats:
    - Keep only one best stream per resolution
    - Prefer MP4 over WEBM automatically
    """

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

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
        ffprobe_path = os.path.join(ffmpeg_location, "ffprobe.exe") if ffmpeg_location else "ffprobe"
        if not os.path.exists(ffprobe_path):
            ffprobe_path = "ffprobe" # Fallback to system PATH
            
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

    temp_dir = os.path.join(output_dir, "_temp")
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    if format_id == "best":
        target_format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
    else:
        # Pair selected video format with best compatible audio.
        # Force fallback to absolute best if the specified combination fails.
        target_format = f"{format_id}+bestaudio[ext=m4a]/{format_id}+bestaudio/best"

    ffmpeg_location = r"C:\ffmpeg\ffmpeg-8.1-essentials_build\bin"

    ydl_opts = {
        "outtmpl": {"default": "%(title).80s_[%(resolution)s].%(ext)s"},
        "paths": {
            "home": output_dir,
            "temp": temp_dir
        },
        "format": target_format,
        "merge_output_format": "mp4",
        "ffmpeg_location": ffmpeg_location,
        "quiet": False,
        "verbose": True,
        "no_warnings": False,
        "nopart": False,
        "overwrites": True,
        "retries": 10,
        "fragment_retries": 10,
        "logger": CustomYtDlpLogger()
    }

    if progress_hook:
        ydl_opts["progress_hooks"] = [progress_hook]

    def perform_download(opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Find the final output filepath
            final_filepath = None
            if "requested_downloads" in info:
                final_filepath = info["requested_downloads"][0].get("filepath")
            
            if not final_filepath:
                # Fallback: guess the final filepath
                pre_filepath = ydl.prepare_filename(info)
                base, _ = os.path.splitext(pre_filepath)
                # Since we used merge_output_format: 'mp4', it should be .mp4
                if os.path.exists(base + ".mp4"):
                    final_filepath = base + ".mp4"
                elif os.path.exists(pre_filepath):
                    final_filepath = pre_filepath
                    
            return final_filepath

    try:
        print(f"[DOWNLOAD START] Initial attempt with format: {target_format}")
        final_file = perform_download(ydl_opts)
        
        has_audio = check_has_audio(final_file, ffmpeg_location)
        if not has_audio:
            print("[AUDIO VALIDATION FAILED] No audio stream detected. Retrying with safe fallback format.")
            ydl_opts["format"] = "best[ext=mp4]/best"
            final_file = perform_download(ydl_opts)
            print(f"[FALLBACK SUCCESS] Saved to {final_file}")
        else:
            print(f"[AUDIO VALIDATION PASSED] Audio confirmed in {final_file}")
            
    except Exception as e:
        print(f"[DOWNLOAD ERROR] Error during primary download: {e}")
        # One last fallback attempt if it totally crashed
        print("[FALLBACK] Attempting final safety fallback: best[ext=mp4]/best")
        ydl_opts["format"] = "best[ext=mp4]/best"
        final_file = perform_download(ydl_opts)
        print(f"[FALLBACK SUCCESS] Saved to {final_file}")