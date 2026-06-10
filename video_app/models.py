"""django models for the video app."""
from django.db import models
from datetime import date


# Create your models here.
class Video(models.Model):
    """Model representing a video."""
    created_at = models.DateField(default=date.today)
    title = models.CharField(max_length=80)
    description = models.TextField(max_length=500)
    video_file = models.FileField(upload_to='videos/', null=True, blank=True)
    thumbnail = models.ImageField(upload_to='thumbnails/', null=True, blank=True)
    category = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        """String representation of the Video model."""
        return self.title