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
        logger.debug("Hive URL detection: sending URL (first 120 chars): %s", content_url[:120])
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
        logger.debug("Hive URL detection: HTTP %s, response size: %d bytes", response.status_code, len(response.content))
        response.raise_for_status()
        raw = response.json()
        logger.debug("Hive URL detection: raw response keys: %s", list(raw.keys()))
        if raw.get("output"):
            logger.debug("Hive URL detection: output[0] keys: %s", list(raw["output"][0].keys()))
            logger.debug("Hive URL detection: all classes: %s", raw["output"][0].get("classes", []))
        return _parse_hive_v3_response(raw)
    except Exception as e:
        logger.warning(f"Hive URL detection failed: {e}")
        return None


def hive_detect_from_file(file_path: str, api_key: str) -> dict | None:
    """
    Upload a local file to Hive V3 for AI detection.
    Uses multipart form-data upload.
    """
    try:
        import os

        file_size = os.path.getsize(file_path)
        logger.debug("Hive file detection: uploading %s (%d bytes)", file_path, file_size)
        with open(file_path, "rb") as f:
            response = requests.post(
                HIVE_V3_ENDPOINT,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"media": (file_path, f)},
                timeout=120,
            )
        logger.debug("Hive file detection: HTTP %s, response size: %d bytes", response.status_code, len(response.content))
        if response.status_code != 200:
            logger.warning("Hive file detection: error response body: %s", response.text[:500])
        response.raise_for_status()
        raw = response.json()
        logger.debug("Hive file detection: all classes: %s", raw.get("output", [{}])[0].get("classes", []) if raw.get("output") else "no output")
        return _parse_hive_v3_response(raw)
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

    logger.debug("Hive YouTube detection: resolving stream URL for %s", youtube_url)

    # Primary: resolve stream URL (no download, ~1-2 seconds)
    stream_url = resolve_youtube_stream_url(youtube_url)
    if stream_url:
        logger.debug("Hive YouTube detection: resolved stream URL (first 120 chars): %s", stream_url[:120])
        # Log whether this looks like a video or audio stream
        if "mime=video" in stream_url:
            logger.debug("Hive YouTube detection: stream appears to be VIDEO")
        elif "mime=audio" in stream_url:
            logger.debug("Hive YouTube detection: stream appears to be AUDIO-ONLY")
        else:
            logger.debug("Hive YouTube detection: stream MIME type unclear from URL")
        result = hive_detect_from_url(stream_url, api_key)
        if result is not None:
            logger.debug("Hive YouTube detection: URL path returned result: %s", result)
            return result
        logger.info("Hive rejected stream URL, trying clip download fallback")
    else:
        logger.warning("Hive YouTube detection: failed to resolve stream URL, going straight to fallback")

    # Fallback: download short clip and upload
    logger.debug("Hive YouTube detection: trying clip download fallback")
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
                "format": "bestvideo[ext=mp4][height<=720]",
                "outtmpl": output_path,
                "download_ranges": lambda info, ydl: [{"start_time": 5, "end_time": 35}],
            }
            logger.debug("Hive fallback: downloading 30s clip with format='bestvideo[ext=mp4][height<=720]'")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])

            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                logger.debug("Hive fallback: downloaded clip %s (%d bytes)", output_path, file_size)
                return hive_detect_from_file(output_path, api_key)
            else:
                logger.warning("Hive fallback: clip file was not created at %s", output_path)
    except Exception as e:
        logger.warning(f"Hive YouTube clip fallback failed: {e}")

    return None


def _parse_hive_v3_response(data: dict) -> dict | None:
    """
    Parse Hive V3 API response for AI detection results.

    For video, Hive returns per-frame results (1 FPS sampling). Per Hive docs,
    a video should be flagged as AI-generated if ANY frame scores >= 0.9.
    We aggregate by taking the max ai_score across all frames.

    Ref: https://docs.thehive.ai/docs/ai-image-and-video-detection
    Ref: https://docs.thehive.ai/reference/ai-generated-image-and-video-detection-1
    """
    try:
        outputs = data.get("output", [])
        if not outputs:
            return None

        best_ai_score = None
        best_generator = None
        best_generator_score = 0.0

        # All generator class names documented by Hive (70+).
        # Ref: https://docs.thehive.ai/reference/ai-generated-image-and-video-detection-1
        generator_names = {
            # Video generators
            "sora", "sora2", "pika", "haiper", "kling", "luma", "hedra",
            "runway", "hailuo", "mochi", "hallo", "hunyuan", "cogvideos",
            "flashvideo", "cosmos", "wan", "veo3", "seedance", "moonvalley",
            "higgsfield", "heygen", "sanavideo", "viduq2",
            # Image generators
            "flux", "flux2", "stable_diffusion", "stablediffusion",
            "stablediffusionxl", "stablediffusioninpaint", "sdxlinpaint",
            "midjourney", "dalle", "adobefirefly", "ideogram", "recraft",
            "leonardo", "imagen", "imagen4", "4o", "grok", "grokimagine",
            "gemini", "gemini3", "qwen", "bingimagecreator",
            # Other generators
            "lcm", "pixart", "glide", "amused", "stablecascade", "deepfloyd",
            "gan", "vqdiffusion", "kandinsky", "wuerstchen", "titan", "sana",
            "emu3", "omnigen", "transpixar", "janus", "dmd2", "switti",
            "infinity", "krea", "reve", "seedream", "mai", "lucid",
            "luminagpt", "var", "liveportrait", "mcnet", "pyramidflows",
            "sadtalker", "aniportrait", "makeittalk", "bria", "zimage",
            "gptimage1_5",
        }

        logger.debug("Hive: analyzing %d frame(s)", len(outputs))

        # Aggregate across all frames — take the max ai_score
        for i, frame in enumerate(outputs):
            classes = frame.get("classes", [])

            frame_ai_score = None
            frame_best_gen = None
            frame_best_gen_score = 0.0

            for cls in classes:
                class_name = cls.get("class", "")
                # V3 uses "value"; fall back to "score" for compatibility
                value = cls.get("value", cls.get("score", 0.0))

                if class_name == "ai_generated":
                    frame_ai_score = value
                elif class_name in generator_names and value > frame_best_gen_score:
                    frame_best_gen_score = value
                    frame_best_gen = class_name

            if frame_ai_score is not None:
                if best_ai_score is None or frame_ai_score > best_ai_score:
                    best_ai_score = frame_ai_score
                    best_generator = frame_best_gen
                    best_generator_score = frame_best_gen_score
                    logger.debug(
                        "Hive frame %d (t=%s): new best ai_score=%.4f, generator=%s(%.4f)",
                        i, frame.get("time", "?"), frame_ai_score,
                        frame_best_gen, frame_best_gen_score,
                    )

        # Only report generator if it has meaningful confidence
        if best_generator_score < 0.01:
            best_generator = None

        if best_ai_score is not None:
            logger.debug(
                "Hive final: ai_score=%.4f, generator=%s (%.4f), frames=%d",
                best_ai_score, best_generator, best_generator_score, len(outputs),
            )
            return {"ai_score": best_ai_score, "generator": best_generator}
        else:
            logger.warning("Hive response had no 'ai_generated' class in any frame")
    except (IndexError, KeyError, TypeError) as e:
        logger.warning(f"Failed to parse Hive V3 response: {e}")

    return None
