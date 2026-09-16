#!/usr/bin/env python3
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import send_chat  # noqa: E402
import voice_config  # noqa: E402


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class SendVoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(
            os.environ,
            {
                "HERMES_HOME": str(self.home),
                "PLOW_API_BASE": "https://api.plow.co",
                "PLOW_AGENT_TOKEN": "plow_test",
                "PLOW_HOME_CHANNEL": "cht_test",
            },
            clear=False,
        )
        self.env.start()
        self.addCleanup(self.env.stop)
        self.audio = self.home / "reply.m4a"
        self.audio.write_bytes(b"fake-aac")

    def test_send_voice_declares_uploads_then_voicememo(self):
        calls = []

        def fake_urlopen(request, timeout=None):
            calls.append((request.get_method(), request.full_url, request.data))
            if request.full_url.endswith("/attachments"):
                body = json.dumps({
                    "uid": "att_1",
                    "upload_url": "https://upload.example/put",
                    "upload_headers": {"Content-Type": "audio/mp4"},
                }).encode()
                return FakeResponse(body)
            return FakeResponse(b"{}")

        with patch("send_chat.urllib.request.urlopen", side_effect=fake_urlopen):
            send_chat.send_voice(str(self.audio), caption="try this")

        urls = [url for _method, url, _data in calls]
        self.assertEqual(urls[0], "https://api.plow.co/v1/chats/cht_test/attachments")
        self.assertEqual(urls[1], "https://upload.example/put")
        self.assertEqual(urls[2], "https://api.plow.co/v1/chats/cht_test/voicememo")
        self.assertEqual(urls[3], "https://api.plow.co/v1/chats/cht_test/messages")
        memo = json.loads(calls[2][2])
        self.assertEqual(memo, {"attachment_uid": "att_1"})
        caption = json.loads(calls[3][2])
        self.assertEqual(caption, {"body": "try this"})

    def test_send_voice_rejects_non_audio(self):
        other = self.home / "note.txt"
        other.write_text("hi")
        with self.assertRaises(SystemExit):
            send_chat.send_voice(str(other))


class VoiceConfigTests(unittest.TestCase):
    def test_apply_sets_auto_detect_and_bilingual_m4a(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text("stt:\n  language: en\nmodel:\n  default: x\n")
            cfg = voice_config.apply(path)
            self.assertEqual(cfg["stt"]["language"], "")
            self.assertEqual(cfg["stt"]["local"]["model"], "small")
            self.assertEqual(cfg["stt"]["provider"], "parley-bilingual")
            self.assertIn("{input_path}", cfg["stt"]["providers"]["parley-bilingual"]["command"])
            self.assertTrue(cfg["voice"]["auto_tts"])
            self.assertEqual(cfg["tts"]["provider"], "parley-bilingual")
            self.assertEqual(cfg["tts"]["providers"]["parley-bilingual"]["output_format"], "m4a")
            self.assertEqual(cfg["model"]["default"], "x")
            self.assertNotIn("fallback_model", cfg)

    def test_apply_does_not_touch_owner_model_or_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.yaml"
            path.write_text(
                "model:\n  provider: openai-codex\n  default: gpt-5\n"
                "fallback_model:\n  provider: anthropic\n  model: claude-sonnet-4\n"
            )
            cfg = voice_config.apply(path)
            self.assertEqual(cfg["model"]["provider"], "openai-codex")
            self.assertEqual(cfg["model"]["default"], "gpt-5")
            self.assertEqual(cfg["fallback_model"]["provider"], "anthropic")
            self.assertEqual(cfg["fallback_model"]["model"], "claude-sonnet-4")


if __name__ == "__main__":
    unittest.main()
