# GSE29819 donor-aware reanalysis

Original reanalysis for ACM Methods Atlas; not original authors' code or an exact reproduction of their preprocessing/statistical tests.

Input: 19 independent donors, 38 tissues; groups {'ARVC': 6, 'DCM': 7, 'NF': 6}.

Primary estimand: mean(log2(RV)-log2(LV)) in ARVC minus mean(log2(RV)-log2(LV)) in NF

主交互作用对比在 20848 个基因中有 41 个达到 BH FDR < 0.05；固定的敏感性模型中为 1–182 个。阈值计数受探针处理、方差趋势及供者集合影响，需同时查看效应量与稳定性。

[Analysis/download report](index.html) · [Machine-readable results](results_summary.json)

## Clinical evidence boundary

- End-stage transplant tissue cannot establish early disease chronology or a treatment window.
- Bulk tissue mixes cell types and cannot identify cellular spatial neighborhoods.
- Pairing controls within-donor chamber comparison, not between-group confounding.
- Age/sex distributions differ and NF_5 has missing covariates; complete-case adjustment is a sensitivity analysis.
- No independent cohort validation; method agreement or leave-one-donor-out stability is not external validation.
- A nonsignificant chamber or interaction test does not demonstrate equivalence.

The original study already examined biventricular expression. This example demonstrates reproducibility and sensitivity; no new biological discovery is claimed.
