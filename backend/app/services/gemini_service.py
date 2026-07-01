"""
YouTube video recommendations via OpenRouter (google/gemini-2.5-flash).
Fetches actual video links and thumbnails using YouTube Data API v3.
"""
import json
import logging
import re
import urllib.parse
from typing import Optional, Dict, Any

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL = "google/gemini-2.5-flash"
_YOUTUBE_SEARCH_URL = "https://www.youtube.com/results?search_query="
_YOUTUBE_DATA_API = "https://www.googleapis.com/youtube/v3"


def _parse_iso_duration(iso: str) -> Optional[str]:
    """Convert ISO 8601 duration (e.g. PT45M30S) to human-readable (e.g. 45 min)."""
    if not iso:
        return None
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    if hours:
        return f"{hours}h {minutes}min" if minutes else f"{hours}h"
    return f"{minutes} min" if minutes else None


async def search_youtube_video(search_query: str) -> Optional[Dict[str, Any]]:
    """
    Call YouTube Data API v3 to find the best matching video.
    Returns video_id, direct video_url, thumbnail_url, title, channel, and duration.
    Returns None if YOUTUBE_API_KEY is unset or the call fails.
    """
    api_key = settings.YOUTUBE_API_KEY
    if not api_key:
        return None

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            # Step 1: Search for the video
            search_resp = await client.get(
                f"{_YOUTUBE_DATA_API}/search",
                params={
                    "part": "snippet",
                    "q": search_query,
                    "type": "video",
                    "maxResults": 1,
                    "relevanceLanguage": "en",
                    "key": api_key,
                },
            )
            if search_resp.status_code != 200:
                logger.warning("YouTube search API returned %d", search_resp.status_code)
                return None

            items = search_resp.json().get("items", [])
            if not items:
                return None

            item = items[0]
            video_id: str = item["id"]["videoId"]
            snippet: dict = item["snippet"]

            thumbnails = snippet.get("thumbnails", {})
            thumbnail_url = (
                thumbnails.get("high", {}).get("url")
                or thumbnails.get("medium", {}).get("url")
                or thumbnails.get("default", {}).get("url")
            )

            # Step 2: Fetch video duration
            duration_str: Optional[str] = None
            videos_resp = await client.get(
                f"{_YOUTUBE_DATA_API}/videos",
                params={
                    "part": "contentDetails",
                    "id": video_id,
                    "key": api_key,
                },
            )
            if videos_resp.status_code == 200:
                video_items = videos_resp.json().get("items", [])
                if video_items:
                    iso = video_items[0].get("contentDetails", {}).get("duration", "")
                    duration_str = _parse_iso_duration(iso)

            return {
                "video_id": video_id,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail_url": thumbnail_url,
                "title": snippet.get("title", "").strip(),
                "channel": snippet.get("channelTitle", "").strip() or None,
                "duration": duration_str,
            }

    except Exception as exc:
        logger.warning("YouTube Data API call failed: %s", exc)
        return None


def _build_fallback_recommendation(
    user_query: str,
    subject: str,
    chapter_title: str = "",
) -> Dict[str, Any]:
    topic = chapter_title.strip() or user_query.strip()
    safe_subject = (subject or "Class 9").strip()
    search_query = f"Class 9 {safe_subject} {topic} NCERT explanation".strip()
    search_url = _YOUTUBE_SEARCH_URL + urllib.parse.quote_plus(search_query)
    return {
        "title": search_query,
        "search_query": search_query,
        "search_url": search_url,
        "video_url": search_url,
        "reason": "Search YouTube for NCERT-aligned visual explanations on this topic.",
        "thumbnail_url": None,
        "duration": None,
        "channel": None,
    }


async def get_youtube_recommendation(
    user_query: str,
    subject: str,
    chapter_title: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Ask Gemini to suggest the best YouTube video for a Class 9 student's question,
    then use YouTube Data API v3 to fetch the real video link and thumbnail.
    Falls back to a YouTube search URL when either API key is missing or a call fails.
    """
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        logger.info("OPENROUTER_API_KEY not configured, using fallback YouTube search.")
        return _build_fallback_recommendation(user_query, subject, chapter_title)

    topic_hint = f" (chapter: {chapter_title})" if chapter_title else ""
    prompt = (
        f"A Class 9 HBSE student studying {subject}{topic_hint} asked:\n"
        f'"{user_query}"\n\n'
        "Suggest the SINGLE BEST YouTube video that would help this student understand the concept clearly.\n\n"
        "Respond ONLY with valid JSON (no markdown, no code blocks):\n"
        "{\n"
        '  "search_query": "exact YouTube search terms that will find this specific video",\n'
        '  "video_title": "title of the recommended video",\n'
        '  "channel": "channel name (e.g., Shobhit Nirwan)",\n'
        '  "duration_estimate": "approximate duration in minutes (e.g., 45 min)",\n'
        '  "reason": "one clear sentence explaining why this video is perfect for this student"\n'
        "}"
    )

    payload = {
        "model": _MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 2048,
        "temperature": 0.7,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://hbse-learn.app",
        "X-Title": "HBSE Adaptive Learning",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(_OPENROUTER_URL, json=payload, headers=headers)

        if r.status_code != 200:
            logger.info("OpenRouter returned %d, using fallback.", r.status_code)
            return _build_fallback_recommendation(user_query, subject, chapter_title)

        text = (
            r.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if not json_match:
            logger.info("OpenRouter response not parseable, using fallback.")
            return _build_fallback_recommendation(user_query, subject, chapter_title)

        rec = json.loads(json_match.group())
        search_query = rec.get("search_query", "").strip()
        if not search_query:
            return _build_fallback_recommendation(user_query, subject, chapter_title)

        # Try to get a real video via YouTube Data API v3
        yt = await search_youtube_video(search_query)

        if yt:
            return {
                "title": yt["title"] or rec.get("video_title", search_query).strip() or search_query,
                "search_query": search_query,
                "search_url": _YOUTUBE_SEARCH_URL + urllib.parse.quote_plus(search_query),
                "video_url": yt["video_url"],
                "thumbnail_url": yt["thumbnail_url"],
                "channel": yt["channel"] or rec.get("channel", "").strip() or None,
                "duration": yt["duration"] or rec.get("duration_estimate", "").strip() or None,
                "reason": rec.get("reason", "Watch this for a visual explanation.").strip(),
            }

        # YouTube API unavailable — fall back to search URL with Gemini metadata
        search_url = _YOUTUBE_SEARCH_URL + urllib.parse.quote_plus(search_query)
        return {
            "title": rec.get("video_title", search_query).strip() or search_query,
            "search_query": search_query,
            "search_url": search_url,
            "video_url": search_url,
            "thumbnail_url": None,
            "channel": rec.get("channel", "").strip() or None,
            "duration": rec.get("duration_estimate", "").strip() or None,
            "reason": rec.get("reason", "Watch this for a visual explanation.").strip(),
        }

    except Exception as exc:
        logger.info("YouTube recommendation failed, using fallback: %s", exc)
        return _build_fallback_recommendation(user_query, subject, chapter_title)
