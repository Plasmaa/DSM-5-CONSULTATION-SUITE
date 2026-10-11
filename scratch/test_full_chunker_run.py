import fitz
import re
from collections import defaultdict
from rapidfuzz import fuzz, process
from transformers import AutoTokenizer

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

class TestDSM5Chunker:
    def __init__(self, target_tokens=400, max_tokens=450):
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.code_pattern = re.compile(r'^\s*([0-9V]\d{2}(?:\.\d{1,3})?)\s*(?:\(([A-Z]\d{2,3}(?:\.\d{1,2})?)\))?\s*(.*)$')
        self.criterion_pattern = re.compile(r'^(?:Criterion\s+)?([A-Z])\.\s+', re.MULTILINE)
        self.clean_soft_hyphens = re.compile(r'(\w+)[\u00ad\ufffd\xad\-\u2010\u2011]\s*\n\s*(\w+)')
        self.clean_generic_replacements = re.compile(r'[\u00ad\ufffd\xad\u2010\u2011]')

        try:
            self.tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-large-en-v1.5")
        except Exception:
            self.tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
            
        self.canonical_toc = []

    def clean_text(self, text):
        text = self.clean_soft_hyphens.sub(r'\1\2', text)
        text = self.clean_generic_replacements.sub('', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def count_tokens(self, text):
        return len(self.tokenizer.encode(text, add_special_tokens=True))

    def build_canonical_toc(self, doc):
        toc_entries = []
        for level, title, page in doc.get_toc():
            clean_title = re.sub(r'[\u00ae\u00a9\u2010\u2011\xad\ufffd\^*\'\"]+', '', title).strip()
            clean_title = re.sub(r'^Section\s+[I|V|X]+\.\s*', '', clean_title).strip()
            if page >= 67 and page < 833:
                if clean_title and len(clean_title) > 3:
                    toc_entries.append(clean_title)

        for p in range(12, 40):
            page = doc[p]
            text = page.get_text()
            text = re.sub(r'(\w+)[\u00ad\ufffd\xad\-\u2010\u2011]\s*\n\s*(\w+)', r'\1\2', text)
            lines = text.split('\n')
            pending_lines = []
            for raw_line in lines:
                line = raw_line.strip()
                if not line:
                    continue
                if (line.startswith("Specify") or line.startswith("Note:") or 
                    line.startswith("ICD-") or line.startswith("Before each") or 
                    line.startswith("Following chapter") or line.startswith("Blank lines")):
                    pending_lines = []
                    continue
                if re.match(r'^[■•·\*\^\'\.\|\-_]+$', line):
                    continue
                if re.match(r'^[\d\s\._\(\)A-Z\-,/]+$', line) and any(c.isdigit() for c in line):
                    continue
                if re.match(r'^_+[._\s\(\)]*$', line):
                    continue
                    
                m = re.search(r'\(\s*(\d+)\s*\)\s*[\^\*\'\"\s]*$', line)
                if m:
                    line_head = line[:m.start()].strip()
                    if line_head:
                        pending_lines.append(line_head)
                    full_cand = " ".join(pending_lines).strip()
                    pending_lines = []
                    
                    full_cand = re.sub(r'^[0-9V]\d{2}(?:\.\d{1,3})?\s*(?:\([A-Z]\d{2,3}(?:\.\d{1,2})?\))?\s*', '', full_cand)
                    full_cand = re.sub(r'^[\d\s\._\(\)A-Z\-,/]+?\s{2,}', '', full_cand)
                    full_cand = re.sub(r'[\u00ae\u00a9\u2010\u2011\xad\ufffd\^*\'\"■•·]+', '', full_cand).strip()
                    
                    if full_cand and len(full_cand) > 3 and full_cand[0].isupper():
                        alpha_ratio = sum(c.isalpha() for c in full_cand) / len(full_cand)
                        if alpha_ratio >= 0.6:
                            toc_entries.append(full_cand)
                            base_match = re.match(r'^(.*?)\s*\((?:includes|also)\s+.*?\)$', full_cand, re.IGNORECASE)
                            if base_match:
                                toc_entries.append(base_match.group(1).strip())
                else:
                    if line[0].isupper() or line[0] in ['(', '"']:
                        cleaned_l = re.sub(r'[\u00ae\u00a9\u2010\u2011\xad\ufffd\^*\'\"■•·]+', '', line).strip()
                        if cleaned_l:
                            pending_lines.append(cleaned_l)
                    else:
                        pending_lines = []
                        
        seen = set()
        canonical = []
        for t in toc_entries:
            norm = " ".join(t.split())
            if norm.lower() not in seen:
                seen.add(norm.lower())
                canonical.append(norm)
        return canonical

    def match_canonical(self, candidate, threshold=90):
        if not candidate:
            return None
        cand_norm = " ".join(candidate.split()).strip()
        for c in self.canonical_toc:
            if cand_norm.lower() == c.lower():
                return c
                
        match, score, _ = process.extractOne(cand_norm, self.canonical_toc, scorer=fuzz.ratio)
        if score >= threshold:
            return match
            
        match_ts, score_ts, _ = process.extractOne(cand_norm, self.canonical_toc, scorer=fuzz.token_set_ratio)
        if score_ts >= 95 and abs(len(cand_norm) - len(match_ts)) < 15:
            return match_ts
            
        return None

    def _split_into_units(self, text):
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

        paras = [p.strip() for p in re.split(r'\n{1,2}', text) if p.strip()]
        if len(paras) > 1:
            return paras

        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        if sentences:
            return sentences
        return [text]

    def _sub_chunk_section(self, disorder_name, code, section_type, chunk_type, content, page_num):
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
            if unit_tokens > available_budget:
                sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', unit) if s.strip()]
                if not sentences:
                    sentences = [unit]
                for sent in sentences:
                    sent_tokens = len(self.tokenizer.encode(sent, add_special_tokens=False))
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
                                curr_slice = [w]
                                curr_slice_toks = w_toks
                            else:
                                curr_slice.append(w)
                                curr_slice_toks += w_toks
                        if curr_slice:
                            current_body.append(" ".join(curr_slice))
                            current_body_tokens += curr_slice_toks
                    elif current_body_tokens + sent_tokens > available_budget and current_body:
                        sub_chunks.append({
                            "disorder_name": disorder_name,
                            "code": code,
                            "section_type": section_type,
                            "chunk_type": chunk_type,
                            "content": (header_prefix + "\n\n".join(current_body)).strip(),
                            "page_number": page_num,
                            "chunk_index": chunk_idx
                        })
                        chunk_idx += 1
                        current_body = [sent]
                        current_body_tokens = sent_tokens
                    else:
                        current_body.append(sent)
                        current_body_tokens += sent_tokens
                continue

            if current_body_tokens + unit_tokens > available_budget and current_body:
                sub_chunks.append({
                    "disorder_name": disorder_name,
                    "code": code,
                    "section_type": section_type,
                    "chunk_type": chunk_type,
                    "content": (header_prefix + "\n\n".join(current_body)).strip(),
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

        merged = []
        for sc in sub_chunks:
            sc_tokens = self.count_tokens(sc["content"])
            if sc_tokens < 60 and merged:
                prev = merged[-1]
                prev_body = prev["content"]
                sc_body = sc["content"]
                if header_prefix.strip() in sc_body:
                    sc_body = sc_body.replace(header_prefix.strip(), "").strip()
                combined_content = f"{prev_body}\n\n{sc_body}".strip()
                if self.count_tokens(combined_content) <= self.max_tokens:
                    prev["content"] = combined_content
                    continue
            merged.append(sc)

        for idx, sc in enumerate(merged):
            sc["chunk_index"] = idx

        return merged

    def extract_chunks(self, pdf_path):
        doc = fitz.open(pdf_path)
        self.canonical_toc = self.build_canonical_toc(doc)
        print(f"Loaded PDF: {pdf_path} ({len(doc)} pages), {len(self.canonical_toc)} canonical TOC entries.")

        raw_sections = []
        current_disorder = None  # None until matched to canonical TOC
        current_code = ""
        current_section = "Overview"
        current_chunk_type = "disorder"
        section_lines = []
        active_page = 1

        def flush_active_section(p_num):
            nonlocal section_lines, current_disorder, current_code, current_section, current_chunk_type, active_page
            if section_lines and current_disorder:
                # Text with no TOC entry is not indexed
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

            # Front matter (< 67) and index/appendices (>= 833) not indexed in Section II
            if page_num < 67 or page_num >= 833:
                continue

            page = doc[page_idx]
            page_dict = page.get_text("dict")

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

                if line.isdigit() or "diagnostic and statistical manual" in lower_line:
                    i += 1
                    continue

                # 1. Major divider check: ONLY on prominent headings (font size >= 15 or short isolated line),
                # NEVER trigger from inline text inside paragraphs!
                # And in Section II (67-832), we do NOT label as "General DSM-5"
                is_major_divider = False
                if (size >= 14.5 or len(line.split()) <= 4):
                    for div in MAJOR_DIVIDERS:
                        if lower_line == div.lower() or lower_line.startswith(div.lower() + " "):
                            is_major_divider = True
                            break
                            
                if is_major_divider:
                    flush_active_section(page_num)
                    if page_num >= 759:
                        current_disorder = "Section III / Emerging Measures"
                        current_chunk_type = "section_iii"
                    else:
                        # Inside Section II, if it's an assessment measure or divider, do not reset to General DSM-5
                        current_disorder = None
                        current_chunk_type = "class_intro"
                    current_code = ""
                    current_section = line
                    active_page = page_num
                    i += 1
                    continue

                # 2. Diagnostic Class Heading (size >= 19.5pt)
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
                        matched_toc = self.match_canonical(full_class_name)
                        if matched_toc:
                            flush_active_section(page_num)
                            current_disorder = matched_toc
                            current_code = ""
                            current_section = "Diagnostic Class Overview"
                            current_chunk_type = "class_intro"
                            active_page = page_num
                            i += 1
                            continue

                # 3. Disorder Title by Font Size (size >= 15.0pt and < 19.5pt, Bold)
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
                        is_cross_reference = False
                        if i + 1 < len(extracted_lines) and "criteria and text for" in extracted_lines[i+1]["text"].lower():
                            is_cross_reference = True

                        if not is_cross_reference:
                            matched_toc = self.match_canonical(full_title)
                            if matched_toc:
                                flush_active_section(page_num)
                                current_disorder = matched_toc
                                current_code = ""
                                current_section = "Diagnostic Criteria"
                                current_chunk_type = "disorder"
                                active_page = page_num
                                i += 1
                                continue

                # 4. Other Specified... / Unspecified... Disorders
                if (lower_line.startswith("other specified") or lower_line.startswith("unspecified")) and line[0].isupper():
                    is_real_disorder = (
                        "disorder" in lower_line or 
                        (size >= 12.0 and len(line.split()) >= 2)
                    )
                    if is_real_disorder and not lower_line.endswith('.') and len(line) < 70 and not lower_line.startswith("unspecified type"):
                        matched_toc = self.match_canonical(line)
                        if matched_toc:
                            flush_active_section(page_num)
                            current_disorder = matched_toc
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

                    if len(clean_rest) > 3 and clean_rest[0].isupper() and not clean_rest.endswith(('.', ';', ':')):
                        matched_toc = self.match_canonical(clean_rest)
                        if matched_toc:
                            flush_active_section(page_num)
                            current_disorder = matched_toc
                            current_code = matched_code
                            current_section = "Diagnostic Criteria"
                            current_chunk_type = "other_conditions" if (746 <= page_num <= 758) else "disorder"
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

        flush_active_section(832)

        final_chunks = []
        import hashlib
        id_counters = defaultdict(int)

        for sec in raw_sections:
            # Alphabetic ratio check: No names with <60% alphabetic characters
            name = sec["disorder_name"]
            alpha_ratio = sum(c.isalpha() for c in name) / len(name)
            if alpha_ratio < 0.6:
                continue

            sub_chunks = self._sub_chunk_section(
                sec["disorder_name"],
                sec["code"],
                sec["section_type"],
                sec["chunk_type"],
                sec["content"],
                sec["page_number"]
            )
            for sc in sub_chunks:
                key = (sc["disorder_name"], sc["section_type"], sc["page_number"])
                seq_num = id_counters[key]
                id_counters[key] += 1
                sc["chunk_index"] = seq_num
                id_str = f"{sc['disorder_name']}_{sc['section_type']}_{sc['page_number']}_chunk{seq_num}"
                det_id = hashlib.md5(id_str.encode('utf-8')).hexdigest()
                sc["id"] = det_id
                final_chunks.append(sc)

        return final_chunks

tc = TestDSM5Chunker()
chunks = tc.extract_chunks('DSM-5.pdf')

counts = defaultdict(int)
for c in chunks:
    counts[c['disorder_name']] += 1

print("\n--- RESULTS ---")
print(f"Total Chunks: {len(chunks)}")
print(f"Total Unique Canonical Disorders: {len(counts)}")
for key in ["Schizophrenia", "Schizoaffective Disorder", "Conduct Disorder", "Autism Spectrum Disorder", "Panic Disorder", "Major Depressive Disorder", "Attention-Deficit/Hyperactivity Disorder"]:
    print(f"{key}: {counts[key]} chunks")

# Check Panic Disorder Differential Diagnosis chunks
panic_diffs = [c for c in chunks if c["section_type"] == "Differential Diagnosis" and "Panic" in c["disorder_name"]]
print(f"Panic Disorder Differential chunks: {len(panic_diffs)}")
for pd in panic_diffs:
    print(f"  Disorder: '{pd['disorder_name']}', Page: {pd['page_number']}")

# Check if any chunk has <60% alphabetic
bad_alpha = [c["disorder_name"] for c in chunks if sum(ch.isalpha() for ch in c["disorder_name"])/len(c["disorder_name"]) < 0.6]
print(f"Bad alpha names: {bad_alpha}")

# Check if any chunk labeled General DSM-5 in Section II
gen_dsm = [c for c in chunks if c["disorder_name"] == "General DSM-5" and c["page_number"] >= 67]
print(f"General DSM-5 chunks in Section II: {len(gen_dsm)}")
