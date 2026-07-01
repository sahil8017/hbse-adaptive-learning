import hashlib
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.app.core.config import settings
from backend.app.core.database import get_student_by_firebase_uid

security_scheme = HTTPBearer(auto_error=False)

_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,30}$")
_EXAM_HMAC_KEY = hashlib.sha256((settings.SECRET_KEY + ":exam").encode()).digest()
_FIREBASE_CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"
_FIREBASE_CERTS_CACHE: Dict[str, Any] = {"expires_at": 0.0, "certs": {}}


def sha256_hex(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def _validate_username(raw: str) -> str:
    username = raw.strip().lower()
    if not _USERNAME_RE.match(username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 3-30 characters: letters, digits, underscores only.",
        )
    return username


def _safe_int(value, field: str = "answer") -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid {field}: must be an integer.")


def _sign_exam(exam_dict: dict) -> str:
    payload = json.dumps(exam_dict, sort_keys=True).encode()
    return hmac.new(_EXAM_HMAC_KEY, payload, hashlib.sha256).hexdigest()


def _verify_exam_sig(exam_dict: dict, sig: str) -> bool:
    expected = _sign_exam(exam_dict)
    return hmac.compare_digest(expected, sig)


async def _fetch_firebase_certs() -> Dict[str, str]:
    now = time.time()
    if _FIREBASE_CERTS_CACHE["certs"] and now < _FIREBASE_CERTS_CACHE["expires_at"]:
        return _FIREBASE_CERTS_CACHE["certs"]

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(_FIREBASE_CERTS_URL)
            response.raise_for_status()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify Firebase credentials right now.",
        ) from exc

    cache_seconds = 3600
    cache_control = response.headers.get("cache-control", "")
    match = re.search(r"max-age=(\d+)", cache_control)
    if match:
        cache_seconds = max(300, int(match.group(1)))

    certs = response.json()
    _FIREBASE_CERTS_CACHE["certs"] = certs
    _FIREBASE_CERTS_CACHE["expires_at"] = now + cache_seconds
    return certs


async def verify_firebase_id_token(id_token: str) -> Dict[str, Any]:
    if not settings.FIREBASE_PROJECT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase auth is not configured on the server.",
        )

    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Malformed Firebase ID token.") from exc

    kid = header.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Malformed Firebase ID token.")

    certs = await _fetch_firebase_certs()
    cert = certs.get(kid)
    if not cert:
        _FIREBASE_CERTS_CACHE["expires_at"] = 0.0
        certs = await _fetch_firebase_certs()
        cert = certs.get(kid)
        if not cert:
            raise HTTPException(status_code=401, detail="Unknown Firebase signing key.")

    issuer = f"https://securetoken.google.com/{settings.FIREBASE_PROJECT_ID}"
    try:
        payload = jwt.decode(
            id_token,
            cert,
            algorithms=["RS256"],
            audience=settings.FIREBASE_PROJECT_ID,
            issuer=issuer,
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired Firebase ID token.") from exc

    firebase_uid = payload.get("user_id") or payload.get("sub")
    email = payload.get("email")
    if not firebase_uid or not email:
        raise HTTPException(status_code=401, detail="Firebase identity is missing required claims.")

    payload["firebase_uid"] = firebase_uid
    payload["email"] = normalize_email(email)
    return payload


def build_session_id(raw_token: str) -> str:
    return sha256_hex(raw_token)[:32]


async def get_current_student(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> dict:
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = await verify_firebase_id_token(token)
    student = await get_student_by_firebase_uid(payload["firebase_uid"])
    if not student:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Student session is not provisioned.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    student_info = dict(student)
    student_info["session_id"] = build_session_id(token)
    student_info["firebase_claims"] = payload
    return student_info


def create_exam_token(student_id: int, answers: Dict[str, int], subtopics: Dict[str, str]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    nonce = secrets.token_hex(16)
    payload = {
        "sub": str(student_id),
        "answers": answers,
        "subtopics": subtopics,
        "nonce": nonce,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_exam_token(token: str, student_id: int) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("sub") != str(student_id):
            raise HTTPException(status_code=403, detail="Exam token does not match the active student session.")
        return payload
    except JWTError:
        raise HTTPException(status_code=403, detail="Exam session has expired or is invalid.")


def create_share_token(student_id: int, expires_days: int = 7) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=expires_days)
    payload = {
        "sub": str(student_id),
        "type": "share",
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_share_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "share":
            return None
        return int(payload["sub"])
    except (JWTError, ValueError, KeyError):
        return None
