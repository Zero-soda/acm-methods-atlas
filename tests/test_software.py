from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from acm_atlas.software import build_software, validate_software


class SoftwareProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "data/software_sources.json").read_text())

    def test_pinned_code_and_on_request_are_distinct(self):
        self.assertTrue(validate_software(self.data))
        rows = {r["code_id"]: r for r in self.data["entries"]}
        self.assertEqual(len(rows), 7)
        self.assertEqual(sum(bool(r["repo_url"]) for r in rows.values()), 6)
        self.assertIsNone(rows["penna2026_original"]["observed_commit"])
        self.assertTrue(all(r["run_status"] == "not_run" for r in rows.values()))
        self.assertIn("0.1.7", " ".join(rows["vima_paper_analysis"]["environment_notes"]))
        self.assertNotEqual(rows["vima_software"]["declared_package_version"], "0.1.7")

    def test_null_github_license_does_not_erase_package_declaration(self):
        rows = {r["code_id"]: r for r in self.data["entries"]}
        for name, declared in (("vima_software", "MIT"), ("scmlnet", "GPL-2")):
            self.assertIsNone(rows[name]["license_github_spdx"])
            self.assertEqual(rows[name]["license_declared"], declared)
            self.assertTrue(rows[name]["license_metadata_url"])
            self.assertNotEqual(rows[name]["license_status"], "license_text_verified")
        bad = deepcopy(self.data)
        bad["entries"][0]["license_status"] = "license_text_verified"
        with self.assertRaisesRegex(ValueError, "license text"):
            validate_software(bad)

    def test_reproduction_claims_require_more_than_a_source_audit(self):
        for status in ("reproduced", "passed", "not_run_but_verified"):
            bad = deepcopy(self.data)
            bad["entries"][0]["run_status"] = status
            with self.assertRaisesRegex(ValueError, "reproduced upstream run"):
                validate_software(bad)
        bad = deepcopy(self.data)
        bad["entries"][0]["observed_commit"] = "main"
        with self.assertRaisesRegex(ValueError, "pinned commit"):
            validate_software(bad)

    def test_local_paths_and_nonpublic_or_active_urls_are_rejected(self):
        for url in ("javascript:alert(1)", "file:///tmp/private", "http://github.com/example/code", "https://localhost/code", "https://127.0.0.1/code", "https://user:secret@example.com/code", "https://example.com/\" onclick=\"alert(1)"):
            bad = deepcopy(self.data)
            bad["entries"][0]["evidence_urls"] = [url]
            with self.assertRaises(ValueError, msg=url):
                validate_software(bad)
        bad = deepcopy(self.data)
        bad["audit_scope"] = "Read from /Users/fixture/private-project/file.json"
        with self.assertRaisesRegex(ValueError, "private local paths"):
            validate_software(bad)

    def test_export_roundtrip_escaped_html_and_separate_workflow(self):
        class Page(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags, self.ids, self.links = [], [], []
            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                self.tags.append(tag)
                if "id" in a:
                    self.ids.append(a["id"])
                if "href" in a:
                    self.links.append(a["href"])
                self.assert_no_handler(a)
            @staticmethod
            def assert_no_handler(attrs):
                if any(key.lower().startswith("on") for key in attrs):
                    raise AssertionError("Unexpected inline event handler")
        with tempfile.TemporaryDirectory() as temp:
            root, out = Path(temp) / "source", Path(temp) / "output"
            (root / "data").mkdir(parents=True)
            data = deepcopy(self.data)
            data["entries"][0]["name"] = "VIMA <script>alert('fixture')</script>"
            (root / "data/software_sources.json").write_text(json.dumps(data))
            build_software(root, out)
            self.assertEqual(json.loads((out / "exports/software_sources.json").read_text()), data)
            text = (out / "software.html").read_text()
            parser = Page()
            parser.feed(text)
            self.assertNotIn("script", parser.tags)
            self.assertIn("&lt;script&gt;", text)
            self.assertEqual(len(parser.ids), len(set(parser.ids)))
            self.assertEqual(len(parser.ids), len(data["entries"]))
            self.assertIn("./workflows/gse29819/index.html", parser.links)
            self.assertIn("本项目独立重分析", text)
            self.assertIn("NOT_RUN", text)
            self.assertIn("统计分母", text)
            first = (out / "software.html").read_bytes()
            build_software(root, out)
            self.assertEqual(first, (out / "software.html").read_bytes())


if __name__ == "__main__":
    unittest.main()
