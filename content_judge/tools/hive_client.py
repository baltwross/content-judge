"""
Hive Moderation API client for AI-generated video detection.

Uses the V3 Playground endpoint for AI-generated and deepfake content detection.
Hive achieves 96-99% accuracy on AI-generated video detection and supports
100+ generators including Sora, Runway, Pika, Kling.
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

HIVE_V3_ENDPOINT = "https://api.thehive.ai/api/v3/hive/ai-generated-and-deepfake-content-detection"


def hive_detect_from_url(content_url: str, api_key: str) -> dict | None:
    """
    Submit a URL to Hive V3 for AI detection.
    Used for YouTube videos (pass the direct stream URL resolved by yt-dlp).
    """
    try:
        response = requests.post(
            HIVE_V3_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "media_metadata": True,
                "input": [{"media_url": content_url}],
            },
            timeout=60,
        )
        response.raise_for_status()
        return _parse_hive_v3_response(response.json())
    except Exception as e:
        logger.warning(f"Hive URL detection failed: {e}")
        return None


def hive_detect_from_file(file_path: str, api_key: str) -> dict | None:
    """
    Upload a local file to Hive V3 for AI detection.
    Uses multipart form-data upload.
    """
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                HIVE_V3_ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"media": (file_path, f)},
                timeout=120,
            )
        response.raise_for_status()
        return _parse_hive_v3_response(response.json())
    except Exception as e:
        logger.warning(f"Hive file detection failed: {e}")
        return None


def hive_detect_youtube(youtube_url: str, api_key: str) -> dict | None:
    """
    Detect AI generation in a YouTube video via Hive.

    Primary path: resolve stream URL via yt-dlp, pass to Hive.
    Fallback: download short clip via yt-dlp, upload to Hive.
    """
    from content_judge.loaders.video import resolve_youtube_stream_url

    # Primary: resolve stream URL (no download, ~1-2 seconds)
    stream_url = resolve_youtube_stream_url(youtube_url)
    if stream_url:
        result = hive_detect_from_url(stream_url, api_key)
        if result is not None:
            return result
        logger.info("Hive rejected stream URL, trying clip download fallback")

    # Fallback: download short clip and upload
    return _hive_youtube_clip_fallback(youtube_url, api_key)


def _hive_youtube_clip_fallback(youtube_url: str, api_key: str) -> dict | None:
    """Download a short clip via yt-dlp and upload to Hive."""
    import tempfile
    import os

    try:
        import yt_dlp

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "clip.mp4")
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "format": "worst[ext=mp4]",
                "outtmpl": output_path,
                "download_ranges": lambda info, ydl: [{"start_time": 0, "end_time": 10}],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])

            if os.path.exists(output_path):
                return hive_detect_from_file(output_path, api_key)
    except Exception as e:
        logger.warning(f"Hive YouTube clip fallback failed: {e}")

    return None


def _parse_hive_v3_response(data: dict) -> dict | None:
    """
    Parse Hive V3 API response for AI detection results.
    V3 uses "value" (not "score") and returns per-frame results.
    Also returns generator-specific scores (sora, pika, kling, etc.).
    """
    try:
        outputs = data.get("output", [])
        if not outputs:
            return None

        # V3 returns per-frame results; take the first frame
        first = outputs[0]
        classes = first.get("classes", [])

        ai_score = None
        generator = None
        best_generator_score = 0.0

        # Known generator class names in Hive V3
        generator_names = {"sora", "pika", "haiper", "kling", "luma", "runway", "stable_diffusion", "midjourney", "dalle"}

        for cls in classes:
            class_name = cls.get("class", "")
            value = cls.get("value", 0.0)

            if class_name == "ai_generated":
                ai_score = value
            elif class_name in generator_names and value > best_generator_score:
                best_generator_score = value
                generator = class_name

        # Only report generator if it has meaningful confidence
        if best_generator_score < 0.01:
            generator = None

        if ai_score is not None:
            return {"ai_score": ai_score, "generator": generator}
    except (IndexError, KeyError, TypeError) as e:
        logger.warning(f"Failed to parse Hive V3 response: {e}")

    return None
