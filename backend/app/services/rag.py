import os
import hashlib
import logging
import time
import asyncpg
from sentence_transformers import SentenceTransformer
from backend.app.core.config import settings
from backend.app.core.prompt_security import contains_prompt_injection

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_DIR = settings.EMBEDDING_MODEL_DIR
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Ensure directories exist
os.makedirs(EMBEDDING_MODEL_DIR, exist_ok=True)

_model = None

def get_embedding_model():
    global _model
    if _model is None:
        print("Initializing SentenceTransformer embedding model...")
        # Check for actual weight files, not just whether the directory is non-empty.
        # The directory may contain only config files without the model binary.
        weight_files = ("model.safetensors", "pytorch_model.bin")
        has_weights = any(
            os.path.isfile(os.path.join(EMBEDDING_MODEL_DIR, f)) for f in weight_files
        )
        if has_weights:
            print(f"Loading embedding model from local directory: {EMBEDDING_MODEL_DIR}")
            _model = SentenceTransformer(EMBEDDING_MODEL_DIR)
        else:
            print("Downloading paraphrase-multilingual-MiniLM-L12-v2 from HuggingFace Hub...")
            temp_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            temp_model.save(EMBEDDING_MODEL_DIR)
            _model = temp_model
    return _model

def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    embeddings = model.encode(text)
    if hasattr(embeddings, "tolist"):
        return embeddings.tolist()
    return [float(x) for x in embeddings]

