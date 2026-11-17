# Automatic Match Validation Report

Date: 2026-11-04. Population: 1,299 `AUTO_EXACT` mappings. Machine-readable results are in `evidence/`.

**This is automated adjudication, not human review. No label here came from a person.**

**Result:** no automatic mapping was shown to be wrong, but direct evidence does not establish 99% precision. Of a fixed random sample of 300, 228 were confirmed, 0 rejected and 72 stayed inconclusive.

## 1. Method

The rule uses evidence that the matching decision did not use. Name and birth date are never read as evidence. Game overlap is never counted as a family.

| Family | Comparison | Source |
|---|---|---|
| **Career** | Senior clubs outside the 27 EPL clubs, with start years within 1 year | FotMob raw `careerHistory`; TM `transfers` |
| **Physical** | Height within 1 cm and same preferred foot | FotMob raw `playerInformation`; TM `players` |
| **Performance** | Season goals, assists, cards (each within 1) and minutes (within 10%), with at least 3 events | FotMob curated metrics; TM `appearances` |

| Label | Rule, fixed before results were seen |
|---|---|
| `CONFIRMED_MATCH` | At least 2 families agree and none disagrees |
| `CONFIRMED_NON_MATCH` | At least 2 families disagree and none agrees |
| `INCONCLUSIVE` | Everything else; never counted as positive |

The 300 pairs are the seeded `AUTO_EXACT_RANDOM` stratum created in Step 3, chosen before this validator existed. Each is recorded in `evidence/auto_match_validation_sample_300.csv` with IDs, label, evidence, source, confidence, reasoning, method and independence flag.

### Why not web lookups for the 300?

A biography found by searching a name and birth date repeats the matching rule rather than testing it. It would add a third source but no independence, so the 72 inconclusive pairs were not cleared this way. External lookups were used only for the 44 unresolved identities, where they answer a different question: whether two name forms or two birth dates belong to one person.

### Remaining limits on independence

- The families are independent of the rule, not necessarily of each other or of the true identity.
- Both providers may share upstream data, so agreement could partly reflect a common source.
- Height and foot are present-day values, and performance comes from the same matches as game overlap, though it uses different fields.

## 2. Validator correction

The first run labeled Zain Silcott-Duberry `CONFIRMED_NON_MATCH`. Investigation showed a **validator defect**: TM abbreviates club names, and `sheff wed`, `qpr`, `west brom` and `olympiacos` did not match their full forms. ESPN's listed height of 183 cm also agrees with FotMob, making TM's 177 cm the outlier. The mapping was not wrong.

Club comparison now handles abbreviations and spelling (`rule_v2`). The label rule and all thresholds are unchanged. Both versions are retained:

| | `rule_v1` | `rule_v2` (final) |
|---|---:|---:|
| Sample: confirmed / inconclusive / non-match | 227 / 73 / 0 | 228 / 72 / 0 |
| All 1,299: confirmed / inconclusive / non-match | 976 / 322 / 1 | 980 / 319 / 0 |

## 3. Results

| Family (sample of 300) | Agree | Uninformative | Disagree | Missing |
|---|---:|---:|---:|---:|
| Career | 232 | 20 | 0 | 48 |
| Physical | 241 | 44 | 13 | 2 |
| Performance | 158 | 137 | 2 | 3 |

## 4. Can the validator say no? Negative controls

The same rule was applied to pairs of **different** mapped players. A validator that confirms anything would be worthless.

| Control (1,299 pairs each) | False confirmations | 95% upper bound | Labeled non-match |
|---|---:|---:|---:|
| Random other player | 0 | 0.23% | 70.1% |
| Random teammate | 0 | 0.23% | 81.1% |
| Teammate with the most similar height and foot | 3 | 0.60% | 22.6% |

These controls assume two different mapped players are different people. That rests on the mappings being checked, but this is a safe assumption for a control because a few wrong mappings would barely change these rates.

## 5. Statistics

| Estimate | Value | What it assumes |
|---|---:|---|
| Confirmed share of the 300 | 76.0% | Nothing; inconclusive counts as unverified, not wrong |
| 95% lower bound on verified share | 71.6% | Random sample; exact binomial |
| Precision among the 228 decided | 100% | Inconclusive pairs resemble decided ones |
| **95% lower bound among decided** | **98.70%** | As above; exact one-sided Clopper-Pearson |
| Wrong pairs consistent with sample, if decided pairs are random | At most 15 of 1,299 | Finite-population exact hypergeometric |

