#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Loon 插件的 [Rewrite] 规则固化成旧版语法规则文件。

用法（在仓库根目录执行）:
    python3 rewrite/gen.py

做什么:
  1. 读取 Loon.conf 的 [Plugin] 段，取出所有 .lpx 插件地址
  2. 逐个下载（kelee.one 需要带 Loon 的 UA，否则 403）
  3. 把每个插件 [Rewrite] 段里「新版脚本语法」的规则逐条等价转换为「旧版语法」
  4. 汇总写成 rewrite/adblock.list，供主配置用 [Remote Rewrite] 引用

为什么需要它:
  插件规则写成 request if ${url} ~= /.../i then reject_dict(200) 这种新版脚本语法，
  且插件会随作者更新而变化，行为不由自己掌控。固化成本地规则文件后，
  插件怎么更新都不影响生效。

动作名对应关系（新版 -> 旧版）:
  reject_dict(200)      -> reject-dict                (HTTP 200 + {})
  reject(404)           -> reject-dict
  reject_img(200)       -> reject-img                 (HTTP 200 + 1x1 图)
  reject_array(200)     -> reject-array
  response.json.jq(x)   -> response-body-json-jq 'x'
  response.json.delete  -> response-body-json-del
  response.json.replace -> response-body-json-replace
  response.header.add   -> response-header-add
  redirect(307, url)    -> 307 url

无法等价转换、仍由插件提供的动作:
  response.body.mock / response.json.jq_file / response.body.replace

参考: Loon 官方文档《复写（旧版语法）》 https://nsloon.app/docs/Rewrite/
"""

import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONF = os.path.join(REPO, 'Loon.conf')
OUT = os.path.join(REPO, 'rewrite', 'adblock.list')
UA = 'Loon/998 CFNetwork/3896.100.1.1.1 Darwin/27.0.0'
KEELE = 'https://kelee.one/Tool/Loon/Lpx/%s.lpx'

# 真机配置里启用、但公开仓库的 [Plugin] 段未列出的插件，规则一并固化。
# 对没有安装这些插件的环境毫无影响（正则不匹配即不生效）。
EXTRA_PLUGINS = [
    'QuarkBrowser_remove_ads',
    '12306_remove_ads',
]

HEADER = """# ============================================================
# 去广告复写规则（旧版语法 / Build 729+ 全兼容）
# ------------------------------------------------------------
# 本文件由 rewrite/gen.py 自动生成，请勿手工编辑。
# 重新生成: python3 rewrite/gen.py
#
# 由来：Loon.conf [Plugin] 段中各去广告插件的 [Rewrite] 逐条等价转换而来。
#
# 为什么要固化成本地规则：
#   插件规则使用新版脚本语法，形如
#       request  if ${url} ~= /.../i then reject_dict(200)
#       response if ${url} ~= /.../i then response.json.jq("...")
#   且插件会随作者更新而变动，行为不由自己掌控。本文件把规则固化下来，
#   插件怎么更新都不影响；也不会被 App 回写主配置时带走。
#
# 动作名对应关系（新版 -> 旧版）：
#   reject_dict(200)      -> reject-dict          (HTTP 200 + {})
#   reject(404)           -> reject-dict
#   reject_img(200)       -> reject-img           (HTTP 200 + 1x1 图)
#   response.json.jq(x)   -> response-body-json-jq 'x'
#   response.json.delete  -> response-body-json-del
#   response.json.replace -> response-body-json-replace
#   redirect(307,url)     -> 307 url
#
# 依据：Loon 官方文档《复写（旧版语法）》https://nsloon.app/docs/Rewrite/
# ============================================================
"""


def plugin_urls(conf_path):
    """从 Loon.conf 的 [Plugin] 段取出插件地址。"""
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


def fetch(url, retries=6):
    """下载插件内容。kelee.one 偶发 SSL EOF / 连接中断，必须重试。"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': UA,
                'Connection': 'close',
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as exc:
            last = exc
            time.sleep(1.2 * (i + 1))
    raise last


def rewrite_block(text):
    """取出 [Rewrite] 段的有效规则行。"""
    lines, inblk = [], False
    for s in text.splitlines():
        s = s.strip()
        if s.startswith('['):
            inblk = (s == '[Rewrite]')
            continue
        if inblk and s and not s.startswith('#'):
            lines.append(s)
    return lines


def convert(rule):
    """新版语法规则 -> 旧版语法规则；无法转换时返回 None。"""
    m = re.match(
        r'^(request|response)\s+if\s+\$\{url\}\s+~=\s+/(.*)/i\s+then\s+(.+)$',
        rule, re.S)
    if not m:
        return None
    rx, act = m.group(2), m.group(3).strip()

    nm = re.match(r'^([a-zA-Z_.]+)\((.*)\)$', act, re.S)
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
            expr = mm.group(1).replace('\\"', '"')
            # 旧语法按空格分隔参数，空格需转义为 \x20（官方文档要求）
            expr = expr.replace(' ', r'\x20').replace("'", r'\x27')
            newact = "response-body-json-jq '%s'" % expr
    elif fn == 'response.json.delete':
        try:
            v = json.loads(args)
            paths = v if isinstance(v, list) else [v]
            newact = 'response-body-json-del ' + ' '.join(
                str(p).replace(' ', r'\x20') for p in paths)
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
    if not rx.startswith('^'):
        rx = '^' + rx
    return '%s %s' % (rx, newact)


def main():
    if not os.path.exists(CONF):
        sys.exit('找不到 %s' % CONF)

    urls = plugin_urls(CONF)
    for n in EXTRA_PLUGINS:
        u = KEELE % n
        if u not in urls:
            urls.append(u)
    if not urls:
        sys.exit('[Plugin] 段里没有找到 .lpx 条目')

    out = [HEADER.rstrip('\n')]
    stat, skipped, failed = Counter(), Counter(), []

    for url in urls:
        name = os.path.basename(url)[:-4]
        try:
            text = fetch(url)
        except Exception as exc:
            failed.append((name, str(exc)[:60]))
            continue
        rules = rewrite_block(text)
        if not rules:
            continue
        conv = []
        for r in rules:
            res = convert(r)
            if res is None:
                nm = re.match(r'^.*?then\s+([a-zA-Z_.]+)\(', r)
                skipped[(name, nm.group(1) if nm else '?')] += 1
                continue
            conv.append(res)
            nm = re.match(r'^.*?then\s+([a-zA-Z_.]+)\(', r)
            stat[nm.group(1) if nm else '?'] += 1
        if conv:
            out.append('')
            out.append('# ===== %s（%d 条）=====' % (name, len(conv)))
            out.extend(conv)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out) + '\n')

    print('转换完成: %s' % OUT)
    print('  插件数: %d   规则数: %d' % (len(urls), sum(stat.values())))
    for k, v in sorted(stat.items(), key=lambda x: -x[1]):
        print('    %-26s %4d' % (k, v))
    if skipped:
        print('  跳过（无法用旧语法等价表达）:')
        for (n, fn), c in sorted(skipped.items()):
            print('    [%s] %s x%d' % (n, fn, c))
    if failed:
        print('  下载失败:')
        for n, e in failed:
            print('    [%s] %s' % (n, e))


if __name__ == '__main__':
    main()
