import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class V109AIAutofillStaticTests(unittest.TestCase):
    def test_version_and_large_question_limit(self):
        app=(ROOT/'app.py').read_text(encoding='utf-8')
        voice=(ROOT/'static'/'voice_assistant.js').read_text(encoding='utf-8')
        exams=(ROOT/'templates'/'exams.html').read_text(encoding='utf-8')
        self.assertIn("APP_VERSION='2.35.0'",app)
        self.assertIn('min(100',app)
        self.assertIn('Math.min(100',voice)
        self.assertIn('max="100"',exams)

    def test_legacy_subject_voice_can_request_ai_autofill(self):
        app=(ROOT/'app.py').read_text(encoding='utf-8')
        voice=(ROOT/'static'/'voice_assistant.js').read_text(encoding='utf-8')
        self.assertIn("request.form.get('auto_fill_ai')=='1'",app)
        self.assertIn('_generate_ai_subject_context_questions',app)
        self.assertIn("aiToggle.checked=true",voice)
        self.assertIn("Create AI-assisted draft exam",voice)

    def test_ai_shortage_is_generated_in_batches(self):
        app=(ROOT/'app.py').read_text(encoding='utf-8')
        ai=(ROOT/'ai_curriculum.py').read_text(encoding='utf-8')
        self.assertIn('batch=min(20',app)
        self.assertIn('generate_subject_context_questions',ai)
        self.assertIn('avoid_questions',ai)
        self.assertIn('No confirmed syllabus is available',ai)

    def test_all_units_curriculum_supported(self):
        app=(ROOT/'app.py').read_text(encoding='utf-8')
        exams=(ROOT/'templates'/'exams.html').read_text(encoding='utf-8')
        voice=(ROOT/'static'/'voice_assistant.js').read_text(encoding='utf-8')
        self.assertIn("selected_units=[item['row'] for item in bundle['units']]",app)
        self.assertIn('All Units</option>',exams)
        self.assertIn("unitValue=''",voice)

if __name__=='__main__':
    unittest.main()
