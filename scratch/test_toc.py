import re
import fitz

doc = fitz.open('DSM-5.pdf')

entries = []
for p in range(12, 40): # pages 13 to 40 (0-indexed 12 to 39)
    text = doc[p].get_text()
    # clean soft hyphens
    text = re.sub(r'(\w+)[\u00ad\ufffd\xad\-\u2010\u2011]\s*\n\s*(\w+)', r'\1\2', text)
    lines = text.split('\n')
    
    buf = []
    for l in lines:
        l_str = l.strip()
        if not l_str:
            continue
        # Check if line ends with (\d+) or (\d+)\s*$
        m = re.search(r'\(\s*(\d+)\s*\)\s*[\^\*\'\"\s]*$', l_str)
        if m:
            page_ref = int(m.group(1))
            cur_line = l_str[:m.start()].strip()
            if buf:
                candidate = ' '.join(buf) + ' ' + cur_line
            else:
                candidate = cur_line
            buf = []
            
            # Clean candidate
            clean_cand = re.sub(r'^[0-9V]\d{2}(?:\.\d{1,3})?\s*(?:\([A-Z]\d{2,3}(?:\.\d{1,2})?\))?\s*', '', candidate)
            clean_cand = re.sub(r'^_+[._\s\(\)]*', '', clean_cand)
            clean_cand = re.sub(r'[\u00ae\u00a9\u2010\u2011\xad\ufffd\^*\'\"]+', '', clean_cand).strip()
            
            if clean_cand and len(clean_cand) > 3 and clean_cand[0].isupper():
                entries.append((clean_cand, page_ref, p+1))
        else:
            if not l_str.startswith('Specify') and not l_str.startswith('Note:') and not l_str.startswith('ICD-') and not l_str.startswith('Before each') and not l_str.startswith('Following chapter'):
                if re.match(r'^\(?\s*[0-9V_]\d*[\.\d]*\s*\)?$', l_str) or re.match(r'^\([A-Z0-9\.]+\)$', l_str):
                    pass
                else:
                    buf.append(l_str)
            else:
                buf = []

print(f'Extracted {len(entries)} TOC entries from pp. 13-40.')
for e in entries[:20]:
    print(e)
print('Conduct Disorder in entries?:', [e for e in entries if 'Conduct' in e[0]])
print('Schizophrenia in entries?:', [e for e in entries if 'Schizo' in e[0]])
print('Panic in entries?:', [e for e in entries if 'Panic' in e[0]])
print('Autism in entries?:', [e for e in entries if 'Autis' in e[0]])
