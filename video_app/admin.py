"""Admin registrations for the video app."""

from django.contrib import admin

from .models import Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    """Admin list configuration for the Video model."""

    list_display = ("title", "category", "created_at")
