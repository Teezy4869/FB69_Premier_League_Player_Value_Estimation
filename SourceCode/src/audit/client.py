"""Bounded, logged access to FotMob's JSON interface."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import requests


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BudgetExceeded(RuntimeError):
    pass


def retry_after_seconds(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return None
            return max(0.0, (date - (now or datetime.now(timezone.utc))).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


class AuditClient:
    def __init__(self, config: dict, log_path: Path, session=None, sleep=time.sleep, clock=time.monotonic):
        self.config = config
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.session = session or requests.Session()
        self.sleep = sleep
        self.clock = clock
        self.attempts = 0
        self.last_started = None

    def get(self, endpoint: str, params: dict | None = None) -> dict:
        url = urljoin(self.config["api_base_url"].rstrip("/") + "/", endpoint.lstrip("/"))
        params = params or {}
        for retry in range(self.config["max_retries"] + 1):
            if self.attempts >= self.config["request_budget"]:
                raise BudgetExceeded("HTTP attempt budget exhausted")
            if self.last_started is not None:
                self.sleep(max(0, self.config["min_request_interval_seconds"] - (self.clock() - self.last_started)))
            self.last_started = self.clock()
            self.attempts += 1
            started = self.clock()
            record = {"timestamp_utc": utc_now(), "endpoint": endpoint, "params": params,
                      "attempt": self.attempts, "retry_index": retry, "source_url": url}
            response = None
            retry_delay = self.config["backoff_seconds"] * (2 ** retry)
            try:
                response = self.session.get(url, params=params,
                    headers={"User-Agent": self.config["user_agent"], "Accept": "application/json"},
                    timeout=self.config["request_timeout_seconds"], stream=True)
                record.update({"source_url": response.url, "http_status": response.status_code,
                               "content_type": response.headers.get("Content-Type", "")})
                limit = self.config["max_response_bytes"]
                chunks = []
                total = 0
                for chunk in response.iter_content(chunk_size=65536):
                    total += len(chunk)
                    if total > limit:
                        raise ValueError(f"response exceeds {limit} bytes")
                    chunks.append(chunk)
                body = b"".join(chunks)
                record["response_bytes"] = total
                server_wait = retry_after_seconds(response.headers.get("Retry-After"))
                if response.status_code == 429 and server_wait is not None:
                    record["retry_after_seconds"] = round(server_wait, 3)
                    retry_delay = max(retry_delay, server_wait)
                if response.status_code in (429, 500, 502, 503, 504) and retry < self.config["max_retries"]:
                    if response.status_code == 429 and retry_delay > self.config.get("max_retry_after_seconds", 30):
                        record.update({"outcome": "FAILED", "error": "Retry-After exceeds bounded wait"})
                        return {"record": record, "payload": None, "raw_body": body}
                    record["outcome"] = "RETRY"
                    record["backoff_wait_seconds"] = round(retry_delay, 3)
                elif response.status_code != 200:
                    record.update({"outcome": "FAILED", "error": f"HTTP {response.status_code}"})
                    error_payload = None
                    if "json" in record["content_type"].lower():
                        try:
                            error_body = json.loads(body)
                            error_payload = error_body
                            record["json_parse_success"] = True
                            if isinstance(error_body, dict) and isinstance(error_body.get("error"), str):
                                record["response_error"] = error_body["error"][:300]
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            record["json_parse_success"] = False
                    return {"record": record, "payload": None, "raw_body": body,
                            "error_payload": error_payload}
                elif "json" not in record["content_type"].lower():
                    record.update({"outcome": "FAILED", "error": "non-JSON content type"})
                    return {"record": record, "payload": None, "raw_body": body}
                else:
                    try:
                        payload = json.loads(body)
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        record.update({"outcome": "FAILED", "error": f"JSON parse: {exc}",
                                       "json_parse_success": False})
                        return {"record": record, "payload": None, "raw_body": body}
                    record["json_parse_success"] = True
                    if not isinstance(payload, (dict, list)):
                        record.update({"outcome": "FAILED", "error": "JSON root is not an object or list"})
                        return {"record": record, "payload": None, "raw_body": body}
                    record["outcome"] = "OK"
                    return {"record": record, "payload": payload, "raw_body": body}
            except (requests.RequestException, ValueError) as exc:
                record.update({"outcome": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
                if retry == self.config["max_retries"]:
                    return {"record": record, "payload": None}
            finally:
                record["elapsed_seconds"] = round(self.clock() - started, 3)
                with self.log_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                if response is not None:
                    response.close()
            self.sleep(retry_delay)
        raise AssertionError("unreachable")
