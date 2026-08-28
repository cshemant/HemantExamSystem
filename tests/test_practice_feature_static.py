import ast
import re
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'app.py').read_text(encoding='utf-8')

class PracticeFeatureStaticTests(unittest.TestCase):
    def test_confidential_is_default(self):
        self.assertIn("practice_visibility:Mapped[str]=mapped_column(String,nullable=False,default='official_only')",APP)
        self.assertIn("('bank_questions','practice_visibility',\"VARCHAR NOT NULL DEFAULT 'official_only'\")",APP)

    def test_practice_and_official_pools_are_separated(self):
        self.assertIn("BankQuestion.practice_visibility.in_(['practice_only','both'])",APP)
        self.assertIn("BankQuestion.practice_visibility.in_(['official_only','both'])",APP)

    def test_active_exam_is_not_exposed_as_previous_paper(self):
        self.assertIn("if not exam or exam.is_active or not practice_release_is_available(release):abort(404)",APP)
        self.assertIn("if not exam or exam.is_active:continue",APP)

    def test_required_practice_routes_exist(self):
        required={
            '/student/practice',
            '/student/practice/start',
            '/student/practice/previous/<int:exam_id>/start',
            '/student/practice/wrong/start',
            '/student/practice/bookmarks/start',
            '/student/practice/check-answer',
            '/student/practice/<int:attempt_id>/submit',
            '/student/practice/<int:attempt_id>/result',
        }
        tree=ast.parse(APP)
        routes=set()
        for node in ast.walk(tree):
            if not isinstance(node,ast.FunctionDef):continue
            for dec in node.decorator_list:
                if isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute) and dec.func.attr=='route' and dec.args and isinstance(dec.args[0],ast.Constant):
                    routes.add(dec.args[0].value)
        self.assertTrue(required.issubset(routes),required-routes)

    def test_templates_and_navigation_exist(self):
        for name in ['practice_centre.html','practice_attempt.html','practice_result.html']:
            self.assertTrue((ROOT/'templates'/name).exists(),name)
        base=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
        self.assertRegex(base,r"url_for\('practice_centre'\)")

if __name__=='__main__':
    unittest.main()
