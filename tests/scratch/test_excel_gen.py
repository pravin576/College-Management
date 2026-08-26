import io
import sys
import os
import zipfile
import xml.etree.ElementTree as ET

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from scratch.test_excel_parser import parse_xlsx

def create_sample_student_xlsx():
    headers = [
        "Student ID", "Roll Number", "Student Name", "Email", "Mobile Number",
        "Gender", "DOB", "Department", "Year", "Semester", "Division",
        "Admission Year", "Address", "Status"
    ]
    sample_row = [
        "STU1001", "R1001", "Aarav Sharma", "aarav.sharma@college.edu", "9876543210",
        "Male", "2005-04-12", "Computer Engineering", "Second Year", "Semester 3", "A",
        "2026", "Awasari, Pune", "Active"
    ]

    strings = headers + sample_row
    string_map = {s: i for i, s in enumerate(strings)}

    sst_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{0}" uniqueCount="{0}">'.format(len(strings))
    for s in strings:
        sst_xml += f'<si><t>{s}</t></si>'
    sst_xml += '</sst>'

    sheet_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    
    sheet_xml += '<row r="1">'
    for col_idx, h in enumerate(headers, start=1):
        col_letter = chr(64 + col_idx) if col_idx <= 26 else 'A' + chr(64 + col_idx - 26)
        sheet_xml += f'<c r="{col_letter}1" t="s"><v>{string_map[h]}</v></c>'
    sheet_xml += '</row>'

    sheet_xml += '<row r="2">'
    for col_idx, val in enumerate(sample_row, start=1):
        col_letter = chr(64 + col_idx) if col_idx <= 26 else 'A' + chr(64 + col_idx - 26)
        sheet_xml += f'<c r="{col_letter}2" t="s"><v>{string_map[val]}</v></c>'
    sheet_xml += '</row>'

    sheet_xml += '</sheetData></worksheet>'

    content_types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>'

    dot_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'

    workbook_rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>'

    workbook = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="Students" sheetId="1" r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets></workbook>'

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', content_types)
        z.writestr('_rels/.rels', dot_rels)
        z.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
        z.writestr('xl/workbook.xml', workbook)
        z.writestr('xl/sharedStrings.xml', sst_xml)
        z.writestr('xl/worksheets/sheet1.xml', sheet_xml)

    return buf.getvalue()

xlsx_bytes = create_sample_student_xlsx()
parsed = parse_xlsx(io.BytesIO(xlsx_bytes))
print("Generated and parsed XLSX successfully! Rows:", len(parsed))
for r in parsed:
    print(r)
