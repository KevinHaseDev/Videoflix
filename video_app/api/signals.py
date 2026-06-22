"""Signals for the video app."""

import shutil
from pathlib import Path

import django_rq
from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from video_app.api.service import convert_video_to_hls, extract_thumbnail
from video_app.models import Video


@receiver(post_save, sender=Video)
def video_post_save(sender, instance, created, **kwargs):
    """Enqueue thumbnail extraction and HLS conversion when a new video is uploaded.

    Both jobs read the uploaded video file, so they are only enqueued when a
    file is actually present; otherwise ffmpeg would fail on an empty path.
    """
    if created and instance.video_file:
        queue = django_rq.get_queue("default")
        queue.enqueue(extract_thumbnail, instance.pk)
        queue.enqueue(convert_video_to_hls, instance.pk)


@receiver(post_delete, sender=Video)
def video_delete_signal(sender, instance, **kwargs):
    """Delete the thumbnail, video file and HLS output directory on deletion."""
    if instance.video_file:
        video_path = Path(instance.video_file.path)
        if video_path.is_file():
            video_path.unlink()
    if instance.thumbnail:
        thumb_path = Path(instance.thumbnail.path)
        if thumb_path.is_file():
            thumb_path.unlink()
    hls_dir = settings.MEDIA_ROOT / "videos" / str(instance.pk)
    if hls_dir.is_dir():
        shutil.rmtree(hls_dir)
