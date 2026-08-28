import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class V108StaticTests(unittest.TestCase):
    def test_ai_module_and_supported_types(self):
        text=(ROOT/'ai_curriculum.py').read_text(encoding='utf-8')
        self.assertIn('https://api.openai.com/v1/responses',text)
        self.assertIn('generativelanguage.googleapis.com',text)
        for qtype in ['single_choice','multiple_select','true_false','numerical','short_text','essay']:
            self.assertIn(qtype,text)

    def test_curriculum_models_and_routes_exist(self):
        text=(ROOT/'app.py').read_text(encoding='utf-8')
        for model in ['AcademicInstitution','CurriculumProgram','CurriculumSubject','SyllabusDocument','SyllabusUnit','SyllabusTopic']:
            self.assertIn(f'class {model}',text)
        for route in ['/admin/academic-setup','/admin/exams/ai-from-curriculum','generate-questions']:
            self.assertIn(route,text)
        self.assertIn("APP_VERSION='2.34.0'",text)

    def test_ai_review_blocks_activation(self):
        text=(ROOT/'app.py').read_text(encoding='utf-8')
        self.assertIn('refresh_exam_ai_review_pending',text)
        self.assertIn('AI-generated question',text)
        self.assertIn("ai_review_status='pending'",text)

    def test_ui_and_voice_are_wired(self):
        exams=(ROOT/'templates'/'exams.html').read_text(encoding='utf-8')
        setup=(ROOT/'templates'/'academic_setup.html').read_text(encoding='utf-8')
        voice=(ROOT/'static'/'voice_assistant.js').read_text(encoding='utf-8')
        self.assertIn('AI-Assisted Exam from Syllabus',exams)
        self.assertIn('ai-curriculum-question-type',exams)
        self.assertIn('Upload / replace syllabus',setup)
        self.assertIn('Confirm Syllabus',setup)
        self.assertIn('EXAM_VOICE_CURRICULUM_CATALOG',voice)
        self.assertIn('inferCurriculumQuestionType',voice)
        self.assertIn('syllabusSummaryCommand',voice)

    def test_env_examples_do_not_contain_real_keys(self):
        for name in ['.env.example','.env.online.example']:
            text=(ROOT/name).read_text(encoding='utf-8')
            self.assertIn('AI_PROVIDER',text)
            self.assertNotIn('sk-proj-',text)

if __name__=='__main__':
    unittest.main()
