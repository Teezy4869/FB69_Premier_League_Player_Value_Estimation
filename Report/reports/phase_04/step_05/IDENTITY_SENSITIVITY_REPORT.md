# Phase 4.5 Identity Sensitivity Report

Date: 2026-11-09. Code: `src/phase4/reliability.py` (with `bivariate.identity_sensitivity`, `multivariate.group_identity_sensitivity`). Notebook: 4.5.F. Evidence: `evidence/identity_overview.csv`, `identity_comparison.csv`, `identity_season_medians.csv`, `identity_feature_target_sensitivity.csv`, `identity_group_sensitivity.csv`. Figure: `fig45_07`. No identity label was invented; the 533 rows stay in the main dataset; exclusion is used for comparison only.

## 1. The subset (P4-B01)

Rows whose evidence tier is not `AUTO_EXACT_VALIDATED` or whose validation label is `INCONCLUSIVE`: 533 rows, 300 players.

| Evidence tier | Validation label | Rows |
|---|---|---:|
| AUTO_EXACT_NOT_INDEPENDENTLY_VALIDATED | INCONCLUSIVE | 449 |
| AUTO_ADJUDICATED_INDEPENDENT_RULE | CONFIRMED_MATCH / INCONCLUSIVE (RD-02) | 73 / 3 |
| AUTO_ADJUDICATED_EXTERNAL | INCONCLUSIVE | 6 |
| UNRESOLVED (ISS-04) | none | 2 |

## 2. Main vs subset vs main without subset

| | Main | P4-B01 subset | Without subset (sensitivity) |
|---|---:|---:|---:|
| Rows / players | 2,747 / 1,228 | 533 / 300 | 2,214 / 928 |
| Target missing | 1.8% | 5.3% | 1.0% |
| Target p25 / median / p75 (EUR m) | 5 / 13 / 25 | 2 / 8 / 22 | 6 / 15 / 28 |
| Median starts / 0-start share | 14 / 11.8% | 7 / 22.3% | 15 / 9.3% |
| Position mix GK/DEF/MID/FWD % | 7.5/34.0/30.5/27.9 | 9.6/35.1/29.1/26.3 | 7.0/33.8/30.9/28.3 |

The subset is not random: lower-valued, more fringe players, more missing targets. Excluding it would shift the population toward regular, higher-valued players.

## 3. Effect on results

| Result type | Effect without the subset |
|---|---|
| Target distribution | Season medians +EUR 0–2m; overall median 13m → 15m |
| Feature-target Spearman (53 features) | median change 0.016, max 0.092 (GK save %); 5 features > 0.05 (4 GK metrics, age); no sign change for \|rho\| > 0.05 |
| Group medians (position x role) | >= 10 starts: at most 3%; 0-start groups: EUR 2.0–2.5m → 3.0–4.25m |
| Population representation | fewer fringe players and goalkeepers |

## 4. Coverage is not precision

Mapping coverage is 99.84% of identities and 99.93% of rows, but no mapping is human-validated (ISS-01). The automated validator's 95% lower bound among decided pairs is 98.73% (SOP 99%), and 73.70% if inconclusive pairs count as unverified. Stable results under P4-B01 do not prove correct mappings.

## 5. Implications for modeling

Descriptive relationships are robust; target levels for fringe players and goalkeepers are the most sensitive. A P4-B01 sensitivity run remains required before final results, and the owner labelling of the validation sample (ISS-01) remains open.
