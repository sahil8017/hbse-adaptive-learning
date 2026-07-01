# Utility functions for endpoints
import os
import json
import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Allowlist pattern: only letters, digits, underscores, and hyphens.
# Prevents path-traversal via ".." or "/" in user-supplied URL segments.
_SAFE_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_\-]{1,80}$")


def _validate_path_segment(value: str, label: str) -> str:
    """Raise ValueError if the segment contains characters that could traverse the filesystem."""
    if not _SAFE_PATH_SEGMENT_RE.match(value):
        raise ValueError(f"Invalid {label}: must be alphanumeric (underscores/hyphens allowed, max 80 chars).")
    return value


def _normalize_question_options(raw_options: Any) -> List[str]:
    if isinstance(raw_options, list):
        return [str(opt) for opt in raw_options]
    if isinstance(raw_options, str):
        try:
            parsed = json.loads(raw_options)
            if isinstance(parsed, list):
                return [str(opt) for opt in parsed]
        except (json.JSONDecodeError, TypeError):
            try:
                fixed = re.sub(r'\\(?![\\"])', r'\\\\', raw_options)
                parsed = json.loads(fixed)
                if isinstance(parsed, list):
                    return [str(opt) for opt in parsed]
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse question options payload: %r", raw_options)
    return []


def _load_textbook_chapter_data(book_id: str, chapter_id: str) -> Optional[Dict[str, Any]]:
    try:
        _validate_path_segment(book_id, "book_id")
        _validate_path_segment(chapter_id, "chapter_id")
    except ValueError as exc:
        logger.warning("Rejected unsafe path segment: %s", exc)
        return None

    textbook_path = os.path.join("data", "textbook", book_id.lower(), f"{chapter_id}.json")
    # Resolve to an absolute path and confirm it stays within the data/textbook directory.
    base_dir = os.path.realpath(os.path.join("data", "textbook"))
    resolved = os.path.realpath(textbook_path)
    if not resolved.startswith(base_dir + os.sep) and resolved != base_dir:
        logger.warning("Path traversal attempt blocked: %s", textbook_path)
        return None

    if not os.path.exists(resolved):
        return None
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("Failed to load textbook chapter data for %s/%s: %s", book_id, chapter_id, exc)
        return None




def _extract_chapter_text_fragments(chapter_data: Dict[str, Any]) -> List[str]:
    fragments: List[str] = []
    if "reading_nodes" in chapter_data and isinstance(chapter_data["reading_nodes"], list):
        for node in chapter_data["reading_nodes"]:
            if isinstance(node, dict):
                text = node.get("content") or node.get("text") or node.get("passage")
                if text:
                    fragments.append(str(text))
    elif isinstance(chapter_data.get("sections"), dict):
        for section in chapter_data["sections"].values():
            if isinstance(section, dict) and section.get("content"):
                fragments.append(str(section["content"]))
    return fragments



