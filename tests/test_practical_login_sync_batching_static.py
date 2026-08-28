import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')
STUDENTS=(ROOT/'templates'/'students.html').read_text(encoding='utf-8')

class PracticalLoginSyncBatchingStaticTests(unittest.TestCase):
    def test_server_limits_practical_sync_batch_size(self):
        self.assertIn("PRACTICAL_SYNC_BATCH_SIZE=max(5,min(50,int(os.getenv('PRACTICAL_SYNC_BATCH_SIZE','20'))))",APP)
        route=APP.split('def sync_students_from_practical():',1)[1].split("@app.route('/admin/students/import'",1)[0]
        self.assertIn("request.form.get('offset','0')",route)
        self.assertIn("request.form.get('batch_size'",route)
        self.assertIn('selected_students=practical_students[offset:offset+batch_size]',route)
        self.assertIn('next_offset=min(total,offset+processed)',route)

    def test_each_student_isolated_and_each_batch_committed(self):
        route=APP.split('def sync_students_from_practical():',1)[1].split("@app.route('/admin/students/import'",1)[0]
        self.assertIn('with s.begin_nested():',route)
        self.assertIn("s.commit()",route)
        self.assertIn("'issues':issues",route)
        self.assertIn("'done':next_offset>=total",route)

    def test_browser_runs_20_student_batches_sequentially(self):
        self.assertIn("data.set('batch_size','20')",STUDENTS)
        self.assertIn("while(true)",STUDENTS)
        self.assertIn("offset=Number(result.next_offset||0)",STUDENTS)
        self.assertIn("Earlier completed batches are safe",STUDENTS)

if __name__=='__main__':
    unittest.main()
