import csv
import io
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib import messages

EXCEL_HEADER_FILL = PatternFill(start_color='DC143C', end_color='DC143C', fill_type='solid')
EXCEL_HEADER_FONT = Font(color='FFFFFF', bold=True, size=12)

def export_csv(model_class, fields, filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    writer = csv.writer(response)
    headers = [str(f.verbose_name) for f in fields]
    writer.writerow(headers)
    for obj in model_class.objects.all():
        row = [getattr(obj, f.name) for f in fields]
        writer.writerow(row)
    return response

def export_xlsx(model_class, fields, filename):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = filename
    headers = [str(f.verbose_name) for f in fields]
    ws.append(headers)
    for col_idx, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = EXCEL_HEADER_FILL
        cell.font = EXCEL_HEADER_FONT
        cell.alignment = Alignment(horizontal='center')
    for obj in model_class.objects.all():
        row = [getattr(obj, f.name) for f in fields]
        ws.append(row)
    for col_idx, _ in enumerate(headers, 1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = 25
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    wb.save(response)
    return response

XLSX_MAGIC = b'\x50\x4B\x03\x04'

ALLOWED_EXTENSIONS = {'.csv', '.xlsx'}

def _validate_file_upload(file, max_size_mb=5):
    """Validate uploaded file: extension, size, and basic content check."""
    name = getattr(file, 'name', '')
    ext = name[name.rfind('.'):].lower() if '.' in name else ''
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f'امتداد الملف "{ext}" غير مسموح. الامتدادات المسموحة: csv, xlsx')
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > max_size_mb * 1024 * 1024:
        raise ValueError(f'حجم الملف يتجاوز {max_size_mb} ميجابايت')
    if size == 0:
        raise ValueError('الملف فارغ')

def import_csv(file, model_class, field_map):
    _validate_file_upload(file)
    decoded = file.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(decoded))
    count = 0
    for row in reader:
        kwargs = {}
        for csv_col, model_field in field_map.items():
            kwargs[model_field] = row.get(csv_col, '')
        model_class.objects.create(**kwargs)
        count += 1
    return count

def import_xlsx(file, model_class, field_map):
    _validate_file_upload(file)
    file.seek(0)
    head = file.read(4)
    file.seek(0)
    if head != XLSX_MAGIC:
        raise ValueError('تنسيق الملف غير صالح - يجب رفع ملف Excel (.xlsx)')
    wb = openpyxl.load_workbook(file)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return 0
    headers = [str(h) if h else '' for h in rows[0]]
    count = 0
    for row in rows[1:]:
        kwargs = {}
        for csv_col, model_field in field_map.items():
            if csv_col in headers:
                idx = headers.index(csv_col)
                kwargs[model_field] = row[idx] if idx < len(row) else ''
        model_class.objects.create(**kwargs)
        count += 1
    return count
