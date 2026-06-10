from django.apps import AppConfig


class VideoAppConfig(AppConfig):
    name = 'video_app'

    def ready(self):
        import video_app.api.signals
