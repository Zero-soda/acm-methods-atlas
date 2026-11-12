"""Protect donor pairing, data provenance and the numerical re-run check."""

import gzip
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gse29819_workflow", ROOT / "workflows" / "gse29819" / "run.py")
WORKFLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKFLOW)


def headers():
    return {
        "!Sample_geo_accession": [["GSM1", "GSM2", "GSM3", "GSM4"]],
        "!Sample_title": [["RV_ARVC_1", "LV_ARVC_1", "LV_NF_1", "RV_NF_1"]],
        "!Sample_characteristics_ch1": [
            ["age: 18", "age: 18", "age: n.a.", "age: n.a."],
            ["gender: w", "gender: w", "gender: n.a.", "gender: n.a."],
            ["ventricle: right", "ventricle: left", "ventricle: left", "ventricle: right"],
        ],
    }


class WorkflowIntegrityTests(unittest.TestCase):
    def test_pairs_are_people_even_when_chambers_are_shuffled(self):
        rows = WORKFLOW.parse_sample_metadata(headers())
        donors = WORKFLOW.validate_pairs(rows)
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(donors), 2)
        self.assertEqual(rows[0]["sex"], "F")
        self.assertEqual(rows[2]["age"], "NA")

    def test_missing_pair_and_conflicting_covariates_stop_analysis(self):
        rows = WORKFLOW.parse_sample_metadata(headers())
        with self.assertRaisesRegex(ValueError, "pair"):
            WORKFLOW.validate_pairs(rows[:-1])
        rows[1]["age"] = "19.0"
        with self.assertRaisesRegex(ValueError, "covariates"):
            WORKFLOW.validate_pairs(rows)

    def test_title_and_source_chamber_must_agree(self):
        source = headers()
        source["!Sample_characteristics_ch1"][-1][0] = "ventricle: left"
        with self.assertRaisesRegex(ValueError, "disagreement"):
            WORKFLOW.parse_sample_metadata(source)

    def test_changed_source_is_rejected_instead_of_silently_updated(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            (cache / "source.gz").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                WORKFLOW.acquire({"filename": "source.gz", "sha256": hashlib.sha256(b"expected").hexdigest()}, cache)

    def test_rerun_verifies_values_and_complete_table_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            current, reference = Path(temporary) / "current", Path(temporary) / "reference"
            current.mkdir()
            reference.mkdir()
            for folder in (current, reference):
                with gzip.open(folder / "effects.tsv.gz", "wt") as handle:
                    handle.write("gene\teffect\nA\t1.25\n")
            self.assertEqual(WORKFLOW.verify_outputs(current, reference)["compared_tables"], 1)
            with gzip.open(current / "effects.tsv.gz", "wt") as handle:
                handle.write("gene\teffect\nA\t1.5\n")
            with self.assertRaisesRegex(ValueError, "differs"):
                WORKFLOW.verify_outputs(current, reference)
            (current / "effects.tsv.gz").unlink()
            with self.assertRaisesRegex(ValueError, "inventory mismatch"):
                WORKFLOW.verify_outputs(current, reference)


if __name__ == "__main__":
    unittest.main()
