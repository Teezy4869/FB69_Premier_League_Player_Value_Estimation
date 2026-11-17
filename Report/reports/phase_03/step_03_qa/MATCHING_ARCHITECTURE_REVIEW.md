# Matching Architecture Review

Date: 2026-11-04. Results: `evidence/architecture_review.json`, computed on `matching_v2_1`.

**Conclusion:** the architecture is sound and the rankings are stable. The scoring is a heuristic and is not calibrated. No change to the match rule was needed, and `AUTO_HIGH_CONFIDENCE` stays off.

## 1. Coverage

| Check | Result |
|---|---|
| FotMob identities processed | 1,343 of 1,343 |
| Identities with no candidate | 0 |
| Mapped pairs found by candidate generation | 1,340 of 1,340 |
| Mapped pairs ranked first | 1,340 of 1,340 |

| Block | Mapped pairs found | Lost if this block alone were removed |
|---|---:|---:|
| `DOB_EXACT` | 1,337 | 0 |
| `ROSTER_NAME` | 1,324 | 0 |
| `BIRTH_YEAR_NAME` | 1,310 | 0 |
| `EXACT_NAME` | 1,302 | 0 |
| `GAME_SET` | 1,163 | 0 |
| `DOB_NEAR` | 0 (plus 1 in the review queue) | 0 |

Every mapped pair was found by at least 2 blocks. The blocks overlap heavily, so a single weakness can't silently lose a player.

**This measures recall only among pairs that were found.** A true match that no block found would not appear here.

## 2. Bias and blind spots

| Exposure | Size | Effect |
|---|---:|---|
| Mononyms have low name similarity | Lowest mapped: Kiko 50.0, Adrián 52.2, Quina 52.6 | Rescued by the token-subset rule and birth date |
| `GAME_SET` needs at least 3 shared games | 165 mapped players have under 3 FotMob games | Short-career players rely on name-based blocks |
| TM has no game rows for 32 player-seasons | 14 identities have none at all | Game and roster blocks can't help them |
| **Combined blind spot** | Different name **and** different birth date **and** few games | Could produce `UNMATCHED` or a wrong-only queue. None occurred, since all identities have candidates |

Name-based blocks do favor players with stable, ASCII-friendly names, but the birth date and game blocks offset this. No systematic loss was found in any group.

## 3. Reproducibility

Rerunning gave byte-identical crosswalks for v1 (from the original code) and v2_1. Candidate order uses score, then TM ID, so ties can't change between runs.

## 4. Scoring review

| Question | Finding |
|---|---|
| Is the score a probability? | **No.** It is a heuristic. The column was named `confidence_score`, which invited that reading, so it's now `ranking_score` |
| Is it calibrated? | No. Weights are judgment-based, and no labels exist to fit them |
| Can it create a mapping? | No. It only orders candidates |
| Double counting? | Partly: `name_similarity` and `name_subset` both read names (up to 40 of 100 points). Mean similarity is 99.6 when subset is true among mapped pairs, so subset adds little there. It's kept because it helps mononyms, and removing it changes no ranking |
| Missing evidence handled consistently? | Yes. No points are earned, and `ranking_score_available` drops accordingly. `name_subset` is always available because names are never missing |

**Ranking stability:** each weight was halved, multiplied by 1.5, and zeroed. The mapped pair stayed first for 1,340 of 1,340 in every scenario, except 1,339 when either name similarity or game Jaccard was zeroed. Exact weights barely matter here, because evidence tends to agree. That stability partly reflects what these mappings are, so it does not validate the weights.

## 5. Changes made

| Change | Why |
|---|---|
| `DOB_NEAR` no longer fires when day equals month | The swap produced the same date, so exact pairs were flagged near |
| Queue cap raised from 5 to 20 | Cap hid 1 candidate (Jota's sixth) |
| `confidence_score` renamed `ranking_score` | Avoids reading it as a probability |
| Added `AUTO_ADJUDICATED` status with adjudicator fields | Keeps automated decisions separate from human review |
| Run folders keep their own review files and hash all outputs | v1's review files could be overwritten, and its manifest hashed only 2 files |
| Stricter review ledger checks | Confirm and reject of one pair was silently treated as confirmed; an unknown identity gave an unclear error |

## 6. Not changed

- **`AUTO_EXACT` rule:** 1,299 mappings are identical to v1.
- **`AUTO_HIGH_CONFIDENCE`:** still off. Adding it would raise coverage without new evidence.
- **Nickname table:** not added. A table would turn human judgment into automatic matches, and would have to be validated first.
- **Thresholds:** not tuned to the results.