async def embed_text_async(text: str) -> list[float]:
    """Non-blocking embedding via thread pool executor."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, embed_text, text)

def format_vector(vector_list: list[float]) -> str:
    """Format float list into a vector string '[v1,v2,...]' for pgvector insertion."""
    return "[" + ",".join(map(str, vector_list)) + "]"

db_pool_ref = None

async def get_db_pool() -> asyncpg.Pool:
    """Resolve database pool reference (global FastAPI pool or CLI-script dynamic pool)."""
    global db_pool_ref
    from backend.app.core.database import db_pool as global_db_pool
    if global_db_pool:
        return global_db_pool
        
    if db_pool_ref is None:
        from dotenv import load_dotenv
        from backend.app.core.database import sanitize_dsn
        load_dotenv()
        dsn = sanitize_dsn(os.getenv("DATABASE_URL", settings.DATABASE_URL))
        db_pool_ref = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    return db_pool_ref

def _looks_like_placeholder_content(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return True
    return (
        normalized.startswith("this section covers ")
        and "it includes definitions, formulas, and step-by-step proofs." in normalized
    )

async def add_documents_to_rag(book_id: str, chapter_id: str, chunks: list[dict]):
    pool = await get_db_pool()
    
    # Pre-calculate embeddings for the entire batch
    valid_chunks = [chunk for chunk in chunks if not _looks_like_placeholder_content(chunk.get("text", ""))]
    if not valid_chunks:
        return
        
    texts = [chunk["text"] for chunk in valid_chunks]
    model = get_embedding_model()
    embeddings = model.encode(texts)
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, chunk in enumerate(valid_chunks):
                text = chunk["text"]
                emb = embeddings[idx]
                if hasattr(emb, "tolist"):
                    emb_list = emb.tolist()
                else:
                    emb_list = [float(x) for x in emb]
                
                emb_str = format_vector(emb_list)
                
                await conn.execute("""
                    INSERT INTO textbook_embeddings 
                    (book_id, chapter_id, section_id, chunk_text, embedding, page_num)
                    VALUES ($1, $2, $3, $4, $5::vector, $6)
                    ON CONFLICT (book_id, chapter_id, section_id, chunk_text) DO NOTHING
                """, book_id, chapter_id, chunk["section_id"], text, emb_str, chunk["page_num"])
                
    print(f"Ingested {len(valid_chunks)} chunks for {book_id} - {chapter_id} into pgvector.")

def extract_textbook_chunks(ch_data: dict) -> list[dict]:
    chunks: list[dict] = []

    if "reading_nodes" in ch_data and isinstance(ch_data.get("reading_nodes"), list):
        before_you_read = ch_data.get("before_you_read", [])
        if isinstance(before_you_read, list) and before_you_read:
            chunks.append({
                "text": "Before You Read:\n" + "\n".join(str(item) for item in before_you_read),
                "section_id": "before_you_read",
                "page_num": 0,
            })

        for node in ch_data.get("reading_nodes", []):
            if not isinstance(node, dict):
                continue
            content = (node.get("content") or "").strip()
            if not content or _looks_like_placeholder_content(content):
                continue
            glossary = node.get("inline_glossary", {}) or node.get("inline_shabdarth", {})
            node_text = f"Section: {node.get('node_title', '')}\n\n{content}"
            if isinstance(glossary, dict) and glossary:
                vocab_label = "Shabdarth" if node.get("inline_shabdarth") else "Vocabulary/Glossary"
                node_text += f"\n\n{vocab_label}:\n" + "\n".join(f"- {w}: {d}" for w, d in glossary.items())
            chunks.append({
                "text": node_text,
                "section_id": node.get("node_id") or "reading_node",
                "page_num": 1,
            })
        return chunks

    sections = ch_data.get("sections", {})
    if isinstance(sections, dict):
        section_items = sections.items()
    elif isinstance(sections, list):
        section_items = ((str(idx), sec) for idx, sec in enumerate(sections))
    else:
        section_items = []

    for sec_id, sec_data in section_items:
        if not isinstance(sec_data, dict):
            continue
        content = (sec_data.get("content") or "").strip()
        if not content or _looks_like_placeholder_content(content):
            continue
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        for idx, para in enumerate(paragraphs):
            chunks.append({
                "text": para,
                "section_id": sec_data.get("id") or sec_id,
                "page_num": idx + 1,
            })

    return chunks

_rag_cache = {}
_CACHE_TTL = 300 # 5 minutes

# Book IDs that hold Previous Year Paper content (ingested by ingest_all_source_materials.py)
PYP_BOOK_IDS = {"PYP_English", "PYP_Hindi", "PYP_Mathematics", "PYP_Science"}
TEXTBOOK_BOOK_IDS = {"English", "Hindi", "Mathematics", "Science"}
ALL_KNOWN_BOOK_IDS = TEXTBOOK_BOOK_IDS | PYP_BOOK_IDS


async def get_relevant_context_global(query: str, n_results: int = 6, book_ids: list[str] = None) -> str:
    """
    Search across ALL ingested materials (textbooks + PYP papers) for the most
    relevant chunks. Used when no specific chapter context is active.
    """
    query_hash = hashlib.md5(query.encode("utf-8")).hexdigest()
    ids_key = ",".join(sorted(book_ids or []))
    cache_key = f"global:{ids_key}:{query_hash}"

    now = time.time()
    if cache_key in _rag_cache:
        ts, cached = _rag_cache[cache_key]
        if now - ts < _CACHE_TTL:
            return cached

    try:
        pool = await get_db_pool()
        query_emb = await embed_text_async(query)
        emb_str = format_vector(query_emb)
    except Exception as e:
        print(f"Error initialising global RAG: {e}")
        return ""

    try:
        async with pool.acquire() as conn:
            if book_ids:
                results = await conn.fetch(
                    """
                    SELECT book_id, chapter_id, chunk_text
                    FROM textbook_embeddings
                    WHERE book_id = ANY($1::text[])
                    ORDER BY embedding <=> $2::vector
                    LIMIT $3
                    """,
                    list(book_ids), emb_str, n_results
                )
            else:
                results = await conn.fetch(
                    """
                    SELECT book_id, chapter_id, chunk_text
                    FROM textbook_embeddings
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                    """,
                    emb_str, n_results
                )

        if not results:
            return ""

        parts = []
        for row in results:
            label = f"[{row['book_id']} / {row['chapter_id']}]"
            parts.append(f"{label}\n{row['chunk_text']}")
        formatted = "\n\n---\n\n".join(parts)

        _rag_cache[cache_key] = (now, formatted)
        return formatted
    except Exception as e:
        print(f"Error in global pgvector search: {e}")
        return ""


async def get_relevant_context(book_id: str, chapter_id: str, query: str, n_results: int = 2, section_id: str = None) -> str:
    query_hash = hashlib.md5(query.encode("utf-8")).hexdigest()
    cache_key = f"{book_id}:{chapter_id}:{section_id or ''}:{query_hash}"

    now = time.time()
    if cache_key in _rag_cache:
        timestamp, cached_text = _rag_cache[cache_key]
        if now - timestamp < _CACHE_TTL:
            return cached_text

    try:
        pool = await get_db_pool()
        query_emb = await embed_text_async(query)
        emb_str = format_vector(query_emb)
    except Exception as e:
        print(f"Error initialising RAG (embedding/pool): {e}")
        return "Could not retrieve reference passage from offline database."

    try:
        async with pool.acquire() as conn:
            if section_id:
                results = await conn.fetch("""
                    SELECT chunk_text 
                    FROM textbook_embeddings
                    WHERE book_id = $1 AND chapter_id = $2 AND section_id = $3
                    ORDER BY embedding <=> $4::vector
                    LIMIT $5
                """, book_id, chapter_id, section_id, emb_str, n_results)
            else:
                results = await conn.fetch("""
                    SELECT chunk_text 
                    FROM textbook_embeddings
                    WHERE book_id = $1 AND chapter_id = $2
                    ORDER BY embedding <=> $3::vector
                    LIMIT $4
                """, book_id, chapter_id, emb_str, n_results)
                
        retrieved_texts = [row["chunk_text"] for row in results]
        
        if not retrieved_texts:
            formatted_text = "No specific reference passage found in the chapter."
        else:
            formatted_text = "\n\n---\n\n".join(retrieved_texts)
            
        _rag_cache[cache_key] = (now, formatted_text)
        return formatted_text
    except Exception as e:
        print(f"Error querying pgvector: {e}")
        return "Could not retrieve reference passage from offline database."

async def ingest_structured_textbooks():
    import json
    import os
    
    print("Ingesting structured textbook files into pgvector...")
    
    textbook_base_dir = os.path.join(BASE_DIR, "data", "textbook")
    if not os.path.exists(textbook_base_dir):
        print(f"Textbook directory not found at {textbook_base_dir}")
        return
        
    for subject in os.listdir(textbook_base_dir):
        subj_dir = os.path.join(textbook_base_dir, subject)
        if not os.path.isdir(subj_dir):
            continue
            
        book_id = subject.capitalize()
        if subject.lower() == "hindi":
            book_id = "Hindi"
        elif subject.lower() == "english":
            book_id = "English"
        elif subject.lower() == "science":
            continue
        elif subject.lower() == "mathematics":
            continue
        
        for file in os.listdir(subj_dir):
            if not file.endswith(".json"):
                continue
                
            filepath = os.path.join(subj_dir, file)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    ch_data = json.load(f)
                    
                chapter_id = ch_data["chapter_id"]
                chunks = extract_textbook_chunks(ch_data)
                if chunks:
                    await add_documents_to_rag(book_id, chapter_id, chunks)
                    continue
                if "reading_nodes" in ch_data:
                    chunks = []
                    before_you_read = ch_data.get("before_you_read", [])
                    if before_you_read:
                        byr_text = "Before You Read:\n" + "\n".join(before_you_read)
                        chunks.append({
                            "text": byr_text,
                            "section_id": "before_you_read",
                            "page_num": 0
                        })
                    
                    for node in ch_data.get("reading_nodes", []):
                        node_id = node.get("node_id", "")
                        node_title = node.get("node_title", "")
                        content = node.get("content", "")
                        glossary = node.get("inline_glossary", {}) or node.get("inline_shabdarth", {})
                        
                        node_text = f"Section: {node_title}\n\n{content}"
                        if glossary:
                            vocab_label = "शब्दार्थ" if node.get("inline_shabdarth") else "Vocabulary/Glossary"
                            glossary_text = f"\n\n{vocab_label}:\n" + "\n".join(f"- {w}: {d}" for w, d in glossary.items())
                            node_text += glossary_text
                            
                        chunks.append({
                            "text": node_text,
                            "section_id": node_id,
                            "page_num": 1
                        })
                        
                    if chunks:
                        await add_documents_to_rag(book_id, chapter_id, chunks)
                else:
                    sections = ch_data.get("sections", {})
                    for sec_id, sec_data in sections.items():
                        content = sec_data.get("content", "")
                        if not content.strip():
                            continue
                            
                        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
                        chunks = []
                        for idx, para in enumerate(paragraphs):
                            chunks.append({
                                "text": para,
                                "section_id": sec_id,
                                "page_num": idx + 1
                            })
                        
                        if chunks:
                            await add_documents_to_rag(book_id, chapter_id, chunks)
            except Exception as e:
                print(f"Error ingesting file {file}: {e}")

async def count_chunks(book_id: str) -> int:
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM textbook_embeddings WHERE book_id = $1", book_id
            )
            return count or 0
    except Exception as e:
        print(f"Error counting chunks for {book_id}: {e}")
    return 0
