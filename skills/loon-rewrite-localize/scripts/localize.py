#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
localize.py —— 把 Loon 插件（.lpx）的 [Rewrite] 规则固化成「旧版语法」规则文件。

用法:
    # 从某个 Loon.conf 的 [Plugin] 段自动收集插件
    python3 localize.py --conf /path/to/Loon.conf --out adblock.list

    # 只转换指定的几个插件（不读配置文件）
    python3 localize.py --plugin Cainiao_remove_ads --plugin JD_remove_ads --out adblock.list

    # 追加不在此配置里的插件（真机版有、公开版没有的情况）
    python3 localize.py --conf Loon.conf --extra QuarkBrowser_remove_ads --out adblock.list

    # 先干跑看统计，不写文件
    python3 localize.py --conf Loon.conf --dry-run

为什么需要它:
    插件规则写成新版脚本语法：
        request  if ${url} ~= /^https:\\/\\/.../i then reject_dict(200)
        response if ${url} ~= /.../i           then response.json.jq("...")
    该语法自 Loon 3.5.1(978) 引入，且插件头部常写 #!loon_version=3.5.1(998)；
    客户端 build 不够时规则被【静默忽略】—— MitM 照常解密（有紫锁），
    但 rewrite 一条不执行，表现为「广告拦不住、Reject 页又没有记录」。
    插件还会随作者更新而变化，行为不由自己掌控。

    依据官方文档《匹配顺序》：本地配置的 [Rewrite] 优先于插件的 [Rewrite]。
    因此把规则转成旧版语法（Build 729+ 全兼容）放进自己的规则文件即可根治。

动作名对应关系（新版 -> 旧版）:
    reject_dict(200)      -> reject-dict              (HTTP 200 + {})
    reject(404)           -> reject-dict              （旧语法无状态码参数）
    reject_img(200)       -> reject-img               (HTTP 200 + 1x1 图)
    reject_array(200)     -> reject-array
    response.json.jq(x)   -> response-body-json-jq 'x'
    response.json.delete  -> response-body-json-del
    response.json.replace -> response-body-json-replace
    response.header.add   -> response-header-add
    redirect(307, url)    -> 307 url

无法用旧语法等价表达（脚本会跳过并在报告中列出）:
    response.body.mock / response.json.jq_file / response.body.replace

参考: Loon 官方文档《复写（旧版语法）》 https://nsloon.app/docs/Rewrite/
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

KEELE = 'https://kelee.one/Tool/Loon/Lpx/%s.lpx'
UA = 'Loon/998 CFNetwork/3896.100.1.1.1 Darwin/27.0.0'

HEADER = """# ============================================================
# 去广告复写规则（旧版语法 / Build 729+ 全兼容）
# ------------------------------------------------------------
# 本文件由 localize.py 自动生成，请勿手工编辑。
#
# 由来：各 Loon 去广告插件的 [Rewrite] 逐条等价转换而来。
#
# 为什么要固化成本地规则：
#   插件规则使用新版脚本语法，形如
#       request  if ${url} ~= /.../i then reject_dict(200)
#       response if ${url} ~= /.../i then response.json.jq("...")
#   该语法需客户端 build >= 978，插件自身常要求 998；build 不够时规则被静默忽略。
#   且插件随作者更新而变动，行为不由自己掌控。
#   本文件把规则固化下来：插件怎么更新都不影响，也不会被 App 回写主配置时带走。
#
# 动作名对应关系（新版 -> 旧版）：
#   reject_dict(200) / reject(404) -> reject-dict          (HTTP 200 + {})
#   reject_img(200)                -> reject-img           (HTTP 200 + 1x1 图)
#   response.json.jq(x)            -> response-body-json-jq 'x'
#   response.json.delete           -> response-body-json-del
#   response.json.replace          -> response-body-json-replace
#   response.header.add            -> response-header-add
#   redirect(307,url)              -> 307 url
#
# 依据：Loon 官方文档《复写（旧版语法）》https://nsloon.app/docs/Rewrite/
# ============================================================
"""

