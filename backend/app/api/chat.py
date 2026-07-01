import json
import logging
from typing import Optional
import re
import urllib.parse

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse

from backend.app.core.config import CHAPTERS_DATA
from backend.app.core.security import (
    get_current_student
)
from backend.app.core.database import (
    save_chat_message, get_chat_history, clear_chat_history
)
from backend.app.services.adaptive import (
    get_tutor_chat_stream,
    tutor_config
)
from backend.app.services.subject_catalog import get_subject_prompt_config
from backend.app.core.limiter import limiter
from backend.app.core.prompt_security import contains_prompt_injection, sanitize_history

# Import Pydantic schemas
from backend.app.schemas.chat import ChatAskRequest


from backend.app.services.gemini_service import get_youtube_recommendation, search_youtube_video

logger = logging.getLogger(__name__)

router = APIRouter()

def normalize_string(s: str) -> str:
    s = s.lower()
    s = re.sub(r'[^\w\s]', '', s) # remove punctuation
    words = []
    for w in s.split():
        if len(w) > 3 and w.endswith('s'):
            words.append(w[:-1])
        else:
            words.append(w)
    return " ".join(words)

def detect_book_and_chapter_from_query(query: str) -> tuple[Optional[str], Optional[str]]:
    query_norm = normalize_string(query)
    
    # 1. Search for normalized chapter titles
    for book, chapters in CHAPTERS_DATA.items():
        for ch in chapters:
            title_norm = normalize_string(ch.get("title", ""))
            if len(title_norm) > 4 and title_norm in query_norm:
                return book, ch["id"]
                
    # 2. Check for subject keywords + chapter number patterns
    subject_map = {
        "mathematics": "Mathematics",
        "maths": "Mathematics",
        "math": "Mathematics",
        "science": "Science",
        "sci": "Science",
        "english": "English",
        "eng": "English",
        "hindi": "Hindi",
        "hin": "Hindi"
    }
    
    query_lower = query.lower()
    detected_book = None
    for keyword, book in subject_map.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', query_lower):
            detected_book = book
            break
            
    if not detected_book:
        return None, None
        
    chapter_num_match = re.search(r'\b(?:chapter|ch\.?|unit)\s*([0-9]+)\b', query_lower)
    
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15
    }
    
    chapter_num = None
    if chapter_num_match:
        try:
            chapter_num = int(chapter_num_match.group(1))
        except ValueError:
            pass
    else:
        for word, num in word_to_num.items():
            if re.search(r'\b(?:chapter|ch\.?|unit)\s*' + re.escape(word) + r'\b', query_lower):
                chapter_num = num
                break
                
    if not chapter_num:
        return detected_book, None
        
    target_id = None
    if detected_book == "Mathematics":
        target_id = f"math_ch{chapter_num}"
    elif detected_book == "Science":
        target_id = f"sci_ch{chapter_num}"
    elif detected_book in ["English", "Hindi"]:
        chapters = CHAPTERS_DATA.get(detected_book, [])
        for ch in chapters:
            ch_id = ch["id"]
            if ch_id.endswith(f"_p{chapter_num}") or ch_id.endswith(f"_{chapter_num}"):
                target_id = ch_id
                break
                
    if target_id:
        chapters = CHAPTERS_DATA.get(detected_book, [])
        if any(ch["id"] == target_id for ch in chapters):
            return detected_book, target_id
            
    return detected_book, None

def check_banned_keywords(message: str, book_id: Optional[str] = None) -> bool:
    banned = []
    if book_id:
        try:
            subject_config = get_subject_prompt_config(book_id)
            banned = subject_config.get("banned_keywords", [])
        except Exception:
            pass
    if not banned:
        banned = tutor_config.get("banned_keywords", [])
    if not banned:
        return False
    # Join with word boundaries
    pattern = re.compile(r'\b(' + '|'.join(map(re.escape, banned)) + r')\b', re.IGNORECASE)
    return bool(pattern.search(message))

@router.get("/chat/history")
async def api_chat_history(chapter_id: Optional[str] = None, student: dict = Depends(get_current_student)):
    history = await get_chat_history(student["id"], student["session_id"], chapter_id, limit=20)
    return [
        {
            "sender": h["sender"],
            "message": h["message"],
            "is_blocked": bool(h["is_blocked"]),
            "timestamp": h["timestamp"]
        }
        for h in history
    ]


@router.delete("/chat/history")
async def api_clear_chat_history(chapter_id: Optional[str] = None, student: dict = Depends(get_current_student)):
    await clear_chat_history(student["id"], chapter_id)
    return {"status": "cleared"}


