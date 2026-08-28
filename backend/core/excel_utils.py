import io
import zipfile
import xml.etree.ElementTree as ET

def parse_xlsx_bytes(file_bytes):
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

def build_xlsx_bytes(headers, sample_rows):
    all_rows = [headers] + sample_rows
    strings = []
    string_map = {}

    for row in all_rows:
        for val in row:
            s_val = str(val)
            if s_val not in string_map:
                string_map[s_val] = len(strings)
                strings.append(s_val)

    sst_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\\n<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{0}" uniqueCount="{0}">'.format(len(strings))
    for s in strings:
        escaped_s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        sst_xml += f'<si><t>{escaped_s}</t></si>'
    sst_xml += '</sst>'

    sheet_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\\n<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    for r_idx, row in enumerate(all_rows, start=1):
        sheet_xml += f'<row r="{r_idx}">'
        for c_idx, val in enumerate(row, start=1):
            col_letter = chr(64 + c_idx) if c_idx <= 26 else 'A' + chr(64 + c_idx - 26)
            s_idx = string_map[str(val)]
            sheet_xml += f'<c r="{col_letter}{r_idx}" t="s"><v>{s_idx}</v></c>'
        sheet_xml += '</row>'
    sheet_xml += '</sheetData></worksheet>'

    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>'
    dot_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'
    workbook_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\\n<Relationships xmlns="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>'
    workbook = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\\n<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="Data" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets></workbook>'

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', dot_rels)
        z.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
        z.writestr('xl/workbook.xml', workbook)
        z.writestr('xl/sharedStrings.xml', sst_xml)
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml)

    return buf.getvalue()

def create_student_template_xlsx():
    headers = [
        "Student ID", "Roll Number", "Student Name", "Email", "Mobile Number",
        "Gender", "DOB", "Department", "Year", "Semester", "Division",
        "Admission Year", "Address", "Status"
    ]
    sample_rows = [
        ["STU1001", "1", "Rahul Patil", "rahul.patil@college.edu", "9876543210", "Male", "2005-04-12", "Computer Engineering", "First Year", "Semester 1", "A", "2026", "Awasari, Pune", "Active"],
        ["STU1002", "2", "Priya Shinde", "priya.shinde@college.edu", "9876543211", "Female", "2005-08-20", "Computer Engineering", "First Year", "Semester 1", "A", "2026", "Awasari, Pune", "Active"]
    ]
    return build_xlsx_bytes(headers, sample_rows)

def create_attendance_template_xlsx():
    headers = [
        "Student ID", "Student Name", "Department", "Year", "Semester",
        "Division", "Subject", "Subject Code", "Date", "Attendance Status"
    ]
    sample_rows = [
        ["STU1001", "Rahul Patil", "Computer Engineering", "Second Year", "Semester 3", "A", "Java Programming", "JPR", "2026-08-18", "Present"],
        ["STU1002", "Amit Shinde", "Computer Engineering", "Second Year", "Semester 3", "A", "Java Programming", "JPR", "2026-08-18", "Absent"],
        ["STU1003", "Priya Patil", "Computer Engineering", "Second Year", "Semester 3", "A", "Java Programming", "JPR", "2026-08-18", "Present"]
    ]
    return build_xlsx_bytes(headers, sample_rows)

def create_results_template_xlsx():
    headers = [
        "Student ID", "Student Name", "Department", "Semester", "Subject",
        "Internal Marks (30)", "End Sem Marks (70)"
    ]
    sample_rows = [
        ["STU1001", "Rahul Patil", "Computer Engineering", "Semester 3", "Software Engineering", "25", "58"],
        ["STU1002", "Priya Shinde", "Computer Engineering", "Semester 3", "Software Engineering", "22", "45"]
    ]
    return build_xlsx_bytes(headers, sample_rows)
