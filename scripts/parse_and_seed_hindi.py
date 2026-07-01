import sys
import os
import re
import json
import asyncio
import httpx
import logging

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("hindi_parser")

# Add workspace root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.core.config import settings
from backend.app.core.database import init_db, add_question, get_pool

# Chapter keywords mapping to automatically categorize questions
CHAPTER_KEYWORDS = {
    "hin_kshitij_p1": ["दो बैलों की कथा", "झूरी", "गया", "हीरा", "मोती", "कांजीहौस", "दढ़ियल", "बैल", "सांड", "काछी"],
    "hin_kshitij_p2": ["ल्हासा की ओर", "तिब्बत", "सुमति", "राहुल सांकृत्यायन", "भिक्षु", "डाँड़े", "थोंगला", "सवारी", "भारवाहक"],
    "hin_kshitij_p3": ["उपभोक्तावाद की संस्कृति", "बाजार", "विज्ञापन", "सामग्री", "उपभोक्ता", "दिखावे", "संस्कृति", "बबूल", "टूथपेस्ट"],
    "hin_kshitij_p4": ["साँवले सपनों की याद", "सालिम अली", "पक्षियों", "डी.एच. लॉरेंस", "फ्रीडा", "बर्ड वाचर", "पर्यावरण"],
    "hin_kshitij_p5": ["प्रेमचंद के फटे जूते", "हरिशंकर परसाई", "फटे जूते", "जूता", "प्रेमचंद", "टोपी", "टीले"],
    "hin_kshitij_p6": ["मेरे बचपन के दिन", "महादेवी वर्मा", "सुभद्रा कुमारी", "बेगम", "कवि-सम्मेलन", "निकासी"],
    "hin_kshitij_po1": ["कबीर", "साखियाँ", "सबद", "हंस", "मानसरोवर", "ज्ञानी", "मोको कहाँ", "सुजान", "काबा", "काशी", "पखापखी"],
    "hin_kshitij_po2": ["ललद्यद", "वाख", "रस्सी", "नाव", "कच्चे धागे", "जेब टटोली", "कौड़ी", "थल-थल"],
    "hin_kshitij_po3": ["रसखान", "सवैये", "मानुस हौं", "गोकुल", "पाहन", "गिरि", "कालिंदी", "लकुटी", "कामरिया", "पुरन्दर"],
    "hin_kshitij_po4": ["माखनलाल चतुर्वेदी", "कैदी और कोकिला", "कोकिल", "गहना", "हथकड़ी", "जेल", "ब्रिटिश", "काल कोठरी", "हुँकार"],
    "hin_kshitij_po5": ["सुमित्रानंदन पंत", "ग्राम श्री", "गंगा की सतरंगी", "खेत", "फसल", "अमरूद", "जामुन", "मखमल"],
    "hin_kshitij_po6": ["सर्वेश्वर दयाल सक्सेना", "मेघ आए", "बादल", "बयार", "दमाद", "तालाब", "धूल", "बूढ़ा पीपल"],
    "hin_kshitij_po7": ["चन्द्रकान्त देवतालें", "यमराज की दिशा", "यमराज", "दक्षिण", "माँ की सीख", "ईश्वर"],
    "hin_kshitij_po8": ["राजेश जोशी", "बच्चे काम पर जा रहे हैं", "मदरसा", "कोहरा", "गेंद", "खिलौने", "बाल श्रम"],
    "hin_kritika_1": ["इस जल प्रलय में", "फणीश्वरनाथ रेणु", "बाढ़", "पटना", "तरल दूत", "पुनपुन", "राजेंद्र नगर", "प्रलय"],
    "hin_kritika_2": ["मेरे संग की औरतें", "मृदुला गर्ग", "नानी", "दादी", "श्रद्धाभाव", "चोर", "शादी", "बहनें", "परदादी"],
    "hin_kritika_3": ["रीढ़ की हड्डी", "जगदीशचंद्र माथुर", "रामस्वरूप", "गोपाल प्रसाद", "उमा", "शंकर", "शिक्षा", "लड़की", "दहेज"],
}

