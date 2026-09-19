"""Weighted classification metrics, vectorized over bootstrap replicate weights."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score


def youden_threshold(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> float:
    """Threshold maximizing weighted sensitivity + specificity - 1 (predict positive if p >= t)."""
    order = np.argsort(-p, kind="stable")
    ps, ys, ws = p[order], y[order], w[order]
    tp = np.cumsum(ws * ys)
    fp = np.cumsum(ws * (1 - ys))
    positives, negatives = tp[-1], fp[-1]
    if positives <= 0 or negatives <= 0:
        return 0.5
    last_of_tie = np.r_[ps[1:] != ps[:-1], True]
    j = tp / positives - fp / negatives
    j = np.where(last_of_tie, j, -np.inf)
    return float(ps[int(np.argmax(j))])


def confusion_sums(
    y: np.ndarray, pred: np.ndarray, weights: np.ndarray, mask: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Weighted TP, FN, TN, FP for one or many weight vectors.

    ``weights`` is (n,) or (B, n); the result has shape () or (B,).
    """
    m = np.ones_like(y, dtype=bool) if mask is None else mask
    yy, pp = y == 1, pred == 1
    cells = [m & yy & pp, m & yy & ~pp, m & ~yy & ~pp, m & ~yy & pp]
    return tuple(weights @ c.astype(float) for c in cells)


def rates(tp: np.ndarray, fn: np.ndarray, tn: np.ndarray, fp: np.ndarray) -> dict[str, np.ndarray]:
    def ratio(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(b > 0, a / np.where(b > 0, b, 1), np.nan)

    return {
        "sensitivity": ratio(tp, tp + fn),
        "specificity": ratio(tn, tn + fp),
        "ppv": ratio(tp, tp + fp),
        "npv": ratio(tn, tn + fn),
    }


def weighted_auc(y: np.ndarray, score: np.ndarray, w: np.ndarray) -> float:
    if w[y == 1].sum() <= 0 or w[y == 0].sum() <= 0:
        return float("nan")
    return float(roc_auc_score(y, score, sample_weight=w))


def weighted_brier(y: np.ndarray, p: np.ndarray, w: np.ndarray) -> float:
    total = w.sum()
    return float((w * (p - y) ** 2).sum() / total) if total > 0 else float("nan")


def calibration_bins(y: np.ndarray, p: np.ndarray, w: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    """Equal-population (weighted) bins of predicted risk versus the weighted observed rate."""
    order = np.argsort(p, kind="stable")
    ps, ys, ws = p[order], y[order], w[order]
    midpoint = (np.cumsum(ws) - ws / 2) / ws.sum()  # each respondent sits at its weight midpoint
    edges = np.minimum((midpoint * bins).astype(int), bins - 1)
    out = []
    for b in range(bins):
        sel = edges == b
        if not sel.any():
            continue
        wb = ws[sel]
        out.append(
            {
                "bin": b + 1,
                "n": int(sel.sum()),
                "mean_predicted": float((wb * ps[sel]).sum() / wb.sum()),
                "observed_rate": float((wb * ys[sel]).sum() / wb.sum()),
                "weighted_n": float(wb.sum()),
            }
        )
    return out
