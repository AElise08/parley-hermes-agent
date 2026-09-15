#!/usr/bin/env python3
import json
import os
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tutor  # noqa: E402
import tutor_config  # noqa: E402


class TempHome(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self._env = patch.dict(os.environ, {"HERMES_HOME": str(self.home)}, clear=False)
        self._env.start()
        os.environ.pop("TUTOR_PROFILE", None)
        self.addCleanup(self._env.stop)
        self.addCleanup(self._tmp.cleanup)


class SetupTests(TempHome):
    def test_empty_home_is_not_ready(self):
        status = tutor.setup_status()
        self.assertFalse(status["ready"])
        self.assertIn("Quer praticar qual idioma?", status["next"])

    def test_setup_local_then_profile_then_ready(self):
        self.assertTrue(tutor.setup_local()["ok"])
        self.assertFalse(tutor.setup_status()["ready"])
        tutor.profile_set(Namespace(target="en", native="pt", goal="write for a US audience",
                                    topics="writing, faith, tech", level=None))
        status = tutor.setup_status()
        self.assertFalse(status["ready"])
        self.assertIn("level", status["next"].lower())
        tutor.level_set(Namespace(level="b1", reason="placement chat"))
        status = tutor.setup_status()
        self.assertTrue(status["ready"])
        self.assertEqual(status["level"], "B1")
        self.assertEqual(status["topics"], ["writing", "faith", "tech"])

    def test_level_set_records_history_and_rejects_bad_level(self):
        tutor.setup_local()
        bad = tutor.level_set(Namespace(level="X9", reason=""))
        self.assertIn("error", bad)
        tutor.level_set(Namespace(level="A2", reason="start"))
        tutor.level_set(Namespace(level="B1", reason="two clean sessions"))
        history = tutor.load_profile()["level_history"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1]["from"], "A2")
        self.assertEqual(history[1]["to"], "B1")
        self.assertEqual(history[1]["reason"], "two clean sessions")

    def test_profile_set_refuses_inline_level(self):
        tutor.setup_local()
        result = tutor.profile_set(Namespace(target="en", native="pt", goal=None,
                                             topics=None, level="C2"))
        self.assertIn("error", result)
        self.assertEqual(tutor.load_profile().get("level", ""), "")


class SessionTests(TempHome):
    def test_log_and_streak(self):
        tutor.setup_local()
        self.assertIn("error", tutor.session_log(Namespace(role="robot", text="hi")))
        self.assertIn("error", tutor.session_log(Namespace(role="owner", text="  ")))
        tutor.session_log(Namespace(role="owner", text="Yesterday I go to the lab"))
        tutor.session_log(Namespace(role="tutor", text="Nice! How did it go?"))
        tail = tutor.session_tail(Namespace(limit=10))
        self.assertEqual(tail["count"], 2)
        streak = tutor.practice_streak()
        self.assertEqual(streak["streak_days"], 1)
        self.assertEqual(streak["last_practice"], datetime.now(tutor.zone()).date().isoformat())

    def test_note_carries_level(self):
        tutor.setup_local()
        tutor.level_set(Namespace(level="A2", reason="start"))
        tutor.session_note(Namespace(summary="placement chat: past tense shaky"))
        rows = tutor.load_sessions()
        self.assertEqual(rows[-1]["role"], "note")
        self.assertEqual(rows[-1]["level"], "A2")