# Grammar topics keywords
GRAMMAR_KEYWORDS = {
    "hin_grammar_alankar": ["अलंकार", "अनुप्रास", "रूपक", "उपमा", "यमक", "श्लेष", "पंक्तियों में प्रयुक्त"],
    "hin_grammar_affixes": ["उपसर्ग", "प्रत्यय", "अप्रत्यय", "बहाव"],
    "hin_grammar_idioms": ["मुहावरे", "लोकोक्ति", "वाक्य-निर्माण", "अर्थ लिखकर"],
    "hin_grammar_samas": ["समास", "विग्रह", "द्वंद्व", "बहुव्रीहि", "अव्ययीभाव", "द्विगु", "तत्पुरुष"],
    "hin_grammar_phonetics": ["वर्ण विच्छेद", "स्वर रहित", "संयुक्त व्यंजन", "द्वित्व व्यंजन"],
    "hin_grammar_vocabulary": ["विलोम", "पर्यायवाची", "तत्सम", "तद्भव", "सार्थक समूह", "पर्याय", "शब्दों के विलोम"]
}

# Standard layout instruction patterns to strip/skip
_INSTRUCTION_RE = re.compile(
    r'^(?:'
    r'निम्नलिखित प्रश्नों के यथानिर्दिष्ट उत्तर दीजिए'
    r'|निम्नलिखित बहुविकल्पीय प्रश्नों के सही विकल्प'
    r'|निम्नलिखित बहुविकल्पीय प्रश्नों के उचित विकल्प'
    r'|निम्नलिखित प्रश्नों के उत्तर दीजिए'
    r'|निम्नलिखित प्रश्नों के संक्षिप्त उत्तर दीजिए'
    r'|निम्नलिखित में से किसी एक विषय पर'
    r'|व्याकरण पर आधारित निम्नलिखित'
    r'|कृतिका भाग-1 के आधार पर'
    r'|नैतिक शिक्षा के आधार पर'
    r'|निम्नलिखित काव्यांश को पढ़कर पूछे गए प्रश्नों'
    r'|निम्नलिखित गद्यांश को पढ़कर'
    r'|अथवा'
    r')',
    re.IGNORECASE
)

def _is_instruction(text: str) -> bool:
    t = text.strip()
    if len(t) > 120:
        return False
    return bool(_INSTRUCTION_RE.match(t))

