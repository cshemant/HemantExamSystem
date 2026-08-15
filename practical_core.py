"""Helpers for the Practical Marks Register.

These functions intentionally have no Flask/database dependency so roster and
experiment imports can be regression-tested independently of the web app.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Iterable

from openpyxl import load_workbook


def cell_text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _key(value) -> str:
    text=cell_text(value).casefold().strip()
    text=re.sub(r'[^a-z0-9]+','_',text).strip('_')
    aliases={
        'roll':'roll_no','roll_no':'roll_no','rollno':'roll_no','roll_number':'roll_no',
        'reg_no':'roll_no','reg_number':'roll_no','registration_no':'roll_no','registration_number':'roll_no',
        'enrollment_no':'roll_no','enrolment_no':'roll_no','student_id':'roll_no',
        'name':'name','student_name':'name','name_of_student':'name','candidate_name':'name','full_name':'name',
        'experiment':'experiment_no','experiment_no':'experiment_no','experiment_number':'experiment_no','exp':'experiment_no','exp_no':'experiment_no','no':'experiment_no','s_no':'experiment_no','sno':'experiment_no',
        'title':'title','experiment_name':'title','experiment_title':'title','name_of_experiment':'title','description':'title','practical':'title',
        'marks':'max_marks','max_marks':'max_marks','maximum_marks':'max_marks',
    }
    return aliases.get(text,text)


def _table_rows(filename: str, raw: bytes) -> list[list[object]]:
    filename=(filename or '').lower()
    if not raw:
        raise ValueError('The uploaded file is empty.')
    if filename.endswith('.csv'):
        try:
            text=raw.decode('utf-8-sig')
        except UnicodeDecodeError as exc:
            raise ValueError('CSV must be UTF-8 encoded.') from exc
        return [list(r) for r in csv.reader(io.StringIO(text))]
    if filename.endswith('.xlsx'):
        try:
            wb=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
            ws=wb.active
            return [list(r) for r in ws.iter_rows(values_only=True)]
        except Exception as exc:
            raise ValueError('The Excel file could not be read. Please upload a valid .xlsx file.') from exc
    raise ValueError('Please upload a CSV or Excel (.xlsx) file.')


def parse_roster_bytes(filename: str, raw: bytes) -> list[dict]:
    """Read a student roster from a clean table or a university evaluation sheet.

    The supplied university practical sheet keeps ``Reg. No`` and ``Name of
    Student`` on different header rows.  Instead of assuming row 1 is the
    header, this scanner locates the roll/name columns independently within the
    first 15 rows and then reads the student records beneath them.
    """
    rows=_table_rows(filename,raw)
    if not rows:
        raise ValueError('The uploaded file has no rows.')

    # Fast path: clean row-based header (roll_no, name).
    for header_idx,row in enumerate(rows[:15]):
        keys=[_key(v) for v in row]
        if 'roll_no' in keys and 'name' in keys:
            roll_col=keys.index('roll_no');name_col=keys.index('name');start=header_idx+1
            return _collect_roster(rows,start,roll_col,name_col)

    # Flexible university-sheet path: roll/name labels can live on separate rows.
    roll_hit=name_hit=None
    for r_idx,row in enumerate(rows[:15]):
        for c_idx,value in enumerate(row):
            key=_key(value)
            if key=='roll_no' and roll_hit is None:
                roll_hit=(r_idx,c_idx)
            if key=='name' and name_hit is None:
                name_hit=(r_idx,c_idx)
    if not roll_hit or not name_hit:
        raise ValueError('Could not find student columns. The sheet must contain a registration/roll number and student name column.')
    return _collect_roster(rows,max(roll_hit[0],name_hit[0])+1,roll_hit[1],name_hit[1])


def _collect_roster(rows: list[list[object]], start: int, roll_col: int, name_col: int) -> list[dict]:
    out=[];seen=set();blank_run=0
    for row in rows[start:]:
        roll=cell_text(row[roll_col] if roll_col<len(row) else '')
        name=cell_text(row[name_col] if name_col<len(row) else '')
        if not roll and not name:
            blank_run+=1
            if blank_run>=8 and out:
                break
            continue
        blank_run=0
        # Skip footer/summary lines and partially populated records.
        if not roll or not name:
            continue
        low=(roll+' '+name).casefold()
        if any(token in low for token in ('total marks','signature','faculty name','average marks')):
            continue
        key=roll.casefold()
        if key in seen:
            continue
        seen.add(key);out.append({'roll_no':roll,'name':name})
    if not out:
        raise ValueError('No student records were found below the detected roll number/name columns.')
    return out


def normalize_experiment_code(value: str, fallback: int) -> str:
    raw=cell_text(value).upper().replace('EXPERIMENT','').replace('EXP.','').replace('EXP','').strip(' :-_')
    raw=re.sub(r'\s+','',raw)
    if raw:
        return raw[:24]
    return str(fallback)


def parse_experiment_text(text: str, default_marks: int=10) -> list[dict]:
    """Parse one experiment per line.

    Accepted examples: ``2A | Linear Layout``, ``2A - Linear Layout`` or simply
    ``Linear Layout``.  Numbered lists pasted from Word are also accepted.
    """
    rows=[]
    for idx,line in enumerate((text or '').splitlines(),start=1):
        line=line.strip()
        if not line:
            continue
        code='';title=line
        if '|' in line:
            code,title=[x.strip() for x in line.split('|',1)]
        else:
            match=re.match(r'^\s*([0-9]+\s*[A-Za-z]?)\s*[.):-]?\s+(.+)$',line)
            if match:
                code=match.group(1);title=match.group(2).strip()
        if not title:
            continue
        rows.append({'experiment_no':normalize_experiment_code(code,idx),'title':title,'max_marks':max(1,int(default_marks))})
    return _dedupe_experiments(rows)


def parse_experiment_bytes(filename: str, raw: bytes, default_marks: int=10) -> list[dict]:
    rows=_table_rows(filename,raw)
    if not rows:
        raise ValueError('The uploaded experiment file has no rows.')

    # Structured header path.
    for header_idx,row in enumerate(rows[:10]):
        keys=[_key(v) for v in row]
        if 'title' in keys:
            title_col=keys.index('title')
            code_col=keys.index('experiment_no') if 'experiment_no' in keys else None
            marks_col=keys.index('max_marks') if 'max_marks' in keys else None
            output=[]
            for pos,data in enumerate(rows[header_idx+1:],start=1):
                title=cell_text(data[title_col] if title_col<len(data) else '')
                if not title:
                    continue
                code=cell_text(data[code_col] if code_col is not None and code_col<len(data) else '')
                marks=cell_text(data[marks_col] if marks_col is not None and marks_col<len(data) else '')
                try:marks_value=max(1,int(float(marks))) if marks else max(1,int(default_marks))
                except ValueError:marks_value=max(1,int(default_marks))
                output.append({'experiment_no':normalize_experiment_code(code,pos),'title':title,'max_marks':marks_value})
            output=_dedupe_experiments(output)
            if output:return output

    # Loose list path: use the first short code-like cell and the longest text cell.
    output=[]
    for pos,row in enumerate(rows,start=1):
        values=[cell_text(v) for v in row if cell_text(v)]
        if not values:
            continue
        if len(values)==1:
            # Ignore likely headings.
            if _key(values[0]) in {'experiment','experiment_no','title','experiment_list'}:
                continue
            code='';title=values[0]
        else:
            code_candidates=[v for v in values[:-1] if re.fullmatch(r'(?:[0-9]+\s*[A-Za-z]?|[A-Za-z])',v.strip())]
            code=''.join(code_candidates[:2]) if code_candidates else ''
            title=max(values,key=len)
            if title==code:
                continue
        if len(title)<4:
            continue
        output.append({'experiment_no':normalize_experiment_code(code,pos),'title':title,'max_marks':max(1,int(default_marks))})
    output=_dedupe_experiments(output)
    if not output:
        raise ValueError('No experiments could be detected. Use the template or paste one experiment per line.')
    return output


def _dedupe_experiments(rows: Iterable[dict]) -> list[dict]:
    out=[];used_codes=set();used_titles=set()
    for pos,row in enumerate(rows,start=1):
        title=cell_text(row.get('title'))
        if not title:
            continue
        title_key=title.casefold()
        if title_key in used_titles:
            continue
        base=normalize_experiment_code(row.get('experiment_no',''),pos)
        code=base;counter=2
        while code.casefold() in used_codes:
            code=f'{base}-{counter}';counter+=1
        used_codes.add(code.casefold());used_titles.add(title_key)
        try:marks=max(1,int(row.get('max_marks') or 10))
        except (TypeError,ValueError):marks=10
        out.append({'experiment_no':code,'title':title,'max_marks':marks})
    return out
