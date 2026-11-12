#!/usr/bin/env Rscript
# Donor-aware reanalysis of archived GSE29819 MAS5 expression.
# This is an independent workflow, not the original investigators' code.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2L || length(args) > 3L) {
  stop("Usage: Rscript analyze.R INPUT_DIR OUTPUT_DIR [LOCAL_R_LIBRARY]", call. = FALSE)
}
input_dir <- normalizePath(args[1L], mustWork = TRUE)
out_dir <- args[2L]
if (length(args) == 3L) {
  local_lib <- normalizePath(args[3L], mustWork = TRUE)
  .libPaths(c(local_lib, .libPaths()))
}
if (!requireNamespace("limma", quietly = TRUE)) {
  stop("This workflow requires limma 3.62.2; supply its R library as the third argument.", call. = FALSE)
}
if (as.character(utils::packageVersion("limma")) != "3.62.2") {
  stop("Expected limma 3.62.2, observed ", utils::packageVersion("limma"), call. = FALSE)
}
suppressPackageStartupMessages(library(limma))
options(stringsAsFactors = FALSE, scipen = 999, OutDec = ".")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
out_dir <- normalizePath(out_dir, mustWork = TRUE)
completion_path <- file.path(out_dir, "RUN_COMPLETE.txt")
if (file.exists(completion_path)) unlink(completion_path)
write_tsv <- function(x, filename) {
  utils::write.table(x, file.path(out_dir, filename), sep = "\t", quote = FALSE,
                     row.names = FALSE, col.names = TRUE, na = "NA")
}
assert <- function(condition, message) {
  if (!isTRUE(condition)) stop(message, call. = FALSE)
}
read_tsv <- function(filename) {
  utils::read.delim(file.path(input_dir, filename), check.names = FALSE,
                   na.strings = c("NA", "", "n.a.", "n.a", "N/A"))
}

expression_connection <- gzfile(file.path(input_dir, "expression.tsv.gz"), "rt")
expr <- tryCatch(utils::read.delim(expression_connection, check.names = FALSE),
                 finally = close(expression_connection))
meta <- read_tsv("samples.tsv")
annotation <- read_tsv("annotation.tsv")
assert(identical(names(expr)[1L], "probe_id"), "Expression first column must be probe_id.")
assert(all(c("sample", "title", "donor", "chamber", "diagnosis", "age", "sex") %in% names(meta)),
       "samples.tsv is missing required columns.")
assert(all(c("probe_id", "gene_symbol") %in% names(annotation)),
       "annotation.tsv must contain probe_id and gene_symbol.")
assert(!anyDuplicated(expr$probe_id) && !anyNA(expr$probe_id), "Expression probe IDs must be unique and present.")
assert(!anyDuplicated(meta$sample) && !anyNA(meta$sample), "Metadata sample IDs must be unique and present.")
assert(!anyDuplicated(annotation$probe_id), "Annotation must have at most one unambiguous gene per probe.")
assert(all(!is.na(annotation$probe_id) & !is.na(annotation$gene_symbol) & nzchar(annotation$gene_symbol)),
       "Annotation IDs and gene symbols must be present.")
assert(!any(grepl("///|;", annotation$gene_symbol)), "Ambiguous multi-gene annotations must be removed upstream.")
assert(setequal(names(expr)[-1L], meta$sample), "Expression and metadata samples must match exactly.")
assert(all(meta$chamber %in% c("LV", "RV")), "Chamber values must be LV or RV.")
assert(all(meta$diagnosis %in% c("ARVC", "DCM", "NF")), "Unexpected diagnosis.")
assert(!anyNA(meta$donor) && !anyDuplicated(paste(meta$donor, meta$chamber)), "Each donor/chamber must occur once.")

probe_ids <- as.character(expr$probe_id)
raw_y <- as.matrix(expr[, -1L, drop = FALSE])
storage.mode(raw_y) <- "double"
rownames(raw_y) <- probe_ids
assert(nrow(raw_y) == 54675L && ncol(raw_y) == 38L,
       "GSE29819 workflow expects 54,675 probe sets and 38 arrays.")
