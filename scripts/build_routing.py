#!/usr/bin/env python3
"""从 Loon.conf 派生「纯分流版」配置 Loon-routing.conf。

只保留分流相关的段：General / Proxy / Remote Proxy / Proxy Group /
Remote Filter / Rule / Remote Rule / Host。
丢弃 MITM / Rewrite / Remote Rewrite / Script / Remote Script / Plugin。

为什么要有这一份：分流与去广告的失效面完全不同。分流靠 [Rule] 命中策略组，
不需要解密；去广告里的 Rewrite 类规则**必须**先解密才能看到明文 URL 与响应体。
把两者放在一个文件里，就等于把去广告的「解密权」冻结在抄写 [MITM] 的那一刻 ——
App 换接口域名、插件新增域名，清单都不会自动跟上，表现为「插件在、规则在、广告照播」。
所以这份配置只做分流，MITM 与规则交给 .lpx 插件自持（规则与 [MitM] 同文件、同源更新）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")

# 保留：纯分流所需
KEEP = {
    "general",
    "proxy",
    "remote proxy",
    "proxy group",
    "remote filter",
    "rule",
    "remote rule",
    "host",
}

# 丢弃：与解密 / 改写 / 插件相关
DROP = {
    "mitm",
    "rewrite",
    "remote rewrite",
    "script",
    "remote script",
    "plugin",
}

# General 里这些键只为 MITM 服务：没有 [Rewrite] 就没有回落 TCP 的必要，
# 留着反而白白禁掉 QUIC，让网页与视频多付一次握手代价。
DROP_GENERAL_KEYS = ("disable-udp-ports",)

CREATED_RE = re.compile(r"^#\s*Created:\s*(.*)$", re.MULTILINE)
UPDATED_RE = re.compile(r"^#\s*Last Updated:\s*(.*)$", re.MULTILINE)

HEADER = """\
# abobb's Loon 分流配置（纯分流版，无 MITM / 无脚本 / 无插件）
# Created: {created}
# Last Updated: {updated}
#
# 本文件由 scripts/build_routing.py 从 Loon.conf 自动生成，请勿手改。
# 保留段落：General / Proxy / Remote Proxy / Proxy Group / Remote Filter /
#           Rule / Remote Rule / Host
# 已移除  ：[MITM] [Rewrite] [Remote Rewrite] [Script] [Remote Script] [Plugin]
#
# ── 为什么去广告要靠自己订阅插件 ─────────────────────────────────────────
#
# 1. 两种去广告走的是两条完全不同的路
#    · 规则层 REJECT（本文件 [Rule] / [Remote Rule] 里那些）—— 不需要解密，
#      按域名/连接直接拒掉，所以在纯分流配置里照样有效。
#    · Rewrite 层（改响应体、删 JSON 字段、mock 返回值）—— **必须先 MITM 解密**。
#      域名不在 [MITM] hostname 里，HTTPS 就是一条密文隧道，rewrite 静默不执行，
#      Loon 不报错、日志也不提示，看起来「规则都在」而广告照播。
#
# 2. 在这里留一份 [MITM] 清单 = 把解密权冻结在抄写那一刻
#    hostname 是一份静态清单，不会自己长。App 换接口域名（闲鱼 2026-11 就把
#    下单/广告接口从 gw.m.goofish.com 挪到了 acs.m.taobao.com）、插件作者新增域名，
#    清单都跟不上 —— 于是出现「插件已加载、规则命中数为 0」这种最难查的状态。
#    历史上那份清单从 6 条膨胀到 188 条，仍然覆盖不全。
#
# 3. 所以：**MITM 交给插件，不要在主配置里保留快照**
#    .lpx 插件的 [MitM] 与 [Rewrite] 写在同一个文件里、随作者一次更新，
#    主配置只要不抢着维护，就不会出现两边漂移。
#    代价是插件必须由你自己订阅 —— 本仓库不转发、不镜像，避免替你承担更新责任。
#
# ── 插件与脚本去哪里订阅 ─────────────────────────────────────────────────
#
# 去广告插件（.lpx，自带 [MitM]，逐个按需添加）
#   https://kelee.one/Tool/Loon/Lpx/            ← 目录页
#   常用：BlockAdvertisers.lpx / FleaMarket_remove_ads.lpx（闲鱼）/
#          WeixinMiniPrograms_Remove_ads.lpx / JD_remove_ads.lpx /
#          Bilibili_remove_ads.lpx / QuarkBrowser_remove_ads.lpx
#   注意：打开插件即等于把它的 hostname 并入 MITM 范围，插件越多解密面越大。
#         只订你真正在用的 App。
#
# 脚本（.scripts / .js）
#   https://github.com/fmz200/wool_scripts/tree/main/Loon/script
#   tools.scripts（工具合集，含 BoxJs 依赖）/ tasks.scripts（定时任务合集）
#   面板与通知类脚本需要 BoxJs：
#   https://kelee.one/Tool/Loon/Lpx/BoxJs.lpx
#
# 规则清单（.list，本文件 [Remote Rule] 已直接引用，不用另订）
#   https://github.com/Cats-Team/AdRules          ← AdRules
#   https://github.com/blackmatrix7/ios_rule_script ← Advertising / 各 App 分流
#
# 想连插件、脚本、MITM 一起用 → 用 Loon.conf（主配置），不要用这一份。
# ─────────────────────────────────────────────────────────────────────────
"""


def read_meta(text: str) -> tuple[str, str]:
    created = CREATED_RE.search(text)
    updated = UPDATED_RE.search(text)
    return (
        created.group(1).strip() if created else "unknown",
        updated.group(1).strip() if updated else "unknown",
    )


def split_sections(text: str) -> list[tuple[str, list[str]]]:
    """切成 [(段名小写, 行列表)]；段名之前的行归属到 "" 段。"""
    blocks: list[tuple[str, list[str]]] = [("", [])]
    for line in text.splitlines():
        match = SECTION_RE.match(line.strip())
        if match:
            blocks.append((match.group(1).strip().lower(), [line.rstrip()]))
        else:
            blocks[-1][1].append(line.rstrip())
    return blocks


def strip_general_keys(lines: list[str]) -> list[str]:
    """删掉只为 MITM 服务的键，连同紧挨着的说明注释。"""
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if any(stripped.startswith(f"{key} ") or stripped.startswith(f"{key}=") for key in DROP_GENERAL_KEYS):
            # 回看：上一行若是解释这个键的注释，一起删掉
            if kept and kept[-1].lstrip().startswith("#") and (
                "MITM" in kept[-1] or "QUIC" in kept[-1]
            ):
                kept.pop()
            continue
        kept.append(line)
    return kept


def collapse_blank(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line)
    while out and not out[-1].strip():
        out.pop()
    return out


def build(source: Path) -> str:
    text = source.read_text(encoding="utf-8")
    created, updated = read_meta(text)

    body: list[str] = []
    unknown: list[str] = []
    emitted: set[str] = set()

    for name, lines in split_sections(text):
        if name == "":
            # 源文件头部说明只保留日期，正文换成上面的 HEADER
            continue
        if name in DROP:
            continue
        if name not in KEEP:
            unknown.append(name)
            continue
        if name == "general":
            lines = strip_general_keys(lines)
        emitted.add(name)
        body.extend(lines)
        body.append("")

    missing = [name for name in ("general", "proxy group", "rule") if name not in emitted]
    if missing:
        raise SystemExit(f"源配置缺少必需段：{', '.join(missing)}")
    if unknown:
        print(f"警告：跳过了未识别的段 {unknown}，请确认是否需要保留", file=sys.stderr)

    header = HEADER.format(created=created, updated=updated)
    return "\n".join(collapse_blank(header.splitlines() + [""] + body)) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="Loon.conf", type=Path)
    parser.add_argument("--output", default="Loon-routing.conf", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="只比对，不写盘：产物与当前文件不一致时返回 1",
    )
    args = parser.parse_args()

    rendered = build(args.source)

    if args.check:
        if not args.output.exists():
            print(f"{args.output} 不存在", file=sys.stderr)
            return 1
        if args.output.read_text(encoding="utf-8") != rendered:
            print(f"{args.output} 与 {args.source} 不同步，请运行 build_routing.py", file=sys.stderr)
            return 1
        print(f"{args.output} 与 {args.source} 同步")
        return 0

    if args.output.exists() and args.output.read_text(encoding="utf-8") == rendered:
        print(f"{args.output} 无变化")
        return 0

    args.output.write_text(rendered, encoding="utf-8")
    lines = len(rendered.splitlines())
    sections = [line for line in rendered.splitlines() if SECTION_RE.match(line.strip())]
    print(f"已生成 {args.output}：{lines} 行 / {len(sections)} 段 -> {' '.join(sections)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
