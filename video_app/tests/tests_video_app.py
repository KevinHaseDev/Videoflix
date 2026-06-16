"""Tests for the video app: model, serializers, utils, views, and signals."""

import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

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


class VideoListViewTests(APITestCase):
    """Tests for GET /api/video/."""

    def setUp(self):
        """Create a viewer and resolve the list URL."""
        self.url = reverse("video-list")
        self.user = User.objects.create_user(
            username="viewer@example.com", is_active=True
        )

    def test_list_requires_authentication(self):
        """An anonymous request is rejected with 401."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_returns_videos_for_authenticated_user(self):
        """An authenticated request returns the video list."""
        Video.objects.create(title="A", description="d")
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class VideoStreamViewTests(APITestCase):
    """Tests for the HLS playlist and segment endpoints."""

    def setUp(self):
        """Authenticate a user and point MEDIA_ROOT at a temp directory."""
        self.user = User.objects.create_user(
            username="stream@example.com", is_active=True
        )
        self.client.force_authenticate(user=self.user)
        self.tmp = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=Path(self.tmp))
        self.override.enable()

    def tearDown(self):
        """Disable the settings override and remove the temp directory."""
        self.override.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _create_file(self, movie_id, resolution, name, content=b"data"):
        """Create an HLS output file under the temporary MEDIA_ROOT."""
        path = Path(self.tmp) / "videos" / str(movie_id) / resolution / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def test_m3u8_returns_playlist(self):
        """An existing manifest is served with the HLS content type."""
        self._create_file(1, "480p", "index.m3u8", b"#EXTM3U")
        url = reverse("video-m3u8", kwargs={"movie_id": 1, "resolution": "480p"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/vnd.apple.mpegurl")

    def test_m3u8_missing_returns_404(self):
        """A missing manifest returns 404."""
        url = reverse("video-m3u8", kwargs={"movie_id": 1, "resolution": "480p"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_segment_returns_ts_file(self):
        """An existing segment is served with the MP2T content type."""
        self._create_file(1, "480p", "000.ts", b"\x00\x01")
        url = reverse(
            "video-segment",
            kwargs={"movie_id": 1, "resolution": "480p", "segment": "000.ts"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "video/MP2T")

    def test_segment_missing_returns_404(self):
        """A missing segment returns 404."""
        url = reverse(
            "video-segment",
            kwargs={"movie_id": 1, "resolution": "480p", "segment": "000.ts"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