assert(all(is.finite(raw_y)) && all(raw_y > 0),
       "Expression must be finite and positive MAS5 signal; missing values and zero/negative values are not accepted.")
meta <- meta[match(colnames(raw_y), meta$sample), , drop = FALSE]
meta$age <- suppressWarnings(as.numeric(meta$age))
sex_raw <- tolower(trimws(as.character(meta$sex)))
sex_normalized <- rep(NA_character_, length(sex_raw))
sex_normalized[sex_raw %in% c("m", "male")] <- "M"
# GEO's German 'w' (weiblich) is explicitly normalized to F.
sex_normalized[sex_raw %in% c("w", "f", "female")] <- "F"
assert(all(is.na(sex_raw) | sex_raw %in% c("m", "male", "w", "f", "female")),
       "Unrecognized sex label; preserve and review the source metadata.")
meta$sex <- sex_normalized
donor_ids <- sort(unique(meta$donor), method = "radix")
donors <- meta[match(donor_ids, meta$donor), c("donor", "diagnosis", "age", "sex"), drop = FALSE]
for (id in donor_ids) {
  mm <- meta[meta$donor == id, , drop = FALSE]
  assert(nrow(mm) == 2L && setequal(mm$chamber, c("LV", "RV")), paste("Incomplete LV/RV pair:", id))
  for (field in c("diagnosis", "age", "sex")) {
    value <- mm[[field]]
    assert(length(unique(value)) == 1L, paste("Conflicting donor metadata:", id, field))
  }
}
assert(nrow(donors) == 19L && all(table(factor(donors$diagnosis, levels = c("ARVC", "DCM", "NF"))) == c(6L, 7L, 6L)),
       "Expected 6 ARVC, 7 DCM and 6 NF paired donors.")
left <- meta$sample[match(paste(donors$donor, "LV"), paste(meta$donor, meta$chamber))]
right <- meta$sample[match(paste(donors$donor, "RV"), paste(meta$donor, meta$chamber))]
assert(!anyNA(left) && !anyNA(right), "Failed to align paired samples.")

qc <- data.frame(sample = meta$sample, donor = meta$donor, diagnosis = meta$diagnosis,
                 chamber = meta$chamber, n_probes = nrow(raw_y),
                 missing_values = colSums(!is.finite(raw_y)), min_raw = apply(raw_y, 2L, min),
                 q25_raw = apply(raw_y, 2L, stats::quantile, probs = 0.25),
                 median_raw = apply(raw_y, 2L, stats::median),
                 q75_raw = apply(raw_y, 2L, stats::quantile, probs = 0.75),
                 max_raw = apply(raw_y, 2L, max), transform = "log2(x); no pseudocount")
write_tsv(qc, "input_qc.tsv")

log_probes <- log2(raw_y)
annotation <- annotation[annotation$probe_id %in% probe_ids, c("probe_id", "gene_symbol"), drop = FALSE]
annotation <- annotation[order(annotation$gene_symbol, annotation$probe_id, method = "radix"), , drop = FALSE]
assert(nrow(annotation) > 0L, "No annotated expression probes remain.")
mapped <- log_probes[annotation$probe_id, , drop = FALSE]
gene_sum <- rowsum(mapped, annotation$gene_symbol, reorder = TRUE)
gene_count <- table(annotation$gene_symbol)
y_all <- gene_sum / as.numeric(gene_count[rownames(gene_sum)])
keep <- rowSums(!is.finite(y_all)) == 0L & apply(y_all, 1L, stats::sd) > 1e-8
y <- y_all[keep, , drop = FALSE]
assert(nrow(y) >= 1000L, "Too few finite variable genes after annotation collapse.")
gene_ids <- rownames(y)
# Representative probes are selected without any diagnosis or outcome labels.
probe_rank <- order(annotation$gene_symbol, -rowMeans(mapped), annotation$probe_id, method = "radix")
representatives <- annotation[probe_rank, , drop = FALSE]
representatives <- representatives[!duplicated(representatives$gene_symbol), , drop = FALSE]
representatives <- representatives[match(gene_ids, representatives$gene_symbol), , drop = FALSE]
y_rep <- log_probes[representatives$probe_id, , drop = FALSE]
rownames(y_rep) <- gene_ids
y_quantile <- normalizeBetweenArrays(y, method = "quantile")
write_tsv(data.frame(metric = c("input_probe_sets", "input_arrays", "paired_donors", "mapped_unambiguous_probes",
                               "mapped_gene_symbols", "finite_variable_gene_universe", "removed_nonvariable_genes",
                               "primary_gene_collapse", "representative_selection", "quantile_sensitivity", "sex_normalization"),
                     value = c(nrow(raw_y), ncol(raw_y), nrow(donors), nrow(annotation), nrow(y_all), nrow(y),
                               sum(!keep), "mean of log2 MAS5 probe intensities", "maximum pooled mean log2 intensity; probe ID tie break",
                               "additional quantile normalization of primary gene expression", "m/male=M; w/f/female=F; missing preserved")),
          "mapping_summary.tsv")

