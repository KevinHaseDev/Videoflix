"""Views for the video app API."""
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.http import FileResponse, Http404

from video_app.models import Video
from video_app.api.serializer import VideoSerializer
from video_app.api.utils import get_m3u8_path


class VideoListView(ListAPIView):
    """Returns a list of all videos."""

    queryset = Video.objects.all()
    serializer_class = VideoSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context


class VideoM3U8View(APIView):
    """Serves the HLS master playlist for a given video and resolution."""

    permission_classes = [IsAuthenticated]

    def get(self, request, movie_id, resolution):
        path = get_m3u8_path(movie_id, resolution)
        if not path.is_file():
            raise Http404
        return FileResponse(path.open('rb'), content_type='application/vnd.apple.mpegurl')
