# Data Dictionary

All files are NHANES 2017-2018 public-use files from
`https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/`. Raw files are downloaded by `nhanes-diabetes download`, recorded in [`data/data_manifest.json`](../data/data_manifest.json) with source URL, retrieval date, byte size and SHA-256, and are never committed.

Refused (7) and do-not-know (9) codes are treated as missing everywhere.

| Variable | File | Plain-English name | Coding and unit | Role | Missing codes | Source |
|---|---|---|---|---|---|---|
| `SEQN` | all | Respondent sequence number | integer, unique | Key | none | [DEMO_J](https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DEMO_J.htm) |
| `RIDAGEYR` | DEMO_J | Age at screening | years, 80 is top-coded | Input, standardization | none | DEMO_J |
| `RIAGENDR` | DEMO_J | Sex | 1 male, 2 female | Input | none | DEMO_J |
| `RIDRETH3` | DEMO_J | Race and Hispanic origin | 1 Mexican American, 2 Other Hispanic, 3 Non-Hispanic White, 4 Non-Hispanic Black, 6 Non-Hispanic Asian, 7 Other including multiracial | Grouping variable; model input only in the sensitivity model | none | DEMO_J |
| `WTMEC2YR` | DEMO_J | Exam sample weight | persons represented; positive for examined | Survey weight | 0 for not examined | DEMO_J |
| `SDMVSTRA` | DEMO_J | Masked variance stratum | 15 strata | Survey design | none | DEMO_J |
| `SDMVPSU` | DEMO_J | Masked variance PSU | 1 or 2 within stratum | Survey design | none | DEMO_J |
| `DIQ010` | DIQ_J | Doctor told you have diabetes | 1 yes, 2 no, 3 borderline | Label `diagnosed` (1 is yes, 2 is no); 3 excluded in the main analysis | 7 refused, 9 do not know, blank | [DIQ_J](https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DIQ_J.htm) |
| `LBXGH` | GHB_J | Glycohemoglobin (HbA1c) | percent | Label `hba1c_pos` when 6.5 or higher; never a model input | blank if not measured | [GHB_J](https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/GHB_J.htm) |
| `BMXBMI` | BMX_J | Body mass index | kg/m2 | Input (extended model) | blank | [BMX_J](https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/BMX_J.htm) |
| `MCQ300C` | MCQ_J | Close relative had diabetes | 1 yes, 2 no; asked of adults 20 and older | Input (extended model) | 7, 9, blank | [MCQ_J](https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/MCQ_J.htm) |
| `HIQ011` | HIQ_J | Covered by health insurance | 1 yes, 2 no | Input (extended model) | 7, 9 | [HIQ_J](https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/HIQ_J.htm) |
| `HUQ030` | HUQ_J | Has a place for routine care | 1 yes, 2 no place, 3 more than one place; 1 and 3 count as yes | Input (extended model) | 7, 9 | [HUQ_J](https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/HUQ_J.htm) |

## Derived variables

| Variable | Definition |
|---|---|
| `diagnosed` | 1 if `DIQ010` is 1, 0 if 2. Borderline (3) is excluded, or counted as 1 or 0 in the sensitivity analyses |
| `hba1c_pos` | 1 if `LBXGH` is at least 6.5 |
| undiagnosed | `hba1c_pos` is 1 and `diagnosed` is 0 |
| `female` | 1 if `RIAGENDR` is 2 |
| `insured`, `routine_care`, `family_history` | 1 for yes, 0 for no, missing otherwise |
