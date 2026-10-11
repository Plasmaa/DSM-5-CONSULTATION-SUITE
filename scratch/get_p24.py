import fitz

doc = fitz.open('DSM-5.pdf')
# Page 24 is index 23
with open('scratch/page24.txt', 'w', encoding='utf-8') as f:
    f.write(doc[23].get_text())

print("Wrote page 24 to scratch/page24.txt")
