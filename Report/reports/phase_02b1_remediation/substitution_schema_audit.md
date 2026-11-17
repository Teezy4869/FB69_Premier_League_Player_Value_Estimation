# Phase 2B.1-R Step 07: Substitution Schema Audit Across Six EPL Seasons

**Document:** `substitution_schema_audit.md`  
**Phase:** Phase 2B.1-R (Post-Collection Remediation) — Step 07  
**Scope:** English Premier League (2019/20–2024/25), 2,280 Completed Matches + 1 Quarantined Abandoned Match  
**Status:** **AUDITED & VERIFIED**

---

## 1. Executive Summary & Problem Context

In earlier collection phases (Phase 2B.0 and Phase 2B.1), **16,314 player-match records** were marked with `participation_status = 'UNKNOWN'` and `validation_status = 'UNRESOLVED'`. Consequently, **586 Player–Season records** lacked definitive appearance evidence, leaving their participation classification as `UNVERIFIED`.

The primary question addressed in this audit is:
> *Can we determine whether currently UNKNOWN substitutes actually entered their historical matches by analyzing existing FotMob raw match details, lineup arrays, match event feeds, and match performance statistics without guessing or data fabrication?*

This audit rigorously inspects the underlying FotMob API JSON schemas across all six seasons to identify the exact technical mechanism that caused the 16,314 unknown classifications.

---

## 2. Technical Root Cause of Historical `UNKNOWN` Status

In the legacy collection pipeline (`src/collection/population_execution02.py`, lines 54–64), substitute participation was parsed using the following logic:

```python
perf = member.get("performance") or {}
events = perf.get("substitutionEvents")
event_types = {e.get("type") for e in events if isinstance(e, dict)} if isinstance(events, list) else set()
if role == "STARTER":
    status = "APPEARED"
elif "subIn" in event_types:
    status = "APPEARED"
elif not isinstance(events, list) or "subOut" in event_types:
    status = "UNKNOWN"
else:
    status = "UNUSED_SUBSTITUTE"
```

### The API Evolution Trap:
1. **In Season 2019/20:** For substitutes who remained on the bench throughout the match, FotMob explicitly populated `performance.substitutionEvents = []` (an empty list). Consequently, `not isinstance(events, list)` evaluated to `False`, and the player was classified as `UNUSED_SUBSTITUTE` (3,374 records in 2019/20).
2. **From Season 2020/21 Onwards:** FotMob updated its backend serialization. For unused bench substitutes who recorded zero match events, FotMob stopped emitting `substitutionEvents: []` and instead returned `performance: {}` (an empty dictionary) or omitted `substitutionEvents` altogether.
3. **The Resulting Fallacy:** Because `events = perf.get("substitutionEvents")` returned `None`, the legacy condition `not isinstance(events, list)` evaluated to `True`, automatically branding every unplayed substitute as `UNKNOWN`!

---

## 3. Comparative Raw Schema Variants Across Seasons

A comprehensive scan of all 2,280 completed match captures reveals three primary schema variants:

### Variant 1: Early Historical Schema (Season 2019/20)
- **Capture Sample:** `data/phase_02b1/raw/2019_2020/matchDetails/cap_661dfdbefe98427b9819d4cd29585d92/response.json` (Match ID `3055856`)
- **Starter Object (`content.lineup.[home/away]Team.starters`):**
  - Contains keys: `['id', 'optaId', 'name', 'positionId', 'usualPlayingPositionId', 'shirtNumber', 'isCaptain', 'horizontalLayout', 'verticalLayout', 'performance', 'firstName', 'lastName', 'rankings']`
  - When subbed off: `performance.substitutionEvents = [{'time': 68, 'type': 'subOut', 'reason': 'tactical'}]`
- **Substituted-On Object (`content.lineup.[home/away]Team.subs`):**
  - Contains keys: `['id', 'name', 'shirtNumber', 'performance', ...]`
  - Explicit entry: `performance.substitutionEvents = [{'time': 68, 'type': 'subIn', 'reason': 'tactical'}]`