make_delta <- function(yy) {
  dd <- yy[, right, drop = FALSE] - yy[, left, drop = FALSE]
  colnames(dd) <- donors$donor
  dd
}
delta <- make_delta(y)
safe_cor <- function(x, z) {
  if (length(x) < 2L || stats::sd(x) == 0 || stats::sd(z) == 0) return(NA_real_)
  suppressWarnings(stats::cor(x, z, method = "spearman"))
}
direction_agreement <- function(x, z) mean(sign(x) == sign(z))
fit_table <- function(values, design, coefficient, intensity = NULL, trend = TRUE) {
  assert(ncol(values) == nrow(design) && qr(design)$rank == ncol(design), "Analysis design is not full rank or sample aligned.")
  fit <- lmFit(values, design)
  if (!is.null(intensity)) fit$Amean <- intensity
  fit <- eBayes(fit, trend = trend, robust = FALSE)
  tt <- topTable(fit, coef = coefficient, number = Inf, sort.by = "none", confint = 0.95)
  tt <- data.frame(gene = rownames(tt), effect_log2 = tt$logFC, CI.L = tt$CI.L, CI.R = tt$CI.R,
                   t = tt$t, P.Value = tt$P.Value, adj.P.Val = tt$adj.P.Val, row.names = NULL)
  assert(identical(tt$gene, gene_ids), "Model changed the prespecified gene universe/order.")
  list(table = tt, fit = fit)
}
tables <- list()
summary_rows <- list()
store_result <- function(name, role, result, chosen_donors) {
  tab <- result$table
  tables[[name]] <<- data.frame(contrast = name, tab, check.names = FALSE)
  group_counts <- table(factor(chosen_donors$diagnosis, levels = c("ARVC", "DCM", "NF")))
  summary_rows[[name]] <<- data.frame(contrast = name, model_role = role, n_genes = nrow(tab),
                                     n_donors = nrow(chosen_donors), n_ARVC = unname(group_counts[1L]),
                                     n_DCM = unname(group_counts[2L]), n_NF = unname(group_counts[3L]),
                                     FDR05 = sum(tab$adj.P.Val < 0.05), nominalP05 = sum(tab$P.Value < 0.05),
                                     min_p = min(tab$P.Value), min_padj = min(tab$adj.P.Val))
  invisible(result)
}
pair_model <- function(yy, group_a, group_b, feature, name, role = "secondary", trend = TRUE) {
  chosen <- donors$diagnosis %in% c(group_a, group_b)
  dd <- donors[chosen, , drop = FALSE]
  design <- cbind(intercept = 1, disease = as.numeric(dd$diagnosis == group_a))
  if (feature == "delta") {
    values <- make_delta(yy)[, chosen, drop = FALSE]
    intensity <- rowMeans(yy[, c(left[chosen], right[chosen]), drop = FALSE])
  } else {
    selected_samples <- if (feature == "LV") left[chosen] else right[chosen]
    values <- yy[, selected_samples, drop = FALSE]
    intensity <- NULL
  }
  result <- fit_table(values, design, "disease", intensity, trend)
  store_result(name, role, result, dd)
  result
}

