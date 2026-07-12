#!/usr/bin/env python3
"""Refresh upstream metadata for the Loon profile."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable


URL_RE = re.compile(r"https?://[^\s,]+")
SKIP_HOSTS = (
    "dns.alidns.com",
    "223.5.5.5",
    "223.6.6.6",
    "1.12.12.12",
    "120.53.53.53",
    "doh.pub",
    "www.gstatic.com",
    "cp.cloudflare.com",
)
CORE_MARKERS = (
    "raw.githubusercontent.com/blackmatrix7/ios_rule_script",
    "raw.githubusercontent.com/Koolson/Qure",
    "raw.githubusercontent.com/fmz200/wool_scripts",
    "github.com/Moli-X/Tool/raw/X/GeoIP",
    "github.com/sub-store-org/Sub-Store/releases",
)


def normalize_url(url: str) -> str:
    return url.rstrip(").\"'")


def should_skip(url: str) -> bool:
    return any(host in url for host in SKIP_HOSTS)


def source_name(url: str) -> str:
    if "blackmatrix7/ios_rule_script" in url:
        return "blackmatrix7/ios_rule_script"
    if "Koolson/Qure" in url:
        return "Koolson/Qure"
    if "fmz200/wool_scripts" in url:
        return "fmz200/wool_scripts"
    if "Moli-X/Tool" in url:
        return "Moli-X/Tool"
    if "sub-store-org/Sub-Store" in url:
        return "sub-store-org/Sub-Store"
    if "sub.store" in url:
        return "Sub-Store subscription"
    if "kelee.one" in url:
        return "Kelee plugin"
    return "other"


def is_core(url: str) -> bool:
    return any(marker in url for marker in CORE_MARKERS)


def extract_urls(config: Path) -> list[str]:
    urls: set[str] = set()
    for raw_line in config.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for match in URL_RE.findall(line):
            url = normalize_url(match)
            if not should_skip(url):
                urls.add(url)
    return sorted(urls)


def fetch(url: str, timeout: int) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "loon-config-upstream-refresh/1.0",
            "Accept": "*/*",
        },
    )
    started = dt.datetime.now(dt.UTC)
    context = ssl.create_default_context()

    def read_response(tls_verified: bool) -> dict[str, object]:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read()
            status = response.getcode()
            headers = response.headers
            ok = 200 <= status < 400
            return {
                "url": url,
                "source": source_name(url),
                "core": is_core(url),
                "ok": ok,
                "status": status,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "etag": headers.get("ETag"),
                "last_modified": headers.get("Last-Modified"),
                "content_type": headers.get("Content-Type"),
                "tls_verified": tls_verified,
                "checked_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
            }

    try:
        return read_response(tls_verified=True)
    except urllib.error.HTTPError as error:
        return {
            "url": url,
            "source": source_name(url),
            "core": is_core(url),
            "ok": False,
            "status": error.code,
            "error": str(error),
            "checked_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
    except urllib.error.URLError as error:
        if "CERTIFICATE_VERIFY_FAILED" in str(error):
            context = ssl._create_unverified_context()  # noqa: S323 - metadata refresh fallback.
            try:
                return read_response(tls_verified=False)
            except Exception as retry_error:  # noqa: BLE001 - keep workflow diagnostics explicit.
                return {
                    "url": url,
                    "source": source_name(url),
                    "core": is_core(url),
                    "ok": False,
                    "status": None,
                    "error": f"{type(retry_error).__name__}: {retry_error}",
                    "checked_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
                }
        return {
            "url": url,
            "source": source_name(url),
            "core": is_core(url),
            "ok": False,
            "status": None,
            "error": f"{type(error).__name__}: {error}",
            "checked_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
        }
    except Exception as error:  # noqa: BLE001 - keep workflow diagnostics explicit.
        return {
            "url": url,
            "source": source_name(url),
            "core": is_core(url),
            "ok": False,
            "status": None,
            "error": f"{type(error).__name__}: {error}",
            "checked_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
        }


def fetch_with_retries(url: str, timeout: int, retries: int) -> dict[str, object]:
    last_result: dict[str, object] | None = None
    for attempt in range(retries + 1):
        result = fetch(url, timeout)
        result["attempt"] = attempt + 1
        if result["ok"]:
            return result
        last_result = result
        status = result.get("status")
        retryable = status is None or status == 429 or int(status) >= 500
        if attempt < retries and retryable:
            time.sleep(min(2 * (attempt + 1), 5))
            continue
        break
    return last_result or fetch(url, timeout)


def load_previous_resources(output: Path) -> dict[str, dict[str, object]]:
    if not output.exists():
        return {}
    try:
        payload = json.loads(output.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        str(item["url"]): item
        for item in payload.get("resources", [])
        if isinstance(item, dict) and "url" in item
    }


def use_stale_core_success(
    resources: list[dict[str, object]],
    previous_resources: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    resolved: list[dict[str, object]] = []
    for item in resources:
        if not item["core"] or item["ok"]:
            resolved.append(item)
            continue

        previous = previous_resources.get(str(item["url"]))
        if not previous or not previous.get("ok"):
            resolved.append(item)
            continue

        stale = dict(previous)
        stale.update(
            {
                "attempt": item.get("attempt"),
                "checked_at": item["checked_at"],
                "core": item["core"],
                "last_error": item.get("error"),
                "last_status": item.get("status"),
                "ok": True,
                "source": item["source"],
                "stale": True,
                "url": item["url"],
            }
        )
        resolved.append(stale)
    return resolved


def refresh(urls: Iterable[str], timeout: int, retries: int) -> list[dict[str, object]]:
    return [fetch_with_retries(url, timeout, retries) for url in urls]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="Loon.conf", type=Path)
    parser.add_argument("--output", default=".upstream/upstreams.lock.json", type=Path)
    parser.add_argument("--timeout", default=30, type=int)
    parser.add_argument("--retries", default=2, type=int)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    urls = extract_urls(args.config)
    previous_resources = load_previous_resources(args.output)
    resources = refresh(urls, args.timeout, args.retries)
    resources = use_stale_core_success(resources, previous_resources)
    payload = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "config": str(args.config),
        "resource_count": len(resources),
        "resources": resources,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    failed_core = [item for item in resources if item["core"] and not item["ok"]]
    if failed_core:
        print("Core upstream failures:", file=sys.stderr)
        for item in failed_core:
            print(f"- {item['status']} {item['url']}", file=sys.stderr)
    return 1 if args.strict and failed_core else 0


if __name__ == "__main__":
    raise SystemExit(main())
