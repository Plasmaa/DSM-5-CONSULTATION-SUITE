import fitz
import re
import uuid

# List of standard DSM-5 section headers we want to split on
SUBSECTION_HEADERS = [
    "Diagnostic Features",
    "Associated Features Supporting Diagnosis",
    "Specifiers",
    "Prevalence",
    "Development and Course",
    "Risk and Prognostic Factors",
    "Culture-Related Diagnostic Issues",
    "Gender-Related Diagnostic Issues",
    "Suicide Risk",
    "Functional Consequences",
    "Differential Diagnosis",
    "Comorbidity"
]

class DSM5Chunker:
    def __init__(self):
        # Compiled regexes for pattern matching
        self.code_pattern = re.compile(r'^\s*(\d{3}\.\d{2,3}|\d{3})\s*\(([A-Z]\d{2,3}(?:\.\d{1,2})?)\)\s*$') # e.g. 315.39 (F80.9)
        self.clean_soft_hyphens = re.compile(r'(\w+)[\u00ad\ufffd\xad\-\u2010\u2011]\s*\n\s*(\w+)')
        self.clean_generic_replacements = re.compile(r'[\u00ad\ufffd\xad\u2010\u2011]')

    def clean_text(self, text):
        """Clean PDF text artifacts like soft hyphens and bad encoding replacements."""
        # Join words split across newlines with soft hyphens
        text = self.clean_soft_hyphens.sub(r'\1\2', text)
        # Remove individual soft hyphens/unicode replacement characters
        text = self.clean_generic_replacements.sub('', text)
        # Replace multiple spaces/newlines
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()

    def is_disorder_header(self, line):
        """Check if line represents the Diagnostic Criteria header."""
        cleaned = line.strip().lower()
        return cleaned == "diagnostic criteria" or cleaned == "diagnostic criteria:"

    def extract_chunks(self, pdf_path):
        doc = fitz.open(pdf_path)
        print(f"Loaded PDF: {pdf_path} ({len(doc)} pages)")

        chunks = []
        
        current_disorder = "General DSM-5"
        current_code = ""
        current_section = "Introduction"
        
        # Accumulators for the state machine
        section_lines = []
        recent_lines = []  # Keep track of recent lines to look back for disorder name
        active_page = 1

        for page_num in range(len(doc)):
            page_text = doc[page_num].get_text("text")
            lines = page_text.split('\n')
            
            # Simple header/footer filtering: skip first/last line if they look like running headers
            filtered_lines = []
            for i, line in enumerate(lines):
                line_str = line.strip()
                if not line_str:
                    continue
                # Skip numeric page numbers at the start/end of pages
                if line_str.isdigit():
                    continue
                # Skip common running header phrases
                if "Diagnostic and Statistical Manual" in line_str:
                    continue
                filtered_lines.append(line)

            for line in filtered_lines:
                cleaned_line = line.strip()
                
                # Check for a new disorder section
                if self.is_disorder_header(cleaned_line):
                    # Save previous section if it has content
                    if section_lines:
                        self._add_chunk(chunks, current_disorder, current_code, current_section, section_lines, active_page)
                        section_lines = []

                    # Find the disorder name from the preceding lines
                    disorder_name = self._find_disorder_name(recent_lines)
                    if disorder_name:
                        current_disorder = disorder_name
                    
                    current_code = ""
                    current_section = "Diagnostic Criteria"
                    active_page = page_num + 1
                    recent_lines = []
                    continue

                # Check if it's a code line directly following Diagnostic Criteria
                if current_section == "Diagnostic Criteria" and not current_code:
                    match = self.code_pattern.match(cleaned_line)
                    if match:
                        current_code = f"{match.group(1)} ({match.group(2)})"
                        continue

                # Check if it's a known subsection header
                is_sub = False
                for sub_header in SUBSECTION_HEADERS:
                    if cleaned_line.lower() == sub_header.lower() or cleaned_line.lower().startswith(sub_header.lower() + " of "):
                        # Save current chunk before switching sections
                        if section_lines:
                            self._add_chunk(chunks, current_disorder, current_code, current_section, section_lines, active_page)
                            section_lines = []
                        
                        current_section = sub_header
                        active_page = page_num + 1
                        is_sub = True
                        break
                
                if is_sub:
                    continue

                # Append line to the active section
                section_lines.append(line)
                
                # Keep track of last few lines for disorder name detection
                recent_lines.append(cleaned_line)
                if len(recent_lines) > 5:
                    recent_lines.pop(0)

        # Add the final chunk
        if section_lines:
            self._add_chunk(chunks, current_disorder, current_code, current_section, section_lines, active_page)

        print(f"Extracted {len(chunks)} chunks.")
        return chunks

    def _find_disorder_name(self, lines):
        """Look backward to extract disorder title."""
        # We look for lines in Title Case that don't look like generic section headers
        valid_title_lines = []
        for l in reversed(lines):
            l_strip = l.strip()
            if not l_strip:
                continue
            # Skip page headers or previous section names
            if l_strip in SUBSECTION_HEADERS or l_strip == "Diagnostic Criteria" or l_strip == "Diagnostic Criteria:":
                continue
            if len(l_strip) < 3:
                continue
            # If we hit an ICD code line, skip it
            if self.code_pattern.match(l_strip):
                continue
            # Check sentence boundary or unusually long text lines
            if l_strip.endswith('.') or l_strip.endswith(';') or l_strip.endswith(':') or len(l_strip) > 60:
                break
            
            valid_title_lines.insert(0, l_strip)
            if len(valid_title_lines) >= 2: # Keep at most 2 lines (some disorders have long subtitles)
                break
                
        if valid_title_lines:
            return " ".join(valid_title_lines)
        return None

    def _add_chunk(self, chunks, disorder_name, code, section_type, lines, page_num):
        content = "\n".join(lines)
        cleaned_content = self.clean_text(content)
        
        # Don't add empty or extremely short chunks
        if len(cleaned_content) < 30:
            return

        # Generate a deterministic ID based on metadata to prevent duplicates
        import hashlib
        id_str = f"{disorder_name}_{section_type}_{page_num}"
        det_id = hashlib.md5(id_str.encode('utf-8')).hexdigest()

        chunks.append({
            "id": det_id,
            "disorder_name": disorder_name,
            "code": code,
            "section_type": section_type,
            "content": cleaned_content,
            "page_number": page_num
        })
