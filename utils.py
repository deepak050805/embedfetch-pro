import shutil
import time

_FFMPEG_AVAILABLE = None

def check_ffmpeg_installed() -> bool:
    """
    Checks if ffmpeg is available in the system PATH, caching the result.
    """
    global _FFMPEG_AVAILABLE
    if _FFMPEG_AVAILABLE is None:
        start_t = time.time()
        _FFMPEG_AVAILABLE = shutil.which('ffmpeg') is not None
        print(f"FFmpeg check took {time.time() - start_t:.4f}s")
    return _FFMPEG_AVAILABLE
