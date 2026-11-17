# Phase 2B.0 Steps 05–06 — reproducible execution guide

Run from `D:\PTIT\Hoc_may\FB69` with the repository's installed Python dependencies. The existing live observations are immutable; `--live` uses checkpoints and currently makes zero new HTTP requests. If checkpoints are missing, `--live` may use the remaining configured budget, so review [configuration](../../configs/reliability_config.yaml) and [current log](../../logs/phase_02b0_reliability_requests.jsonl) first.

```powershell
python -m src.collection.reliability_runner
python -m src.collection.reliability_runner --live
python -m src.collection.recovery_validator
python -m unittest discover -s tests -v
python -m src.collection.hardening_acceptance --tests "54/54 passing; failures 0; skipped 0"
python -m src.collection.final_validation --check
```

The report-only runner command performs no HTTP. Recovery replay uses saved live wire bytes and isolated temporary outputs; it does not call FotMob. The acceptance command audits saved evidence and rebuilds reports without HTTP. The full historical collector is **not** invoked by this guide. [Request metrics](request_metrics.csv), [recovery results](recovery_test_results.csv), [readiness report](phase_02b0_readiness_report.md).
