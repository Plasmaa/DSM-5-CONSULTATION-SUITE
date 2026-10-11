import fitz

doc = fitz.open('DSM-5.pdf')

def check_printed(p):
    txt = doc[p-1].get_text('text')
    lines = [l.strip() for l in txt.split('\n') if l.strip()]
    header = lines[0] if lines else ""
    footer = lines[-1] if lines else ""
    print(f"PDF page {p}: top={repr(header)} | bottom={repr(footer)}")

for p in [71, 97, 198, 260, 308]:
    check_printed(p)
