"""Build excel/nhanes_diabetes_quality_review.xlsx from outputs/tables.

Equivalent to ``python -m nhanes_diabetes excel``. Run from the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

from nhanes_diabetes.config import load_config
from nhanes_diabetes.workbook import build_workbook, verify_workbook


def main() -> int:
    config = load_config(root=Path(__file__).resolve().parents[1])
    path = build_workbook(config)
    problems = verify_workbook(config, path)
    if problems:
        print("Workbook does not match outputs/tables:\n  " + "\n  ".join(problems))
        return 1
    print(f"Wrote {path.relative_to(config.root)} and verified it against outputs/tables")
    return 0


if __name__ == "__main__":
    sys.exit(main())
