import zipfile
import xml.etree.ElementTree as ET

def parse_xlsx(file_bytes):
    rows_data = []
    with zipfile.ZipFile(file_bytes) as z:
        # Load shared strings if available
        shared_strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            with z.open('xl/sharedStrings.xml') as f:
                tree = ET.parse(f)
                root = tree.getroot()
                # handle namespace
                ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for si in root.findall('.//ns:si', ns) or root.findall('.//si'):
                    texts = [t.text or '' for t in (si.findall('.//ns:t', ns) or si.findall('.//t'))]
                    shared_strings.append(''.join(texts))

        # Find first sheet
        sheet_name = [name for name in z.namelist() if name.startswith('xl/worksheets/sheet') and name.endswith('.xml')][0]
        with z.open(sheet_name) as f:
            tree = ET.parse(f)
            root = tree.getroot()
            ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            
            rows = root.findall('.//ns:row', ns) or root.findall('.//row')
            for row in rows:
                row_vals = []
                cells = row.findall('.//ns:c', ns) or row.findall('.//c')
                for c in cells:
                    t = c.get('t')
                    v = c.find('ns:v', ns) if ns else c.find('v')
                    if v is None:
                        v = c.find('.//ns:t', ns) or c.find('.//t')
                        val = v.text if v is not None else ''
                    else:
                        val = v.text or ''
                    
                    if t == 's' and val.isdigit():
                        idx = int(val)
                        if idx < len(shared_strings):
                            val = shared_strings[idx]
                    row_vals.append(val.strip())
                if any(row_vals):
                    rows_data.append(row_vals)
    return rows_data

print("Parser function compiled cleanly!")
