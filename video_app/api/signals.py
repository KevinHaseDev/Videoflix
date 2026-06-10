"""signals for the video app."""
from ..models import Video
from django.dispatch import receiver
from django.db.models.signals import post_save, post_delete
import os

@receiver(post_save, sender=Video)
def video_post_save(sender, instance, created, **kwargs):
    """Signal handler for post_save of Video model."""
    print("Video post save signal triggered")
    if created:
        print("New video created")

@receiver(post_delete, sender=Video)
def video_delete_signal(sender, instance, **kwargs):
    """Signal handler for post_delete of Video model."""
    if instance.video_file:
        if os.path.isfile(instance.video_file.path):
            os.remove(instance.video_file.path)
