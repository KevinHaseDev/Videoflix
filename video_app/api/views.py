"""Views for the video app API."""

from django.http import FileResponse, Http404
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView

from video_app.api.permissions import IsAuthenticatedVideo
from video_app.api.serializer import VideoSerializer
from video_app.api.utils import get_m3u8_path, get_segment_path
from video_app.models import Video


class VideoListView(ListAPIView):
    """Returns a list of all videos."""

    queryset = Video.objects.all()
    serializer_class = VideoSerializer
    permission_classes = [IsAuthenticatedVideo]

    def get_serializer_context(self):
        """Add the request to the serializer context for absolute thumbnail URLs."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class VideoM3U8View(APIView):
    """Serves the HLS master playlist for a given video and resolution."""

    permission_classes = [IsAuthenticatedVideo]

    def get(self, _request, movie_id, resolution):
        """Return the HLS playlist file."""
        path = get_m3u8_path(movie_id, resolution)
        if not path.is_file():
            raise Http404
        return FileResponse(path.open("rb"), content_type="application/vnd.apple.mpegurl")


class VideoSegmentView(APIView):
    """Serves a single HLS transport stream segment."""

    permission_classes = [IsAuthenticatedVideo]

    def get(self, _request, movie_id, resolution, segment):
        """Return the .ts segment file."""
        path = get_segment_path(movie_id, resolution, segment)
        if not path.is_file():
            raise Http404
        return FileResponse(path.open("rb"), content_type="video/MP2T")