def clean_tex(text: str) -> str:
    """Clean LaTeX markup completely, keep Devanagari text clean."""
    # Remove comments
    text = re.sub(r'(?<!\\)%[^\n]*', '', text)
    # Remove \scoremarks{...}
    text = re.sub(r'\\scoremarks\{[^}]*\}', '', text)
    # Remove \blank{...}
    text = re.sub(r'\\blank\{[^}]*\}', '_______', text)
    # Remove formatting markup but preserve inner content
    text = re.sub(r'\\textbf\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\textit\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\emph\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\underline\{([^}]+)\}', r'\1', text)
    text = re.sub(r'\\textcolor\{[^}]*\}\{([^}]+)\}', r'\1', text)
    # Remove layout commands
    text = re.sub(r'\\newpage\b', '', text)
    text = re.sub(r'\\noindent\b', '', text)
    text = re.sub(r'\\bigskip\b', '', text)
    text = re.sub(r'\\medskip\b', '', text)
    text = re.sub(r'\\smallskip\b', '', text)
    text = re.sub(r'\\centering\b', '', text)
    text = re.sub(r'\\hfill\b', '', text)
    text = re.sub(r'\\rule\{[^}]*\}\{[^}]*\}', '_______', text)
    # Remove environments
    text = re.sub(r'\\begin\{center\}', '', text)
    text = re.sub(r'\\end\{center\}', '', text)
    text = re.sub(r'\\begin\{flushleft\}', '', text)
    text = re.sub(r'\\end\{flushleft\}', '', text)
    text = re.sub(r'\\begin\{document\}', '', text)
    text = re.sub(r'\\end\{document\}', '', text)
    text = re.sub(r'\\documentclass\[[^\]]*\]\{[^}]*\}', '', text)
    text = re.sub(r'\\usepackage\*?(\[[^\]]*\])?\{[^}]*\}', '', text)
    text = re.sub(r'\\newfontfamily\b.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\\setmainfont\b.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\\setlength\b.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\\newcommand\b.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\\title\{[^}]*\}', '', text)
    text = re.sub(r'\\author\{[^}]*\}', '', text)
    text = re.sub(r'\\date\{[^}]*\}', '', text)
    text = re.sub(r'\\pagestyle\{[^}]*\}', '', text)
    text = re.sub(r'\\lhead\{[^}]*\}', '', text)
    text = re.sub(r'\\rhead\{[^}]*\}', '', text)
    text = re.sub(r'\\maketitle', '', text)
    text = re.sub(r'\\section\*?\{[^}]*\}', '', text)
    text = re.sub(r'\\subsection\*?\{[^}]*\}', '', text)
    text = re.sub(r'\{\\hindfont', '', text)
    text = re.sub(r'\}', '', text) # Close bracket for hindfont if leftover
    # Clean up double backslashes
    text = text.replace('\\\\', ' ')
    # Normalize whitespaces
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_enumerate_items(body: str) -> list[str]:
    """Parse list items at the current level, ignoring nested lists."""
    items = []
    current = []
    depth = 0
    i = 0
    while i < len(body):
        if body[i:].startswith('\\begin'):
            depth += 1
            current.append(body[i:i+6])
            i += 6
        elif body[i:].startswith('\\end'):
            depth -= 1
            current.append(body[i:i+4])
            i += 4
        elif body[i:].startswith('\\item') and depth == 0:
            if current:
                items.append(''.join(current).strip())
            current = []
            i += 5
        else:
            current.append(body[i])
            i += 1
    if current:
        items.append(''.join(current).strip())
    return [item for item in items if item.strip()]

def find_all_outer_enumerates(text: str) -> list[tuple[str, str]]:
    """
    Find all outer-level \begin{enumerate} ... \end{enumerate} blocks in the text.
    Returns a list of tuples: (parent_instruction_text, inner_enumerate_body)
    """
    results = []
    idx = 0
    while idx < len(text):
        match = re.search(r'\\begin\{enumerate\}(\[[^\]]*\])?', text[idx:])
        if not match:
            break
            
        start_pos = idx + match.start()
        inner_start = idx + match.end()
        
        depth = 1
        sub_idx = inner_start
        while sub_idx < len(text):
            if text[sub_idx:].startswith('\\begin{enumerate'):
                depth += 1
                sub_idx += 16
            elif text[sub_idx:].startswith('\\end{enumerate}'):
                depth -= 1
                if depth == 0:
                    parent_text = text[idx:start_pos].strip()
                    inner_body = text[inner_start:sub_idx].strip()
                    results.append((parent_text, inner_body))
                    idx = sub_idx + 15
                    break
                sub_idx += 15
            else:
                sub_idx += 1
        else:
            idx = inner_start
            
    return results

def find_outer_enumerate(text: str) -> tuple[str, str, int, int]:
    """Find the first outer \begin{enumerate} and its matching \end{enumerate} in text."""
    match = re.search(r'\\begin\{enumerate\}(\[[^\]]*\])?', text)
    if not match:
        return text, "", -1, -1
        
    start_pos = match.start()
    depth = 1
    idx = match.end()
    while idx < len(text):
        if text[idx:].startswith('\\begin{enumerate'):
            depth += 1
            idx += 16
        elif text[idx:].startswith('\\end{enumerate}'):
            depth -= 1
            if depth == 0:
                parent_text = text[:start_pos].strip()
                inner_body = text[match.end():idx].strip()
                return parent_text, inner_body, start_pos, idx + 15
            idx += 15
        else:
            idx += 1
    return text, "", -1, -1

