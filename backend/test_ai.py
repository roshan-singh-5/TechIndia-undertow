import json
import os
import unittest
from unittest.mock import patch

from assistant_service import ai_configuration, optional_llm_reply
from assistant_service import deterministic_reply
from main import AssistantChatRequest


class FakeResponse:
    output_text = "Grounded answer."


class FakeClient:
    def __init__(self, **kwargs): self.responses = self
    def create(self, **kwargs): return FakeResponse()


class AiProviderTests(unittest.TestCase):
    def tearDown(self):
        for name in ("AI_PROVIDER", "AI_API_KEY", "AI_MODEL", "AI_BASE_URL"):
            os.environ.pop(name, None)

    def test_missing_configuration_uses_fallback(self):
        self.assertFalse(ai_configuration()["configured"])
        self.assertIsNone(optional_llm_reply("What happened?", {"summary": {}}))

    @patch("assistant_service.OpenAI", FakeClient)
    def test_configured_provider_response_is_parsed(self):
        os.environ.update(AI_PROVIDER="openai", AI_API_KEY="test-key", AI_MODEL="test-model")
        self.assertEqual(optional_llm_reply("Summarize", {"summary": {"transactions": 1}}), "Grounded answer.")

    @patch("assistant_service.OpenAI", side_effect=TimeoutError())
    def test_provider_timeout_returns_fallback_signal(self, _):
        os.environ.update(AI_PROVIDER="openai", AI_API_KEY="test-key", AI_MODEL="test-model")
        self.assertIsNone(optional_llm_reply("Summarize", {}))

    def test_unknown_account_and_message_limits_are_safe(self):
        answer, references = deterministic_reply("Why was ACC-999 flagged?", {"accounts_data": [], "transaction_records": [], "alerts": [], "summary": {"transactions": 0, "accounts": 0, "flagged_accounts": 0}, "data_source": "test"}, [])
        self.assertIn("could not find", answer.lower())
        self.assertEqual(references, [])
        with self.assertRaises(Exception):
            AssistantChatRequest(message="x" * 1501)


if __name__ == "__main__":
    unittest.main()
