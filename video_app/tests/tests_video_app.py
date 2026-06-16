"""Tests for the video app: model, serializers, utils, views, and signals."""

from django.conf import settings
from django.test import RequestFactory, TestCase

from video_app.api.serializer import VideoSerializer
from video_app.api.utils import get_m3u8_path, get_segment_path
from video_app.models import Video


class VideoModelTests(TestCase):
    """Tests for the Video model."""

    def test_str_returns_title(self):
        """__str__ returns the video title."""
        video = Video.objects.create(title="My Movie", description="Desc")
        self.assertEqual(str(video), "My Movie")


class VideoPathHelperTests(TestCase):
    """Tests for the HLS path helper functions."""

    def test_m3u8_path(self):
        """get_m3u8_path builds the manifest path under MEDIA_ROOT."""
        expected = settings.MEDIA_ROOT / "videos" / "1" / "480p" / "index.m3u8"
        self.assertEqual(get_m3u8_path(1, "480p"), expected)

    def test_segment_path(self):
        """get_segment_path builds the segment path under MEDIA_ROOT."""
        expected = settings.MEDIA_ROOT / "videos" / "1" / "480p" / "000.ts"
        self.assertEqual(get_segment_path(1, "480p", "000.ts"), expected)


class VideoSerializerTests(TestCase):
    """Tests for VideoSerializer.get_thumbnail_url."""

    def test_no_thumbnail_returns_none(self):
        """A video without a thumbnail serializes thumbnail_url as None."""
        video = Video.objects.create(title="No Thumb", description="d")
        data = VideoSerializer(video).data
        self.assertIsNone(data["thumbnail_url"])

    def test_thumbnail_with_request_is_absolute(self):
        """With a request in context, the thumbnail URL is absolute."""
        video = Video.objects.create(
            title="Thumb", description="d", thumbnail="thumbnails/t.jpg"
        )
        request = RequestFactory().get("/")
        data = VideoSerializer(video, context={"request": request}).data
        self.assertTrue(data["thumbnail_url"].startswith("http"))
        self.assertIn("thumbnails/t.jpg", data["thumbnail_url"])

    def test_thumbnail_without_request_is_relative(self):
        """Without a request in context, the thumbnail URL is relative."""
        video = Video.objects.create(
            title="Thumb", description="d", thumbnail="thumbnails/t.jpg"
        )
        data = VideoSerializer(video).data
        self.assertEqual(data["thumbnail_url"], video.thumbnail.url)
