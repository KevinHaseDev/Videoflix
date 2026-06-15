"""signals for the video app."""
import shutil
from pathlib import Path

import django_rq
from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from video_app.api.service import convert_video_to_hls
from video_app.models import Video


@receiver(post_save, sender=Video)
def video_post_save(sender, instance, created, **kwargs):
    """Enqueue HLS conversion when a new video is uploaded."""
    if created:
        django_rq.get_queue('default').enqueue(convert_video_to_hls, instance.pk)


@receiver(post_delete, sender=Video)
def video_delete_signal(sender, instance, **kwargs):
    """Delete the video file and HLS output directory on deletion."""
    if instance.video_file:
        video_path = Path(instance.video_file.path)
        if video_path.is_file():
            video_path.unlink()
    hls_dir = settings.MEDIA_ROOT / "videos" / str(instance.pk)
    if hls_dir.is_dir():
        shutil.rmtree(hls_dir)