# 新版脚本语法：  request if ${url} ~= /<正则>/i then <动作>(<参数>)
NEW_SYNTAX_RE = re.compile(
    r'^(request|response)\s+if\s+\$\{url\}\s+~=\s+/(.*)/i\s+then\s+(.+)$', re.S)
ACTION_RE = re.compile(r'^([a-zA-Z_.]+)\((.*)\)$', re.S)
CALLNAME_RE = re.compile(r'^.*?then\s+([a-zA-Z_.]+)\(')


# ---------------------------------------------------------------- 采集

def plugin_urls(conf_path):
    """从 Loon.conf 的 [Plugin] 段取出 .lpx 地址。"""
    urls, inblk = [], False
    with open(conf_path, encoding='utf-8', errors='replace') as fh:
        for ln in fh:
            s = ln.strip()
            if s.startswith('['):
                inblk = (s == '[Plugin]')
                continue
            if not inblk or not s or s.startswith('#'):
                continue
            m = re.match(r'^(https?://\S+?\.lpx)\s*,', s)
            if m:
                urls.append(m.group(1))
    return urls


def fetch(url, retries=6, ua=UA, timeout=30):
    """下载插件。源站偶发 SSL UNEXPECTED_EOF / 连接中断，必须退避重试。

    不加重试的话，30 个插件会稳定掉 5 个左右（规则数从 311 掉到 192）。
    另外必须带 Loon 的 UA：裸 curl / 浏览器 UA 会被源站判定非客户端而 403。
    """
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': ua, 'Connection': 'close'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as exc:            # noqa: BLE001 - 网络异常种类多，一律重试
            last = exc
            time.sleep(1.2 * (i + 1))
    raise last


def rewrite_block(text):
    """取出 [Rewrite] 段的有效规则行（去注释去空行）。"""
    out, inblk = [], False
    for s in text.splitlines():
        s = s.strip()
        if s.startswith('['):
            inblk = (s == '[Rewrite]')
            continue
        if inblk and s and not s.startswith('#'):
            out.append(s)
    return out


# ---------------------------------------------------------------- 转换

def esc(expr):
    """旧版语法按空格分隔参数：表达式内的空格 / 单引号必须转义。

    官方文档《复写（旧版语法）》明确要求。漏掉这一步时，含空格的 jq 表达式
    （例如 `if .data.x == "y" then . else ... end`）会被截断成错误的参数。
    """
    return expr.replace(' ', r'\x20').replace("'", r'\x27')


