# Phase 2B.1 Execution 01 — reproducible commands

Run from `D:\PTIT\Hoc_may\FB69`. These commands use saved evidence and make zero collection HTTP requests:

```powershell
python -m src.collection.full_orchestrator --init-manifest
python -m src.collection.full_orchestrator --report-status
python -m src.collection.full_orchestrator --dry-run --batch-size 10
python -m src.collection.full_orchestrator --season 2019/2020 --stage A --dry-run
python -m src.collection.full_orchestrator --validation-only --from-raw --batch-size 50 --resume
python -m src.collection.execution01_preflight
```

`--init-manifest` is idempotent and preserves checkpoint states. `--validation-only --from-raw` checks existing responses and never calls the API. The runner also supports `--season`, `--stage`, `--batch-size`, `--resume`, `--max-requests`, and `--report-status`. Live `--execute` requires an explicit run budget of 1–50 actual attempts including retries and is **not part of Execution 01**. It must not be used until Execution 02 is separately authorized and the Stage F/G blockers are closed. [Configuration](../../configs/full_collection.yaml), [manifest](collection_manifest.csv), [preflight](preflight_report.md).