def extract_mcqs_and_opens(content: str) -> list[dict]:
    """Hierarchically parse LaTeX file content and extract MCQ or Open questions."""
    # Find all year blocks
    year_blocks = []
    matches = list(re.finditer(r'\\section\*?\{वर्ष\s*(20\d\d)\}', content))
    if not matches:
        matches = list(re.finditer(r'\\section\*?\{Year\s*(20\d\d)\}', content))
    
    if matches:
        for idx, m in enumerate(matches):
            year = int(m.group(1))
            start_pos = m.end()
            end_pos = matches[idx+1].start() if idx + 1 < len(matches) else len(content)
            year_blocks.append((year, content[start_pos:end_pos]))
    else:
        year_blocks.append((2024, content)) # Default fallback year
        
    extracted_questions = []
    
    for year, block_text in year_blocks:
        enums = find_all_outer_enumerates(block_text)
        
        for parent_instruction, inner_body in enums:
            parent_instruction_clean = clean_tex(parent_instruction)
            is_parent_instruction = _is_instruction(parent_instruction_clean)
            
            top_items = parse_enumerate_items(inner_body)
            
            for item in top_items:
                if not item.strip():
                    continue
                
                sub_parent, sub_body, _, _ = find_outer_enumerate(item)
                
                if sub_body:
                    sub_items = parse_enumerate_items(sub_body)
                    is_sub_parent_instruction = _is_instruction(sub_parent)
                    
                    combined_instruction = ""
                    if not is_parent_instruction and parent_instruction_clean:
                        combined_instruction = parent_instruction_clean
                    if not is_sub_parent_instruction and sub_parent:
                        if combined_instruction:
                            combined_instruction = f"{combined_instruction} : {clean_tex(sub_parent)}"
                        else:
                            combined_instruction = clean_tex(sub_parent)
                            
                    for sub_item in sub_items:
                        opt_parent, opts_body, _, _ = find_outer_enumerate(sub_item)
                        
                        if opts_body:
                            options = parse_enumerate_items(opts_body)
                            q_text = clean_tex(opt_parent)
                            if combined_instruction:
                                q_text = f"{combined_instruction} : {q_text}"
                                
                            if len(options) == 4:
                                extracted_questions.append({
                                    "text": q_text,
                                    "options": [clean_tex(o) for o in options],
                                    "type": "mcq",
                                    "year": year
                                })
                            else:
                                opt_str = " | ".join(clean_tex(o) for o in options)
                                subjective_text = f"{q_text} ({opt_str})"
                                extracted_questions.append({
                                    "text": subjective_text,
                                    "options": [],
                                    "type": "open",
                                    "year": year
                                })
                        else:
                            sub_text = clean_tex(sub_item)
                            if combined_instruction:
                                sub_text = f"{combined_instruction} : {sub_text}"
                            extracted_questions.append({
                                "text": sub_text,
                                "options": [],
                                "type": "open",
                                "year": year
                            })
                else:
                    q_text = clean_tex(item)
                    if _is_instruction(q_text):
                        continue
                        
                    parts = re.split(r'\bअथवा\b', q_text)
                    for part in parts:
                        part_clean = part.strip()
                        if part_clean and len(part_clean) > 5:
                            extracted_questions.append({
                                "text": part_clean,
                                "options": [],
                                "type": "open",
                                "year": year
                            })
                            
    return extracted_questions

