# Phase 1 audit execution guide

Run commands from the project root with Python 3.10+.

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m src.audit.final_review
```

`final_review` is offline. It reads the existing Phase 1 CSVs, endpoint catalog, JSON samples and the saved 2023/24 fixture anomaly. It validates source paths and season IDs, then writes:

- `data_quality_audit.csv`
- `cross_season_consistency.csv`
- `fotmob_data_availability_audit.md`

It does not download data, impute values or modify the earlier CSVs. Two bounded source checks were logged in `logs/fotmob_final_review_requests.jsonl`: the 2023/24 fixture anomaly and the 2019/20 saves unit label. Their evidence is in `data/audit/raw_samples/final_review/`.

The earlier live audits can be rerun with `python -m src.audit` and `python -m src.audit.phase_01_steps_03_05`. Those commands send bounded requests under `configs/fotmob_audit.json` and `configs/phase_01_steps_03_05.json`, respectively, and replace their corresponding reports and samples. If they are rerun, run `final_review` again afterward.

Saved leaderboard samples retain only five rows per request. The identity lists and aggregate counts in `player_coverage_report.csv` were computed from full responses during the earlier bounded audit, but cannot be fully reconstructed from these subsets. The final report marks this evidence limitation and does not claim a complete player denominator.