def convert(rule):
    """新版语法规则 -> 旧版语法规则；无法转换返回 None。"""
    m = NEW_SYNTAX_RE.match(rule)
    if not m:
        return None
    rx, act = m.group(2), m.group(3).strip()

    nm = ACTION_RE.match(act)
    if not nm:
        return None
    fn, args = nm.group(1), nm.group(2).strip()
    newact = None

    if fn in ('reject_dict', 'reject'):
        newact = 'reject-dict'
    elif fn == 'reject_img':
        newact = 'reject-img'
    elif fn == 'reject_array':
        newact = 'reject-array'
    elif fn == 'redirect':
        mm = re.match(r'^(\d+)\s*,\s*"(.*)"$', args, re.S)
        if mm:
            newact = '%s %s' % (mm.group(1), mm.group(2))
    elif fn == 'response.json.jq':
        mm = re.match(r'^"(.*)"$', args, re.S)
        if mm:
            newact = "response-body-json-jq '%s'" % esc(mm.group(1).replace('\\"', '"'))
    elif fn == 'response.json.delete':
        try:
            v = json.loads(args)
            paths = v if isinstance(v, list) else [v]
            newact = 'response-body-json-del ' + ' '.join(esc(str(p)) for p in paths)
        except Exception:
            pass
    elif fn == 'response.json.replace':
        mm = re.match(r'^(\[.*?\])\s*,\s*(\[.*\])$', args, re.S)
        if mm:
            try:
                ks = json.loads(mm.group(1))
                vs = json.loads(mm.group(2))
                if len(ks) == len(vs):
                    newact = 'response-body-json-replace ' + ' '.join(
                        '%s %s' % (k, v) for k, v in zip(ks, vs))
            except Exception:
                pass
    elif fn == 'response.header.add':
        mm = re.match(r'^"(.*?)"\s*,\s*"(.*)"$', args, re.S)
        if mm:
            newact = 'response-header-add %s %s' % (mm.group(1), mm.group(2))

    if newact is None:
        return None

    # 坑：插件的正则【自带 ^】，此处不能无脑再加，否则生成 ^^https:\/\/...
    if not rx.startswith('^'):
        rx = '^' + rx
    return '%s %s' % (rx, newact)


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser(description='把 Loon 插件 [Rewrite] 固化为旧版语法规则')
    ap.add_argument('--conf', action='append', default=[],
                    help='Loon.conf 路径（可重复）。多份配置的插件会合并去重——'
                         '真机版与公开版插件清单不同时，两份都传即可。')
    ap.add_argument('--plugin', action='append', default=[],
                    help='直接指定插件名（可重复），不读配置文件')
    ap.add_argument('--plugin-url', action='append', default=[],
                    help='直接指定插件完整 URL（可重复）')
    ap.add_argument('--extra', action='append', default=[],
                    help='额外插件名（走 kelee 默认地址），用于补配置文件里没有的')
    ap.add_argument('--out', default='adblock.list', help='输出文件（默认 adblock.list）')
    ap.add_argument('--ua', default=UA, help='下载用 UA，默认 Loon/998 ...')
    ap.add_argument('--dry-run', action='store_true', help='只统计，不写文件')
    args = ap.parse_args()

    urls = []
    for conf in args.conf:
        if not os.path.exists(conf):
            sys.exit('找不到 %s' % conf)
        urls += plugin_urls(conf)
    urls += [KEELE % n for n in args.plugin]
    urls += list(args.plugin_url)
    urls += [KEELE % n for n in args.extra]

    seen, uniq = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    urls = uniq

    if not urls:
        sys.exit('没有插件可处理：请给 --conf，或 --plugin / --plugin-url')

    out = [HEADER.rstrip('\n')]
    stat, skipped, failed, ok_plugins = Counter(), Counter(), [], []

    for url in urls:
        name = os.path.basename(url).rsplit('.lpx', 1)[0]
        try:
            text = fetch(url, ua=args.ua)
        except Exception as exc:            # noqa: BLE001
            failed.append((name, '%s: %s' % (type(exc).__name__, str(exc)[:60])))
            continue
        rules = rewrite_block(text)
        if not rules:
            continue
        conv = []
        for r in rules:
            res = convert(r)
            nm = CALLNAME_RE.match(r)
            key = nm.group(1) if nm else '?'
            if res is None:
                skipped[(name, key)] += 1
                continue
            conv.append(res)
            stat[key] += 1
        if conv:
            ok_plugins.append(name)
            out.append('')
            out.append('# ===== %s（%d 条）=====' % (name, len(conv)))
            out.extend(conv)

    print('插件 %d 个 -> 成功 %d 个，规则 %d 条'
          % (len(urls), len(ok_plugins), sum(stat.values())))
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        print('    %-26s %4d' % (k, v))
    if skipped:
        print('  跳过（旧语法无法等价表达，仍由插件提供）:')
        for (n, fn), c in sorted(skipped.items()):
            print('    [%s] %s x%d' % (n, fn, c))
    if failed:
        print('  下载失败:')
        for n, e in failed:
            print('    [%s] %s' % (n, e))

    if args.dry_run:
        print('(dry-run，未写文件)')
        return
    if not ok_plugins:
        sys.exit('没有任何规则转换成功，不写文件')
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out) + '\n')
    print('已写入: %s（%d 行）' % (args.out, len(out)))


if __name__ == '__main__':
    main()