class ErrorAndReviewTests(TempHome):
    def setUp(self):
        super().setUp()
        tutor.setup_local()

    def test_add_requires_wrong_and_better(self):
        self.assertIn("error", tutor.error_add(Namespace(wrong="", better="x", note="", kind="grammar")))
        self.assertIn("error", tutor.error_add(Namespace(wrong="x", better="", note="", kind="grammar")))

    def test_add_merge_and_kinds(self):
        first = tutor.error_add(Namespace(wrong="I go", better="I went", note="past", kind="grammar"))
        self.assertEqual(first["id"], "err-0001")
        self.assertFalse(first["merged"])
        again = tutor.error_add(Namespace(wrong="I go", better="I went", note="past", kind="grammar"))
        self.assertTrue(again["merged"])
        self.assertEqual(again["seen_count"], 2)
        unknown = tutor.error_add(Namespace(wrong="a", better="b", note="", kind="weird"))
        self.assertEqual(tutor.load_errors()[-1]["kind"], "grammar")
        self.assertNotEqual(unknown["id"], first["id"])

    def test_review_ladder(self):
        tutor.error_add(Namespace(wrong="I go", better="I went", note="", kind="grammar"))
        due = tutor.review(Namespace(limit=5))
        self.assertEqual(due["due"], 1)
        err_id = due["review"][0]["id"]

        for expected_days, expected_streak in ((3, 1), (7, 2), (14, 3), (30, 4)):
            grade = tutor.review_grade(Namespace(id=err_id, result="good"))
            self.assertEqual(grade["streak"], expected_streak)
            next_due = datetime.fromisoformat(grade["next_due"])
            delta = next_due - tutor.now_local()
            self.assertAlmostEqual(delta.days + delta.seconds / 86400, expected_days, delta=0.01)
            self.assertEqual(tutor.review(Namespace(limit=5))["due"], 0)
            # wind the clock back so it is due again for the next rung
            items = tutor.load_errors()
            items[0]["next_due"] = (tutor.now_local() - timedelta(minutes=1)).isoformat(timespec="seconds")
            tutor.save_errors(items)

        grade = tutor.review_grade(Namespace(id=err_id, result="good"))
        self.assertTrue(grade["graduated"])
        # graduated items leave the default error list
        self.assertEqual(tutor.error_list(Namespace(all=False))["count"], 0)
        self.assertEqual(tutor.error_list(Namespace(all=True))["count"], 1)

    def test_bad_grade_resets_to_tomorrow(self):
        tutor.error_add(Namespace(wrong="I go", better="I went", note="", kind="grammar"))
        tutor.review_grade(Namespace(id="err-0001", result="good"))
        bad = tutor.review_grade(Namespace(id="err-0001", result="bad"))
        self.assertEqual(bad["streak"], 0)
        self.assertIn("error", tutor.review_grade(Namespace(id="err-9999", result="good")))
        self.assertIn("error", tutor.review_grade(Namespace(id="err-0001", result="meh")))


class DigestPromptTests(TempHome):
    def test_rotates_topics_and_carries_due_item(self):
        tutor.setup_local()
        tutor.profile_set(Namespace(target="en", native="pt", goal=None,
                                    topics="writing, faith", level=None))
        tutor.level_set(Namespace(level="B1", reason="placement"))
        tutor.error_add(Namespace(wrong="my TCC", better="my final-year project", note="", kind="vocab"))
        prompt = tutor.digest_prompt()
        self.assertTrue(prompt["ready"])
        self.assertEqual(prompt["topic"], "writing")
        self.assertEqual(prompt["due_count"], 1)
        self.assertEqual(prompt["review_item"]["prompt"], "my TCC")
        # a second practice day rotates the topic
        tutor.session_log(Namespace(role="owner", text="hi"))
        yesterday = (tutor.now_local() - timedelta(days=1)).isoformat(timespec="seconds")
        rows = tutor.load_sessions()
        rows[-1]["ts"] = yesterday
        path = tutor.sessions_path()
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        self.assertEqual(tutor.digest_prompt()["topic"], "faith")

    def test_not_ready_without_level(self):
        tutor.setup_local()
        self.assertFalse(tutor.digest_prompt()["ready"])


class SettingsTests(TempHome):
    def test_json_wins_over_env_tz(self):
        Path(self.home, "tutor-settings.json").write_text(json.dumps({
            "timezone": "America/Belem", "practice_hour": 19, "locale": "pt",
        }), encoding="utf-8")
        with patch.dict(os.environ, {"TZ": "UTC"}, clear=False):
            settings = tutor_config.load_settings()
            self.assertEqual(tutor_config.timezone_name(settings), "America/Belem")
            self.assertEqual(tutor_config.practice_hour(settings), 19)
            self.assertEqual(tutor_config.locale(settings), "pt")

    def test_env_override_and_bad_values_fall_back(self):
        with patch.dict(os.environ, {"PARLEY_PRACTICE_HOUR": "7", "PARLEY_LOCALE": "en"}, clear=False):
            self.assertEqual(tutor_config.practice_hour({}), 7)
            self.assertEqual(tutor_config.locale({}), "en")
        self.assertEqual(tutor_config.practice_hour({"practice_hour": 99}), 18)
        self.assertEqual(tutor_config.timezone_name({"timezone": "Not/AZone"}), "UTC")
        with self.assertRaises(ValueError):
            tutor_config.set_locale("fr")


class StatsTests(TempHome):
    def test_stats_counts(self):
        tutor.setup_local()
        tutor.level_set(Namespace(level="B1", reason="placement"))
        tutor.session_log(Namespace(role="owner", text="hi"))
        tutor.session_log(Namespace(role="tutor", text="hello"))
        tutor.error_add(Namespace(wrong="a", better="b", note="", kind="grammar"))
        stats = tutor.stats()
        self.assertEqual(stats["sessions_turns"], 2)
        self.assertEqual(stats["mistakes_logged"], 1)
        self.assertEqual(stats["due_now"], 1)
        self.assertEqual(stats["level_changes"], 1)


if __name__ == "__main__":
    unittest.main()
