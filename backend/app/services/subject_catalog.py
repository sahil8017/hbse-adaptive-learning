import json
import logging
import os
from typing import Any, Dict, Optional

from backend.app.core.config import CHAPTERS_DATA, settings

logger = logging.getLogger(__name__)


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _resolve_catalog_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(_project_root(), path)


def _load_subject_catalog_file() -> Dict[str, Any]:
    path = settings.SUBJECT_CATALOG_PATH
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        logger.warning("Subject catalog file not found at %s", path)
    except Exception as exc:
        logger.warning("Failed to load subject catalog from %s: %s", path, exc)
    return {}


def get_subject_catalog() -> Dict[str, Dict[str, Any]]:
    raw_catalog = _load_subject_catalog_file()
    catalog: Dict[str, Dict[str, Any]] = {}

    for book_id, chapters in CHAPTERS_DATA.items():
        raw_meta = raw_catalog.get(book_id, {})
        prompt_config_path = raw_meta.get("prompt_config_path")
        catalog[book_id] = {
            "book_id": book_id,
            "title": raw_meta.get("title", book_id),
            "slug": raw_meta.get("slug", book_id.lower()),
            "category": raw_meta.get("category", "subject"),
            "tag": raw_meta.get("tag", "Subject"),
            "tag_class": raw_meta.get("tag_class", "badge"),
            "icon": raw_meta.get("icon", "📘"),
            "color": raw_meta.get("color", "var(--mg-steel)"),
            "description": raw_meta.get("description", ""),
            "reader_mode": raw_meta.get("reader_mode", "section_textbook"),
            "reader_component": raw_meta.get("reader_component", "SectionTextbookReader"),
            "practice_component": raw_meta.get("practice_component", "ScienceMathPracticePanel"),
            "textbook_format": raw_meta.get("textbook_format", "sections"),
            "chapter_count": len(chapters),
            "first_chapter_id": raw_meta.get("first_chapter_id") or (chapters[0]["id"] if chapters else None),
            "badge": raw_meta.get("badge", {}),
            "prompt_guard_key": raw_meta.get("prompt_guard_key"),
            "prompt_config_path": _resolve_catalog_path(prompt_config_path) if prompt_config_path else None,
        }

    return catalog


def get_subject_meta(book_id: str) -> Optional[Dict[str, Any]]:
    return get_subject_catalog().get(book_id)


def get_subject_prompt_config(book_id: str) -> Dict[str, Any]:
    meta = get_subject_meta(book_id)
    if not meta:
        return {}

    prompt_config_path = meta.get("prompt_config_path")
    if not prompt_config_path:
        return {}

    try:
        with open(prompt_config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        logger.warning("Prompt config file not found for %s at %s", book_id, prompt_config_path)
    except Exception as exc:
        logger.warning("Failed to load prompt config for %s: %s", book_id, exc)
    return {}
