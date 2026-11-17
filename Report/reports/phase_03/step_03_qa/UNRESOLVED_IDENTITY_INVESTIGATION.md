# Unresolved Identity Investigation

Date: 2026-11-04. Full evidence per player: `evidence/unresolved_44_decisions.csv`, and the same data at `data/phase_03/review/automated_adjudications.csv`.

**All decisions are automated adjudication, not human review.** They appear as `AUTO_ADJUDICATED` or `REVIEW_REQUIRED`. Any reviewer decision overrides them, and all 44 identities stay in the review queue.

**Result:** 41 of 44 are confirmed (98 player-season rows). 3 remain `REVIEW_REQUIRED` (3 rows). None was rejected.

## 1. Decision rule

| Outcome | Requirement |
|---|---|
| `CONFIRMED_MATCH` (rule) | The independent validator confirmed it, and it is the only likely candidate |
| `CONFIRMED_MATCH` (external) | Validator inconclusive, but a biography ties the identities together, at least 2 games agree, and at least 1 independent family agrees |
| `REVIEW_REQUIRED` | Evidence supports the pair but is too thin for an automated decision |
| `INSUFFICIENT_EVIDENCE` | No evidence settles it (none occurred) |
| `CONFIRMED_NON_MATCH` | Independent evidence rejects it (none occurred) |

| Basis | Identities | Confidence |
|---|---:|---|
| Validator rule | 32 | HIGH 11, MEDIUM 21 |
| Validator rule plus external | 2 | MEDIUM |
| External | 7 | MEDIUM |
| Too thin, kept for review | 3 | LOW |

A first draft (`matching_v2`) confirmed all 44. I considered that unjustifiably complete, tightened the external requirement, and retained the draft unused. `matching_v2_1` is final.

## 2. Group A: 40 different-name-form cases

| Pattern | Count | Examples |
|---|---:|---|
| Formal vs short name | 16 | Joseph/Joe Gomez; Daniel/Dan Burn; Valentino/Tino Livramento |
| Mononym vs fuller name | 9 | Alisson Becker/Alisson; Kiko/Kiko Femenía; Quina/Domingos Quina |
| Middle name omitted | 6 | Pape Sarr/Pape Matar Sarr; Victor Nilsson Lindelöf/Victor Lindelöf |
| Different name in common use | 3 | Sávio/Savinho; Juan/Cucho Hernández; Mbwana/Ally Samatta |
| Surname part dropped | 2 | Jaden Philogene-Bidace/Jaden Philogene; Mads Bech/Mads Bech Sørensen |
| Transliteration | 2 | Yehor Yarmoliuk/Yegor Yarmolyuk; Jose Holebas/Jose Cholevas |
| Spacing in surname | 1 | Ahmed El Mohamady/Ahmed Elmohamady |
| Given name part dropped | 1 | Jens-Lys Cajuste/Jens Cajuste |

**No case looks like a different person.** All 40 have exact birth-date agreement. Identical game histories were treated as corroboration only.

**Outcomes:** 38 confirmed, 2 kept for review.

**External basis (6 confirmed):**

