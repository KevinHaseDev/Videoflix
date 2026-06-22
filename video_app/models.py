"""Django models for the video app."""

from django.db import models


class Video(models.Model):
    """Model representing a video."""

    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=80)
    description = models.TextField(max_length=500)
    video_file = models.FileField(upload_to="videos/", null=True)
    thumbnail = models.ImageField(
        upload_to="thumbnails/", null=True, blank=True)
    category = models.CharField(max_length=50, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Video"
        verbose_name_plural = "Videos"

    def __str__(self):
        """String representation of the Video model."""
        return self.title
