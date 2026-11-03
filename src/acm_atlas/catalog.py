"""Validation and study-level aggregation. Python standard library only."""

from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import json

from .pathways import validate_paths
from .evidence import validate_evidence

FAMILIES = {"design", "measurement", "computational", "intervention"}
STATUSES = {"verified_existing_audit", "verified_local_text", "abstract_only"}
COHORTS = ("manuscript", "peer_reviewed", "all")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_catalog(data_dir):
    data_dir = Path(data_dir)
    catalog = {name: read_json(data_dir / f"{name}.json") for name in
               ("studies", "methods", "method_annotations", "clinical_questions", "context_sources", "manifest", "research_paths", "connection_evidence")}
    validate(catalog)
    return catalog


def _unique(records, key, label):
    values = [r[key] for r in records]
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {label}")
    return set(values)


def validate(catalog):
    studies = catalog["studies"]
    methods = catalog["methods"]
    annotations = catalog["method_annotations"]
    study_ids = _unique(studies, "study_id", "study ID")
    method_ids = _unique(methods, "method_id", "method ID")
    question_ids = _unique(catalog["clinical_questions"], "question_id", "clinical question ID")
    dois = [s["doi"].lower() for s in studies]
    if len(dois) != len(set(dois)):
        raise ValueError("Duplicate DOI / version family in primary corpus")
    for s in studies:
        if s["publication_status"] not in {"peer_reviewed", "preprint"}:
            raise ValueError("Invalid publication status")
        if not isinstance(s["in_manuscript"], bool):
            raise ValueError("in_manuscript must be boolean")
        if not set(s["clinical_question_ids"]) <= question_ids:
            raise ValueError("Unknown clinical question")
        if not s["url"].startswith("https://"):
            raise ValueError("Primary source must have an HTTPS URL")
        if not set(s["systems"]) <= {"human", "animal", "in_vitro_or_engineered_model"}:
            raise ValueError("Invalid research system")
    for m in methods:
        if m["family"] not in FAMILIES or not m["group_id"]:
            raise ValueError("Invalid method family/group")
    pairs = set()
    covered = set()
    for a in annotations:
        if a["study_id"] not in study_ids or a["method_id"] not in method_ids:
            raise ValueError("Annotation references unknown study/method")
        pair = (a["study_id"], a["method_id"])
        if pair in pairs:
            raise ValueError("Duplicate study-method pair")
        pairs.add(pair)
        covered.add(a["study_id"])
        if a["annotation_status"] not in STATUSES:
            raise ValueError("Invalid annotation status")
        if a["data_origin"] not in {"generated", "reused", "not_classified"}:
            raise ValueError("Invalid data origin")
        if a["annotation_id"] != a["study_id"] + "::" + a["method_id"]:
            raise ValueError("Invalid annotation ID")
        if not a["source_url"].startswith("https://"):
            raise ValueError("Annotation source must have an HTTPS URL")
        if not a["evidence_basis"].strip() or not a["source_locator"].strip():
            raise ValueError("Every positive annotation needs evidence and a locator")
    if covered != study_ids:
        raise ValueError("Every included study needs at least one positive annotation")
    validate_paths(catalog["research_paths"], studies)
    validate_evidence(catalog["connection_evidence"], catalog)
    return True


def select_studies(studies, cohort="manuscript"):
    if cohort not in COHORTS:
        raise ValueError(f"Unknown cohort: {cohort}")
    if cohort == "all":
        return list(studies)
    selected = [s for s in studies if s["publication_status"] == "peer_reviewed"]
    if cohort == "manuscript":
        selected = [s for s in selected if s["in_manuscript"]]
    return selected


def summarize(catalog, cohort="manuscript"):
    selected = select_studies(catalog["studies"], cohort)
    study_ids = {s["study_id"] for s in selected}
    denominator = len(study_ids)
    methods = {m["method_id"]: m for m in catalog["methods"]}
    method_studies = defaultdict(set)
    family_studies = defaultdict(set)
    group_studies = defaultdict(set)
    study_methods = defaultdict(set)
    levels = Counter()
    for a in catalog["method_annotations"]:
        sid = a["study_id"]
        if sid not in study_ids:
            continue
        mid = a["method_id"]
        method_studies[mid].add(sid)
        family_studies[methods[mid]["family"]].add(sid)
        group_studies[methods[mid]["group_id"]].add(sid)
        study_methods[sid].add(mid)
        levels[a["annotation_status"]] += 1

    def row(key, members, **extra):
        return {"id": key, "n_studies": len(members), "denominator": denominator,
                "percent": round(100 * len(members) / denominator, 2) if denominator else 0.0,
                "study_ids": sorted(members), **extra}

    by_method = [row(mid, members, label=methods[mid]["label_zh"], family=methods[mid]["family"],
                     group_id=methods[mid]["group_id"]) for mid, members in method_studies.items()]
    by_method.sort(key=lambda r: (-r["n_studies"], r["id"]))
    by_family = [row(fam, family_studies[fam]) for fam in sorted(FAMILIES)]
    by_group = [row(group, members) for group, members in sorted(group_studies.items())]
    pairs = Counter()
    for mids in study_methods.values():
        pairs.update(combinations(sorted(mids), 2))
    cooccurrence = [{"method_a": a, "method_b": b, "n_studies": n}
                    for (a, b), n in sorted(pairs.items(), key=lambda p: (-p[1], p[0])) if n >= 2]
    questions = []
    for q in catalog["clinical_questions"]:
        qids = {s["study_id"] for s in selected if q["question_id"] in s["clinical_question_ids"]}
        qmethods = []
        for mid, members in method_studies.items():
            overlap = members & qids
            if overlap:
                qmethods.append({"method_id": mid, "label": methods[mid]["label_zh"],
                                 "n_studies": len(overlap), "study_ids": sorted(overlap)})
        questions.append({**q, "n_studies": len(qids), "study_ids": sorted(qids),
                          "methods": sorted(qmethods, key=lambda r: (-r["n_studies"], r["method_id"]))})
    return {"corpus_version": catalog["manifest"]["version"], "evidence_cutoff": catalog["manifest"]["evidence_cutoff"],
            "cohort": cohort, "denominator": denominator, "denominator_unit": "research articles, not patients or independent cohorts",
            "annotation_count": sum(levels.values()), "annotated_method_count": len(by_method),
            "catalog_studies": len(catalog["studies"]), "context_sources": len(catalog["context_sources"]),
            "missingness_rule": "Only positive verified annotations are counted; unrecorded is unknown, not absent.",
            "multilabel": True, "by_family": by_family, "by_group": by_group, "by_method": by_method,
            "by_year": dict(sorted(Counter(str(s["year"]) for s in selected).items())),
            "annotation_status_counts": dict(sorted(levels.items())), "cooccurrence": cooccurrence,
            "clinical_questions": questions, "selected_study_ids": sorted(study_ids)}
