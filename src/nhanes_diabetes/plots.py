"""Figures: dot-and-interval charts on honest axes, in a colour-blind-safe palette."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from nhanes_diabetes.config import Config  # noqa: E402

BLUE, ORANGE, INK, GRID = "#0072B2", "#E69F00", "#222222", "#D9D9D9"  # Okabe-Ito
PRIMARY_MODEL, RACE_MODEL = "demographic_logistic", "demographic_race_logistic"
ALL = "All groups"

ALT_TEXT = {
    "undiagnosis_by_group": (
        "Dot-and-interval chart of the survey-weighted share of people meeting the HbA1c criterion "
        "who were never told they have diabetes, for each race and ethnicity group, with 95% intervals "
        "and the overall estimate as a dashed reference line. Groups with fewer than 30 respondents or "
        "an effective sample under 30 are hollow and labelled as small samples."),
    "sensitivity_by_group": (
        "Dot-and-interval chart of sensitivity against the HbA1c criterion for the race-excluded model "
        "trained on the diagnosed label and on the HbA1c label, by group, on a 0 to 100 percent axis. "
        "Intervals are wide and overlap in every group."),
    "specificity_cost": (
        "Two panels of dot-and-interval charts of specificity cost by group, defined as specificity of "
        "the diagnosed-label model minus specificity of the HbA1c-label model, in percentage points. "
        "With race excluded the cost is near zero everywhere; with race included it is positive for "
        "non-White groups and slightly negative for Non-Hispanic White respondents."),
    "calibration": (
        "Calibration curves for the diagnosed-label and HbA1c-label race-excluded models, plotting mean "
        "predicted risk against the weighted observed rate in ten equal-population bins, with the "
        "diagonal as perfect calibration."),
}


def _style(ax: plt.Axes) -> None:
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)


def _save(fig: plt.Figure, config: Config, name: str) -> None:
    config.figures_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(config.figures_dir / f"{name}.{ext}", dpi=200, bbox_inches="tight",
                    metadata={"Date": None} if ext == "svg" else None)
    plt.close(fig)


def _title(fig: plt.Figure, title: str, subtitle: str) -> None:
    fig.text(0.01, 0.995, title, fontsize=13, fontweight="bold", color=INK, va="top", ha="left")
    fig.text(0.01, 0.94, subtitle, fontsize=9.5, color="#555555", va="top", ha="left")


def figure_undiagnosis(config: Config, tables: dict[str, pd.DataFrame]) -> None:
    est = tables["undiagnosis_estimates"]
    overall = float(est.loc[est["group"] == ALL, "estimate"].iloc[0])
    groups = est[est["group"] != ALL].set_index("group").loc[config.groups].reset_index()
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    y = np.arange(len(groups))[::-1]
    for yi, row in zip(y, groups.itertuples(), strict=True):
        small = bool(row.small_n_warning)
        ax.hlines(yi, row.ci_low_logit * 100, row.ci_high_logit * 100, color=BLUE, linewidth=2.2)
        ax.plot(row.estimate * 100, yi, "o", markersize=8, color=BLUE,
                markerfacecolor="white" if small else BLUE, markeredgewidth=1.8)
        note = f"n={row.respondents}, effective n={row.effective_n_kish:.0f}" + ("  small sample" if small else "")
        ax.text(73, yi, note, va="center", fontsize=8.5, color=INK, clip_on=False)
    ax.axvline(overall * 100, color=INK, linestyle="--", linewidth=1,
               label=f"All groups {overall * 100:.1f}%")
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)
    ax.set_yticks(y, groups["group"])
    ax.set_xlim(0, 70)
    ax.set_xticks(range(0, 71, 10))
    ax.set_xlabel("Percent never told they have diabetes (95% interval)")
    _style(ax)
    _title(fig, "Undiagnosed diabetes among people meeting the HbA1c criterion",
           "NHANES 2017-2018, survey-weighted; HbA1c 6.5% or higher; hollow markers are small samples")
    fig.subplots_adjust(top=0.84, right=0.66)
    _save(fig, config, "undiagnosis_by_group")


def figure_sensitivity(config: Config, tables: dict[str, pd.DataFrame]) -> None:
    sub = tables["subgroup_metrics"]
    sub = sub[sub["model"] == PRIMARY_MODEL]
    groups = config.groups + [ALL]
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    offsets = {"diagnosed": 0.16, "hba1c_pos": -0.16}
    style = {"diagnosed": (BLUE, "o", "Trained on diagnosed label"), "hba1c_pos": (ORANGE, "s", "Trained on HbA1c label")}
    y = np.arange(len(groups))[::-1]
    for label, (color, marker, text) in style.items():
        rows = sub[sub["label"] == label].set_index("group").loc[groups]
        for yi, (_, r) in zip(y, rows.iterrows(), strict=True):
            small = bool(r["small_n_warning"])
            ax.hlines(yi + offsets[label], r["sensitivity_ci_low"] * 100, r["sensitivity_ci_high"] * 100,
                      color=color, linewidth=2)
            ax.plot(r["sensitivity"] * 100, yi + offsets[label], marker, color=color, markersize=7,
                    markerfacecolor="white" if small else color, markeredgewidth=1.6)
        ax.plot([], [], marker, color=color, label=text)
    counts = sub[sub["label"] == "diagnosed"].set_index("group").loc[groups]
    for yi, (_, r) in zip(y, counts.iterrows(), strict=True):
        ax.text(103, yi, f"{int(r['positives'])} positives" + ("  small sample" if r["small_n_warning"] else ""),
                va="center", fontsize=8.5)
    ax.set_yticks(y, groups)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Sensitivity against the HbA1c criterion, percent (95% interval)")
    ax.legend(loc="lower left", frameon=False, fontsize=8.5, bbox_to_anchor=(0, -0.32), ncol=2)
    _style(ax)
    _title(fig, "Sensitivity is similar under both labels when race is excluded",
           "Age and sex only; repeated grouped cross-validation, nested thresholds; hollow markers are small samples")
    fig.subplots_adjust(top=0.85, right=0.72)
    _save(fig, config, "sensitivity_by_group")


def figure_specificity_cost(config: Config, tables: dict[str, pd.DataFrame]) -> None:
    cost = tables["specificity_cost"]
    groups = config.groups + [ALL]
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.4), sharey=True)
    xlim = (-15, 15)
    for ax, model, title in ((axes[0], PRIMARY_MODEL, "Race excluded (primary)"),
                             (axes[1], RACE_MODEL, "Race included (sensitivity)")):
        rows = cost[cost["model"] == model].set_index("group").loc[groups]
        y = np.arange(len(groups))[::-1]
        for yi, (_, r) in zip(y, rows.iterrows(), strict=True):
            ax.hlines(yi, r["ci_low"] * 100, r["ci_high"] * 100, color=BLUE, linewidth=2.2)
            ax.plot(r["cost"] * 100, yi, "o", color=BLUE, markersize=7.5)
        ax.axvline(0, color=INK, linewidth=1)
        ax.set_xlim(*xlim)
        ax.set_xlabel("Percentage points (95% interval)")
        ax.set_title(title, fontsize=10.5, loc="left")
        _style(ax)
    axes[0].set_yticks(np.arange(len(groups))[::-1], groups)
    _title(fig, "Specificity cost of training on the HbA1c label instead of the diagnosed label",
           "Cost = specificity of the diagnosed-label model minus the HbA1c-label model. Positive means more false positives")
    fig.subplots_adjust(top=0.8, wspace=0.08)
    _save(fig, config, "specificity_cost")


def figure_calibration(config: Config, tables: dict[str, pd.DataFrame]) -> None:
    cal = tables["calibration"]
    cal = cal[(cal["model"] == PRIMARY_MODEL) & (cal["group"] == ALL)]
    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    for label, color, marker, text in (("diagnosed", BLUE, "o", "Diagnosed-label model"),
                                       ("hba1c_pos", ORANGE, "s", "HbA1c-label model")):
        rows = cal[cal["label"] == label]
        ax.plot(rows["mean_predicted"], rows["observed_rate"], marker + "-", color=color, label=text, markersize=6)
    top = float(max(cal["mean_predicted"].max(), cal["observed_rate"].max()) * 1.1)
    ax.plot([0, top], [0, top], color=INK, linestyle="--", linewidth=1)
    ax.set_xlim(0, top)
    ax.set_ylim(0, top)
    ax.set_xlabel("Mean predicted risk")
    ax.set_ylabel("Weighted observed rate")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    _title(fig, "Calibration, race-excluded models", "Ten equal-population bins; each model against its own label")
    fig.subplots_adjust(top=0.86)
    _save(fig, config, "calibration")


def make_figures(config: Config) -> None:
    tables = {p.stem: pd.read_csv(p) for p in config.tables_dir.glob("*.csv")}
    figure_undiagnosis(config, tables)
    figure_sensitivity(config, tables)
    figure_specificity_cost(config, tables)
    figure_calibration(config, tables)
    lines = ["# Figure alt text", ""]
    lines += [f"- `{name}`: {text}" for name, text in ALT_TEXT.items()]
    (config.figures_dir / "ALT_TEXT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
