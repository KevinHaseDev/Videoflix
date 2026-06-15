"""Business logic for the video app."""
import subprocess
from pathlib import Path

from django.conf import settings

from video_app.models import Video

RESOLUTIONS = {'480p': 480, '720p': 720, '1080p': 1080}


def convert_video_to_hls(video_id: int) -> None:
    """Convert a video to HLS streams at 480p, 720p, and 1080p."""
    video = Video.objects.get(pk=video_id)
    input_path = Path(video.video_file.path)
    base_dir = settings.MEDIA_ROOT / "videos" / str(video_id)

    for label, height in RESOLUTIONS.items():
        out_dir = base_dir / label
        out_dir.mkdir(parents=True, exist_ok=True)
        _run_ffmpeg(input_path, out_dir, height)


def _run_ffmpeg(input_path: Path, out_dir: Path, height: int) -> None:
    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-vf", f"scale=-2:{height}",
        "-c:v", "libx264", "-c:a", "aac",
        "-hls_time", "10", "-hls_list_size", "0",
        "-hls_segment_filename", str(out_dir / "seg%04d.ts"),
        str(out_dir / "index.m3u8"),
    ]
    subprocess.run(cmd, check=True)