| FotMob | TM | What it adds | Note |
|---|---|---|---|
| Joshua King | Josh King | [Biography](https://en.wikipedia.org/wiki/Josh_King_(footballer,_born_2007)): Joshua David Steven King, Fulham, born 3 January 2007 | |
| Mbwana Samatta | Ally Samatta | [Biography](https://en.wikipedia.org/wiki/Mbwana_Samatta): full name Mbwana Ally Samatta, Aston Villa | |
| Joshua Onomah | Josh Onomah | [Biography](https://en.wikipedia.org/wiki/Josh_Onomah): Joshua Oghenetega Peter Onomah | |
| Rasmus Kristensen | Rasmus Nissen Kristensen | [Biography](https://lex.dk/Rasmus_Nissen_Kristensen): same name, born 11 July 1997 | Height disagrees |
| Quina | Domingos Quina | [Biography](https://en.wikipedia.org/wiki/Domingos_Quina): born 18 November 1999, Watford and Fulham | Height disagrees |
| Hákon Rafn Valdimarsson | Hákon Valdimarsson | [Brentford](https://brentfordfc.com/en/news/article/first-team-hakon-valdimarsson-signs-new-long-term-contract), biography | Height disagrees |

## 3. Group B: 4 different-birth-date cases

**Neither source can be declared correct.** External sources are split on each player, which is the key finding: these look like one person with a disputed date, not two people.

| Player | FotMob | TM | Sources agreeing with FotMob | Sources agreeing with TM | Decision |
|---|---|---|---|---|---|
| **Alfie Pond** | 2004-03-01 | 2004-02-17 | [ESPN](https://www.espn.com.au/football/player/bio/_/id/308554/alfie-pond), LiveSoccerTV, Soccerway, Exeter's Grecian Archive | [Wikipedia](https://en.wikipedia.org/wiki/Alfie_Pond), [11v11](https://www.11v11.com/players/alfie-pond-274082/) | Confirmed, MEDIUM; 2 families agree |
| **Omari Kellyman** | 2005-09-25 | 2005-09-15 | LiveSoccerTV, [AVFC History](https://www.avfchistory.co.uk/player/omari-kellyman) | [Premier League](https://premierleague.com/players/117753), [Wikipedia](https://en.wikipedia.org/wiki/Omari_Kellyman), ESPN | Confirmed, MEDIUM; 2 families agree |
| **Michael Olakigbe** | 2004-04-06 | 2004-04-25 | [Wikipedia](https://en.wikipedia.org/wiki/Michael_Olakigbe), [Wigan heritage](https://wiganathleticheritage.co.uk/player-profile/10266/michael-olakigbe) | Premier League (mislabeled URL, weak), SuperSport | Confirmed, MEDIUM; career agrees, 8 of 8 games |
| **Jimi Tauriainen** | 2004-03-09 | 2004-03-08 | [11v11](https://www.11v11.com/players/jimi-tauriainen-275359/), Sports Mole | [Premier League](https://premierleague.com/players/98290), Soccerway | **`REVIEW_REQUIRED`**; no family agrees, 1 game |

11v11 also lists 23 April 2004 for Olakigbe, a third date.

**Origin of the discrepancy:**
- **Cannot be resolved.** Premier League pages side with TM for Kellyman and Tauriainen (and weakly Olakigbe), which leans toward TM. That is suggestive, not proof, and no birth record was checked.
- **Effect on birth-date reliability:** the exact-date rule has a real weakness, because reputable sources disagree on dates. It sends these cases to review rather than mapping them wrongly, which is the safe failure direction.

## 4. The 3 unresolved identities

| Player | Rows | Why it stays open | What would settle it |
|---|---:|---|---|
| **Jimi Tauriainen** | 1 | No independent family agrees; only 1 game of history | A person's review, or an official record of the birth date |
| **Jota** (→ Jota Peleteiro) | 1 | Career data missing, other families uninformative. A [biography](https://www.fantasyfootballscout.co.uk/2019/06/11/jota-with-plenty-to-prove-as-an-fpl-asset-after-villa-move/) gives José Ignacio Peleteiro Ramallo, and all 10 games match, but no independent family agrees | A person's review |
| **Daniel Chesters** (→ Dan Chesters) | 1 | TM has no EPL game rows, so games can't corroborate; only career agrees. A [biography](https://en.wikipedia.org/wiki/Daniel_Chesters) gives Daniel Peter James Chesters | A person's review |

All 3 look likely to be the same person. They are held back because the automated standard was not met, not because of contrary evidence. Their rows stay in the population with a missing target and reason `NO_ELIGIBLE_IDENTITY_MATCH`.

## 5. Caveats

- External notes come from search-result summaries on 2026-11-04, not from reading each primary page. One Premier League result had a mislabeled URL.
- A biography found by name can't exclude every namesake, which is why external evidence alone is never sufficient.
- Height disagreement on confirmed external cases reflects known source noise, but a person should treat those with care.
