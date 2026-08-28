import io
import unittest
from openpyxl import Workbook

from practical_core import parse_roster_bytes, parse_experiment_bytes, parse_experiment_text, normalize_experiment_sequence


class PracticalImportTests(unittest.TestCase):
    def _xlsx_bytes(self,rows):
        wb=Workbook();ws=wb.active
        for row in rows:ws.append(row)
        out=io.BytesIO();wb.save(out);return out.getvalue()

    def test_clean_roster(self):
        raw=self._xlsx_bytes([['roll_no','name'],['2024/1','Asha'],['2024/2','Ravi']])
        self.assertEqual(len(parse_roster_bytes('roster.xlsx',raw)),2)

    def test_university_multiline_headers(self):
        raw=self._xlsx_bytes([
            ['PRACTICAL EVALUATION SHEET'],
            ['Lab'],
            ['Sno','Reg. No','Experiment'],
            ['', '', 'Date'],
            ['', '', 'Name of Student'],
            [1,'2024/1','Asha'],
            [2,'2024/2','Ravi'],
        ])
        rows=parse_roster_bytes('sheet.xlsx',raw)
        self.assertEqual(rows,[{'roll_no':'2024/1','name':'Asha'},{'roll_no':'2024/2','name':'Ravi'}])

    def test_experiment_template(self):
        raw=self._xlsx_bytes([['experiment_no','title','max_marks'],['2A','Linear layout',10],['2B','Relative layout',10]])
        rows=parse_experiment_bytes('experiments.xlsx',raw)
        self.assertEqual(rows[0]['experiment_no'],'2-A')
        self.assertEqual(len(rows),2)

    def test_pasted_numbered_experiments(self):
        rows=parse_experiment_text('1 Installation of Android Studio\n2A Develop Hello World\n2B Linear layout')
        self.assertEqual([r['experiment_no'] for r in rows],['1','2-A','2-B'])

    def test_loose_sheet_carries_major_number_to_subparts(self):
        raw=self._xlsx_bytes([
            [1,'','Installation of Android Studio'],
            [2,'A','Develop Hello World'],
            ['', 'B','Linear and absolute layout'],
            ['', 'C','Frame, table and relative layout'],
            [3,'A','Text View and Edit Text'],
            ['', 'B','Auto Complete Text View'],
            [12,'A','Send and receive SMS'],
            ['', 'B','Send and receive e-mail'],
            ['', 'C','Deploy map based application'],
        ])
        rows=parse_experiment_bytes('mad-lab.xlsx',raw)
        self.assertEqual([r['experiment_no'] for r in rows],['1','2-A','2-B','2-C','3-A','3-B','12-A','12-B','12-C'])

    def test_legacy_letter_counter_codes_are_repaired_by_sequence(self):
        self.assertEqual(
            normalize_experiment_sequence(['9-A','B-7','10','11-A','B-8','C-4','12-A','B-9','C-5']),
            ['9-A','9-B','10','11-A','11-B','11-C','12-A','12-B','12-C']
        )


if __name__=='__main__':unittest.main()