def map_question_to_chapter(q_text: str, filename: str) -> tuple[str, str]:
    """Map a question to its proper chapter_id and subtopic based on keywords and filename."""
    lower_text = q_text.lower()
    
    # 1. Grammar Files mapping
    if "grammar" in filename:
        for ch_id, keywords in GRAMMAR_KEYWORDS.items():
            if any(kw in lower_text for kw in keywords):
                title = "व्याकरण"
                if ch_id == "hin_grammar_alankar": title = "Alankar"
                elif ch_id == "hin_grammar_affixes": title = "Upsarg & Pratyay"
                elif ch_id == "hin_grammar_idioms": title = "Idioms & Proverbs"
                elif ch_id == "hin_grammar_samas": title = "Samas"
                elif ch_id == "hin_grammar_phonetics": title = "Varn-Vicched"
                else: title = "Vocabulary"
                return ch_id, title
        return "hin_grammar_vocabulary", "Vocabulary"
        
    # 2. Essay/Letter Files mapping
    if "essay" in filename:
        if "हरिशंकर परसाई" in q_text:
            return "hin_kshitij_p5", "Premchand ke Phate Joote"
        if "राहुल सांकृत्यायन" in q_text:
            return "hin_kshitij_p2", "Lhasa ki Aur"
        if "प्रेमचंद" in q_text:
            return "hin_kshitij_p1", "Do Bailon Ki Katha"
        if "महादेवी वर्मा" in q_text:
            return "hin_kshitij_p6", "Mere Bachpan ke Din"
        return "hin_essay_writings", "Essay and Letter"
        
    # 3. Kshitiz & Kritika keyword mapping
    for ch_id, keywords in CHAPTER_KEYWORDS.items():
        if any(kw in q_text for kw in keywords):
            subtopic = "Kshitiz" if "kshitij" in ch_id else "Kritika"
            if ch_id == "hin_kshitij_p1": subtopic = "Do Bailon Ki Katha"
            elif ch_id == "hin_kshitij_p2": subtopic = "Lhasa ki Aur"
            elif ch_id == "hin_kshitij_p3": subtopic = "Upbhoktavad ki Sanskriti"
            elif ch_id == "hin_kshitij_p4": subtopic = "Sanwle Sapnon ki Yaad"
            elif ch_id == "hin_kshitij_p5": subtopic = "Premchand ke Phate Joote"
            elif ch_id == "hin_kshitij_p6": subtopic = "Mere Bachpan ke Din"
            elif ch_id == "hin_kritika_1": subtopic = "Is Jal Pralay Mein"
            elif ch_id == "hin_kritika_2": subtopic = "Mere Sang ki Auratein"
            elif ch_id == "hin_kritika_3": subtopic = "Reedh ki Haddi"
            return ch_id, subtopic
            
    # Fallbacks based on filename
    if "kritika" in filename:
        return "hin_kritika_1", "Is Jal Pralay Mein"
    return "hin_kshitij_p1", "Do Bailon Ki Katha"

