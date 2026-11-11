#!/usr/bin/env python3
"""同步并体检 Loon 配置引用的上游资源。

配置里的远程规则不是本地副本 —— Loon 运行时直接向上游拉取。所以这里的「同步」
指的不是下载正文，而是每天把每条上游资源的现状记下来，并对上一次：

  1. 还活着吗（HTTP 状态、是否被 Cloudflare 挑战）
  2. 内容还是规则吗（不能变成 HTML 错误页，清单不能突然变空）
  3. 变了没有（sha256 / ETag 与上一次对比，规则条数一起记）

结果写进 .upstream/upstreams.lock.json，并可选写进 GitHub Actions 的 Step
Summary。有变化时由 workflow 提交 lock 文件 —— 正文仍然由 Loon 客户端自己拉。

kelee.one 的资源有客户端门禁：站方校验 UA（必须 Loon/ 开头），Cloudflare 还会
按出口 IP 下发机器人挑战。GitHub Actions 是机房出口，拿到 403 / challenge 属于
预期结果，记为 gated，不计入失败。

用法：
    python3 scripts/sync_upstreams.py
    python3 scripts/sync_upstreams.py --strict --summary "$GITHUB_STEP_SUMMARY"
    python3 scripts/sync_upstreams.py --dry-run
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
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

URL_RE = re.compile(r"https?://[^\s,]+")
SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")
KV_RE = re.compile(r"(?<![A-Za-z0-9_-])(policy|tag|enabled)\s*=\s*([^,]+)")

# 必须冒充 Loon 客户端，否则 kelee.one 一律 403。UA 只是第一道闸：
# UA 对了、出口是机房，仍会被 Cloudflare 的机器人挑战挡住（cf-mitigated: challenge）。
LOON_UA = "Loon/998 CFNetwork/3896.100.1.1.1 Darwin/27.0.0"

CLIENT_GATED_HOSTS = ("kelee.one",)

# 占位符 / DoH / 测速地址不是可抓取的上游资源。
SKIP_HOSTS = (
    "example.com",
    "223.5.5.5",
    "223.6.6.6",
    "120.53.53.53",
    "1.12.12.12",
    "dns.alidns.com",
    "doh.pub",
    "www.gstatic.com",
    "cp.cloudflare.com",
)

# 配置里只同步这些 [General] 资源；订阅地址与图标不算上游正文。
GENERAL_RESOURCE_KEYS = ("resource-parser", "geoip-url", "ipasn-url")

CORE_KINDS = {"rule", "resource"}
HTML_PREFIXES = ("<!doctype", "<html", "<head", "<?xml")


def normalize_url(url: str) -> str:
    return url.rstrip(").\"'")


def should_skip(url: str) -> bool:
    return any(host in url for host in SKIP_HOSTS)


def is_gated(url: str) -> bool:
    return any(host in url for host in CLIENT_GATED_HOSTS)


def source_name(url: str) -> str:
    if "blackmatrix7/ios_rule_script" in url:
        return "blackmatrix7/ios_rule_script"
    if "Cats-Team/AdRules" in url:
        return "Cats-Team/AdRules"
    if "fmz200/wool_scripts" in url:
        return "fmz200/wool_scripts"
    if "Loyalsoldier/geoip" in url:
        return "Loyalsoldier/geoip"
    if "sub-store-org/Sub-Store" in url:
        return "sub-store-org/Sub-Store"
    if "kelee.one" in url:
        return "kelee.one"
    return "other"


def extract_resources(config: Path) -> list[dict[str, object]]:
    """从配置里提取可抓取的上游资源，按 URL 去重。

    只取 [Remote Rule] 与 [General] 的三个资源键。图标是自托管文件，由
    validate_config.py 在本地校验存在性，不占上游请求额度。
    """
    resources: dict[str, dict[str, object]] = {}
    section = ""

    def add(entry: dict[str, object]) -> None:
        url = str(entry["url"])
        if url in resources:
            existing = resources[url]
            labels = {str(existing.get("label", "")), str(entry.get("label", ""))}
            existing["label"] = " / ".join(sorted(item for item in labels if item))
            return
        resources[url] = entry

    for raw in config.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        match = SECTION_RE.match(line)
        if match:
            section = match.group(1).strip().lower()
            continue
        if not line or line.startswith("#"):
            continue

        if section == "remote rule":
            url_match = URL_RE.match(line.split(",", 1)[0].strip())
            if not url_match:
                continue
            url = normalize_url(url_match.group(0))
            if should_skip(url):
                continue
            fields = {key: value.strip() for key, value in KV_RE.findall(line)}
            add(
                {
                    "url": url,
                    "kind": "rule",
                    "label": fields.get("tag", ""),
                    "policy": fields.get("policy", ""),
                    "enabled": fields.get("enabled", "true").lower() != "false",
                }
            )

        elif section == "general" and "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            if key not in GENERAL_RESOURCE_KEYS:
                continue
            for candidate in URL_RE.findall(value):
                url = normalize_url(candidate)
                if should_skip(url):
                    continue
                add({"url": url, "kind": "resource", "label": key})

    for entry in resources.values():
        entry["source"] = source_name(str(entry["url"]))
        entry["core"] = entry["kind"] in CORE_KINDS and not is_gated(str(entry["url"]))
        entry["gated"] = is_gated(str(entry["url"]))
    return sorted(resources.values(), key=lambda item: (str(item["kind"]), str(item["url"])))


def count_rules(body: bytes) -> tuple[int, dict[str, int]]:
    text = body.decode("utf-8", errors="replace")
    types: collections.Counter[str] = collections.Counter()
    count = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "!", ";", "//")):
            continue
        rule_type = line.split(",", 1)[0].strip().upper()
        if not rule_type or " " in rule_type:
            continue
        types[rule_type] += 1
        count += 1
    return count, dict(types.most_common(8))


def check_body(entry: dict[str, object], body: bytes) -> str | None:
    """返回内容错误；None 表示内容看起来正常。"""
    kind = entry["kind"]
    if kind == "icon":
        return None if body.startswith(b"\x89PNG\r\n\x1a\n") else "不是 PNG"
    if kind != "rule":
        return None

    text = body.decode("utf-8", errors="replace").lstrip().lower()
    if text.startswith(HTML_PREFIXES):
        return "返回 HTML（被挑战页 / 错误页替换）"
    count, _ = count_rules(body)
    if count == 0:
        return "规则条数为 0"
    return None


def fetch(url: str, timeout: int) -> tuple[dict[str, object], bytes | None]:
    """抓取一条资源，返回 (元数据, 正文)。正文只用于本地校验，不落盘。"""
    request = urllib.request.Request(url, headers={"User-Agent": LOON_UA, "Accept": "*/*"})
    started = dt.datetime.now(dt.timezone.utc)
    context = ssl.create_default_context()

    def read(tls_verified: bool) -> tuple[dict[str, object], bytes]:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            body = response.read()
            status = response.getcode()
            meta = {
                "status": status,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "etag": response.headers.get("ETag"),
                "last_modified": response.headers.get("Last-Modified"),
                "content_type": response.headers.get("Content-Type"),
                "tls_verified": tls_verified,
                "checked_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
            }
            return meta, body

    try:
        return read(tls_verified=True)
    except urllib.error.HTTPError as error:
        return (
            {
                "status": error.code,
                "error": f"HTTP {error.code}: {error.reason}",
                "cf_mitigated": error.headers.get("cf-mitigated") if error.headers else None,
                "checked_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
            },
            None,
        )
    except urllib.error.URLError as error:
        if "CERTIFICATE_VERIFY_FAILED" in str(error):
            try:
                return read(tls_verified=False)
            except Exception as retry_error:  # noqa: BLE001 - 诊断信息要原样保留
                return (
                    {
                        "error": f"{type(retry_error).__name__}: {retry_error}",
                        "checked_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
                    },
                    None,
                )
        return (
            {
                "error": f"{type(error).__name__}: {error}",
                "checked_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
            },
            None,
        )
    except Exception as error:  # noqa: BLE001 - 诊断信息要原样保留
        return (
            {
                "error": f"{type(error).__name__}: {error}",
                "checked_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
            },
            None,
        )


def fetch_with_retries(url: str, timeout: int, retries: int) -> tuple[dict[str, object], bytes | None]:
    last: tuple[dict[str, object], bytes | None] = ({}, None)
    for attempt in range(retries + 1):
        meta, body = fetch(url, timeout)
        meta["attempts"] = attempt + 1
        if meta.get("sha256"):
            return meta, body
        last = (meta, body)
        status = meta.get("status")
        retryable = status is None or status == 429 or int(status) >= 500
        if attempt < retries and retryable:
            time.sleep(min(2 * (attempt + 1), 5))
        else:
            break
    return last


def load_previous(output: Path) -> dict[str, dict[str, object]]:
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


def sync_one(entry: dict[str, object], timeout: int, retries: int) -> dict[str, object]:
    url = str(entry["url"])
    meta, body = fetch_with_retries(url, timeout, retries)
    result = {**entry, **meta}
    result["ok"] = bool(meta.get("sha256"))

    if result["ok"] and body is not None:
        content_error = check_body(entry, body)
        if content_error:
            result["ok"] = False
            result["error"] = content_error
        if entry["kind"] == "rule":
            count, types = count_rules(body)
            result["rule_count"] = count
            result["rule_types"] = types

    if not result["ok"] and result.get("gated"):
        # 客户端门禁：CI 侧拿不到属于预期，状态码之外再留一条原因。
        result["gated_reason"] = "仅 Loon 客户端可下：UA + 非机房出口才过 Cloudflare"

    return result


def annotate_changes(
    resources: list[dict[str, object]],
    previous: dict[str, dict[str, object]],
) -> None:
    for item in resources:
        old = previous.get(str(item["url"]))
        if old is None:
            item["status_vs_previous"] = "new"
            continue
        if not item["ok"]:
            item["status_vs_previous"] = "failed"
            continue
        item["status_vs_previous"] = "unchanged" if old.get("sha256") == item.get("sha256") else "changed"
        if item["status_vs_previous"] == "changed":
            item["previous_sha256"] = old.get("sha256")
            item["previous_rule_count"] = old.get("rule_count")


def write_summary(
    path: Path,
    payload: dict[str, object],
    resources: list[dict[str, object]],
) -> None:
    reachable = [item for item in resources if item["ok"]]
    gated = [item for item in resources if not item["ok"] and item.get("gated")]
    failed = [item for item in resources if not item["ok"] and not item.get("gated")]
    failed_core = [item for item in failed if item["core"]]
    changed = [item for item in resources if item.get("status_vs_previous") == "changed"]
    new = [item for item in resources if item.get("status_vs_previous") == "new"]

    lines: list[str] = [
        "## 上游同步",
        "",
        f"- 配置：`{payload['config']}`",
        f"- 生成时间：`{payload['generated_at']}`",
        f"- 资源总数：**{len(resources)}**（可达 {len(reachable)} / 门禁 {len(gated)} / 失败 {len(failed)}）",
        f"- 内容有变化：**{len(changed)}**；首次记录：**{len(new)}**",
    ]

    if changed:
        lines += ["", "### 有变化的上游", "", "| 资源 | 规则条数 | sha256 |", "|---|---|---|"]
        for item in changed[:30]:
            label = item.get("label") or item["url"]
            lines.append(
                f"| {label} | {item.get('previous_rule_count', '-')} → {item.get('rule_count', '-')} "
                f"| `{str(item.get('sha256', ''))[:12]}` |"
            )

    rules = [item for item in resources if item["kind"] == "rule"]
    if rules:
        lines += ["", "### 规则清单", "", "| 名称 | 条数 | 状态 |", "|---|---|---|"]
        for item in rules:
            if item["ok"]:
                state = "可达"
            elif item.get("gated"):
                state = "客户端门禁"
            else:
                state = f"失败（{item.get('status') or item.get('error', '未知')}）"
            lines.append(f"| {item.get('label') or item['url']} | {item.get('rule_count', '-')} | {state} |")

    if failed:
        lines += ["", "### 失败", "", "| 状态 | 资源 | URL |", "|---|---|---|"]
        for item in failed[:30]:
            lines.append(f"| `{item.get('status') or '-'}` | {item.get('label') or item['source']} | {item['url']} |")

    if gated:
        lines += [
            "",
            f"> {len(gated)} 条 kelee.one 资源在 CI 上必然被 Cloudflare 拦下，属预期，不计失败。",
        ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="Loon-routing.conf", type=Path)
    parser.add_argument("--output", default=".upstream/upstreams.lock.json", type=Path)
    parser.add_argument("--timeout", default=30, type=int)
    parser.add_argument("--retries", default=2, type=int)
    parser.add_argument("--workers", default=8, type=int)
    parser.add_argument("--strict", action="store_true", help="核心资源失败时返回非零退出码")
    parser.add_argument("--dry-run", action="store_true", help="只抓取和打印，不写 lock / summary")
    parser.add_argument("--summary", type=Path, default=None, help="写入 GitHub Step Summary")
    args = parser.parse_args()

    if not args.config.exists():
        print(f"找不到配置：{args.config}", file=sys.stderr)
        return 2

    entries = extract_resources(args.config)
    if not entries:
        print("配置里没有提取到任何上游资源。", file=sys.stderr)
        return 2

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(sync_one, entry, args.timeout, args.retries) for entry in entries]
        resources = [future.result() for future in futures]

    previous = load_previous(args.output)
    annotate_changes(resources, previous)

    reachable = [item for item in resources if item["ok"]]
    gated = [item for item in resources if not item["ok"] and item.get("gated")]
    failed = [item for item in resources if not item["ok"] and not item.get("gated")]
    failed_core = [item for item in failed if item["core"]]
    changed = [item for item in resources if item.get("status_vs_previous") == "changed"]
    new = [item for item in resources if item.get("status_vs_previous") == "new"]

    payload = {
        "config": str(args.config),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "resource_count": len(resources),
        "summary": {
            "reachable": len(reachable),
            "gated": len(gated),
            "failed": len(failed),
            "failed_core": len(failed_core),
            "changed": len(changed),
            "new": len(new),
        },
        "resources": resources,
    }

    if not args.dry_run:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if args.summary:
            write_summary(args.summary, payload, resources)

    total_bytes = sum(int(item.get("bytes", 0)) for item in reachable)
    print(f"扫描 {args.config} -> {len(resources)} 个上游资源")
    print(f"  可达      : {len(reachable)}")
    print(f"  有变化    : {len(changed)}  首次记录: {len(new)}")
    if gated:
        by_source = collections.Counter(str(item["source"]) for item in gated)
        detail = " / ".join(f"{name} {count}" for name, count in by_source.most_common())
        print(f"  客户端门禁: {len(gated)}（{detail}，CI 侧 403 属预期）")
    if failed:
        by_status = collections.Counter(str(item.get("status") or "-") for item in failed)
        detail = " / ".join(f"{status} {count} 条" for status, count in by_status.most_common())
        print(f"  不可达    : {len(failed)}（{detail}）")
    print(f"  规则总数  : {sum(int(item.get('rule_count', 0)) for item in resources)}")
    print(f"  合计内容  : {total_bytes / 1024 / 1024:.1f} MB / {len(reachable)} 个 sha256")
    print(f"  generated : {payload['generated_at']}")

    if failed_core:
        print("核心资源失败：", file=sys.stderr)
        for item in failed_core:
            print(f"  - {item.get('status') or '-'} {item['url']}", file=sys.stderr)

    return 1 if args.strict and failed_core else 0


if __name__ == "__main__":
    raise SystemExit(main())
