from copy import deepcopy
from html.parser import HTMLParser
from pathlib import Path
import csv
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from acm_atlas.catalog import load_catalog, select_studies, summarize, validate
from acm_atlas.cli import build


class CountingPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(ROOT / "data")

    def test_separate_article_and_context_denominators(self):
        self.assertEqual(len(select_studies(self.catalog["studies"], "manuscript")), 23)
        self.assertEqual(len(select_studies(self.catalog["studies"], "peer_reviewed")), 24)
        self.assertEqual(len(select_studies(self.catalog["studies"], "all")), 25)
        self.assertEqual(len(self.catalog["context_sources"]), 14)
        self.assertNotIn("DSP_STAGE_605_PREPRINT", summarize(self.catalog)["selected_study_ids"])

    def test_parent_counts_do_not_sum_child_methods(self):
        stats = summarize(self.catalog)
        expected = {a["study_id"] for a in self.catalog["method_annotations"]
                    if a["method_id"] in {m["method_id"] for m in self.catalog["methods"] if m["group_id"] == "single_cell_omics"}
                    and a["study_id"] in stats["selected_study_ids"]}
        row = next(r for r in stats["by_group"] if r["id"] == "single_cell_omics")
        self.assertEqual(row["n_studies"], len(expected))
        self.assertEqual(len(row["study_ids"]), len(set(row["study_ids"])))

    def test_multilabel_percentages_are_study_based(self):
        stats = summarize(self.catalog)
        for row in stats["by_method"]:
            self.assertEqual(row["percent"], round(100 * len(row["study_ids"]) / 23, 2))
        self.assertGreater(sum(row["percent"] for row in stats["by_method"]), 100)
        self.assertIn("unknown", stats["missingness_rule"])

    def test_duplicate_annotations_are_rejected(self):
        bad = deepcopy(self.catalog)
        bad["method_annotations"].append(deepcopy(bad["method_annotations"][0]))
        with self.assertRaisesRegex(ValueError, "Duplicate study-method"):
            validate(bad)

    def test_unknown_data_origin_is_rejected(self):
        bad = deepcopy(self.catalog)
        bad["method_annotations"][0]["data_origin"] = "assumed_new"
        with self.assertRaisesRegex(ValueError, "Invalid data origin"):
            validate(bad)

    def test_required_scientific_distinctions(self):
        annotations = {(a["study_id"], a["method_id"]): a for a in self.catalog["method_annotations"]}
        methods = {m["method_id"]: m for m in self.catalog["methods"]}
        self.assertIn(("T04", "single_nucleus_rna_sequencing"), annotations)
        self.assertEqual(annotations[("T08", "bulk_rna_sequencing")]["data_origin"], "reused")
        self.assertEqual(annotations[("T08", "single_cell_rna_sequencing")]["data_origin"], "generated")
        self.assertIn(("Gaertner2012", "microarray_transcriptomics"), annotations)
        self.assertNotIn(("Gaertner2012", "bulk_rna_sequencing"), annotations)
        self.assertIn(("Fu2024", "trajectory_inference"), annotations)
        self.assertNotIn(("Fu2024", "longitudinal_clinical_follow_up"), annotations)
        self.assertIn(("Kyriakopoulou2025", "spatial_expression_pattern_analysis"), annotations)
        self.assertNotIn(("Kyriakopoulou2025", "spatial_niche_analysis"), annotations)
        self.assertEqual(methods["observational_treatment_exposure"]["family"], "design")

    def test_exports_use_the_selected_denominator(self):
        with tempfile.TemporaryDirectory() as temp:
            for cohort, n in [("manuscript", 23), ("peer_reviewed", 24), ("all", 25)]:
                out = Path(temp) / cohort
                build(ROOT, out, cohort)
                summary = json.loads((out / "summary.json").read_text())
                self.assertEqual(summary["denominator"], n)
                with (out / "method_summary.csv").open(encoding="utf-8-sig") as handle:
                    for row in csv.DictReader(handle):
                        self.assertEqual(int(row["denominator"]), n)


class PathwayIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog(ROOT / "data")

    def test_path_coverage_matches_review_without_supplemental_records(self):
        data = self.catalog["research_paths"]
        covered = {sid for path in data["paths"] for stage in path["stages"] for sid in stage["study_ids"]}
        self.assertEqual(covered, {s["study_id"] for s in select_studies(self.catalog["studies"])})
        self.assertFalse(data["curation_provenance"]["citation_genealogy_verified"])

    def test_dangling_evidence_and_unverified_causal_edges_are_rejected(self):
        bad = deepcopy(self.catalog)
        bad["research_paths"]["paths"][0]["stages"][0]["study_ids"].append("NONEXISTENT_STUDY")
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            validate(bad)
        bad = deepcopy(self.catalog)
        bad["research_paths"]["paths"][0]["connections"][0]["relation_type"] = "causal"
        with self.assertRaisesRegex(ValueError, "causal/citation"):
            validate(bad)

    def test_pathway_exports_and_internal_navigation(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.targets, self.controls = [], [], []
            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if "id" in a:
                    self.ids.append(a["id"])
                if a.get("href", "").startswith("#"):
                    self.targets.append(a["href"][1:])
                if "aria-controls" in a:
                    self.controls.append(a["aria-controls"])
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            build(ROOT, out, "manuscript")
            exported = json.loads((out / "exports/research_paths.json").read_text())
            self.assertEqual(exported, self.catalog["research_paths"])
            text = (out / "research_paths.html").read_text()
            parser = Links()
            parser.feed(text)
            self.assertEqual(len(parser.ids), len(set(parser.ids)))
            self.assertTrue(set(parser.targets + parser.controls) <= set(parser.ids))
            self.assertEqual(len(parser.controls), 3)
            for path in exported["paths"]:
                self.assertIn(path["next_study"]["public_data_now_zh"], text)
                self.assertIn(path["next_study"]["falsification_zh"], text)


if __name__ == "__main__":
    unittest.main()
