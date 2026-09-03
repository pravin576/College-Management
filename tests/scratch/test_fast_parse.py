import io
import sys
import os
import time
import zipfile
import xml.etree.ElementTree as ET

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from backend.app import create_student_template_xlsx

def fast_parse_xlsx_bytes(file_bytes):
    rows_data = []
    bio = io.BytesIO(file_bytes)
    with zipfile.ZipFile(bio) as z:
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            with z.open('xl/sharedStrings.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                for si in root.iter():
                    if si.tag.endswith('si'):
                        texts = [t.text or '' for t in si.iter() if t.tag.endswith('t')]
                        shared_strings.append(''.join(texts))

        sheet_names = [n for n in z.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')]
        if not sheet_names:
            return []

        with z.open(sheet_names[0]) as f:
            tree = ET.parse(f)
            root = tree.getroot()
            
            for elem in root.iter():
                if elem.tag.endswith('row'):
                    row_vals = []
                    for c in elem:
                        if c.tag.endswith('c'):
                            t = c.get('t')
                            val = ''
                            for child in c:
                                if child.tag.endswith('v') or child.tag.endswith('t'):
                                    val = child.text or ''
                                    break
                            if t == 's' and val.isdigit():
                                idx = int(val)
                                if idx < len(shared_strings):
                                    val = shared_strings[idx]
                            row_vals.append(val.strip())
                    if any(row_vals):
                        rows_data.append(row_vals)
    return rows_data

print("Compiling fast_parse_xlsx_bytes...")
tmpl = create_student_template_xlsx()
t0 = time.time()
rows = fast_parse_xlsx_bytes(tmpl)
t1 = time.time()
print(f"Parsed template in {(t1-t0)*1000:.2f} ms. Rows found: {len(rows)}")
for r in rows:
    print(r)
