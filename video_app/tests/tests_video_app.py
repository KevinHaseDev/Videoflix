"""Tests for the video app: model, serializers, utils, views, and signals."""

from django.conf import settings
from django.test import TestCase

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