@router.post("/chat/ask")
@limiter.limit("5/minute")
async def api_chat_ask(request: Request, body: ChatAskRequest, student: dict = Depends(get_current_student)):
    message = body.message.strip()[:4000]

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    if contains_prompt_injection(message):
        raise HTTPException(status_code=400, detail="Prompt-injection style instructions are not allowed.")

    is_quiz = "quiz" in message.lower()
    history = [] if is_quiz else sanitize_history(body.history)

    # Resolve subject context from the explicit book_id first, then fall back to chapter lookup.
    # All RAG retrieval + query reformulation is delegated to get_tutor_chat_stream.
    book_id = body.book_id if body.book_id in CHAPTERS_DATA else None
    if not book_id and body.chapter_id:
        for b_id, chapters in CHAPTERS_DATA.items():
            if any(ch["id"] == body.chapter_id for ch in chapters):
                book_id = b_id
                break

    resolved_book_id = book_id
    resolved_chapter_id = body.chapter_id

    # If book and chapter are not explicitly given, try parsing from user message query
    if not resolved_book_id and not resolved_chapter_id:
        detected_book, detected_ch = detect_book_and_chapter_from_query(message)
        if detected_book:
            resolved_book_id = detected_book
            if detected_ch:
                resolved_chapter_id = detected_ch

    is_blocked = check_banned_keywords(message, resolved_book_id or book_id)
    session_id = student["session_id"]

    await save_chat_message(student["id"], session_id, body.chapter_id, "user", message, is_blocked)


    # Determine chapter title for YouTube recommendation context
    chapter_title = ""
    if resolved_book_id and resolved_chapter_id:
        try:
            chapters = CHAPTERS_DATA.get(resolved_book_id, [])
            ch = next((c for c in chapters if c["id"] == resolved_chapter_id), None)
            if ch:
                chapter_title = ch.get("title", "")
        except Exception:
            pass

    is_video_asked = any(k in message.lower() for k in ["video", "youtube", "yt", "watch", "link", "visual"])

    async def chat_event_generator():
        if is_blocked:
            refusal = tutor_config.get("refusal_message", "I cannot answer off-topic queries.")
            await save_chat_message(student["id"], session_id, body.chapter_id, "ai", refusal, True)
            yield f"data: {json.dumps({'text': refusal})}\n\n"
            yield f"data: {json.dumps({'done': True, 'is_blocked': True})}\n\n"
            return

        collected_tokens = []
        stop_streaming = False
        try:
            async for token in get_tutor_chat_stream(
                user_query=message,
                chat_history=history,
                is_quiz=is_quiz,
                chapter_id=resolved_chapter_id,
                section_id=body.section_id,
                book_id=resolved_book_id,
                tab_id=body.tab_id,
            ):
                collected_tokens.append(token)
                current_text = "".join(collected_tokens)
                if "---YOUTUBE_REC" in current_text:
                    stop_streaming = True
                
                if not stop_streaming:
                    yield f"data: {json.dumps({'text': token})}\n\n"
        except Exception as e:
            logger.error("Error in get_tutor_chat_stream: %s", e)
            yield f"data: {json.dumps({'text': 'All AI tutoring services are temporarily offline. Please try again later or consult your class teacher.'})}\n\n"

        full_response = "".join(collected_tokens)

        # Extract ---YOUTUBE_REC--- block if present
        youtube_rec_data = None
        rec_match = re.search(r'---YOUTUBE_REC---\n(.*?)\n---END_YOUTUBE_REC---', full_response, re.DOTALL)
        if rec_match:
            rec_block = rec_match.group(1).strip()
            rec_dict: dict[str, str] = {}
            for line in rec_block.split('\n'):
                if line.startswith('Title:'):
                    rec_dict['title'] = line.replace('Title:', '', 1).strip()
                elif line.startswith('Channel:'):
                    rec_dict['channel'] = line.replace('Channel:', '', 1).strip()
                elif line.startswith('Duration:'):
                    rec_dict['duration'] = line.replace('Duration:', '', 1).strip()
            if rec_dict:
                title = rec_dict.get('title') or ''
                sq = title or message
                youtube_rec_data = {
                    'title': title,
                    'search_query': sq,
                    'video_url': f"https://www.youtube.com/results?search_query={urllib.parse.quote(sq)}",
                    'reason': 'Watch this video for a clear explanation.',
                    'channel': rec_dict.get('channel') or None,
                    'duration': rec_dict.get('duration') or None,
                    'thumbnail_url': None,
                }
            full_response = re.sub(r'\n*---YOUTUBE_REC---.*?---END_YOUTUBE_REC---', '', full_response, flags=re.DOTALL)

        refusal_keywords = [
            "cannot answer", "cannot help", "not related to", "focus on your class 9",
            "focus on your studies", "outside the", "class 9 tutor", "syllabus"
        ]
        response_is_blocked = any(k in full_response.lower() for k in refusal_keywords)

        await save_chat_message(student["id"], session_id, body.chapter_id, "ai", full_response, response_is_blocked)

        # Emit YouTube recommendation card
        if not is_quiz and not response_is_blocked and is_video_asked:
            if youtube_rec_data:
                # LLM embedded a block — enrich it with real thumbnail + direct link via YouTube API
                try:
                    sq = youtube_rec_data.get("search_query") or youtube_rec_data.get("title") or message
                    yt = await search_youtube_video(sq)
                    if yt:
                        youtube_rec_data.update({
                            "video_url": yt["video_url"],
                            "thumbnail_url": yt["thumbnail_url"],
                            "title": yt["title"] or youtube_rec_data["title"],
                            "channel": yt.get("channel") or youtube_rec_data.get("channel"),
                            "duration": yt.get("duration") or youtube_rec_data.get("duration"),
                        })
                except Exception as exc:
                    logger.debug("YouTube API enrichment failed: %s", exc)
                yield f"data: {json.dumps({'type': 'youtube_rec', 'video': youtube_rec_data})}\n\n"
            else:
                # LLM didn't embed a block — ask Gemini + YouTube API directly
                try:
                    rec = await get_youtube_recommendation(
                        user_query=message,
                        subject=resolved_book_id or "General",
                        chapter_title=chapter_title,
                    )
                    if rec:
                        yield f"data: {json.dumps({'type': 'youtube_rec', 'video': rec})}\n\n"
                except Exception as exc:
                    logger.debug("YouTube recommendation skipped: %s", exc)

        yield f"data: {json.dumps({'done': True, 'is_blocked': response_is_blocked})}\n\n"

    return StreamingResponse(chat_event_generator(), media_type="text/event-stream")


