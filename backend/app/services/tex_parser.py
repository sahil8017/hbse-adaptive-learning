"""
Parse LaTeX (.tex) Previous Year Paper files and extract questions.
Handles HBSE Class 9: Mathematics, Science, English, Hindi.
"""
import os
import re
import logging
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger(__name__)

SUBJECT_MAP = {
    "Mathematics": "Mathematics",
    "Science": "Science",
    "English": "English",
    "Hindi": "Hindi",
}

# LaTeX commands to strip (keeping math expressions intact)
_STRIP_PATTERNS = [
    (r'\\\\', ' '),  # LaTeX line break (\\)
    (r'\\scoremarks\{[^}]*\}', ''),
    (r'\\hfill\s*\[[^\]]*\]', ''),
    (r'\\textbf\{([^}]+)\}', r'\1'),
    (r'\\textit\{([^}]+)\}', r'\1'),
    (r'\\emph\{([^}]+)\}', r'\1'),
    (r'\\underline\{([^}]+)\}', r'\1'),
    (r'\\textcolor\{[^}]*\}\{([^}]+)\}', r'\1'),
    (r'\\blank\{[^}]*\}', '_______'),
    (r'\\noindent\b', ''),
    (r'\\bigskip\b', ''),
    (r'\\medskip\b', ''),
    (r'\\smallskip\b', ''),
    (r'\\newpage\b', ''),
    (r'\\hfill\b', ''),
    (r'\\vspace\*?\{[^}]*\}', ''),
    (r'\\hspace\*?\{[^}]*\}', ''),
    (r'\\centering\b', ''),
    (r'\\begin\{center\}', ''),
    (r'\\end\{center\}', ''),
    (r'\\begin\{flushleft\}', ''),
    (r'\\end\{flushleft\}', ''),
    (r'\\label\{[^}]*\}', ''),
    (r'\\ref\{[^}]*\}', ''),
    # Structural markup that can leak into multi-part questions
    (r'\\resizebox\{[^}]*\}\{[^}]*\}', ''),
    (r'\\begin\{tabular\}\{[^}]*\}', ''),
    (r'\\end\{tabular\}', ''),
    (r'\\hline\b', ''),
    (r'\\begin\{enumerate\}\[[^\]]*\]', ''),
    (r'\\begin\{enumerate\}', ''),
    (r'\\end\{enumerate\}', ''),
    (r'\\item\b', ' • '),
]

# Section/exam directives that are not actual questions.
_INSTRUCTION_RE = re.compile(
    r'^(?:'
    r'this question paper'
    r'|all questions are compulsory'
    r'|attempts?\s+all\b'
    r'|attempt any (?:one|two|three|four|five|six|\d+|\w+)\b'
    r'|stick to the word limit'
    r'|do any \w+'
    r'|read the (?:following )?passages?\b'
    r'|figures? to the right'
    r'|internal choice'
    r'|maximum marks'
    r'|time allowed'
    r')',
    re.IGNORECASE,
)


def _is_instruction(text: str) -> bool:
    """Return True for short section/exam directives that are not questions."""
    t = text.strip()
    if len(t) > 150:
        return False
    return bool(_INSTRUCTION_RE.match(t))


def _clean_tex(text: str) -> str:
    """Strip formatting LaTeX commands, preserve math expressions."""
    # Remove LaTeX line comments (not inside math)
    text = re.sub(r'(?<!\\)%[^\n]*', '', text)
    # Remove tikzpicture environments
    text = re.sub(
        r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
        '[See Figure]', text, flags=re.DOTALL
    )
    # Apply stripping patterns
    for pattern, repl in _STRIP_PATTERNS:
        text = re.sub(pattern, repl, text)
    # Normalize whitespace
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _split_top_level_items(body: str) -> List[str]:
    """
    Split an enumerate body into top-level \\item segments.
    Correctly handles nested enumerate environments.
    """
    items: List[str] = []
    current: List[str] = []
    depth = 0
    i = 0

    while i < len(body):
        # Detect \begin{ or \end{
        if body[i] == '\\':
            if body[i:i+6] == '\\begin' and i + 6 < len(body) and body[i + 6] == '{':
                depth += 1
                current.append(body[i])
                i += 1
                continue
            elif body[i:i+4] == '\\end' and i + 4 < len(body) and body[i + 4] == '{':
                depth -= 1
                current.append(body[i])
                i += 1
                continue
            elif body[i:i+5] == '\\item' and depth == 0:
                if current:
                    items.append(''.join(current).strip())
                current = []
                i += 5
                continue

        current.append(body[i])
        i += 1

    if current:
        items.append(''.join(current).strip())

    return [item for item in items if item.strip()]


def _extract_mcq_options(item_text: str) -> Tuple[str, Optional[List[str]]]:
    """
    Given an \\item text block, extract question body and MCQ options.
    Returns (question_text, options_list or None).
    """
    # Find inner enumerate with alph or Alph options
    inner_match = re.search(
        r'(.*?)\\begin\{enumerate\}\[label=\(\\(?:alph|Alph)\*\)\](.*?)\\end\{enumerate\}',
        item_text, re.DOTALL
    )
    if not inner_match:
        return item_text, None

    question_part = inner_match.group(1)
    options_body = inner_match.group(2)

    option_items = _split_top_level_items(options_body)
    options = [_clean_tex(opt).strip() for opt in option_items]
    options = [opt for opt in options if opt]

    # Must have exactly 4 options for a valid MCQ (skip True/False single-option)
    if len(options) != 4:
        return question_part, None

    # Reject false positives: genuine MCQ options are short. Long "options" are
    # almost always the sub-parts of an "answer any four ..." subjective item
    # that happens to use an (\alph*) list. Real options observed up to a mean
    # length of ~64 (Assertion-Reason items); fakes run well above that.
    mean_len = sum(len(opt) for opt in options) / 4
    if any(len(opt) > 140 for opt in options) or mean_len > 70:
        return question_part, None

    return question_part, options


