#!/usr/bin/env python3
"""打印配置概览（Markdown），供 GitHub Step Summary 使用。

    python3 scripts/summarize.py >> "$GITHUB_STEP_SUMMARY"
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_config import Config  # noqa: E402

FILES = ("Loon.conf", "Loon-routing.conf", "Loon-minimal.conf")


def main() -> int:
    rows: list[str] = [
        "### 配置概览",
        "",
        "| 文件 | 行数 | 策略组 | 本地规则 | 远程规则 | 插件 | MITM 域名 |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in FILES:
        path = Path(name)
        if not path.exists():
            continue
        cfg = Config(path)
        mitm = cfg.keys("mitm").get("hostname", "")
        mitm_count = len([item for item in mitm.split(",") if item.strip()]) if mitm else 0
        rows.append(
            f"| `{name}` | {len(path.read_text(encoding='utf-8').splitlines())} "
            f"| {len(cfg.keys('proxy group'))} | {len(cfg.body('rule'))} "
            f"| {len(cfg.body('remote rule'))} | {len(cfg.body('plugin'))} | {mitm_count} |"
        )
    rows += [
        "",
        "> `Loon-routing.conf` 是 `Loon.conf` 的派生分流版：无 MITM / 脚本 / 插件，"
        "去广告插件与脚本需自行订阅（见文件头注释）。",
    ]
    print("\n".join(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
