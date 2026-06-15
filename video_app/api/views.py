from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from video_app.models import Video
from video_app.api.serializer import VideoSerializer


class VideoListView(ListAPIView):
    queryset = Video.objects.all()
    serializer_class = VideoSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
