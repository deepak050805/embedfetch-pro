import yt_dlp

def fetch_playlist(url: str):
    ydl_opts = {
        'extract_flat': 'in_playlist',
        'quiet': True,
        'no_warnings': True
    }

    videos = []

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        if 'entries' in info:
            for entry in info['entries']:
                videos.append({
                    'title': entry.get('title', 'Unknown Title'),
                    'url': entry.get('url', ''),
                    'duration': entry.get('duration', 0)
                })
        else:
            videos.append({
                'title': info.get('title', 'Unknown Title'),
                'url': url,
                'duration': info.get('duration', 0)
            })

    return videos