"""App configuration for the video app."""

from django.apps import AppConfig


class VideoAppConfig(AppConfig):
    """Default configuration that wires up the video app's signal handlers."""

    name = "video_app"

    def ready(self):
        """Import signal handlers so they are registered on app startup."""
        import video_app.api.signals  # pylint: disable=import-outside-toplevel,unused-import
