import re
import fitz
from transformers import AutoTokenizer

# Standard clinical subsection headings
SUBSECTION_HEADERS = [
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

# Major structural divides
MAJOR_DIVIDERS = [
    "Section III",
    "Assessment Measures",
    "Cultural Formulation",
    "Alternative DSM-5 Model",
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
        """Split text by criterion (A., B., C.), double newlines, single newlines, or sentences."""
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

        # Split by double newline or single newline if paragraphs are structured with newlines
        paras = [p.strip() for p in re.split(r'\n{1,2}', text) if p.strip()]
        if len(paras) > 1:
            return paras

        # Fallback: split by sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        if sentences:
            return sentences
        return [text]

    def _sub_chunk_section(self, disorder_name, code, section_type, chunk_type, content, page_num):
        """Second-pass: Split a large section into <= max_tokens sub-chunks with prepended metadata header."""
        header_prefix = f"{disorder_name}"
        if code:
            header_prefix += f" ({code})"
        header_prefix += f" — {section_type}\n\n"
        
        prefix_token_count = len(self.tokenizer.encode(header_prefix, add_special_tokens=False))
        available_budget = self.max_tokens - prefix_token_count - 10
        if available_budget < 100:
            available_budget = 300

        full_tokens = self.count_tokens(header_prefix + content)
        if full_tokens <= self.max_tokens:
            return [{
                "disorder_name": disorder_name,
                "code": code,
                "section_type": section_type,
                "chunk_type": chunk_type,
                "content": (header_prefix + content).strip(),
                "page_number": page_num,
                "chunk_index": 0
            }]

        units = self._split_into_units(content)
        sub_chunks = []
        current_body = []
        current_body_tokens = 0
        chunk_idx = 0

        for unit in units:
            unit_tokens = len(self.tokenizer.encode(unit, add_special_tokens=False))
            
            # If a single unit itself exceeds budget, split it by sentence or hard boundary
            if unit_tokens > available_budget:
                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', unit) if s.strip()]
                if not sentences:
                    sentences = [unit]
                for sent in sentences:
                    sent_tokens = len(self.tokenizer.encode(sent, add_special_tokens=False))
                    # If even an individual sentence exceeds available budget, slice by words
                    if sent_tokens > available_budget:
                        words = sent.split()
                        curr_slice = []
                        curr_slice_toks = 0
                        for w in words:
                            w_toks = len(self.tokenizer.encode(w + " ", add_special_tokens=False))
                            if current_body_tokens + curr_slice_toks + w_toks > available_budget and (current_body or curr_slice):
                                full_slice = current_body + [" ".join(curr_slice)] if curr_slice else current_body
                                sub_chunks.append({
                                    "disorder_name": disorder_name,
                                    "code": code,
                                    "section_type": section_type,
                                    "chunk_type": chunk_type,
                                    "content": (header_prefix + "\n\n".join(full_slice)).strip(),
                                    "page_number": page_num,
                                    "chunk_index": chunk_idx
                                })
                                chunk_idx += 1
                                current_body = []
                                current_body_tokens = 0
                                curr_slice = []
                                curr_slice_toks = 0
                            curr_slice.append(w)
                            curr_slice_toks += w_toks
                        if curr_slice:
                            current_body.append(" ".join(curr_slice))
                            current_body_tokens += curr_slice_toks
                        continue

                    if current_body_tokens + sent_tokens > available_budget and current_body:
                        body_txt = "\n\n".join(current_body)
                        sub_chunks.append({
                            "disorder_name": disorder_name,
                            "code": code,
                            "section_type": section_type,
                            "chunk_type": chunk_type,
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
                    "chunk_type": chunk_type,
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
                "chunk_type": chunk_type,
                "content": (header_prefix + body_txt).strip(),
                "page_number": page_num,
                "chunk_index": chunk_idx
            })

        # Step 4: Merge trailing sub-chunks under 60 tokens into the previous one if it fits in max_tokens
        merged = []
        for sc in sub_chunks:
            sc_tokens = self.count_tokens(sc["content"])
            if sc_tokens < 60 and merged:
                prev = merged[-1]
                # Try combining bodies
                prev_body = prev["content"]
                # Strip duplicate header prefix from sc
                sc_body = sc["content"]
                if header_prefix.strip() in sc_body:
                    sc_body = sc_body.replace(header_prefix.strip(), "").strip()
                combined_content = f"{prev_body}\n\n{sc_body}".strip()
                if self.count_tokens(combined_content) <= self.max_tokens:
                    prev["content"] = combined_content
                    continue
            merged.append(sc)

        # Re-index chunks
        for idx, sc in enumerate(merged):
            sc["chunk_index"] = idx

        return merged

    def extract_chunks(self, pdf_path):
        """Extract all DSM-5 chunks with visual font title detection, strict boundaries, and token-budget splitting."""
        doc = fitz.open(pdf_path)
        print(f"Loaded PDF: {pdf_path} ({len(doc)} pages)")

        raw_sections = []
        current_disorder = "Introduction"
        current_code = ""
        current_section = "Overview"
        current_chunk_type = "class_intro"
        section_lines = []
        active_page = 1

        def flush_active_section(p_num):
            nonlocal section_lines, current_disorder, current_code, current_section, current_chunk_type, active_page
            if section_lines:
                raw_text = "\n".join(section_lines).strip()
                cleaned = self.clean_text(raw_text)
                if len(cleaned) >= 30:
                    raw_sections.append({
                        "disorder_name": current_disorder,
                        "code": current_code,
                        "section_type": current_section,
                        "chunk_type": current_chunk_type,
                        "page_number": active_page,
                        "content": cleaned
                    })
                section_lines = []

        for page_idx in range(len(doc)):
            page_num = page_idx + 1

            # Deliberately exclude front matter (< page 67) and appendices/index (>= page 833)
            if page_num < 67 or page_num >= 833:
                continue

            page = doc[page_idx]
            page_dict = page.get_text("dict")

            # Extract lines with font metadata
            extracted_lines = []
            for b in page_dict.get("blocks", []):
                if "lines" in b:
                    for l in b["lines"]:
                        spans = l.get("spans", [])
                        if not spans:
                            continue
                        line_text = "".join(s.get("text", "") for s in spans).strip()
                        if not line_text:
                            continue
                        # Get dominant span size and font
                        max_span = max(spans, key=lambda s: len(s.get("text", "")))
                        extracted_lines.append({
                            "text": line_text,
                            "size": max_span.get("size", 9.5),
                            "font": max_span.get("font", ""),
                            "flags": max_span.get("flags", 0)
                        })

            i = 0
            while i < len(extracted_lines):
                item = extracted_lines[i]
                line = item["text"]
                size = item["size"]
                font = item["font"]
                lower_line = line.lower()

                # Skip running headers / footers
                if line.isdigit() or "diagnostic and statistical manual" in lower_line:
                    i += 1
                    continue

                # 1. Major divider check (Section III, etc.)
                is_major_divider = False
                for div in MAJOR_DIVIDERS:
                    if div.lower() in lower_line:
                        is_major_divider = True
                        break
                if is_major_divider:
                    flush_active_section(page_num)
                    current_disorder = "Section III / Emerging Measures" if page_num >= 759 else "General DSM-5"
                    current_code = ""
                    current_section = line
                    current_chunk_type = "section_iii" if page_num >= 759 else "class_intro"
                    active_page = page_num
                    i += 1
                    continue

                # 2. Diagnostic Class Heading (size >= 19.5pt) e.g. "Schizophrenia Spectrum...", "Disruptive, Impulse-Control..."
                # Must start with an uppercase ASCII letter and contain valid English alphabetic words (not OCR artifacts like 'alilll')
                if size >= 19.5 and ("bold" in font.lower() or "arial" in font.lower()) and len(line) > 3:
                    if line[0].isupper() and re.match(r'^[A-Z][A-Za-z\s,\-\/\(\)]+$', line):
                        heading_lines = [line]
                        while i + 1 < len(extracted_lines) and extracted_lines[i+1]["size"] >= 19.5:
                            next_text = extracted_lines[i+1]["text"].strip()
                            if not re.match(r'^[A-Za-z\s,\-\/\(\)]+$', next_text):
                                break
                            i += 1
                            heading_lines.append(next_text)
                        full_class_name = " ".join(heading_lines).strip()
                        if full_class_name[0].isupper():
                            flush_active_section(page_num)
                            current_disorder = full_class_name
                            current_code = ""
                            current_section = "Diagnostic Class Overview"
                            current_chunk_type = "class_intro"
                            active_page = page_num
                            i += 1
                            continue

                # 3. Disorder Title by Font Size (size >= 15.0pt and < 19.5pt, Bold)
                # Matches "Major Depressive Disorder", "Kleptomania", "Posttraumatic Stress Disorder", etc.
                if 15.0 <= size < 19.5 and ("bold" in font.lower() or "arial" in font.lower()):
                    if line and line[0].isupper() and not any(lower_line == h.lower() for h in SUBSECTION_HEADERS):
                        heading_lines = [line]
                        while i + 1 < len(extracted_lines) and 15.0 <= extracted_lines[i+1]["size"] < 19.5:
                            next_text = extracted_lines[i+1]["text"].strip()
                            if any(next_text.lower() == h.lower() for h in SUBSECTION_HEADERS) or not next_text:
                                break
                            if not next_text[0].isupper():
                                break
                            i += 1
                            heading_lines.append(next_text)
                        
                        full_title = " ".join(heading_lines).strip()
                        if len(full_title) > 3 and not full_title.startswith("With") and not full_title.startswith("Due to") and not full_title.startswith("Unspecified type"):
                            flush_active_section(page_num)
                            current_disorder = full_title
                            current_code = ""
                            current_section = "Diagnostic Criteria"
                            current_chunk_type = "disorder"
                            active_page = page_num
                            i += 1
                            continue

                # 4. Other Specified... / Unspecified... Disorders
                # Treat "Other Specified..." and "Unspecified..." as their own disorders and end previous section!
                if (lower_line.startswith("other specified") or lower_line.startswith("unspecified")) and line[0].isupper():
                    if not lower_line.endswith('.') and len(line) < 70 and not lower_line.startswith("unspecified type"):
                        flush_active_section(page_num)
                        current_disorder = line
                        current_code = ""
                        current_section = "Diagnostic Criteria"
                        current_chunk_type = "disorder"
                        active_page = page_num
                        i += 1
                        continue

                # 5. Diagnostic Criteria / Proposed Criteria header
                is_criteria = (
                    lower_line == "diagnostic criteria" or
                    lower_line == "diagnostic criteria:" or
                    lower_line == "proposed criteria" or
                    lower_line == "proposed criteria:"
                )
                if is_criteria:
                    flush_active_section(page_num)
                    current_section = "Diagnostic Criteria" if "diagnostic" in lower_line else "Proposed Criteria"
                    active_page = page_num
                    i += 1
                    continue

                # 6. Standalone ICD code header
                code_match = self.code_pattern.match(line)
                if code_match:
                    c1, c2, rest = code_match.group(1), code_match.group(2), code_match.group(3)
                    matched_code = f"{c1} ({c2})" if c2 else c1
                    clean_rest = rest.strip() if rest else ""

                    # Validate clean_rest is a legitimate disorder title:
                    # - Must not start with lowercase
                    # - Must not start with specifiers / subtitles like "With", "Due to", "Unspecified type", or end with punctuation
                    # - Must be Title Cased or start with uppercase
                    is_valid_disorder_name = (
                        len(clean_rest) > 3 and
                        clean_rest[0].isupper() and
                        not clean_rest.startswith("With") and
                        not clean_rest.startswith("Due to") and
                        not clean_rest.startswith("Unspecified type") and
                        not clean_rest.endswith('.') and
                        not clean_rest.endswith(';') and
                        not clean_rest.endswith(':') and
                        len(clean_rest) < 80
                    )

                    if is_valid_disorder_name:
                        flush_active_section(page_num)
                        current_disorder = clean_rest
                        current_code = matched_code
                        current_section = "Diagnostic Criteria"
                        if page_num >= 746 and page_num <= 758:
                            current_chunk_type = "other_conditions"
                        else:
                            current_chunk_type = "disorder"
                        active_page = page_num
                        i += 1
                        continue
                    elif not current_code and current_section in ["Diagnostic Criteria", "Proposed Criteria"]:
                        current_code = matched_code
                        i += 1
                        continue

                # 7. Standard subsection headers
                matched_sec = None
                for h in SUBSECTION_HEADERS:
                    if lower_line == h.lower() or lower_line.startswith(h.lower() + " of ") or lower_line == h.lower() + ":":
                        matched_sec = h
                        break

                if matched_sec:
                    flush_active_section(page_num)
                    current_section = matched_sec
                    active_page = page_num
                    i += 1
                    continue

                # Regular text line
                section_lines.append(line)
                i += 1

        # Flush final active section
        flush_active_section(832)

        print(f"Extracted {len(raw_sections)} raw bounded sections. Running sub-chunking & merge pass...")

        # Second Pass: Sub-chunk into max_tokens chunks with disambiguated IDs
        final_chunks = []
        import hashlib

        for sec in raw_sections:
            sub_chunks = self._sub_chunk_section(
                sec["disorder_name"],
                sec["code"],
                sec["section_type"],
                sec["chunk_type"],
                sec["content"],
                sec["page_number"]
            )
            for sc in sub_chunks:
                id_str = f"{sc['disorder_name']}_{sc['section_type']}_{sc['page_number']}_chunk{sc['chunk_index']}"
                det_id = hashlib.md5(id_str.encode('utf-8')).hexdigest()
                sc["id"] = det_id
                final_chunks.append(sc)

        print(f"Produced {len(final_chunks)} total chunks.")
        return final_chunks