primary <- pair_model(y, "ARVC", "NF", "delta", "interaction_ARVC_vs_NF", "primary")
for (pair in list(c("ARVC", "NF"), c("DCM", "NF"), c("ARVC", "DCM"))) {
  for (chamber in c("LV", "RV")) {
    pair_model(y, pair[1L], pair[2L], chamber, paste0(chamber, "_", pair[1L], "_vs_", pair[2L]))
  }
  if (!identical(pair, c("ARVC", "NF"))) {
    pair_model(y, pair[1L], pair[2L], "delta", paste0("interaction_", pair[1L], "_vs_", pair[2L]))
  }
}
for (diagnosis in c("ARVC", "DCM", "NF")) {
  chosen <- donors$diagnosis == diagnosis
  design <- matrix(1, nrow = sum(chosen), ncol = 1L, dimnames = list(NULL, "RV_minus_LV"))
  result <- fit_table(delta[, chosen, drop = FALSE], design, "RV_minus_LV",
                      rowMeans(y[, c(left[chosen], right[chosen]), drop = FALSE]))
  store_result(paste0("within_", diagnosis, "_RV_minus_LV"), "secondary", result, donors[chosen, , drop = FALSE])
}

sensitivity_results <- list()
sensitivity_results$representative_probe <- pair_model(y_rep, "ARVC", "NF", "delta", "sensitivity_representative_probe", "sensitivity")
sensitivity_results$extra_quantile <- pair_model(y_quantile, "ARVC", "NF", "delta", "sensitivity_extra_quantile", "sensitivity")
sensitivity_results$no_trend <- pair_model(y, "ARVC", "NF", "delta", "sensitivity_no_trend", "sensitivity", trend = FALSE)
primary_chosen <- donors$diagnosis %in% c("ARVC", "NF")
primary_donors <- donors[primary_chosen, , drop = FALSE]
complete <- primary_chosen & is.finite(donors$age) & !is.na(donors$sex)
complete_case_unadjusted_status <- "not_run: too few complete-case donors per diagnosis"
adjusted_status <- "not_run: incomplete or rank-deficient covariate design"
if (sum(complete & donors$diagnosis == "ARVC") >= 2L && sum(complete & donors$diagnosis == "NF") >= 2L) {
  complete_case_donors <- donors[complete, , drop = FALSE]
  complete_case_design <- cbind(intercept = 1, disease = as.numeric(complete_case_donors$diagnosis == "ARVC"))
  result <- fit_table(delta[, complete, drop = FALSE], complete_case_design, "disease",
                      rowMeans(y[, c(left[complete], right[complete]), drop = FALSE]))
  store_result("sensitivity_complete_case_unadjusted", "sensitivity", result, complete_case_donors)
  sensitivity_results$complete_case_unadjusted <- result
  complete_case_unadjusted_status <- paste0("run: ", sum(complete), " complete-case donors; no covariate adjustment")
}
if (sum(complete) > 4L && length(unique(donors$sex[complete])) == 2L) {
  adjusted_donors <- donors[complete, , drop = FALSE]
  adjusted_donors$disease <- as.numeric(adjusted_donors$diagnosis == "ARVC")
  adjusted_donors$sex <- factor(adjusted_donors$sex, levels = c("F", "M"))
  design <- model.matrix(~disease + age + sex, adjusted_donors)
  if (qr(design)$rank == ncol(design) && nrow(design) > ncol(design)) {
    result <- fit_table(delta[, complete, drop = FALSE], design, "disease",
                        rowMeans(y[, c(left[complete], right[complete]), drop = FALSE]))
    store_result("sensitivity_complete_case_age_sex", "sensitivity", result, adjusted_donors)
    sensitivity_results$complete_case_age_sex <- result
    adjusted_status <- paste0("run: ", sum(complete), " complete-case donors; descriptive sensitivity")
  }
}
sensitivity_summary <- do.call(rbind, lapply(names(sensitivity_results), function(name) {
  result <- sensitivity_results[[name]]$table
  data.frame(model = name, n_genes = nrow(result), FDR05 = sum(result$adj.P.Val < 0.05),
             spearman_effect = safe_cor(primary$table$effect_log2, result$effect_log2),
             same_direction_fraction = direction_agreement(primary$table$effect_log2, result$effect_log2))
}))
write_tsv(sensitivity_summary, "primary_sensitivity_summary.tsv")
writeLines(c(paste0("Complete-case unadjusted: ", complete_case_unadjusted_status),
             paste0("Complete-case age/sex adjusted: ", adjusted_status),
             "The two complete-case models use identical donors, separating exclusion effects from covariate adjustment.",
             "Primary all-donor model is retained regardless of covariate sensitivity.",
             "Age/sex adjustment does not establish exchangeability or causal disease effects."),
           file.path(out_dir, "covariate_sensitivity_status.txt"))

