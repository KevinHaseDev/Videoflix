"""Serializers for the video app."""
from rest_framework import serializers

from video_app.models import Video


class VideoSerializer(serializers.ModelSerializer):
    """Serializes Video instances for the list endpoint."""

    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = ['id', 'created_at', 'title', 'description', 'thumbnail_url', 'category']

    def get_thumbnail_url(self, obj):
        """Return the absolute URL of the thumbnail, or None if not set."""
        if not obj.thumbnail:
            return None
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(obj.thumbnail.url)
        return obj.thumbnail.url
