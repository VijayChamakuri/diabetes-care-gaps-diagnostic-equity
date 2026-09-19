"""Design-based survey estimation for a stratified, clustered sample (NHANES).

Conventions, chosen to match R's ``survey`` package (``svydesign(nest=TRUE)``):

* Point estimates are weighted ratios. A subpopulation ("domain") is estimated by zeroing the
  domain indicator outside it, keeping every stratum and PSU of the full design in the variance.
  Dropping out-of-domain PSUs (analysing a subgroup as if it were its own survey) is wrong and
  understates variance.
* Variance is Taylor linearization with the stratified with-replacement PSU estimator and no
  finite-population correction: ``sum_h n_h/(n_h - 1) * sum_j (t_hj - mean_h)^2``.
* Degrees of freedom for domain ``d`` are the PSUs with positive domain weight minus the strata
  with positive domain weight, which is ``survey::degf``.
* Proportion intervals use the logit method (``svyciprop(method="logit")``) with a t quantile on
  those degrees of freedom. Wald intervals are reported alongside because they are what most
  readers expect.
* Bootstrap replicates use the Rao-Wu rescaled bootstrap: ``n_h - 1`` PSUs drawn with replacement
  per stratum. Drawing ``n_h`` PSUs, as a naive bootstrap does, understates variance by
  ``(n_h - 1) / n_h``, which is a factor of two in NHANES' two-PSU strata.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


class SurveyError(ValueError):
    """Invalid survey design or an estimate that cannot be computed."""


@dataclass(frozen=True)
class Design:
    """Weights and the stratum and PSU of every respondent."""

    weight: np.ndarray
    cluster: np.ndarray  # integer index of the (stratum, PSU) cluster
    cluster_stratum: np.ndarray  # stratum index of each cluster
    lonely: str = "fail"

    @property
    def n(self) -> int:
        return int(self.weight.size)

    @property
    def n_clusters(self) -> int:
        return int(self.cluster_stratum.size)

    @classmethod
    def from_frame(
        cls,
        frame: pd.DataFrame,
        weight: str = "weight",
        psu: str = "psu",
        stratum: str = "stratum",
        lonely: str = "fail",
    ) -> Design:
        if lonely not in ("fail", "centered", "remove"):
            raise SurveyError(f"lonely must be fail, centered or remove, not {lonely!r}")
        w = frame[weight].to_numpy(dtype=float)
        if not np.isfinite(w).all():
            raise SurveyError("Survey weights contain missing or non-finite values")
        if (w < 0).any():
            raise SurveyError("Survey weights must not be negative")
        if not (w > 0).any():
            raise SurveyError("At least one survey weight must be positive")
        if frame[[psu, stratum]].isna().any().any():
            raise SurveyError("PSU and stratum must not be missing")
        keys = list(zip(frame[stratum].tolist(), frame[psu].tolist(), strict=True))
        cluster_ids = {key: i for i, key in enumerate(sorted(set(keys)))}
        strata_ids = {s: i for i, s in enumerate(sorted({key[0] for key in keys}))}
        cluster = np.array([cluster_ids[key] for key in keys], dtype=int)
        cluster_stratum = np.zeros(len(cluster_ids), dtype=int)
        for (s, _), i in cluster_ids.items():
            cluster_stratum[i] = strata_ids[s]
        return cls(w, cluster, cluster_stratum, lonely)

    def with_weights(self, weight: np.ndarray) -> Design:
        return Design(np.asarray(weight, dtype=float), self.cluster, self.cluster_stratum, self.lonely)


@dataclass(frozen=True)
class Estimate:
    estimate: float
    se: float
    df: int
    n: int
    weighted_total: float
    n_eff_kish: float
    n_eff_design: float
    ci_wald: tuple[float, float]
    ci_logit: tuple[float, float]


@dataclass(frozen=True)
class Contrast:
    difference: float
    se: float
    df: int
    t: float
    p_value: float
    ci: tuple[float, float]
    ratio: float
    ratio_ci: tuple[float, float]


def _domain(design: Design, domain: np.ndarray | None) -> np.ndarray:
    if domain is None:
        return np.ones(design.n)
    d = np.asarray(domain, dtype=float)
    if d.shape != (design.n,):
        raise SurveyError("Domain indicator must have one entry per respondent")
    return d


def linearized_scores(
    design: Design, y: np.ndarray, domain: np.ndarray | None = None
) -> tuple[float, np.ndarray, float]:
    """Return (weighted mean, linearized scores, weighted domain total)."""
    d = _domain(design, domain)
    yy = np.asarray(y, dtype=float)
    active = (d > 0) & (design.weight > 0)
    if np.isnan(yy[active]).any():
        raise SurveyError("Outcome has missing values inside the domain")
    yy = np.where(active, yy, 0.0)
    wd = design.weight * d
    total = float(wd.sum())
    if total <= 0:
        raise SurveyError("Domain is empty: no respondent with positive weight")
    p = float((wd * yy).sum() / total)
    return p, wd * (yy - p) / total * active, total


def variance(design: Design, scores: np.ndarray) -> float:
    """Stratified with-replacement PSU variance of a linearized total."""
    totals = np.bincount(design.cluster, weights=scores, minlength=design.n_clusters)
    n_strata = int(design.cluster_stratum.max()) + 1
    n_h = np.bincount(design.cluster_stratum, minlength=n_strata).astype(float)
    mean_h = np.bincount(design.cluster_stratum, weights=totals, minlength=n_strata) / np.maximum(n_h, 1)
    sq = np.bincount(
        design.cluster_stratum,
        weights=(totals - mean_h[design.cluster_stratum]) ** 2,
        minlength=n_strata,
    )
    multi = n_h > 1
    var = float((n_h[multi] / (n_h[multi] - 1) * sq[multi]).sum())
    lonely = ~multi
    if lonely.any():
        if design.lonely == "fail":
            raise SurveyError(
                f"{int(lonely.sum())} stratum(s) have a single PSU; set lonely to 'centered' or 'remove'"
            )
        if design.lonely == "centered":
            grand = float(totals.mean())
            for h in np.flatnonzero(lonely):
                (i,) = np.flatnonzero(design.cluster_stratum == h)
                var += (totals[i] - grand) ** 2
    return var


def degf(design: Design, domain: np.ndarray | None = None) -> int:
    """Degrees of freedom as in ``survey::degf``: PSUs minus strata with positive weight."""
    d = _domain(design, domain)
    live = (design.weight * d) > 0
    clusters = np.unique(design.cluster[live])
    strata = np.unique(design.cluster_stratum[clusters])
    return int(clusters.size - strata.size)


def kish_effective_n(weights: np.ndarray) -> float:
    w = np.asarray(weights, dtype=float)
    w = w[w > 0]
    return float(w.sum() ** 2 / (w**2).sum()) if w.size else 0.0


def _t_crit(df: int, alpha: float = 0.05) -> float:
    return float(stats.t.ppf(1 - alpha / 2, max(df, 1)))


def estimate_mean(
    design: Design,
    y: Sequence[float] | np.ndarray,
    domain: np.ndarray | None = None,
    bounded: bool = True,
) -> Estimate:
    """Weighted mean (a proportion when ``y`` is 0/1) with design-based uncertainty."""
    p, scores, total = linearized_scores(design, np.asarray(y, dtype=float), domain)
    se = float(np.sqrt(variance(design, scores)))
    df = degf(design, domain)
    crit = _t_crit(df)
    wald = (p - crit * se, p + crit * se)
    if bounded:
        wald = (max(0.0, wald[0]), min(1.0, wald[1]))
    logit = (float("nan"), float("nan"))
    if bounded and 0.0 < p < 1.0 and se > 0:
        centre = np.log(p / (1 - p))
        half = crit * se / (p * (1 - p))
        logit = (float(1 / (1 + np.exp(-(centre - half)))), float(1 / (1 + np.exp(-(centre + half)))))
    d = _domain(design, domain)
    active = (d > 0) & (design.weight > 0)
    design_neff = p * (1 - p) / se**2 if bounded and se > 0 and 0 < p < 1 else float("nan")
    return Estimate(
        estimate=p,
        se=se,
        df=df,
        n=int(active.sum()),
        weighted_total=total,
        n_eff_kish=kish_effective_n(design.weight * d),
        n_eff_design=float(design_neff),
        ci_wald=(float(wald[0]), float(wald[1])),
        ci_logit=logit,
    )


estimate_proportion = estimate_mean


def contrast(
    design: Design,
    y: Sequence[float] | np.ndarray,
    domain_a: np.ndarray,
    domain_b: np.ndarray,
) -> Contrast:
    """Difference and ratio of two disjoint-domain proportions, with their covariance.

    The two domains share PSUs, so their estimates are correlated; adding their variances as if
    independent is not correct. The contrast is linearized jointly.
    """
    yy = np.asarray(y, dtype=float)
    p_a, u_a, _ = linearized_scores(design, yy, domain_a)
    p_b, u_b, _ = linearized_scores(design, yy, domain_b)
    union = ((np.asarray(domain_a) > 0) | (np.asarray(domain_b) > 0)).astype(float)
    df = degf(design, union)
    crit = _t_crit(df)
    diff = p_a - p_b
    se = float(np.sqrt(variance(design, u_a - u_b)))
    t = diff / se if se > 0 else float("nan")
    p_value = float(2 * stats.t.sf(abs(t), max(df, 1))) if se > 0 else float("nan")
    if p_b > 0 and p_a > 0:
        ratio = p_a / p_b
        se_ratio = float(np.sqrt(variance(design, (u_a - ratio * u_b) / p_b)))
        half = crit * se_ratio / ratio
        ratio_ci = (float(ratio * np.exp(-half)), float(ratio * np.exp(half)))
    else:
        ratio, ratio_ci = float("nan"), (float("nan"), float("nan"))
    return Contrast(diff, se, df, float(t), p_value, (diff - crit * se, diff + crit * se), ratio, ratio_ci)


def standardized_proportion(
    design: Design,
    y: Sequence[float] | np.ndarray,
    domain: np.ndarray,
    bands: Sequence[np.ndarray],
    standard: Sequence[float],
) -> Estimate:
    """Directly standardized proportion: sum_k s_k * p_k over mutually exclusive bands."""
    weights = np.asarray(standard, dtype=float)
    if len(bands) != weights.size or not np.isclose(weights.sum(), 1.0):
        raise SurveyError("Standard weights must sum to 1 and match the bands")
    yy = np.asarray(y, dtype=float)
    estimate, scores = 0.0, np.zeros(design.n)
    for band, s in zip(bands, weights, strict=True):
        p_k, u_k, _ = linearized_scores(design, yy, np.asarray(domain) * np.asarray(band))
        estimate += s * p_k
        scores += s * u_k
    se = float(np.sqrt(variance(design, scores)))
    df = degf(design, domain)
    crit = _t_crit(df)
    return Estimate(
        estimate=float(estimate),
        se=se,
        df=df,
        n=int(((np.asarray(domain) > 0) & (design.weight > 0)).sum()),
        weighted_total=float((design.weight * np.asarray(domain)).sum()),
        n_eff_kish=kish_effective_n(design.weight * np.asarray(domain)),
        n_eff_design=float("nan"),
        ci_wald=(max(0.0, estimate - crit * se), min(1.0, estimate + crit * se)),
        ci_logit=(float("nan"), float("nan")),
    )


def holm_adjust(p_values: Sequence[float]) -> list[float]:
    """Holm-Bonferroni step-down adjusted p-values (order preserved)."""
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    m = p.size
    adjusted = np.empty(m)
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, (m - rank) * p[index])
        adjusted[index] = min(1.0, running)
    return adjusted.tolist()


def rao_wu_multipliers(design: Design, rng: np.random.Generator, replicates: int) -> np.ndarray:
    """Cluster multipliers for the Rao-Wu rescaled bootstrap, shape (replicates, n_clusters).

    Each stratum with ``n_h`` PSUs draws ``n_h - 1`` PSUs with replacement; a PSU drawn ``r``
    times gets multiplier ``n_h / (n_h - 1) * r``. A single-PSU stratum keeps multiplier 1.
    """
    n_strata = int(design.cluster_stratum.max()) + 1
    out = np.ones((replicates, design.n_clusters))
    for h in range(n_strata):
        members = np.flatnonzero(design.cluster_stratum == h)
        n_h = members.size
        if n_h < 2:
            continue
        counts = rng.multinomial(n_h - 1, np.full(n_h, 1.0 / n_h), size=replicates)
        out[:, members] = counts * (n_h / (n_h - 1))
    return out


def row_multipliers(design: Design, cluster_multipliers: np.ndarray) -> np.ndarray:
    """Expand cluster multipliers to respondents, shape (replicates, n)."""
    return cluster_multipliers[:, design.cluster]
