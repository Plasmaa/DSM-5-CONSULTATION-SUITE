import fitz
import re

doc = fitz.open('DSM-5.pdf')

def extract_toc_disorders(doc):
    canonical_disorders = []
    
    # Also add chapters from doc.get_toc()
    doc_toc = doc.get_toc()
    for level, title, page in doc_toc:
        clean_title = re.sub(r'[\u00ae\u00a9\u2010\u2011\xad\ufffd\^*\'\"]+', '', title).strip()
        # Remove "Section II. ", "Section I. ", etc.
        clean_title = re.sub(r'^Section\s+[I|V|X]+\.\s*', '', clean_title).strip()
        if clean_title and len(clean_title) > 3 and clean_title[0].isupper():
            canonical_disorders.append(clean_title)

    for p in range(12, 40): # PDF pages 13 to 40
        page = doc[p]
        text = page.get_text()
        text = re.sub(r'(\w+)[\u00ad\ufffd\xad\-\u2010\u2011]\s*\n\s*(\w+)', r'\1\2', text)
        lines = text.split('\n')
        
        pending_lines = []
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            
            # Skip noise / notes / intro
            if (line.startswith("Specify") or line.startswith("Note:") or 
                line.startswith("ICD-") or line.startswith("Before each") or 
                line.startswith("Following chapter") or line.startswith("Blank lines")):
                pending_lines = []
                continue
            
            # Skip lone bullet/symbol characters
            if re.match(r'^[■•·\*\^\'\.\|\-_]+$', line):
                continue
            
            # Skip code-only lines e.g. "302.71 (F52.0)", "312.34 (F63.81)", "(F64.2)", "___.__"
            if re.match(r'^[\d\s\._\(\)A-Z\-,/]+$', line) and any(c.isdigit() for c in line):
                continue
            if re.match(r'^_+[._\s\(\)]*$', line):
                continue
                
            # Check if line contains (page_number) at the end
            m = re.search(r'\(\s*(\d+)\s*\)\s*[\^\*\'\"\s]*$', line)
            if m:
                # This line finishes a title
                line_head = line[:m.start()].strip()
                if line_head:
                    pending_lines.append(line_head)
                full_cand = " ".join(pending_lines).strip()
                pending_lines = []
                
                # Clean candidate
                # Remove any leftover codes at start e.g. "319 (___.__) Intellectual Disability"
                full_cand = re.sub(r'^[0-9V]\d{2}(?:\.\d{1,3})?\s*(?:\([A-Z]\d{2,3}(?:\.\d{1,2})?\))?\s*', '', full_cand)
                full_cand = re.sub(r'^[\d\s\._\(\)A-Z\-,/]+?\s{2,}', '', full_cand)
                full_cand = re.sub(r'[\u00ae\u00a9\u2010\u2011\xad\ufffd\^*\'\"■•·]+', '', full_cand).strip()
                
                # Check validity
                if full_cand and len(full_cand) > 3 and full_cand[0].isupper():
                    # Calculate alphabetic percentage
                    alpha_ratio = sum(c.isalpha() for c in full_cand) / len(full_cand)
                    if alpha_ratio >= 0.6:
                        canonical_disorders.append(full_cand)
            else:
                # Candidate continuation line
                # Make sure it's not a specifier line e.g. "Mild", "Moderate", "Childhood-onset type"
                # In classification pages, specifiers are under "Specify whether:", etc.
                # But actual title lines are uppercase
                if line[0].isupper() or line[0] in ['(', '"']:
                    # Clean symbol noise
                    cleaned_l = re.sub(r'[\u00ae\u00a9\u2010\u2011\xad\ufffd\^*\'\"■•·]+', '', line).strip()
                    if cleaned_l:
                        pending_lines.append(cleaned_l)
                else:
                    pending_lines = []
    
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for d in canonical_disorders:
        if d.lower() not in seen:
            seen.add(d.lower())
            unique.append(d)
    return unique

disorders = extract_toc_disorders(doc)
print(f"Total canonical disorders/classes extracted: {len(disorders)}")
with open("scratch/canonical_toc.txt", "w", encoding="utf-8") as f:
    for d in disorders:
        f.write(f"{d}\n")

# Check our target golden disorders
check_list = [
    "Schizophrenia",
    "Schizoaffective Disorder",
    "Conduct Disorder",
    "Autism Spectrum Disorder",
    "Panic Disorder",
    "Major Depressive Disorder",
    "Attention-Deficit/Hyperactivity Disorder",
    "Generalized Anxiety Disorder",
    "Posttraumatic Stress Disorder"
]
for item in check_list:
    found = [d for d in disorders if item.lower() in d.lower()]
    print(f"Check '{item}': {found}")