**On "300 clean labels prove 99%":** the exact binomial bound for 300 of 300 is 99.006%. That only applies if all 300 are decided, are random, and have perfect labels. Here 228 are decided, which gives 98.70% and **misses the 99% target**.

**Sensitivity bound across all 1,299 (model-based):** 0 non-matches were found. If a wrong mapping would be flagged at a control's rate, then at 95% confidence:

| If a wrong mapping behaves like | Flag rate | Maximum wrong pairs | Implied minimum precision |
|---|---:|---:|---:|
| Random teammate | 81.1% | 1 | 99.92% |
| Random other player | 70.1% | 2 | 99.85% |
| Most similar body teammate | 22.6% | 11 | 99.15% |

This is encouraging but rests on an assumption, because a namesake with the same birth date is not exactly any of these. It is supporting evidence only and does not replace a direct estimate.

## 6. Nationality disagreements

None of the 9 suggests an identity mismatch. External notes come from search-result summaries.

| Player | FotMob | TM | Finding | Category | Validator |
|---|---|---|---|---|---:|
| Myles Peart-Harris | England | Jamaica | Born London; listed with both nationalities | Legitimate source difference | Confirmed |
| Adrian Mariappa | England | Jamaica | Born in London; Jamaica international 2012–2023 | Legitimate source difference | Inconclusive |
| Sébastien Haller | France | Côte d'Ivoire | France youth player, switched to Ivory Coast | Historical change | Confirmed |
| Malang Sarr | Senegal | France | Born in Nice, France youth, chose Senegal | Historical change | Confirmed |
| Andre Brooks | Jamaica | England | English-born; Jamaica debut March 2026 | Historical change | Confirmed |
| Keinan Davis | Jamaica | England | England youth; Jamaican passport still pending in October 2026 | Historical change in progress | Inconclusive |
| Cameron Archer | Jamaica | England | No external evidence found; TM birthplace Walsall | Unresolved explanation | Inconclusive |
| Willy Kambwala | DR Congo | France | No external evidence found; TM birthplace Kinshasa | Unresolved explanation | Confirmed |
| Ivan Cavaleiro | Portugal | Angola | No external evidence found; TM birthplace Portugal | Unresolved explanation | Confirmed |

The 3 "unresolved" entries concern why the nationality differs. Identity evidence for each is separate.

## 7. Other audit findings

| Check | Result |
|---|---|
| Birth dates re-derived from raw FotMob JSON and the original TM CSV | 0 mismatches across 1,299; all FotMob times at midnight UTC, so no time-zone shift |
| Raw vs normalized FotMob birth dates | 0 differences |
| One TM ID mapped from two FotMob IDs (a split identity) | 0 |
| Rival with higher game overlap than the mapped pair | 0 |
| Same-name, same-birth-date TM duplicates among mapped players | None; the one TM duplicate pair is unrelated to this population |
| Position disagreements | 97 (7.5%); TM's value is present-day, so this is weak evidence |
| Club contradictions | 0 |

**Source-quality findings for later phases:**

- **Height is noisy.** 71 of 1,278 mapped pairs (5.6%) differ by 5 cm or more, for example Koulibaly at 195 vs 186 cm. This makes confirmation harder rather than easier. Height should be used cautiously in any later analysis.
- **Assists differ between sources** in a few cases, such as Van Dijk 2021/22 (1 vs 4) and Evanilson 2024/25 (1 vs 5), while minutes match. It looks like a definitional difference. 9 pairs have a `PERFORMANCE DISAGREE`, and none is an identity concern on current evidence.

## 8. Limitations

- No human label exists.
- 72 of 300 (24%) sampled pairs are inconclusive, mostly young or fringe players with little career history and few events.
- Non-human evidence can't rule out a namesake with the same birth date who also has similar career data, although that's very unlikely.
- What would settle this: a person labeling the sampled pairs, especially the 72 inconclusive ones. The file is ready at `data/phase_03/review/validation_sample_for_labeling.csv`.