async def get_correct_answer_index(q_text: str, options: list[str]) -> int:
    """Use OpenRouter LLM to verify the correct answer of the Hindi MCQ."""
    if not settings.OPENROUTER_API_KEY:
        return 0
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "X-Title": "HBSE Question Parser Seeder",
        "Content-Type": "application/json"
    }
    
    prompt = f"""दी गई हिंदी बहुविकल्पीय प्रश्न (MCQ) के लिए सही विकल्प का इंडेक्स (0, 1, 2, या 3) बताइए।
प्रश्न: {q_text}
विकल्प:
0. {options[0]}
1. {options[1]}
2. {options[2]}
3. {options[3]}

केवल सही विकल्प का इंडेक्स नंबर (0, 1, 2, या 3) ही लिखें। अतिरिक्त कोई भी शब्द या स्पष्टीकरण न लिखें।
उत्तर:"""
    
    payload = {
        "model": settings.OPENROUTER_MODEL or "meta-llama/llama-3.3-70b-instruct",
        "messages": [
            {"role": "system", "content": "You are a Hindi subject expert. Answer with a single digit index only."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 5
    }
    
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if r.status_code == 200:
                res = r.json()
                content = res["choices"][0]["message"]["content"].strip()
                match = re.search(r'[0-3]', content)
                if match:
                    val = int(match.group(0))
                    return val
    except Exception as e:
        logger.warning(f"Error querying correct answer: {e}")
        
    return 0

async def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hindi_folder = os.path.join(project_root, "Class 9", "Chapter wise papers", "HINDI")
    
    files = {
        "essay_letter_author_questions.tex": os.path.join(hindi_folder, "essay_letter_author_questions.tex"),
        "grammar_questions.tex": os.path.join(hindi_folder, "grammar_questions.tex"),
        "kritika_questions.tex": os.path.join(hindi_folder, "kritika_questions.tex"),
        "kshitiz_questions.tex": os.path.join(hindi_folder, "kshitiz_questions.tex")
    }
    
    raw_questions = []
    
    for name, filepath in files.items():
        if not os.path.exists(filepath):
            logger.error(f"File {name} not found at {filepath}")
            continue
            
        logger.info(f"Parsing {name}...")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        questions = extract_mcqs_and_opens(content)
        logger.info(f"Extracted {len(questions)} raw questions from {name}")
        
        for q in questions:
            q["filename"] = name
            raw_questions.append(q)
            
    logger.info(f"Total raw questions extracted: {len(raw_questions)}")
    
    seen_texts = set()
    mapped_questions = []
    
    for q in raw_questions:
        txt = q["text"]
        normalized_txt = re.sub(r'\s+', '', txt)
        if normalized_txt in seen_texts or len(txt) < 8:
            continue
        seen_texts.add(normalized_txt)
        
        chapter_id, subtopic = map_question_to_chapter(txt, q["filename"])
        
        q["book_id"] = "Hindi"
        q["chapter_id"] = chapter_id
        q["subtopic"] = subtopic
        mapped_questions.append(q)
        
    logger.info(f"Total unique questions after deduplication: {len(mapped_questions)}")
    
    mcqs = [q for q in mapped_questions if q["type"] == "mcq"]
    logger.info(f"Querying correct answer indices for {len(mcqs)} MCQs...")
    
    for idx, mcq in enumerate(mcqs):
        correct_idx = await get_correct_answer_index(mcq["text"], mcq["options"])
        mcq["correct_answer"] = correct_idx
        if (idx + 1) % 10 == 0:
            logger.info(f"Processed {idx + 1}/{len(mcqs)} MCQs...")
            
    final_questions = []
    for i, q in enumerate(mapped_questions):
        q_key = f"q_hin_{q['chapter_id']}_pyq{q['year']}_{q['type']}_{i + 1}"
        
        tier = 2
        if q["type"] == "mcq":
            tier = 1
        elif q["chapter_id"] in ["hin_essay_writings", "hin_kritika_3"]:
            tier = 3
            
        marks = 1
        if q["type"] == "open":
            marks = 2 if q["chapter_id"] != "hin_essay_writings" else 5
            
        final_questions.append({
            "q_key": q_key,
            "book_id": "Hindi",
            "chapter_id": q["chapter_id"],
            "tier": tier,
            "text": q["text"],
            "options": q["options"],
            "correct_answer": q.get("correct_answer", 0),
            "subtopic": q["subtopic"],
            "is_pyq": 1,
            "pyq_year": q["year"],
            "question_type": "mcq" if q["type"] == "mcq" else "open",
            "marks": marks
        })
        
    output_filepath = os.path.join(project_root, "data", "questions", "hindi.json")
    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
    with open(output_filepath, "w", encoding="utf-8") as f:
        json.dump(final_questions, f, ensure_ascii=False, indent=2)
    logger.info(f"Successfully saved {len(final_questions)} questions to {output_filepath}")
    
    logger.info("Initializing connection to database...")
    await init_db()
    
    logger.info("Clearing old Hindi PYQ questions from database to avoid duplicates...")
    async with get_pool().acquire() as conn:
        deleted = await conn.execute("DELETE FROM questions WHERE book_id = 'Hindi' AND is_pyq = TRUE")
        logger.info(f"Removed {deleted} old records.")
        
    logger.info("Seeding new parsed questions into DB...")
    inserted_count = 0
    for q in final_questions:
        try:
            await add_question(
                book_id=q["book_id"],
                chapter_id=q["chapter_id"],
                tier=q["tier"],
                text=q["text"],
                options=q["options"],
                correct_answer=q["correct_answer"],
                subtopic=q["subtopic"],
                is_pyq=1,
                pyq_year=q["pyq_year"],
                q_key=q["q_key"],
                question_type=q["question_type"],
                marks=q["marks"]
            )
            inserted_count += 1
        except Exception as e:
            logger.error(f"Error seeding question {q['q_key']}: {e}")
            
    logger.info(f"Successfully seeded {inserted_count} questions into the database!")

if __name__ == "__main__":
    asyncio.run(main())
