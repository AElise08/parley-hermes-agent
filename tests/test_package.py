import hashlib
import json
import pathlib
import py_compile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class PackageTests(unittest.TestCase):
    def test_generator_compiles(self):
        py_compile.compile(str(ROOT / "app" / "odiario.py"), doraise=True)

    def test_config_is_json(self):
        data = json.loads((ROOT / "app" / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(data["paper_name"], "The News")

    def test_no_private_attribution_or_contact(self):
        source = (ROOT / "app" / "odiario.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("não quer fait-divers", source)
        self.assertNotIn("@mail.instinct.com", source)

    def test_cleaner_handles_broken_feed_text(self):
        source = (ROOT / "app" / "odiario.py").read_text(encoding="utf-8")
        self.assertIn("Drop invalid control characters", source)

    def test_reporter_checksum(self):
        got = hashlib.sha256((ROOT / "vendor" / "agent_index_client.py").read_bytes()).hexdigest()
        self.assertEqual(got, "c3bf54ed37aec22704b8003a7ff6385a1fd3ef49207ce55613ddc41df36a1b01")

if __name__ == "__main__":
    unittest.main()
