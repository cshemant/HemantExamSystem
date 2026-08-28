import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class BatchSectionDeleteStaticTests(unittest.TestCase):
    def test_delete_route_preserves_practical_tables(self):
        text=(ROOT/'app.py').read_text(encoding='utf-8')
        block=text.split("def delete_group(group_id):",1)[1].split("@app.route('/admin/question-bank'",1)[0]
        self.assertIn("delete(StudentGroup)",block)
        self.assertIn("delete(ExamSession)",block)
        self.assertNotIn("delete(PracticalStudent)",block)
        self.assertNotIn("delete(PracticalMark)",block)
        self.assertNotIn("delete(PracticalRegister)",block)

    def test_manage_batches_has_confirmed_delete_icon(self):
        text=(ROOT/'templates'/'groups.html').read_text(encoding='utf-8')
        self.assertIn("url_for('delete_group'",text)
        self.assertIn('Practical lists and practical marks will NOT be deleted',text)
        self.assertIn('practical-delete-icon',text)
        self.assertIn("staff_role=='super_admin'",text)

    def test_practical_sync_rejects_section_mismatch(self):
        text=(ROOT/'app.py').read_text(encoding='utf-8')
        self.assertIn('This practical list belongs to Section',text)
        self.assertIn('_practical_register_section_code',text)

if __name__=='__main__':
    unittest.main()
