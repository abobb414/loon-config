#!/usr/bin/env python3
"""静态校验 Loon 分流配置：段结构、策略引用、规则收尾、图标文件。

改配置最常见的翻车不是语法错（Loon 会报），而是**引用了不存在的东西**：
策略组写了个拼错的名字、`[Rule]` 指向已删掉的组、`[Remote Rule]` 的 policy
指向一个不存在的组、图标 URL 指向仓库里已经删掉的文件。这些 Loon 不报错，
只会静默落到 FINAL 或显示空白图标，事后极难定位。

仓库只维护纯分流配置，所以 [MITM] / [Rewrite] / [Script] / [Plugin] 一律视为错误：
解密权归插件，不归这里。

用法：
    python3 scripts/validate_config.py Loon-routing.conf
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SECTION_RE = re.compile(r"^\[([^\]]+)\]\s*$")

KNOWN_SECTIONS = {
    "general",
    "proxy",
    "remote proxy",
    "proxy group",
    "remote filter",
    "rule",
    "remote rule",
    "host",
    "mitm",
    "rewrite",
    "remote rewrite",
    "script",
    "remote script",
    "plugin",
    "proxy chain",
}

# 分流配置必须不含这些段，且不能出现 MITM 白名单（出现即说明有人在手维护快照）
ROUTING_FORBIDDEN = {"mitm", "rewrite", "remote rewrite", "script", "remote script", "plugin"}

ICON_PATH_RE = re.compile(r"IconSet/Color/([A-Za-z0-9._-]+\.png)")

BUILTIN_POLICIES = {"DIRECT", "REJECT", "REJECT-DROP", "PROXY", "REJECT-TINYGIF"}

# 这些规则类型的 policy 不在第 3 段
NO_POLICY_TYPES = {"FINAL", "AND", "NOT", "OR", "GEOIP", "IP-ASN"}


def split_top(line: str, sep: str = ",") -> list[str]:
    """按顶层分隔符切分，忽略括号内的分隔符（AND/OR 组合规则要用）。"""
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    for char in line:
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        if char == sep and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(char)
    parts.append("".join(buf).strip())
    return parts


class Config:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.sections: dict[str, list[str]] = {}
        name = ""
        for raw in path.read_text(encoding="utf-8").splitlines():
            match = SECTION_RE.match(raw.strip())
            if match:
                name = match.group(1).strip().lower()
                self.sections.setdefault(name, [])
                continue
            self.sections.setdefault(name, []).append(raw)

    def body(self, name: str) -> list[str]:
        return [line.strip() for line in self.sections.get(name, []) if line.strip() and not line.strip().startswith("#")]

    def keys(self, name: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in self.body(name):
            if "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip()
        return result


def check(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"{path}: 文件不存在"]

    cfg = Config(path)

    # 1. 段名拼写
    for name in cfg.sections:
        if name and name not in KNOWN_SECTIONS:
            errors.append(f"[段] 未识别的段名 [{name}]，检查拼写")

    # 2. 必需段
    for required in ("general", "proxy group", "rule"):
        if required not in cfg.sections:
            errors.append(f"[段] 缺少必需的 [{required}]")

    # 3. 不得带解密 / 改写 / 插件
    for name in ROUTING_FORBIDDEN & set(cfg.sections):
        if cfg.body(name):
            errors.append(f"[段] 分流配置不应包含有内容的 [{name}]")
    for name, lines in cfg.sections.items():
        for line in lines:
            if re.match(r"^\s*hostname\s*=", line):
                errors.append(f"[MITM] 分流配置不应出现 hostname 白名单：{line.strip()[:60]}…")

    # 4. 策略命名空间
    groups = set(cfg.keys("proxy group"))
    nodes = set(cfg.keys("proxy"))
    subs = set(cfg.keys("remote proxy"))
    filters = set(cfg.keys("remote filter"))
    known = groups | nodes | subs | filters | BUILTIN_POLICIES

    unknown_filters = {f for f in filters if not re.match(r"^[A-Za-z][A-Za-z0-9_-]*", f)}
    for name in sorted(unknown_filters):
        errors.append(f"[Remote Filter] 名称含可疑字符：{name}")

    # 5. 策略组成员必须存在
    for group, definition in cfg.keys("proxy group").items():
        parts = split_top(definition)
        if len(parts) < 2:
            errors.append(f"[Proxy Group] {group} 定义不完整：{definition}")
            continue
        members: list[str] = []
        for part in parts[1:]:
            if not part or "=" in part:
                break
            members.append(part)
        if not members:
            errors.append(f"[Proxy Group] {group} 没有任何成员")
        for member in members:
            if member == group:
                errors.append(f"[Proxy Group] {group} 引用了自身")
            elif member not in known:
                errors.append(f"[Proxy Group] {group} 的成员 {member} 未定义")

    # 6. [Rule] 的 policy 必须存在
    rules = cfg.body("rule")
    if not rules:
        errors.append("[Rule] 为空")
    for line in rules:
        parts = split_top(line)
        kind = parts[0].upper()
        if kind == "FINAL":
            policy = parts[1] if len(parts) > 1 else ""
        elif kind in NO_POLICY_TYPES:
            policy = parts[-1]
        else:
            policy = parts[2] if len(parts) > 2 else ""
        if not policy:
            errors.append(f"[Rule] 缺少 policy：{line}")
        elif policy not in known:
            errors.append(f"[Rule] policy {policy} 未定义：{line}")
    if rules and split_top(rules[-1])[0].upper() != "FINAL":
        errors.append("[Rule] 最后一条不是 FINAL，未匹配流量会无处可去")

    # 7. [Remote Rule] 的 policy 与 URL
    for line in cfg.body("remote rule"):
        head = line.split(",")[0].strip()
        if not head.startswith(("http://", "https://")):
            errors.append(f"[Remote Rule] 首字段不是 URL：{line[:70]}…")
        match = re.search(r"policy\s*=\s*([^,\s]+)", line)
        if not match:
            errors.append(f"[Remote Rule] 缺少 policy=：{line[:70]}…")
        elif match.group(1) not in known:
            errors.append(f"[Remote Rule] policy {match.group(1)} 未定义")
        if "tag=" not in line:
            errors.append(f"[Remote Rule] 缺少 tag=：{line[:70]}…")

    # 8. Host 段语法
    for line in cfg.body("host"):
        if "=" not in line:
            errors.append(f"[Host] 缺少等号：{line[:60]}")

    # 9. 自托管图标必须真实存在（Loon 不会报 404，只会显示空白）
    root = path.resolve().parent
    icons = sorted(set(ICON_PATH_RE.findall(path.read_text(encoding="utf-8"))))
    for icon in icons:
        if not (root / "IconSet" / "Color" / icon).is_file():
            errors.append(f"[Icon] 引用了不存在的图标：IconSet/Color/{icon}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("configs", nargs="+", type=Path)
    args = parser.parse_args()

    failed = False
    for path in args.configs:
        errors = check(path)
        if errors:
            failed = True
            print(f"✗ {path}")
            for error in errors:
                print(f"    {error}")
        else:
            cfg = Config(path)
            groups = len(cfg.keys("proxy group"))
            rules = len(cfg.body("rule"))
            remote = len(cfg.body("remote rule"))
            icons = len(set(ICON_PATH_RE.findall(path.read_text(encoding="utf-8"))))
            print(f"✓ {path}  {groups} 组 / {rules} 条本地规则 / {remote} 条远程规则 / {icons} 个图标")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
