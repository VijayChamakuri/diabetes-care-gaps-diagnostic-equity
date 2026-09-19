#!/usr/bin/env Rscript
# Independent check of the Python survey estimators against R's `survey` package.
# Usage: Rscript r/validation.R data/processed/cohort.csv outputs/tables/r_estimates.csv
#
# Design: svydesign(ids = ~psu, strata = ~stratum, weights = ~weight, nest = TRUE). Subgroups are
# subpopulations of the full design (domain estimation), not separate surveys.

suppressPackageStartupMessages(library(survey))
args <- commandArgs(trailingOnly = TRUE)
cohort_path <- if (length(args) >= 1) args[1] else "data/processed/cohort.csv"
out_path <- if (length(args) >= 2) args[2] else "outputs/tables/r_estimates.csv"

options(survey.lonely.psu = "fail")
cohort <- read.csv(cohort_path, check.names = FALSE, stringsAsFactors = FALSE)
cohort$undiagnosed <- 1 - cohort$diagnosed

design <- svydesign(ids = ~psu, strata = ~stratum, weights = ~weight, nest = TRUE, data = cohort)
positives <- subset(design, hba1c_pos == 1)

estimate_domain <- function(dom, label) {
  m <- svymean(~undiagnosed, dom)
  d <- degf(dom)
  logit <- attr(svyciprop(~undiagnosed, dom, method = "logit"), "ci")
  wald <- confint(m, df = d)
  data.frame(
    group = label,
    estimate = as.numeric(coef(m)),
    se = as.numeric(SE(m)),
    df = d,
    ci_low_logit = as.numeric(logit[1]),
    ci_high_logit = as.numeric(logit[2]),
    ci_low_wald = max(0, as.numeric(wald[1, 1])),
    ci_high_wald = min(1, as.numeric(wald[1, 2])),
    stringsAsFactors = FALSE
  )
}

groups <- sort(unique(cohort$race_label))
rows <- list(estimate_domain(positives, "All groups"))
for (g in groups) {
  rows[[length(rows) + 1]] <- estimate_domain(subset(positives, race_label == g), g)
}

# Difference between two groups, using the joint covariance from svyby(covmat = TRUE).
contrast_row <- function(a, b, label) {
  pair <- subset(positives, race_label %in% c(a, b))
  by <- svyby(~undiagnosed, ~race_label, pair, svymean, covmat = TRUE)
  diff <- svycontrast(by, setNames(c(1, -1), c(a, b)))
  data.frame(
    group = label, estimate = as.numeric(coef(diff)), se = as.numeric(SE(diff)), df = degf(pair),
    ci_low_logit = NA_real_, ci_high_logit = NA_real_, ci_low_wald = NA_real_, ci_high_wald = NA_real_,
    stringsAsFactors = FALSE
  )
}
rows[[length(rows) + 1]] <- contrast_row("Non-Hispanic Black", "Non-Hispanic White",
                                        "Non-Hispanic Black minus Non-Hispanic White")

result <- do.call(rbind, rows)
dir.create(dirname(out_path), showWarnings = FALSE, recursive = TRUE)
write.csv(result, out_path, row.names = FALSE)
cat(sprintf("survey %s: wrote %d estimates to %s\n", as.character(packageVersion("survey")), nrow(result), out_path))
