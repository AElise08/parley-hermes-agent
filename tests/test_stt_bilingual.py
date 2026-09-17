#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import stt_bilingual  # noqa: E402
from stt_bilingual import Segment  # noqa: E402


def seg(start, end, text, lang, avg=-0.3, nospeech=0.1):
    return Segment(start, end, text, avg, nospeech, lang)


class MergeTests(unittest.TestCase):
    def test_keeps_portuguese_when_english_pass_covers_the_same_span(self):
        # Whisper-en often "translates" the PT half into English with a worse
        # logprob; the PT pass should win that window so the Portuguese stays.
        en = [
            seg(0.0, 2.5, "Hello how are you", "en", avg=-0.15),
            seg(2.5, 5.0, "I went to the market yesterday", "en", avg=-0.9),
        ]
        pt = [
            seg(0.0, 2.5, "rolo rau iu", "pt", avg=-1.2),
            seg(2.5, 5.0, "ontem eu fui ao mercado", "pt", avg=-0.2),
        ]
        text = stt_bilingual.merge_segments({"en": en, "pt": pt})
        self.assertIn("Hello how are you", text)
        self.assertIn("ontem eu fui ao mercado", text)
        self.assertNotIn("I went to the market yesterday", text)

    def test_non_overlapping_halves_stay_in_order(self):
        en = [seg(0.0, 2.0, "Good morning", "en", avg=-0.1)]
        pt = [seg(2.2, 4.0, "tudo bem com você", "pt", avg=-0.1)]
        text = stt_bilingual.merge_segments({"en": en, "pt": pt})
        self.assertEqual(text, "Good morning tudo bem com você")

    def test_empty_passes_return_empty(self):
        self.assertEqual(stt_bilingual.merge_segments({"en": [], "pt": []}), "")


class ProfileLanguageTests(unittest.TestCase):
    def test_reads_native_and_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tutor-profile.json"
            path.write_text(json.dumps({"native_language": "pt", "target_language": "en"}))
            with patch.object(stt_bilingual, "PROFILE", str(path)):
                self.assertEqual(stt_bilingual.profile_languages(), ("pt", "en"))

    def test_missing_profile_is_auto_detect(self):
        with patch.object(stt_bilingual, "PROFILE", "/no/such/profile.json"):
            self.assertEqual(stt_bilingual.profile_languages(), ())

    def test_empty_profile_is_auto_detect(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tutor-profile.json"
            path.write_text(json.dumps({"native_language": "", "target_language": ""}))
            with patch.object(stt_bilingual, "PROFILE", str(path)):
                self.assertEqual(stt_bilingual.profile_languages(), ())


class CliTests(unittest.TestCase):
    def test_writes_transcript_file_and_stdout(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "memo.m4a"
            audio.write_bytes(b"fake")
            out = Path(tmp) / "transcript.txt"
            with patch.object(stt_bilingual, "transcribe_file", return_value="Hello olá"):
                with patch.object(sys, "argv", ["stt_bilingual.py", str(audio), str(out)]):
                    with patch("sys.stdout"):
                        code = stt_bilingual.main()
            self.assertEqual(code, 0)
            self.assertEqual(out.read_text(encoding="utf-8").strip(), "Hello olá")

    def test_format_transcript_tags_detected_language(self):
        self.assertEqual(
            stt_bilingual.format_transcript("Bonjour", "fr"),
            "[lang:fr] Bonjour",
        )
        self.assertEqual(
            stt_bilingual.format_transcript("Guten Tag", "de"),
            "[lang:de] Guten Tag",
        )
        self.assertEqual(
            stt_bilingual.format_transcript("Hello", "en"),
            "[lang:en] Hello",
        )

    def test_iso_lang_keeps_any_whisper_code(self):
        self.assertEqual(stt_bilingual.iso_lang("de-DE"), "de")
        self.assertEqual(stt_bilingual.iso_lang("ja"), "ja")
        self.assertEqual(stt_bilingual.iso_lang("en"), "en")
        self.assertEqual(stt_bilingual.iso_lang("yue"), "yue")


if __name__ == "__main__":
    unittest.main()
