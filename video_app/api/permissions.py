"""Permission classes for video endpoints."""
from rest_framework.permissions import IsAuthenticated


class IsAuthenticatedVideo(IsAuthenticated):
    """Require authentication to access video content (list, m3u8 playlists, segments)."""