loo_effects <- matrix(NA_real_, nrow = nrow(y), ncol = nrow(primary_donors),
                      dimnames = list(gene_ids, primary_donors$donor))
loo_rows <- list()
primary_hits <- primary$table$adj.P.Val < 0.05
for (id in primary_donors$donor) {
  chosen <- primary_chosen & donors$donor != id
  dd <- donors[chosen, , drop = FALSE]
  design <- cbind(intercept = 1, disease = as.numeric(dd$diagnosis == "ARVC"))
  result <- fit_table(delta[, chosen, drop = FALSE], design, "disease",
                      rowMeans(y[, c(left[chosen], right[chosen]), drop = FALSE]))
  store_result(paste0("LOO_without_", id), "leave_one_donor_out", result, dd)
  effects <- result$table$effect_log2
  loo_effects[, id] <- effects
  loo_rows[[id]] <- data.frame(omitted_donor = id, group = donors$diagnosis[match(id, donors$donor)],
                               n_donors = nrow(dd), n_genes = nrow(result$table),
                               FDR05 = sum(result$table$adj.P.Val < 0.05),
                               spearman_effect = safe_cor(primary$table$effect_log2, effects),
                               same_direction_fraction = direction_agreement(primary$table$effect_log2, effects),
                               median_absolute_effect_change = stats::median(abs(effects - primary$table$effect_log2)),
                               primary_selected_FDR05_genes = sum(primary_hits),
                               conditional_selected_same_direction_fraction = if (any(primary_hits)) direction_agreement(primary$table$effect_log2[primary_hits], effects[primary_hits]) else NA_real_)
}
loo_summary <- do.call(rbind, loo_rows)
write_tsv(loo_summary, "primary_leave_one_out_summary.tsv")
sign_stability <- rowMeans(sign(loo_effects) == sign(primary$table$effect_log2))
stability <- data.frame(gene = gene_ids, primary_effect_log2 = primary$table$effect_log2,
                        primary_adj.P.Val = primary$table$adj.P.Val,
                        loo_min_effect_log2 = apply(loo_effects, 1L, min),
                        loo_max_effect_log2 = apply(loo_effects, 1L, max),
                        loo_same_direction_fraction = sign_stability)
write_tsv(stability, "primary_gene_stability.tsv")

