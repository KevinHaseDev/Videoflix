"""Path helpers for the video app API."""
from pathlib import Path

from django.conf import settings


def get_m3u8_path(movie_id: int, resolution: str) -> Path:
    return settings.MEDIA_ROOT / "videos" / str(movie_id) / resolution / "index.m3u8"


def get_segment_path(movie_id: int, resolution: str, segment: str) -> Path:
    return settings.MEDIA_ROOT / "videos" / str(movie_id) / resolution / segment
