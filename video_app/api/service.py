"""Business logic for the video app."""

import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files import File

from video_app.models import Video

RESOLUTIONS = {"480p": 480, "720p": 720, "1080p": 1080}


def extract_thumbnail(video_id: int) -> None:
    """Extract one frame at 00:00:01 and save it to Video.thumbnail."""
    video = Video.objects.get(pk=video_id)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                str(video.video_file.path),
                "-ss",
                "00:00:01",
                "-vframes",
                "1",
                "-y",
                str(tmp_path),
            ],
            check=True,
        )
        with tmp_path.open("rb") as f:
            video.thumbnail.save(f"{video_id}.jpg", File(f), save=True)
    finally:
        tmp_path.unlink(missing_ok=True)


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
    """Run ffmpeg to transcode the input into an HLS playlist at the given height."""
    cmd = [
        "ffmpeg",
        "-i",
        str(input_path),
        "-vf",
        f"scale=-2:{height}",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-hls_time",
        "10",
        "-hls_list_size",
        "0",
        "-hls_segment_filename",
        str(out_dir / "seg%04d.ts"),
        str(out_dir / "index.m3u8"),
    ]
    subprocess.run(cmd, check=True)