# Orthogonal parametrization check: fixed donor intercepts cannot identify the
# disease main effect, but can identify disease-by-chamber interaction.
check_meta <- meta[meta$diagnosis %in% c("ARVC", "NF"), , drop = FALSE]
check_meta$donor <- factor(check_meta$donor)
check_meta$RV <- as.numeric(check_meta$chamber == "RV")
check_meta$ARVCxRV <- as.numeric(check_meta$diagnosis == "ARVC") * check_meta$RV
full_design <- model.matrix(~donor + RV + ARVCxRV, check_meta)
assert(qr(full_design)$rank == ncol(full_design), "Fixed-donor verification design is not full rank.")
full_fit <- lmFit(y[, check_meta$sample, drop = FALSE], full_design)
full_fit$Amean <- rowMeans(y[, check_meta$sample, drop = FALSE])
full_eb <- eBayes(full_fit, trend = TRUE, robust = FALSE)
delta_fit <- primary$fit
paired_check <- data.frame(
  max_absolute_coefficient_difference = max(abs(full_eb$coefficients[, "ARVCxRV"] - delta_fit$coefficients[, "disease"])),
  max_absolute_unmoderated_SE_difference = max(abs(full_eb$stdev.unscaled[, "ARVCxRV"] * full_eb$sigma - delta_fit$stdev.unscaled[, "disease"] * delta_fit$sigma)),
  max_absolute_moderated_t_difference = max(abs(full_eb$t[, "ARVCxRV"] - delta_fit$t[, "disease"])),
  max_absolute_moderated_p_difference = max(abs(full_eb$p.value[, "ARVCxRV"] - delta_fit$p.value[, "disease"])),
  tolerance = 1e-8)
write_tsv(paired_check, "paired_model_check.tsv")
assert(all(unlist(paired_check[1L, 1:4]) < 1e-8), "Paired-difference and fixed-donor models failed the equivalence check.")
write_tsv(do.call(rbind, summary_rows), "contrast_summary.tsv")
write_tsv(do.call(rbind, tables), "gene_statistics.tsv")
capture.output(utils::sessionInfo(), file = file.path(out_dir, "sessionInfo.txt"))

