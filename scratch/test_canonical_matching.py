import fitz
import re
from collections import defaultdict
from rapidfuzz import fuzz, process

doc = fitz.open('DSM-5.pdf')

def build_canonical_toc(doc):
    toc_entries = []
    
    # 1. From doc.get_toc()
    for level, title, page in doc.get_toc():
        clean_title = re.sub(r'[\u00ae\u00a9\u2010\u2011\xad\ufffd\^*\'\"]+', '', title).strip()
        clean_title = re.sub(r'^Section\s+[I|V|X]+\.\s*', '', clean_title).strip()
        # Only Section II and Section III categories
        if page >= 67 and page < 833:
            if clean_title and len(clean_title) > 3:
                toc_entries.append(clean_title)
                
    # 2. From classification pages 13-40
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
                
                # Strip ICD codes or leading numbers
                full_cand = re.sub(r'^[0-9V]\d{2}(?:\.\d{1,3})?\s*(?:\([A-Z]\d{2,3}(?:\.\d{1,2})?\))?\s*', '', full_cand)
                full_cand = re.sub(r'^[\d\s\._\(\)A-Z\-,/]+?\s{2,}', '', full_cand)
                full_cand = re.sub(r'[\u00ae\u00a9\u2010\u2011\xad\ufffd\^*\'\"■•·]+', '', full_cand).strip()
                
                if full_cand and len(full_cand) > 3 and full_cand[0].isupper():
                    alpha_ratio = sum(c.isalpha() for c in full_cand) / len(full_cand)
                    if alpha_ratio >= 0.6:
                        toc_entries.append(full_cand)
                        # Also if has parenthetical like (includes ...) add base
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
                    
    # Deduplicate while preserving order
    seen = set()
    canonical = []
    for t in toc_entries:
        # Normalize internal whitespace
        norm = " ".join(t.split())
        if norm.lower() not in seen:
            seen.add(norm.lower())
            canonical.append(norm)
    return canonical

canonical_toc = build_canonical_toc(doc)
print(f"Canonical TOC entries count: {len(canonical_toc)}")

def match_canonical(candidate, canonical_list, threshold=90):
    if not candidate:
        return None
    cand_norm = " ".join(candidate.split()).strip()
    # 1. Exact match (case-insensitive)
    for c in canonical_list:
        if cand_norm.lower() == c.lower():
            return c
            
    # 2. Fuzzy match
    match, score, _ = process.extractOne(cand_norm, canonical_list, scorer=fuzz.ratio)
    if score >= threshold:
        return match
        
    # 3. Token set ratio fallback for slight word order or punctuation variations if score >= 90
    match_ts, score_ts, _ = process.extractOne(cand_norm, canonical_list, scorer=fuzz.token_set_ratio)
    if score_ts >= 95 and abs(len(cand_norm) - len(match_ts)) < 15:
        return match_ts
        
    return None

# Test matching on some tricky candidate strings
test_cands = [
    "Schizophrenia",
    "Conduct Disorder",
    "Autism Spectrum Disorder",
    "Posttraumatic Stress Disorder",
    "Panic Disorder",
    "Major Depressive Disorder, Single Episode",
    "Major Depressive Disorder",
    "Attention-Deficit/Hyperactivity Disorder",
    "Due to Another Medical Condition",
    "With Prominent Anxiety Symptoms",
    "Disruptive, Impulse-Control, and Conduct Disorders"
]
print("\n--- Match testing ---")
for tc in test_cands:
    m = match_canonical(tc, canonical_toc)
    print(f"'{tc}' -> '{m}'")
