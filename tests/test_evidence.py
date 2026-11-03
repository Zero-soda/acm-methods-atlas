from copy import deepcopy
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
from acm_atlas.catalog import load_catalog, select_studies, validate
from acm_atlas.cli import build
from acm_atlas.evidence import summarize_evidence
from search_update import merge_records


class EvidenceAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(ROOT / "data")

    def test_claim_counts_are_not_article_counts(self):
        data = self.catalog["connection_evidence"]
        summary = summarize_evidence(data)
        self.assertEqual(summary["n_relations"], 29)
        self.assertEqual(summary["n_studies"], 23)
        self.assertEqual(sum(x["n_relations"] for x in summary["by_domain"]), 29)
        self.assertEqual({r["study_id"] for r in data["relations"]}, {s["study_id"] for s in select_studies(self.catalog["studies"])})
        self.assertTrue(all(r["human_review_status"] == "pending" for r in data["relations"]))

    def test_evidence_locators_and_human_review_record_are_required(self):
        bad = deepcopy(self.catalog)
        bad["connection_evidence"]["relations"][0]["source_locator"] = ""
        with self.assertRaisesRegex(ValueError, "locator"):
            validate(bad)
        bad = deepcopy(self.catalog)
        bad["connection_evidence"]["relations"][0]["human_review_status"] = "verified_with_public_review_record"
        with self.assertRaisesRegex(ValueError, "requires a review record"):
            validate(bad)

    def test_audit_navigation_and_exports(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.targets = [], []
            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if "id" in a:
                    self.ids.append(a["id"])
                if a.get("href", "").startswith("#"):
                    self.targets.append(a["href"][1:])
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            build(ROOT, out, "manuscript")
            self.assertEqual(json.loads((out / "exports/connection_evidence.json").read_text()), self.catalog["connection_evidence"])
            parser = Links()
            parser.feed((out / "connection_audit.html").read_text())
            self.assertEqual(len(parser.ids), len(set(parser.ids)))
            self.assertTrue(set(parser.targets) <= set(parser.ids))
            self.assertTrue((out / ".nojekyll").exists())
            self.assertEqual((out / "exports/search_candidates.csv").read_bytes(), (ROOT / "searches/20261103_v02/candidates.csv").read_bytes())


class RetrievalProvenanceTests(unittest.TestCase):
    def test_identifier_dedup_preserves_provenance_without_title_matching(self):
        def row(provider, sid, doi="", pmid=""):
            return dict(provider=provider, source_id=sid, query_id="fixture", doi=doi, pmid=pmid, title="Identical title", year="2026", journal="Fixture", publication_types=[])
        source = [row("pubmed", "1", pmid="1"), row("europe_pmc", "MED:1", "https://doi.org/10.example/ABC", "1"), row("europe_pmc", "PPR:2", "10.example/abc"), row("pubmed", "3", "10.example/other", "3")]
        merged = merge_records(source, [{"doi":"10.example/abc", "study_id":"PILOT"}])
        self.assertEqual(len(merged), 2)
        combined = next(r for r in merged if r["doi"] == "10.example/abc")
        self.assertEqual(len(combined["source_records"]), 3)
        self.assertEqual(combined["existing_pilot_study_id"], "PILOT")
        self.assertTrue(all(r["screening_status"] == "not_screened_this_update" for r in merged))

    def test_logged_strategy_and_protocol_snapshots_are_preserved(self):
        for directory in ("20261103", "20261103_v02"):
            folder = ROOT / "searches" / directory
            run = json.loads((folder / "search_run.json").read_text())
            self.assertEqual(hashlib.sha256((folder / "protocol_at_search_start.md").read_bytes()).hexdigest(), run["protocol_sha256"])
            self.assertEqual(json.loads((folder / "strategy_at_search_start.json").read_text()), run["strategy"])
            rows = json.loads((folder / "candidates.json").read_text())
            self.assertEqual(len(rows), run["deduplicated_candidate_records"])
            self.assertTrue(all(r["screening_status"] == "not_screened_this_update" for r in rows))


if __name__ == "__main__":
    unittest.main()
