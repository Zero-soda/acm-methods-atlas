# ACM Methods Atlas

A traceable methods catalogue and reproducible descriptive evidence map for arrhythmogenic cardiomyopathy (ACM).

[Online catalogue](https://zero-soda.github.io/acm-methods-atlas/) · [Chinese README](README.md) · [Annotation protocol](docs/annotation_protocol.md)

Version 0.1 contains 25 primary research records (24 peer-reviewed articles and one preprint), 232 positive study–method annotations, and 122 method concepts. The default analysis contains the 23 peer-reviewed primary articles cited by the associated integrative review, including one two-patient case series. Fourteen contextual references—guidelines, reviews, trial registrations and a conference presentation—are kept outside the analysis denominator.

## Interpretation

These are **confirmed annotation frequencies within a purposively assembled corpus**, not field-wide method prevalence, temporal trends, or study-quality scores. Annotation depth varies. Unrecorded methods are unknown, not confirmed absences. Article counts are not counts of independent patient cohorts.

Each positive annotation contains an original evidence summary, a source locator, a reading/verification level, and the original source URL. Generated versus reused data are marked only where verified. Spatial order, computational pseudotime and true longitudinal observations are kept distinct. Observational treatment is not coded as a randomized clinical trial.

AI assisted source reading, extraction and targeted independent checking. This is not a claim of dual-human full-text coding. The catalogue is intended for community correction and expansion.

## Reproduce

Python 3.10 or later; no third-party runtime dependencies:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/build_atlas.py
```

Open `docs/index.html`, or use the JSON/CSV exports. `--cohort manuscript`, `--cohort peer_reviewed`, and `--cohort all` use denominators of 23, 24, and 25 articles respectively. Prefer a separate `--out` directory for non-default cohorts.

The clinical-question mapping organizes evidence and research questions; it is not a validated clinical algorithm. No manuscript drafts, paper PDFs, third-party figures or patient-level data are redistributed.

Code: MIT. Original curation and documentation: CC BY 4.0. Third-party material retains its own rights. Cite the dataset/code version and the original studies relevant to your claims. See `CITATION.cff` and `CONTRIBUTING.md`.
