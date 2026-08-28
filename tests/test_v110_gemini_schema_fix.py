import os
import unittest
from unittest.mock import patch

import ai_curriculum


class GeminiJsonSchemaRegressionTests(unittest.TestCase):
    def test_gemini_uses_response_json_schema(self):
        captured = {}

        def fake_http(url, payload, headers, timeout=90):
            captured["url"] = url
            captured["payload"] = payload
            return {
                "candidates": [
                    {"content": {"parts": [{"text": '{"questions": []}'}]}}
                ]
            }

        with patch.dict(os.environ, {
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "GEMINI_MODEL": "gemini-2.5-flash",
        }, clear=False), patch.object(ai_curriculum, "_http_json", side_effect=fake_http):
            result = ai_curriculum._call_gemini(
                "test",
                "questions",
                {
                    "type": "object",
                    "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
                    "required": ["questions"],
                    "additionalProperties": False,
                },
            )

        self.assertEqual(result, {"questions": []})
        config = captured["payload"]["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertIn("responseJsonSchema", config)
        self.assertNotIn("responseSchema", config)
        self.assertFalse(config["responseJsonSchema"]["additionalProperties"])

    def test_source_does_not_send_legacy_gemini_schema_field(self):
        source = open(ai_curriculum.__file__, "r", encoding="utf-8").read()
        self.assertIn('"responseJsonSchema": schema', source)
        self.assertNotIn('"responseSchema": schema', source)


if __name__ == "__main__":
    unittest.main()
