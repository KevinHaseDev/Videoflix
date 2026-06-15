"""URL configuration for the video app API."""
from django.urls import path

from video_app.api.views import VideoListView, VideoM3U8View

urlpatterns = [
    path('video/', VideoListView.as_view(), name='video-list'),
    path('video/<int:movie_id>/<str:resolution>/index.m3u8', VideoM3U8View.as_view(), name='video-m3u8'),
]