# A top-level QUESTION list uses arabic / roman / Roman numbering.
# (Option lists use (\alph*) / (\Alph*) and are handled separately.)
_QUESTION_LABEL_RE = re.compile(
    r'\\begin\{enumerate\}\[label=(?:\\arabic\*|\(\\roman\*\)|\(\\Roman\*\))[^\]]*\]'
)

_ENUM_BEGIN = r'\begin{enumerate}'
_ENUM_END = r'\end{enumerate}'


def _matching_enumerate_end(content: str, body_start: int) -> int:
    """
    Given an index just past a \\begin{enumerate}[...], return the index of the
    \\end{enumerate} that balances it, accounting for nested enumerate blocks.
    Returns -1 if no balanced end is found.
    """
    depth = 1
    i = body_start
    while i < len(content):
        nb = content.find(_ENUM_BEGIN, i)
        ne = content.find(_ENUM_END, i)
        if ne == -1:
            return -1
        if nb != -1 and nb < ne:
            depth += 1
            i = nb + len(_ENUM_BEGIN)
        else:
            depth -= 1
            if depth == 0:
                return ne
            i = ne + len(_ENUM_END)
    return -1


def _find_numbered_enum_bodies(content: str) -> List[str]:
    """
    Find all top-level question enumerate bodies (arabic / roman / Roman labels),
    correctly handling nested enumerate environments (e.g. MCQ option lists).

    The previous implementation used a lazy regex that stopped at the FIRST
    nested \\end{enumerate}, truncating every section at its first MCQ's options.
    This walks each block with a depth counter to capture the full body, and
    skips begins that are nested inside an already-captured body.
    """
    bodies: List[str] = []
    captured_spans: List[Tuple[int, int]] = []

    for m in _QUESTION_LABEL_RE.finditer(content):
        # Skip a question list that is nested inside one we already captured
        # (e.g. roman sub-parts inside an arabic question) — it stays as part
        # of the parent item's text.
        if any(start <= m.start() < end for start, end in captured_spans):
            continue
        body_start = m.end()
        end_idx = _matching_enumerate_end(content, body_start)
        if end_idx == -1:
            continue
        bodies.append(content[body_start:end_idx])
        captured_spans.append((m.start(), end_idx))

    return bodies


def parse_tex_questions(filepath: str) -> Dict[str, Any]:
    """
    Parse a .tex PYP file and extract structured questions.

    Returns:
        {
            "book_id": str,
            "year": int,
            "mcq_questions": [{"text": str, "options": [str, str, str, str]}],
            "open_questions": [{"text": str}]
        }
    Returns empty dict on parse failure.
    """
    # Determine book_id and year from file path
    norm = os.path.normpath(filepath)
    parts = norm.split(os.sep)

    subject: Optional[str] = None
    year: Optional[int] = None

    for part in parts:
        if part in SUBJECT_MAP:
            subject = SUBJECT_MAP[part]
        m = re.match(r'^(20\d\d)\.tex$', part)
        if m:
            year = int(m.group(1))

    if not subject or not year:
        logger.warning("Could not determine subject/year from path: %s", filepath)
        return {}

    # Read file with UTF-8 fallback
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                content = f.read()
        except Exception as e:
            logger.error("Failed to read %s: %s", filepath, e)
            return {}

    # Preprocess: remove comments and tikzpicture blocks early
    content = re.sub(r'(?<!\\)%[^\n]*', '', content)
    content = re.sub(
        r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
        '[See Figure]', content, flags=re.DOTALL
    )

    mcq_questions: List[Dict] = []
    open_questions: List[Dict] = []
    seen: set = set()

    for body in _find_numbered_enum_bodies(content):
        items = _split_top_level_items(body)

        for item_text in items:
            if not item_text.strip():
                continue

            q_raw, options = _extract_mcq_options(item_text)
            q_text = _clean_tex(q_raw)

            if not q_text or len(q_text) < 8:
                continue

            # Deduplicate by first 60 chars
            key = q_text[:60]
            if key in seen:
                continue
            seen.add(key)

            if options and len(options) == 4:
                mcq_questions.append({"text": q_text, "options": options})
            else:
                # Open/subjective question — drop section/exam directives
                if len(q_text) > 10 and not _is_instruction(q_text):
                    open_questions.append({"text": q_text})

    logger.info(
        "Parsed %s year=%d: %d MCQs, %d open questions",
        subject, year, len(mcq_questions), len(open_questions)
    )

    return {
        "book_id": subject,
        "year": year,
        "mcq_questions": mcq_questions,
        "open_questions": open_questions,
    }


def discover_pyp_tex_files(project_root: str) -> List[str]:
    """Find all PYP .tex files under Class 9/Previous Year Papers/."""
    pyp_dir = os.path.join(project_root, "Class 9", "Previous Year Papers")
    files: List[str] = []

    if not os.path.isdir(pyp_dir):
        logger.warning("PYP directory not found: %s", pyp_dir)
        return files

    for subject in sorted(os.listdir(pyp_dir)):
        subject_dir = os.path.join(pyp_dir, subject)
        if not os.path.isdir(subject_dir):
            continue
        for fname in sorted(os.listdir(subject_dir)):
            if re.match(r'^20\d\d\.tex$', fname):
                files.append(os.path.join(subject_dir, fname))

    return files
