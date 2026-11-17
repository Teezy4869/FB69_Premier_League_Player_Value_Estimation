# rs5 Step 3: Entity Resolution Revalidation

Crosswalk version: **`matching_v2_1_rs5`** (`data/research_rs5/entity_resolution/matching_v2_1_rs5__reviews_none/`). Builder: `src/research_scope/entity_resolution_rs5.py`. Manifest: `data/research_rs5/entity_resolution/crosswalk_rs5_manifest.json`.

## What was re-run, and on what evidence

| Component | Code | Evidence |
|---|---|---|
| Matching (exact rule, candidates, review queue) | `src.phase3.entity_resolution.run`, unchanged | FotMob rs5 tables; Transfermarkt games, appearances and club-seasons for seasons 2020-2024 only |
| Automated adjudications | historical 44 rows, filtered to the rs5 universe (38) | `run` refuses any adjudication whose candidate wasn't regenerated. None was refused |
| Independent identity validator | `step3_qa_validate.judge`, rule_v2, unchanged | Career (FotMob profile vs TM transfers), physical (height, foot), performance (in-scope seasons only) |

Not season-scoped, because they're player-level: TM player profiles, TM transfer history and FotMob profile career and physical data. The 2019/20 game-level evidence was removed from 400 in-scope players.

## Player-level identity (1,228 FotMob identities)

| Status | Players | Player-season rows | Basis |
|---|---:|---:|---|
| `AUTO_EXACT` | 1,190 | 2,663 | Unique exact name + exact birth date, no club contradiction |
| `AUTO_ADJUDICATED` | 36 | 82 | **Automated** evidence; not human review |
| `REVIEW_REQUIRED` | 2 | 2 | Kept unresolved |
| `MANUAL_CONFIRMED` | 0 | 0 | No human review exists |

**Mapping coverage:** 1,226 of 1,228 identities (99.84%); 2,745 of 2,747 player-season rows (99.93%).

## Comparison with the historical crosswalk `matching_v2_1`

| Item | Result |
|---|---:|
| Identities compared | 1,228 |
| **Status or Transfermarkt id changed** | **0** |
| Method label changed | 1 (Troy Deeney: `CLUB_CONFIRMED` → `NO_CLUB_EVIDENCE`) |
| Club map (FotMob team ↔ TM club) | identical, 27 clubs |
| Duplicate FotMob / canonical / TM ids | 0 / 0 / 0 |
| One-to-many (one player, several TM ids across seasons) | 0 |
| Many-to-one (one TM id, several players) | 0 |
| Conflicting automatic claims (TM id claimed twice) | 0 |

Deeney's in-scope rows are 2 Watford games in 2021/22, which Transfermarkt doesn't list (its known appearance shortfall, historical ISS-08). Only 2019/20 games had confirmed his club. Name and birth date still match uniquely, and nothing contradicts. He stays `AUTO_EXACT`, with the weaker method label recorded.

**Player-level identity vs player-season coverage.** A mapping is a fact about a person, so all 1,226 mappings stay valid. Coverage is a fact about rows: removing 2019/20 removed 515 rows and 115 players who appear only in that season. Among them were 1 unresolved identity (Jota) and 5 adjudicated identities. None of them is in the rs5 crosswalk.

## Identity validation labels on in-scope evidence

These labels are automated. They are not human validation.

| Group | CONFIRMED_MATCH | INCONCLUSIVE | CONFIRMED_NON_MATCH |
|---|---:|---:|---:|
| AUTO_EXACT (1,190) | 928 | 262 | **0** |
| AUTO_ADJUDICATED (36) | 29 | 7 | **0** |

Transitions vs the six-season labels for AUTO_EXACT: 922 stayed confirmed, 252 stayed inconclusive, **10 confirmed → inconclusive** (their performance agreement needed 2019/20), **6 inconclusive → confirmed**. Raheem Sterling and Riyad Mahrez are among the 6: their 2019/20 season stats disagreed between the sources, and without that season they agree.

**New random sample (300 of 1,190 AUTO_EXACT, seed `fb69-matching-v1`):** 234 confirmed, 66 inconclusive, 0 rejected. The 95% lower bound among decided pairs is **98.73%**, below the SOP's 99%. Counting inconclusive pairs as unverified, the lower bound on the verified share is 73.70%. 274 of the 300 also appear in the historical sample.

Because labels changed for 16 identities (32 rows), `identity_evidence_tier` changed. The target was therefore rebuilt under the revalidated crosswalk as `target_rs5_v1__matching_v2_1_rs5`. Compared with the Step 2 target, only identity columns differ: tier 32 rows, method 1 row, `matching_version` every row. Value, date, age, status and lineage differ on 0 rows.

## Two RULE-based adjudications not confirmed on in-scope evidence

| Player | In-scope rows | In-scope evidence | Historical basis |
|---|---:|---|---|
| Ahmed El Mohamady (111930 → 66333) | 1 | Exact birth date and nationality; 14 of 14 games shared; physical agrees; performance uninformative (1 season) | Rule confirmed with 2 seasons of performance |
| Wesley (656562 → 381362, "Wesley Moraes") | 2 | Exact birth date and nationality; 3 of 4 games shared; only plausible candidate; physical agrees | Rule confirmed with 2 seasons of performance |

Nothing in scope contradicts either one, so **both mappings are kept**, with `identity_rs5_validation_label = INCONCLUSIVE` on their rows. Whether to keep them is **research decision RD-02**. The 5 EXTERNAL adjudications rest on cited biographies, which aren't season evidence; the rule was already inconclusive for them historically.

## Conclusion

The in-scope identities are reassessed, and no decision changed. Unresolved identities stay unresolved. **No identity has been human-validated**: the SOP's 99% bound is still not reached (98.73%), and that keeps G3 conditional, as in Phase 3.