- **Unused Substitute Object:**
  - `performance = {'events': [], 'substitutionEvents': [], 'playerOfTheMatch': False}`
  - Presence of explicit empty list allowed the legacy parser to recognize unused bench status.

### Variant 2: Mid-Historical Schema (Seasons 2020/21 – 2021/22)
- **Capture Sample:** `data/phase_02b1/raw/2020_2021/matchDetails/cap_013fa58eb7804528a2ea726a78ae1b75/response.json` (Match ID `3411606`)
- **Substituted-On Object:**
  - `performance = {'rating': 7.1, 'events': [{'type': 'goal'}], 'substitutionEvents': [{'time': 70, 'type': 'subIn', 'reason': 'tactical'}]}`
- **Unused Substitute Object:**
  - `performance = {}` (empty dictionary)
  - Key `substitutionEvents` is absent.

### Variant 3: Modern Schema (Seasons 2022/23 – 2024/25)
- **Capture Sample:** `data/phase_02b1/raw/2024_2025/matchDetails/cap_02660c2e0fce4d22b2f74da27eadd979/response.json` (Match ID `4506350`)
- **Rules Context:** Premier League adopted permanent 5-substitute rule with up to 9 bench players (total squad of 20 players per team).
- **Additional Metadata:** Added `marketValue`, `nationalTeamId`, `rankings`.
- **Substituted-On Object:**
  - Contains `performance.substitutionEvents = [{'time': 46, 'type': 'subIn'}]`.
- **Unused Substitute Object:**
  - `performance = {}`.
  - Zero entries in `content.playerStats[pid].stats`.

---

## 4. Multi-Source Evidence Triangulation

To guarantee that absence of a `subIn` event in `lineup.subs` is genuine negative evidence (and not a missing data artifact), the Step 07 parser cross-examines four distinct data structures within each `matchDetails` capture:

```
+-----------------------------------------------------------------------------------+
|                           FOTMOB MATCH DETAILS CAPTURE                            |
+-----------------------------------------------------------------------------------+
        |                                   |                                |
        v                                   v                                v
1. LINEUP ARRAYS                 2. MATCHFACTS EVENTS             3. PLAYERSTATS
- content.lineup.homeTeam        - content.matchFacts.events.     - content.playerStats
  starters (11 players)            events array                     dictionary keyed
- content.lineup.awayTeam        - type: "Substitution"             by player_id
  starters (11 players)          - swap: [subIn, subOut]          - stats array
- content.lineup.homeTeam/       - type: "Card" (yellow/red)      - minutesPlayed
  awayTeam subs (7-9 players)    - type: "Goal"                   - ratings
- performance.substitutionEvents
```

### Parity Audit Findings Across All 2,280 Completed Matches:
1. **Starter Integrity:** Exactly 2,280 of 2,280 matches feature a `standard` lineup type with exactly 11 home starters and 11 away starters (total 50,160 verified starter appearances).
2. **Substitution Parity:** The count and player IDs of `subIn` events in `content.matchFacts.events` match the `subIn` events in `content.lineup.subs` in **2,280 of 2,280 matches (100.0% parity, 0 discrepancies)**.
3. **PlayerStats Alignment:** In all 2,280 matches, every player who entered the pitch has populated match statistics in `content.playerStats`. Conversely, all 16,314 `UNKNOWN` bench players have **0 stats** and **0 minutes played** in `content.playerStats`.

---

## 5. Special Edge Cases Audited

