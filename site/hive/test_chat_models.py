"""Offline tests: run `python -m unittest hive.test_chat_models -v` from site.

Only OpenAI requests are mocked. No API credentials, database or MQTT broker
are needed; minimal Django settings are used for standalone unittest execution.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch


class ChatModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import django
        from django.conf import settings

        if not settings.configured:
            settings.configure(
                INSTALLED_APPS=["hive"],
                TEMPLATES=[{"BACKEND": "django.template.backends.django.DjangoTemplates"}],
                SECRET_KEY="offline-chat-model-tests",
            )
        django.setup()
        from hive.mqtt import conversations
        cls.module = conversations

    def setUp(self):
        self.client = Mock()
        self.api = self.client.chat.completions.create
        self.api.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Hello, Moxie!"))]
        )
        factory = patch.object(self.module, "create_openai", return_value=self.client)
        factory.start()
        self.addCleanup(factory.stop)

    def session(self, model):
        return self.module.SingleContextChatSession(
            model=model, max_tokens=70, temperature=0.5
        )

    def assert_reasoning_none_options(self, kwargs, model, limit=70):
        self.assertEqual(kwargs["model"], model)
        self.assertEqual(kwargs["max_completion_tokens"], limit)
        self.assertEqual(kwargs["reasoning_effort"], "none")
        self.assertEqual(kwargs["temperature"], 0.5)
        self.assertNotIn("max_tokens", kwargs)

    def assert_reasoning_low_options(self, kwargs, model, limit=70):
        self.assertEqual(kwargs["model"], model)
        self.assertEqual(kwargs["max_completion_tokens"], limit)
        self.assertEqual(kwargs["reasoning_effort"], "low")
        self.assertNotIn("max_tokens", kwargs)
        self.assertNotIn("temperature", kwargs)

    def assert_legacy_options(self, kwargs, model):
        self.assertEqual(kwargs["model"], model)
        self.assertEqual(kwargs["max_tokens"], 70)
        self.assertEqual(kwargs["temperature"], 0.5)
        self.assertNotIn("max_completion_tokens", kwargs)
        self.assertNotIn("reasoning_effort", kwargs)

    def test_completion_options_helpers(self):
        for model in ("gpt-6-luna", "gpt-5.5", "gpt-6-sol"):
            with self.subTest(model=model):
                self.assertTrue(self.module.is_reasoning_chat_model(model))
                self.assertTrue(self.module.supports_reasoning_none(model))
                opts = self.module.completion_options(model, 70, 0.5)
                self.assertEqual(opts, {
                    "max_completion_tokens": 70,
                    "reasoning_effort": "none",
                    "temperature": 0.5,
                })

        for model in ("o3-mini", "gpt-6-astra", "gpt-6.1-sol"):
            with self.subTest(model=model):
                self.assertTrue(self.module.is_reasoning_chat_model(model))
                self.assertFalse(self.module.supports_reasoning_none(model))
                opts = self.module.completion_options(model, 70, 0.5)
                self.assertEqual(opts, {
                    "max_completion_tokens": 70,
                    "reasoning_effort": "low",
                })

        for model in ("gpt-3.5-turbo", "gpt-4o-mini"):
            with self.subTest(model=model):
                self.assertFalse(self.module.is_reasoning_chat_model(model))
                self.assertEqual(
                    self.module.completion_options(model, 70, 0.5),
                    {"max_tokens": 70, "temperature": 0.5},
                )

    def test_luna_conversation(self):
        context = [{"role": "system", "content": "Be friendly and brief."}]
        session = self.session("gpt-6-luna")
        session.add_history("assistant", "Hi there!")
        text, overflow = session.next_response("Hello", context)
        self.assertEqual(text, "Hello, Moxie!")
        self.assertFalse(overflow)
        kwargs = self.api.call_args.kwargs
        self.assert_reasoning_none_options(kwargs, "gpt-6-luna")
        self.assertEqual(kwargs["messages"], context + [
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "Hello"},
        ])
        self.assertEqual(session._history, [{"role": "assistant", "content": "Hi there!"}])

    def test_legacy_conversation_parameters_unchanged(self):
        for model in ("gpt-3.5-turbo", "gpt-4o-mini"):
            with self.subTest(model=model):
                self.session(model).next_response("Hello", [])
                self.assert_legacy_options(self.api.call_args.kwargs, model)

    def test_astra_uses_low_effort(self):
        self.session("gpt-6-astra").next_response("Hello", [])
        self.assert_reasoning_low_options(self.api.call_args.kwargs, "gpt-6-astra")

    def test_luna_summary(self):
        text = self.session("gpt-6-luna").summarize(append_transcript=False)
        self.assertEqual(text, "Hello, Moxie!")
        self.assert_reasoning_none_options(self.api.call_args.kwargs, "gpt-6-luna")

    def test_summary_model_override_uses_luna_options(self):
        self.session("gpt-3.5-turbo").summarize(
            model="gpt-6-luna", max_tokens=120, append_transcript=False
        )
        self.assert_reasoning_none_options(
            self.api.call_args.kwargs, "gpt-6-luna", limit=120
        )

    def test_summary_model_override_preserves_legacy_options(self):
        self.session("gpt-6-luna").summarize(
            model="gpt-3.5-turbo", append_transcript=False
        )
        self.assert_legacy_options(self.api.call_args.kwargs, "gpt-3.5-turbo")

    def test_luna_conversation_error_keeps_existing_fallback(self):
        self.api.side_effect = RuntimeError("synthetic API failure")
        with self.assertLogs("hive.mqtt.conversations", level="WARNING"):
            text, overflow = self.session("gpt-6-luna").next_response("Hello", [])
        self.assertEqual(text, "Oh no.  I have run into a bug")
        self.assertFalse(overflow)


if __name__ == "__main__":
    unittest.main()