# Small reusable base-graphics figures. All analyses are cross-sectional and
# all leave-one-out summaries are conditional internal sensitivities.
palette <- c(ARVC = "#B54736", DCM = "#4A73A6", NF = "#428166")
figures_dir <- file.path(out_dir, "figures")
dir.create(figures_dir, recursive = TRUE, showWarnings = FALSE)
plot_density <- function(x, z, xlab, ylab, main, diagonal = FALSE) {
  assert(all(is.finite(x)) && all(is.finite(z)), "Nonfinite figure coordinates.")
  if (diagonal) {
    limits <- range(c(x, z))
    if (diff(limits) == 0) limits <- limits + c(-0.5, 0.5)
    xlim <- ylim <- limits
  } else {
    xlim <- range(x); ylim <- range(z)
    if (diff(xlim) == 0) xlim <- xlim + c(-0.5, 0.5)
    if (diff(ylim) == 0) ylim <- ylim + c(-0.5, 0.5)
  }
  xb <- seq(xlim[1L], xlim[2L], length.out = 66L)
  zb <- seq(ylim[1L], ylim[2L], length.out = 66L)
  xi <- findInterval(x, xb, all.inside = TRUE)
  zi <- findInterval(z, zb, all.inside = TRUE)
  counts <- matrix(tabulate(xi + 65L * (zi - 1L), nbins = 65L * 65L), nrow = 65L)
  counts[counts == 0L] <- NA
  graphics::image((xb[-1L] + xb[-length(xb)]) / 2, (zb[-1L] + zb[-length(zb)]) / 2,
                  log1p(counts), col = grDevices::hcl.colors(32L, "YlOrRd", rev = TRUE),
                  xlim = xlim, ylim = ylim, xlab = xlab, ylab = ylab, main = main,
                  useRaster = TRUE, asp = if (diagonal) 1 else NA)
  abline(h = 0, v = 0, col = "grey70", lty = 3)
  if (diagonal) abline(0, 1, col = "grey35", lty = 2)
  mtext("Colour: log(1 + genes per bin)", side = 3, line = 0.15, cex = 0.62)
}
figure <- function(name, draw) {
  # PDF is the sole R rendering backend. The runner converts this identical
  # vector master to SVG/PNG with Poppler, avoiding X11/Cairo dependencies.
  path <- file.path(figures_dir, paste0(name, ".pdf"))
  grDevices::pdf(path, width = 11, height = 8.5, pointsize = 10, useDingbats = FALSE)
  tryCatch({
    par(mfrow = c(2, 2), mar = c(4.4, 4.5, 3.0, 1.1), oma = c(2, 0, 2, 0), las = 1)
    draw()
  }, finally = grDevices::dev.off())
}
figure("01_design_and_pca", function() {
  donor_counts <- table(factor(donors$diagnosis, levels = names(palette)))
  barplot(rbind(Donors = donor_counts, Arrays = 2L * donor_counts), beside = TRUE,
          col = c("#405469", "#A9B6C4"), ylab = "Count", main = "Paired ventricles: 19 donors, 38 arrays", ylim = c(0, 17))
  legend("topright", c("Donors (analysis units)", "Arrays (two per donor)"),
         fill = c("#405469", "#A9B6C4"), bty = "n", cex = 0.8)
  pc <- stats::prcomp(t(y), center = TRUE, scale. = FALSE)
  variance <- pc$sdev^2 / sum(pc$sdev^2)
  plot(pc$x[, 1L], pc$x[, 2L], type = "n", xlab = sprintf("PC1 (%.1f%%)", 100 * variance[1L]),
       ylab = sprintf("PC2 (%.1f%%)", 100 * variance[2L]), main = "Paired-sample PCA (all retained genes)")
  for (id in donor_ids) {
    ii <- which(meta$donor == id)
    lines(pc$x[ii, 1L], pc$x[ii, 2L], col = grDevices::adjustcolor(palette[meta$diagnosis[ii[1L]]], alpha.f = 0.35))
  }
  points(pc$x[, 1L], pc$x[, 2L], pch = ifelse(meta$chamber == "RV", 17L, 16L), col = palette[meta$diagnosis], cex = 0.85)
  legend("topright", c(names(palette), "LV", "RV"), col = c(palette, "grey25", "grey25"),
         pch = c(rep(16L, 3L), 16L, 17L), bty = "n", cex = 0.7)
  boxplot(as.data.frame(log_probes), outline = FALSE, names = rep("", ncol(y)),
          col = palette[meta$diagnosis], ylab = "log2(MAS5 signal)", xlab = "Arrays in source order", main = "Archived signal distributions")
  age_x <- as.numeric(factor(donors$diagnosis, levels = names(palette)))
  for (diagnosis in names(palette)) {
    ii <- which(donors$diagnosis == diagnosis & is.finite(donors$age))
    age_x[ii] <- age_x[ii] + seq(-0.07, 0.07, length.out = length(ii))
  }
  plot(age_x, donors$age,
       xaxt = "n", xlim = c(0.5, 3.5), xlab = "Diagnosis", ylab = "Age (years)",
       col = palette[donors$diagnosis], pch = 16L, main = "Donor covariates: observational groups")
  axis(1, 1:3, names(palette))
  mtext(paste(sum(!is.finite(donors$age)), "donor age missing; no imputation"), side = 3, line = 0.15, cex = 0.65)
  mtext("GSE29819 | Failing cardiomyopathy tissue and non-failing controls; cross-sectional", outer = TRUE, side = 1, cex = 0.8)
})
figure("02_chamber_effects", function() {
  get_effect <- function(name) tables[[name]]$effect_log2
  plot_density(get_effect("LV_ARVC_vs_NF"), get_effect("RV_ARVC_vs_NF"),
               "LV ARVC - NF (log2)", "RV ARVC - NF (log2)", "ARVC disease-associated effects", TRUE)
  plot_density(get_effect("LV_DCM_vs_NF"), get_effect("RV_DCM_vs_NF"),
               "LV DCM - NF (log2)", "RV DCM - NF (log2)", "DCM disease-associated effects", TRUE)
  plot_density(get_effect("LV_ARVC_vs_NF"), get_effect("LV_DCM_vs_NF"),
               "LV ARVC - NF (log2)", "LV DCM - NF (log2)", "Shared NF comparator: LV", TRUE)
  plot_density(get_effect("RV_ARVC_vs_NF"), get_effect("RV_DCM_vs_NF"),
               "RV ARVC - NF (log2)", "RV DCM - NF (log2)", "Shared NF comparator: RV", TRUE)
  mtext("All retained genes | Effect concordance is not equivalence or independent validation", outer = TRUE, side = 1, cex = 0.8)
})
figure("03_interaction", function() {
  tt <- primary$table
  plot_density(tt$effect_log2, -log10(pmax(tt$P.Value, .Machine$double.xmin)),
               "(RV - LV) ARVC - (RV - LV) NF (log2)", "-log10(nominal P)", "Primary disease-by-chamber contrast")
  if (any(primary_hits)) points(tt$effect_log2[primary_hits], -log10(tt$P.Value[primary_hits]), col = "#B54736", pch = 16, cex = 0.4)
  legend("topright", paste0("BH FDR < 0.05: ", sum(primary_hits), " genes"), bty = "n", cex = 0.72)
  hist(tt$effect_log2, breaks = 70L, col = "#91B7C1", border = "white",
       xlab = "Interaction coefficient (log2)", main = "Primary coefficient distribution")
  abline(v = 0, lty = 2, col = "grey35")
  plot_density(tt$effect_log2, tables$interaction_DCM_vs_NF$effect_log2,
               "ARVC - NF interaction (log2)", "DCM - NF interaction (log2)", "DCM disease control; shared NF donors", TRUE)
  selected_names <- c("interaction_ARVC_vs_NF", "LV_ARVC_vs_NF", "RV_ARVC_vs_NF", "interaction_DCM_vs_NF")
  counts <- vapply(tables[selected_names], function(tab) sum(tab$adj.P.Val < 0.05), integer(1L))
  barplot(counts, names.arg = c("ARVC\ninteraction", "ARVC\nLV", "ARVC\nRV", "DCM\ninteraction"),
          col = c("#B54736", "#D79380", "#D79380", "#4A73A6"), ylab = "Genes at BH FDR < 0.05",
          main = "Separate prespecified contrast families", cex.names = 0.7)
  mtext("Gene-level associations | Absence of significance does not establish biventricular equivalence", outer = TRUE, side = 1, cex = 0.8)
})
figure("04_stability", function() {
  plot_density(primary$table$effect_log2, sensitivity_results$representative_probe$table$effect_log2,
               "Primary mean-probe effect (log2)", "Representative-probe effect (log2)", "Probe summarization sensitivity", TRUE)
  plot_density(primary$table$effect_log2, sensitivity_results$extra_quantile$table$effect_log2,
               "Primary archived-MAS5 effect (log2)", "Extra-quantile effect (log2)", "Normalization sensitivity", TRUE)
  barplot(loo_summary$spearman_effect, names.arg = loo_summary$omitted_donor,
          ylim = c(min(0, min(loo_summary$spearman_effect, na.rm = TRUE)), 1), las = 2,
          col = palette[loo_summary$group], ylab = "Spearman effect correlation", cex.names = 0.65,
          main = "Leave one whole donor out (all genes)")
  hist(sign_stability, breaks = seq(-1/24, 1 + 1/24, by = 1/12), col = "#789CA8", border = "white",
       xlab = "Fraction of 12 omissions retaining effect direction", xlim = c(0, 1),
       main = "All-gene sign stability")
  mtext("Descriptive internal sensitivities | Selected-hit stability is conditional, not external validation", outer = TRUE, side = 1, cex = 0.8)
})

writeLines(c("GSE29819 donor-aware workflow completed.",
             "schema_version=1", "limma=3.62.2", paste0("R=", getRversion()),
             paste0("retained_genes=", nrow(y)), "donors=19; primary_ARVC=6; primary_NF=6",
             "primary_estimand=(RV-LV)_ARVC-(RV-LV)_NF",
             "All inference is observational and cross-sectional."), completion_path)
cat("Completed GSE29819 analysis:", nrow(y), "genes; 19 paired donors; figures and TSV tables in", out_dir, "\n")