### 5.1 Bench Bookings (Cards Received on the Bench)
The audit identified **9 specific matches** where an unused substitute was issued a card by the referee while sitting on the bench (dissent, bench altercation, or delay of restart):
1. **Match 3610229 (Season 2021/22), PID 1203668 (Kwadwo Baah):** Yellow card at min 90. Subs entered: 0. `playerStats.stats`: 0.
2. **Match 3901160 (Season 2022/23), PID 843040 (Pedro Neto):** Yellow card at min 88. Subs entered: 0. `playerStats.stats`: 0.
3. **Match 3901211 (Season 2022/23), PID 955529 (Shandon Baptiste):** Red card at min 90. Subs entered: 0. `playerStats.stats`: 0.
4. **Match 3901087 (Season 2022/23), PID 279489 (Lucas Digne):** Yellow card at min 90. Subs entered: 0. `playerStats.stats`: 0.
5. **Match 3901112 (Season 2022/23), PID 279489 (Lucas Digne):** Yellow card at min 90. Subs entered: 0. `playerStats.stats`: 0.
6. **Match 4193798 (Season 2023/24), PID 268212 (Oriol Romeu):** Yellow card at min 90. Subs entered: 0. `playerStats.stats`: 0.
7. **Match 4193710 (Season 2023/24), PID 363357 (Ben Davies):** Yellow card at min 90. Subs entered: 0. `playerStats.stats`: 0.
8. **Match 4193835 (Season 2023/24), PID 729988 (Emil Krafth):** Yellow card at min 64. Subs entered: 0. `playerStats.stats`: 0.
9. **Match 4506402 (Season 2024/25), PID 240054 (Vitaly Janelt):** Yellow card at min 90. Subs entered: 0. `playerStats.stats`: 0.

*Verification Rule:* Receiving a disciplinary sanction on the bench does **not** constitute an on-pitch appearance. The Step 07 parser correctly classifies these 9 cases as `UNUSED_SUBSTITUTE` with reason `COMPLETE_EVIDENCE_UNUSED_SUBSTITUTE_WITH_BENCH_CARD`.

### 5.2 Abandoned Fixture
- **Match ID `4193691` (Bournemouth vs Luton Town, 2023/24):**
  - Abandoned at 59th minute due to medical emergency involving Tom Lockyer.
  - Quarantined in `matches.parquet` with `eligible_completed = False`.
  - Excluded from `player_match_appearances.parquet` (0 appearance records).
  - Replayed in full on 2024-03-13 under Match ID `4193850` (which is fully resolved and complete).

---

## 6. Formal Evidence Hierarchy & State Mapping

| Evidence Class | Participation Status | Validation Status | Mandatory Conditions |
| :--- | :---: | :---: | :--- |
| **`DIRECT_STARTER_EVIDENCE`** | `STARTED` | `CONFIRMED` | Player is in verified 11-man starting lineup of home or away team. |
| **`DIRECT_SUBSTITUTION_ON_EVIDENCE`** | `SUBSTITUTED_ON` | `CONFIRMED` | Player is in team bench list AND recorded as `subIn` in `lineup.subs.performance` OR as `swap[0]` in `matchFacts.events`. |
| **`COMPLETE_UNUSED_SUBSTITUTE_EVIDENCE`** | `UNUSED_SUBSTITUTE` | `NOT_APPEARED` | Standard 11v11 lineup verified, match event feed complete and non-empty, all substitutions fully accounted for, player not in any `subIn` swap, and player has 0 match stats. |
| **`INSUFFICIENT_EVIDENCE`** | `UNKNOWN` | `UNRESOLVED` | Non-standard lineup, incomplete event timeline, or missing raw match capture. |
| **`CONFLICTING_EVIDENCE`** | `CONFLICTING` | `UNRESOLVED` | Contradictory evidence (e.g. player in starters on both teams, or active stats present without substitution entry). |

---

## 7. Conclusion

The audit conclusively demonstrates that all 16,314 `UNKNOWN` records in release v2 were artefacts of the FotMob API schema shift from `substitutionEvents: []` to `performance: {}`. Because every completed Premier League match has complete and verified lineup, event, and player-stats feeds, all 16,314 records possess **`COMPLETE_UNUSED_SUBSTITUTE_EVIDENCE`** and are safely resolved to `UNUSED_SUBSTITUTE` with zero data fabrication.

