# ACM Methods Atlas

**v0.3 adds a pilot audit of evidence conditions.** Twenty-nine selected within-study assertions from the 23 core articles retain temporal, spatial, perturbational and clinical-outcome evidence. Six predefined translational questions list applicable validation conditions and missing alignment. These are descriptive annotations, not quality scores or field-wide absence claims. [Browse the audit](https://zero-soda.github.io/acm-methods-atlas/connection_audit.html).

A scoping-review protocol draft and two logged retrieval runs are available. The calibrated PubMed/Europe PMC run retrieved 3,741 overlapping source records, deduplicated by identifiers into 2,079 **unscreened candidates**. Retrieval, inclusion and the existing pilot corpus remain separate. The project has not completed an exhaustive scoping review or independent dual-human screening/coding. Both the initial known-item failures and query amendments are retained.

**v0.2 connects studies into question-driven research paths.** Each step links a research question, approach, within-study finding, unresolved gap and a proposed clinical validation study. [Explore the research paths](https://zero-soda.github.io/acm-methods-atlas/research_paths.html).

Three paths cover the 23 primary peer-reviewed studies cited by the review: early electrical/metabolic abnormalities and progression; injury, inflammation and repair; and local tissue states, electrophysiology and risk. Twelve cross-study connections distinguish conceptual synthesis, parallel evidence and four unvalidated bridges. The paths are not verified citation genealogy or a universal disease chronology. Proposed studies include falsification conditions and a statement of what public data can currently establish.

A traceable methods catalogue and reproducible descriptive evidence map for arrhythmogenic cardiomyopathy (ACM).

[Online catalogue](https://zero-soda.github.io/acm-methods-atlas/) · [Chinese README](README.md) · [Annotation protocol](docs/annotation_protocol.md)

The catalogue contains 25 primary research records (24 peer-reviewed articles and one preprint), 232 positive study–method annotations, and 122 method concepts. The default analysis contains the 23 peer-reviewed primary articles cited by the associated integrative review, including one two-patient case series. Fourteen contextual references—guidelines, reviews, trial registrations and a conference presentation—are kept outside the analysis denominator.

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
