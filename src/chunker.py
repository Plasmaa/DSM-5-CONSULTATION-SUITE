import re
import fitz
from transformers import AutoTokenizer

# Comprehensive standard DSM-5 headings that define section boundaries
SECTION_HEADERS = [
    "Diagnostic Criteria",
    "Proposed Criteria",
    "Diagnostic Features",
    "Associated Features Supporting Diagnosis",
    "Associated Features",
    "Subtypes",
    "Specifiers",
    "Prevalence",
    "Development and Course",
    "Risk and Prognostic Factors",
    "Culture-Related Diagnostic Issues",
    "Gender-Related Diagnostic Issues",
    "Suicide Risk",
    "Diagnostic Markers",
    "Functional Consequences",
    "Differential Diagnosis",
    "Comorbidity",
    "Recording Procedures",
    "Relationship to Other Classifications"
]

# Major DSM-5 chapter / part boundaries
MAJOR_DIVIDERS = [
    "Section III",
    "Highlights of Changes",
    "Glossary of Technical Terms",
    "Glossary of Cultural Concepts",
    "Alphabetical Listing",
    "Numerical Listing",
    "Index"
]

class DSM5Chunker:
    def __init__(self, target_tokens=400, max_tokens=450):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        
        # Compiled patterns
        self.code_pattern = re.compile(r'^\s*([0-9V]\d{2}(?:\.\d{1,3})?)\s*(?:\(([A-Z]\d{2,3}(?:\.\d{1,2})?)\))?\s*(.*)$')
        self.criterion_pattern = re.compile(r'^(?:Criterion\s+)?([A-Z])\.\s+', re.MULTILINE)
        self.clean_soft_hyphens = re.compile(r'(\w+)[\u00ad\ufffd\xad\-\u2010\u2011]\s*\n\s*(\w+)')
        self.clean_generic_replacements = re.compile(r'[\u00ad\ufffd\xad\u2010\u2011]')

        # Load tokenizer for BGE / BERT
        try:
            self.tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-large-en-v1.5")
        except Exception:
            self.tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

    def clean_text(self, text):
        """Clean PDF text artifacts, soft hyphens, and whitespace anomalies."""
        text = self.clean_soft_hyphens.sub(r'\1\2', text)
        text = self.clean_generic_replacements.sub('', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def count_tokens(self, text):
        """Count tokens including special tokens like [CLS] and [SEP]."""
        return len(self.tokenizer.encode(text, add_special_tokens=True))

    def _split_into_units(self, text):
        """Split text by criterion (A., B., C.) or double newlines (paragraphs)."""
        # If text has DSM-5 criteria markers (e.g. A., B., C.), split preserving them
        matches = list(self.criterion_pattern.finditer(text))
        if len(matches) >= 2:
            units = []
            prev_idx = 0
            for m in matches:
                if m.start() > prev_idx:
                    seg = text[prev_idx:m.start()].strip()
                    if seg:
                        units.append(seg)
                prev_idx = m.start()
            if prev_idx < len(text):
                seg = text[prev_idx:].strip()
                if seg:
                    units.append(seg)
            if units:
                return units

        # Default: split by paragraphs
        paras = [p.strip() for p in text.split('\n\n') if p.strip()]
        if len(paras) > 1:
            return paras

        # Fallback: split by sentences if single huge paragraph
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _sub_chunk_section(self, disorder_name, code, section_type, content, page_num):
        """Second-pass: Split a large section into <= max_tokens sub-chunks with prepended metadata header."""
        header_prefix = f"{disorder_name}"
        if code:
            header_prefix += f" ({code})"
        header_prefix += f" — {section_type}\n\n"
        
        prefix_token_count = len(self.tokenizer.encode(header_prefix, add_special_tokens=False))
        # Available tokens for chunk body (leaving room for [CLS], [SEP] + buffer)
        available_budget = self.max_tokens - prefix_token_count - 5
        if available_budget < 100:
            available_budget = 350 # fallback safety

        full_tokens = self.count_tokens(header_prefix + content)
        if full_tokens <= self.max_tokens:
            return [{
                "disorder_name": disorder_name,
                "code": code,
                "section_type": section_type,
                "content": (header_prefix + content).strip(),
                "page_number": page_num,
                "chunk_index": 0
            }]

        # Split into semantic units (criteria / paragraphs / sentences)
        units = self._split_into_units(content)
        sub_chunks = []
        current_body = []
        current_body_tokens = 0
        chunk_idx = 0

        for unit in units:
            unit_tokens = len(self.tokenizer.encode(unit, add_special_tokens=False))
            
            # If a single unit itself exceeds budget, split it by sentence or hard boundary
            if unit_tokens > available_budget:
                sentences = re.split(r'(?<=[.!?])\s+', unit)
                for sent in sentences:
                    sent_tokens = len(self.tokenizer.encode(sent, add_special_tokens=False))
                    if current_body_tokens + sent_tokens > available_budget and current_body:
                        body_txt = "\n\n".join(current_body)
                        sub_chunks.append({
                            "disorder_name": disorder_name,
                            "code": code,
                            "section_type": section_type,
                            "content": (header_prefix + body_txt).strip(),
                            "page_number": page_num,
                            "chunk_index": chunk_idx
                        })
                        chunk_idx += 1
                        current_body = []
                        current_body_tokens = 0
                    current_body.append(sent)
                    current_body_tokens += sent_tokens
                continue

            if current_body_tokens + unit_tokens > available_budget and current_body:
                body_txt = "\n\n".join(current_body)
                sub_chunks.append({
                    "disorder_name": disorder_name,
                    "code": code,
                    "section_type": section_type,
                    "content": (header_prefix + body_txt).strip(),
                    "page_number": page_num,
                    "chunk_index": chunk_idx
                })
                chunk_idx += 1
                current_body = []
                current_body_tokens = 0

            current_body.append(unit)
            current_body_tokens += unit_tokens

        if current_body:
            body_txt = "\n\n".join(current_body)
            sub_chunks.append({
                "disorder_name": disorder_name,
                "code": code,
                "section_type": section_type,
                "content": (header_prefix + body_txt).strip(),
                "page_number": page_num,
                "chunk_index": chunk_idx
            })

        return sub_chunks

    def extract_chunks(self, pdf_path):
        """Extract all DSM-5 chunks with strict section boundaries and token-capped sub-chunking."""
        doc = fitz.open(pdf_path)
        print(f"Loaded PDF: {pdf_path} ({len(doc)} pages)")

        raw_sections = []
        current_disorder = "Introduction"
        current_code = ""
        current_section = "Overview"
        section_lines = []
        active_page = 1
        recent_lines = []

        def flush_active_section(p_num):
            nonlocal section_lines, current_disorder, current_code, current_section, active_page
            if section_lines:
                raw_text = "\n".join(section_lines).strip()
                cleaned = self.clean_text(raw_text)
                if len(cleaned) >= 40:
                    raw_sections.append({
                        "disorder_name": current_disorder,
                        "code": current_code,
                        "section_type": current_section,
                        "page_number": active_page,
                        "content": cleaned
                    })
                section_lines = []

        for page_idx in range(len(doc)):
            page_num = page_idx + 1

            # Deliberately exclude front matter (< page 67) and appendices/index (>= page 833)
            if page_num < 67 or page_num >= 833:
                continue

            text = doc[page_idx].get_text("text")
            lines = [l.strip() for l in text.split('\n') if l.strip()]

            for line in lines:
                if line.isdigit() or "Diagnostic and Statistical Manual" in line:
                    continue

                # Check for major divider (e.g. Section III, Highlights of Changes, Index)
                is_major_divider = False
                for div in MAJOR_DIVIDERS:
                    if div.lower() in line.lower():
                        is_major_divider = True
                        break
                if is_major_divider:
                    flush_active_section(page_num)
                    current_disorder = "Section III / Emerging Measures" if page_num >= 759 else "General DSM-5"
                    current_section = line
                    active_page = page_num
                    recent_lines = []
                    continue

                # Check for Diagnostic / Proposed Criteria
                is_criteria_header = (
                    line.lower() == "diagnostic criteria" or
                    line.lower() == "diagnostic criteria:" or
                    line.lower() == "proposed criteria" or
                    line.lower() == "proposed criteria:"
                )

                # Check for standalone code line e.g. "300.02 (F41.1) Generalized Anxiety Disorder"
                code_match = self.code_pattern.match(line)
                is_standalone_disorder = False
                cand_name = None
                cand_code = ""

                if code_match:
                    c1, c2, rest = code_match.group(1), code_match.group(2), code_match.group(3)
                    cand_code = f"{c1} ({c2})" if c2 else c1
                    if rest and len(rest) > 3 and not rest.endswith('.'):
                        is_standalone_disorder = True
                        cand_name = rest.strip()

                if is_criteria_header:
                    flush_active_section(page_num)
                    # Infer disorder name from previous lines
                    for r_line in reversed(recent_lines):
                        if (len(r_line) > 3 and len(r_line) < 80 and
                            not any(r_line.lower() == h.lower() for h in SECTION_HEADERS) and
                            not r_line.endswith('.') and not r_line.endswith(';')):
                            current_disorder = r_line
                            break
                    current_section = "Diagnostic Criteria" if "diagnostic" in line.lower() else "Proposed Criteria"
                    active_page = page_num
                    recent_lines = []
                    continue

                if is_standalone_disorder:
                    flush_active_section(page_num)
                    current_disorder = cand_name
                    current_code = cand_code
                    current_section = "Diagnostic Criteria"
                    active_page = page_num
                    recent_lines = []
                    continue

                # Check standard subsection headers
                matched_sec = None
                for h in SECTION_HEADERS:
                    if line.lower() == h.lower() or line.lower().startswith(h.lower() + " of ") or line.lower() == h.lower() + ":":
                        matched_sec = h
                        break

                if matched_sec:
                    flush_active_section(page_num)
                    current_section = matched_sec
                    active_page = page_num
                    continue

                section_lines.append(line)
                recent_lines.append(line)
                if len(recent_lines) > 8:
                    recent_lines.pop(0)

        # Flush final section
        flush_active_section(832)

        print(f"Extracted {len(raw_sections)} raw bounded sections. Running token-aware sub-chunking pass...")

        # Second Pass: Sub-chunk into max_tokens chunks with disambiguated IDs
        final_chunks = []
        import hashlib

        for sec in raw_sections:
            sub_chunks = self._sub_chunk_section(
                sec["disorder_name"],
                sec["code"],
                sec["section_type"],
                sec["content"],
                sec["page_number"]
            )
            for sc in sub_chunks:
                # Include chunk_index in ID to avoid collisions
                id_str = f"{sc['disorder_name']}_{sc['section_type']}_{sc['page_number']}_chunk{sc['chunk_index']}"
                det_id = hashlib.md5(id_str.encode('utf-8')).hexdigest()
                sc["id"] = det_id
                final_chunks.append(sc)

        print(f"Sub-chunking complete: Produced {len(final_chunks)} total chunks.")
        return final_chunks
