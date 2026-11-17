"""Step 3 QA: record automated adjudication decisions for the 44 identities unresolved in matching_v1.

These are AUTOMATED decisions and are not human review. A reviewer's decision always overrides them.

A pair is CONFIRMED_MATCH only if it is the only LIKELY or rank-1 candidate and either:
  RULE      the independent validator confirmed it (at least 2 evidence families, none disagreeing), or
  EXTERNAL  third-party biographies tie the two name forms, or both birth dates, to one person, and
            the game history agrees over at least 2 games, and at least one independent family agrees.
Anything else stays REVIEW_REQUIRED or INSUFFICIENT_EVIDENCE.

External notes come from search-result summaries on 2026-11-04, not from primary records.

Usage: python -I src/phase3/step3_qa_adjudicate.py <evidence_dir>
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.phase3.tm_common import ROOT  # noqa: E402

OUTPUT = ROOT / "data/phase_03/review/automated_adjudications.csv"
ADJUDICATOR = "automated:claude-opus-5-5"
ADJUDICATION_DATE = "2026-11-04"
MIN_EXTERNAL_GAMES = 2
COLUMNS = ["fotmob_player_id", "tm_player_id", "group", "outcome", "basis", "confidence", "name_difference_pattern", "evidence", "rationale", "external_sources", "adjudicator", "adjudication_date", "human_reviewed"]

PATTERNS = {
    "Toti Gomes": "Mononym vs fuller name", "Jaden Philogene-Bidace": "Surname part dropped", "Pape Sarr": "Middle name omitted", "Valentino Livramento": "Formal vs short name (Tino)", "Thomas Cannon": "Formal vs short name (Tom)",
    "Hannibal Mejbri": "Mononym vs fuller name", "Ahmed El Mohamady": "Spacing in surname", "Michael Olakigbe": "Same name; birth date differs", "Yehor Yarmoliuk": "Transliteration", "Sávio": "Different name in common use (Savinho)",
    "Jimi Tauriainen": "Same name; birth date differs", "Alfie Pond": "Same name; birth date differs", "Daniel Gore": "Formal vs short name (Dan)", "Omari Kellyman": "Same name; birth date differs", "Joshua King": "Formal vs short name (Josh)",
    "Adrian | Adrián": "Mononym vs fuller name", "Kiko": "Mononym vs fuller name", "Daniel Burn": "Formal vs short name (Dan)", "Wesley Foderingham": "Formal vs short name (Wes)", "Robert Brady": "Formal vs short name (Robbie)",
    "Jota": "Mononym vs fuller name", "Victor Nilsson Lindelöf": "Middle name omitted", "Alisson Becker": "Mononym vs fuller name", "Jose Holebas | José Holebas": "Transliteration (Holebas, Cholevas)", "Mbwana Samatta": "Different given name in use (Mbwana, Ally)",
    "Joshua Onomah": "Formal vs short name (Josh)", "Joseph Gomez": "Formal vs short name (Joe)", "Wesley": "Mononym vs fuller name", "Mads Bech": "Surname part dropped", "Rasmus Kristensen": "Middle name omitted",
    "Trincao | Trincão": "Mononym vs fuller name", "Ørjan Håskjold Nyland": "Middle name omitted", "Quina": "Mononym vs fuller name", "Joshua Dasilva": "Formal vs short name (Josh)", "Jens-Lys Cajuste": "Given name part dropped",
    "Hákon Rafn Valdimarsson": "Middle name omitted", "Juan Hernández": "Different name in common use (Cucho)", "Edward Nketiah": "Formal vs short name (Eddie)", "Joseph Willock": "Formal vs short name (Joe)", "Andy Irving": "Formal vs short name (Andrew)",
    "Matthew O'Riley": "Formal vs short name (Matt)", "Cheick Oumar Doucouré": "Middle name omitted", "Kelland Watts": "Formal vs short name (Kell)", "Daniel Chesters": "Formal vs short name (Dan)",
}

# Third-party evidence. Only entered for pairs where it answers a question the rule could not.
EXTERNAL = {
    "Michael Olakigbe": ("Birth date is disputed across sources for one Brentford player: 6 April 2004 (FotMob, Wikipedia, Wigan heritage site), 25 April 2004 (TM, Premier League page, SuperSport), 23 April 2004 (11v11). The Premier League result had a mislabeled URL, so it is weak.",
                         "https://en.wikipedia.org/wiki/Michael_Olakigbe; https://wiganathleticheritage.co.uk/player-profile/10266/michael-olakigbe; https://www.11v11.com/players/michael-olakigbe-272424/team/peterborough-united/"),
    "Jimi Tauriainen": ("Birth date is disputed across sources for one Chelsea academy player: 8 March 2004 (TM, Premier League page, Soccerway), 9 March 2004 (FotMob, 11v11, Sports Mole).",
                        "https://premierleague.com/players/98290; https://www.11v11.com/players/jimi-tauriainen-275359/; https://en.wikipedia.org/wiki/Jimi_Tauriainen"),
    "Alfie Pond": ("Birth date is disputed across sources for one Wolves defender: 17 February 2004 (TM, Wikipedia, 11v11), 1 March 2004 (FotMob, ESPN, LiveSoccerTV, Soccerway, Exeter's Grecian Archive).",
                   "https://en.wikipedia.org/wiki/Alfie_Pond; https://www.11v11.com/players/alfie-pond-274082/; https://www.espn.com.au/football/player/bio/_/id/308554/alfie-pond"),
    "Omari Kellyman": ("Birth date is disputed across sources for one Aston Villa and Chelsea player: 15 September 2005 (TM, Premier League page, Wikipedia, ESPN), 25 September 2005 (FotMob, LiveSoccerTV, AVFC History).",
                       "https://premierleague.com/players/117753; https://en.wikipedia.org/wiki/Omari_Kellyman; https://www.avfchistory.co.uk/player/omari-kellyman"),
    "Joshua King": ("Biography gives Joshua David Steven King, known as Josh King, Fulham, born 3 January 2007.", "https://en.wikipedia.org/wiki/Josh_King_(footballer,_born_2007)"),
    "Jota": ("Biography gives José Ignacio Peleteiro Ramallo, known as Jota, Aston Villa winger born June 1991.", "https://www.fantasyfootballscout.co.uk/2019/06/11/jota-with-plenty-to-prove-as-an-fpl-asset-after-villa-move/"),
    "Mbwana Samatta": ("Biography gives full name Mbwana Ally Samatta, Aston Villa, born 23 December 1992.", "https://en.wikipedia.org/wiki/Mbwana_Samatta; https://www.livesoccertv.com/player/m-samatta/147497/"),
    "Joshua Onomah": ("Biography gives Joshua Oghenetega Peter Onomah, known as Josh, Fulham, born 27 April 1997.", "https://en.wikipedia.org/wiki/Josh_Onomah"),
    "Rasmus Kristensen": ("Biography gives Rasmus Nissen Kristensen, Leeds United right-back, born 11 July 1997.", "https://en.wikipedia.org/wiki/Rasmus_Kristensen; https://lex.dk/Rasmus_Nissen_Kristensen"),
    "Quina": ("Biography gives Domingos Quina, Watford and Fulham midfielder, born 18 November 1999.", "https://en.wikipedia.org/wiki/Domingos_Quina"),
    "Hákon Rafn Valdimarsson": ("Biography gives Hákon Rafn Valdimarsson, also Hákon Valdimarsson, Brentford goalkeeper, born 13 October 2001.", "https://en.wikipedia.org/wiki/H%C3%A1kon_Valdimarsson; https://brentfordfc.com/en/news/article/first-team-hakon-valdimarsson-signs-new-long-term-contract"),
    "Daniel Chesters": ("Biography gives Daniel Peter James Chesters, known as Dan, West Ham academy, born 4 April 2002. TM has no EPL game rows for him, so game history cannot corroborate.", "https://en.wikipedia.org/wiki/Daniel_Chesters; https://www.whufc.com/player/107"),
}


def decide(rows: list[dict]) -> dict:
    """Decide one identity from its candidates, using the rule result and any external note."""
    top = rows[0]
    name = top["fotmob_names"]
    likely = [r for r in rows if r["suggestion"] == "LIKELY_MATCH"]
    group = "B_BIRTH_DATE_DIFFERS" if top["dob_relation"] != "EXACT" else "A_NAME_FORM_DIFFERS"
    if len(likely) > 1 or (likely and likely[0]["tm_player_id"] != top["tm_player_id"]):
        return {"group": group, "outcome": "REVIEW_REQUIRED", "basis": "COMPETING_CANDIDATES", "confidence": "NONE", "rationale": "More than one likely candidate, or the top-ranked pair is not the likely one."}
    external = EXTERNAL.get(name)
    games_agree = top["shared_games"] > 0 and top["game_jaccard"] >= 0.9
    if top["label"] == "CONFIRMED_NON_MATCH":
        return {"group": group, "outcome": "CONFIRMED_NON_MATCH", "basis": "RULE", "confidence": top["confidence"], "rationale": "Independent evidence rejected this pair."}
    if top["label"] == "CONFIRMED_MATCH":
        extra = " External sources also tie both birth dates to one person." if external else ""
        return {"group": group, "outcome": "CONFIRMED_MATCH", "basis": "RULE_AND_EXTERNAL" if external else "RULE", "confidence": top["confidence"], "rationale": f"Independent validator confirmed the pair, without using name or birth date.{extra}"}
    families_agreeing = sum(top[k] == "AGREE" for k in ("career_result", "physical_result", "performance_result"))
    if external and games_agree and top["fm_games"] >= MIN_EXTERNAL_GAMES and families_agreeing >= 1:
        return {"group": group, "outcome": "CONFIRMED_MATCH", "basis": "EXTERNAL", "confidence": "MEDIUM", "rationale": "Validator inconclusive. Third-party biography ties the identities together, game history agrees, and at least one independent family agrees."}
    if external:
        return {"group": group, "outcome": "REVIEW_REQUIRED", "basis": "EXTERNAL_TOO_THIN", "confidence": "LOW", "rationale": "A third-party biography supports this pair, but game history or independent evidence is too thin for an automated decision. Precision takes priority over coverage."}
    return {"group": group, "outcome": "INSUFFICIENT_EVIDENCE", "basis": "NONE", "confidence": "NONE", "rationale": "No independent or external evidence settles this pair."}


def main() -> None:
    evidence = Path(sys.argv[1])
    data = json.loads((evidence / "unresolved_44_automated_evidence.json").read_text(encoding="utf-8"))
    grouped = defaultdict(list)
    for row in data["candidates"]:
        grouped[row["fotmob_player_id"]].append(row)
    if len(grouped) != 44:
        raise RuntimeError(f"Expected 44 identities, found {len(grouped)}")
    output = []
    for fid in sorted(grouped):
        rows = sorted(grouped[fid], key=lambda r: r["candidate_rank"])
        top = rows[0]
        decision = decide(rows)
        note, urls = EXTERNAL.get(top["fotmob_names"], ("", ""))
        pattern = PATTERNS[top["fotmob_names"]]
        facts = f"FotMob {top['fotmob_names']} ({top['fotmob_dob']}, {top['fotmob_nationality']}); TM {top['tm_name']} ({top['tm_dob']}, {top['tm_nationality']}). Games {top['shared_games']} shared of {top['fm_games']} FotMob, {top['tm_games']} TM. {top['evidence']} {note}".strip()
        output.append({"fotmob_player_id": fid, "tm_player_id": top["tm_player_id"], "name_difference_pattern": pattern, "evidence": facts, "external_sources": urls, "adjudicator": ADJUDICATOR, "adjudication_date": ADJUDICATION_DATE, "human_reviewed": False, **decision})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # An optional second argument redirects the review copy, so reproduction checks can't touch the real file.
    review_copy = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT
    review_copy.parent.mkdir(parents=True, exist_ok=True)
    for path in (review_copy, evidence / "unresolved_44_decisions.csv"):
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(output)
    print(Counter(r["outcome"] for r in output), Counter(r["basis"] for r in output), Counter(r["confidence"] for r in output), Counter(r["group"] for r in output))
    for r in output:
        if r["basis"] != "RULE":
            print(r["group"][:1], r["outcome"], r["basis"], r["confidence"], r["evidence"][:90])


if __name__ == "__main__":
    main()
