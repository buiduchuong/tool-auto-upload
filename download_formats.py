"""Shared yt-dlp format rules for downloads that need video and audio."""

from __future__ import annotations


# ``res:1080`` understands both 1920x1080 landscape and 1080x1920 portrait.
# Prefer separate video/audio, then a combined stream that explicitly has both.
# There is intentionally no video-only fallback.
FULL_HD_WITH_AUDIO_FORMAT = "bv+ba/b[vcodec!=none][acodec!=none]"


def full_hd_with_audio_args() -> list[str]:
    """Return fresh args so callers can safely extend the result."""

    return [
        "-f",
        FULL_HD_WITH_AUDIO_FORMAT,
        "-S",
        "res:1080",
        "--merge-output-format",
        "mp4",
        "--remux-video",
        "mp4",
    ]
