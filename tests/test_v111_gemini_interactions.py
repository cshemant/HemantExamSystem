import json
import os
import unittest
from unittest.mock import patch

import ai_curriculum


class GeminiInteractionsTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'AI_PROVIDER': 'gemini',
            'GEMINI_API_KEY': 'test-key',
            'GEMINI_MODEL': 'gemini-3.6-flash',
        }, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_gemini_36_uses_interactions_structured_output(self):
        seen = {}
        def fake_http(url, payload, headers, timeout=90):
            seen.update(url=url, payload=payload, headers=headers, timeout=timeout)
            return {
                'status': 'completed',
                'steps': [{
                    'type': 'model_output',
                    'content': [{'type': 'text', 'text': json.dumps({'questions': []})}],
                }],
            }
        with patch.object(ai_curriculum, '_http_json', fake_http):
            result = ai_curriculum.structured_generate('test', 'question_batch', ai_curriculum.QUESTION_SCHEMA)
        self.assertEqual(result, {'questions': []})
        self.assertEqual(seen['url'], 'https://generativelanguage.googleapis.com/v1beta/interactions')
        self.assertEqual(seen['payload']['model'], 'gemini-3.6-flash')
        self.assertEqual(seen['payload']['response_format']['mime_type'], 'application/json')
        self.assertEqual(seen['payload']['response_format']['schema'], ai_curriculum.QUESTION_SCHEMA)
        self.assertNotIn('generationConfig', seen['payload'])

    def test_legacy_gemini_25_keeps_generate_content(self):
        seen = {}
        with patch.dict(os.environ, {'GEMINI_MODEL': 'gemini-2.5-flash'}, clear=False):
            def fake_http(url, payload, headers, timeout=90):
                seen.update(url=url, payload=payload)
                return {'candidates': [{'content': {'parts': [{'text': json.dumps({'questions': []})}]}}]}
            with patch.object(ai_curriculum, '_http_json', fake_http):
                result = ai_curriculum.structured_generate('test', 'question_batch', ai_curriculum.QUESTION_SCHEMA)
        self.assertEqual(result, {'questions': []})
        self.assertIn('/models/gemini-2.5-flash:generateContent', seen['url'])
        self.assertIn('responseJsonSchema', seen['payload']['generationConfig'])


if __name__ == '__main__':
    unittest.main()
