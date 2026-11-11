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

推荐用法 —— --emit lpx（2026-11-11 起）:
    python3 localize.py --conf Loon.conf --emit lpx --out rewrite/adblock.lpx

    生成一个「自持插件」：规则用新版语法【原样保留】（一条不丢，包括旧语法
    表达不了的 body.mock / jq_file / body.replace），同时把各个插件的 [MitM]
    hostname 合并进同一个文件的 [MitM] 段。

    为什么换成这个：旧 .list 方案里「规则在 adblock.list、MitM 白名单在
    Loon.conf」，两边靠人工对账，实测已经漂移过一次 —— 311 条规则里 244 条
    的解密权只来自某一个插件、22 条完全没覆盖，插件一挂那批规则就静默一起死。
    lpx 把两者放进同一个文件、同一次生成，物理上不存在对账问题。

    主配置侧只需：[Plugin] 里挂一行 lpx 的 URL，撤掉 [Remote Rewrite] 的
    adblock.list，[MitM] hostname 回落到真正需要手写的那几条。

    --emit list（默认）保留旧行为，用于回退对照。

参考: Loon 官方文档《复写（旧版语法）》 https://nsloon.app/docs/Rewrite/
      Loon 官方文档《插件》 https://nsloon.app/docs/Plugin/
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

# ---------------------------------------------------------------- lpx 模板
# 生成一个自持插件：新版语法规则 + 合并后的 [MitM]。
# 注意：正文里【不写普通 # 注释行】。kelee 的插件正文全是纯规则，没有先例，
# 万一解析器不认注释会让整份规则静默失效 —— 说明性文字一律放进 #!desc。
LPX_TPL = """#!name={name}
#!desc={desc}
#!author=abobb
#!homepage=https://github.com/abobb414/loon-config
#!loon_version={loon_version}
#!date={date}
#!tag=去广告
"""

LPX_LOON_VERSION = '3.5.1(978)'

LPX_DESC = (
    '由 localize.py 从 kelee 去广告插件的 [Rewrite] 逐条固化而来，规则用新版语法原样保留，'
    '并合并各插件的 [MitM] hostname 一起发布。'
    '\\n\\n为什么要固化：插件规则会随作者更新而变动，行为不由自己掌控；'
    '而旧版 .list 方案把规则和解密白名单分放在两个文件里，靠人工对账，'
    '实测已漂移过（311 条规则里 244 条的 MitM 解密权只来自某一个插件）。'
    '本插件把两者同源生成，插件停用/更新失败都不再影响这些规则。'
    '\\n\\n本文件由 rewrite/gen.py 自动生成，请勿手工编辑。'
)

# 已被自有方案接管、不能再固化进来的规则（按 URL 正则匹配）。
#
# 闲鱼（FleaMarket_remove_ads）：2026-11 上游把开屏接口换成 splash.ads/2.0，
# 广告不再走 adMap，而是下发一个 cacheAd 引用、由 App 读本地缓存播放——所以
# request 阶段 reject_dict(200)（返回空 adMap）并不会去掉广告，反而把响应掐断，
# 让改写 body 的方案没机会执行。正确做法是放行响应、由脚本清 cacheAd/cacheAdInfo/dspList。
# 同理悬浮与圈子两条也要让位（Response Body Rewrite 命中时 Response Script 不执行）。
# 这三条由主配置 [Script] 里挂的 xianyu 脚本负责，固化里必须让路。
CONFLICT_SKIP = [
    (r'idlecommerce\.splash\.(async\.)?ads', '开屏：需放行响应后改 body'),
    (r'mtop\.taobao\.idle\.user\.strategy\.list', '悬浮策略：由脚本按类型过滤'),
    (r'idlehome\.home\.circle\.list', '圈子追踪：由脚本清理 trackParams'),
]


def conflict_reason(rule):
    # 规则里的点被转义成 \.，先还原成普通点再匹配，免得每个 pattern 都要写 \\?\.
    norm = rule.replace('\\.', '.').replace('\\/', '/')
    for pat, why in CONFLICT_SKIP:
        if re.search(pat, norm):
            return why
    return None


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
    另外 UA 必须冒充 Loon：源站按客户端身份放行，形态是「Loon/ 前缀锚定 + CFNetwork/ + Darwin/」。
    实测同一出口同一 URL —— curl/浏览器/脚本自取名 → 403；仅 'Loon/998' → 403（缺 CFNetwork、Darwin）；
    'X Loon/998 …' → 403（Loon/ 不在开头）；'Loon/3.5.1 CFNetwork/… Darwin/…' → 200。
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


def section_lines(text, name):
    """取出某个 [Section] 段的有效行（去注释去空行）。

    段名大小写不敏感：kelee 插件的 MitM 段写作 [MitM]，主配置里也见过 [MITM]，
    两者都得认，否则会漏掉整段 hostname。
    """
    out, inblk = [], False
    for s in text.splitlines():
        s = s.strip()
        if s.startswith('[') and s.endswith(']'):
            inblk = (s[1:-1].strip().lower() == name.lower())
            continue
        if inblk and s and not s.startswith('#'):
            out.append(s)
    return out


def rewrite_block(text):
    """取出 [Rewrite] 段的有效规则行（去注释去空行）。"""
    return section_lines(text, 'Rewrite')


def mitm_hostnames(text):
    """取出 [MitM] 段的 hostname（支持多行，剔除 Surge 专有的 %APPEND%）。"""
    out = []
    for line in section_lines(text, 'MitM'):
        m = re.match(r'^hostname\s*=\s*(.+)$', line, re.I)
        if not m:
            continue
        for h in m.group(1).split(','):
            h = h.strip()
            if h and h != '%APPEND%':
                out.append(h)
    return out


def _expand_alts(h, depth=0):
    """展开 (a|b) / (?:a|b) 这类二选一，返回具体域名列表。"""
    m = re.search(r'\(\??:?([^()]*\|[^()]*)\)', h)
    if not m or depth > 5:
        return [h]
    out = []
    for alt in m.group(1).split('|'):
        out += _expand_alts(h[:m.start()] + alt + h[m.end():], depth + 1)
    return out


def rule_hosts(rule):
    """从一条复写规则的正则里反推它要解密的域名。

    这一步是 lpx 方案的关键：插件的 [MitM] 并不是规则域名的超集。
    实测 311 条固化规则里有 22 条打向插件从未声明过的域名（腾讯文档 kdocs、
    高德 oss.amap.com、淘宝 guide-acs、菜鸟 e2e-mtop 等），只合并各插件
    [MitM] 的话这些规则还是发不出去。所以必须再用规则本身兜一遍。
    """
    m = re.search(r'\$\{url\}\s*~=\s*/(.*)/i', rule, re.S)
    if not m:
        return []
    rx = m.group(1).lstrip('^').replace('\\/', '/')
    mm = re.match(r'https?://([^/]*)', rx)
    if not mm:
        return []
    raw = mm.group(1).replace('\\.', '.').replace('\\-', '-')
    out = []
    for h in _expand_alts(raw):
        # 正则量词 -> 通配符。注意只吃【带量词】的形态：
        # 单个 `.` 是域名分隔符，被误吞就变成 api*example*com 这种废域名。
        h = re.sub(r'\\d\?', '*', h)
        h = re.sub(r'\\w[+*]', '*', h)
        h = re.sub(r'\.\+', '*', h)
        h = re.sub(r'\.\*', '*', h)
        h = re.sub(r'[\\^$+?{}\[\]()|]', '', h).strip('.')
        h = re.sub(r'\*+', '*', h)
        if h and re.fullmatch(r'[a-z0-9.*_-]+', h) and h not in out:
            out.append(h)
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
    ap.add_argument('--emit', choices=('list', 'lpx'), default='list',
                    help='list=旧语法 .list（旧行为）；lpx=自持插件（规则+[MitM] 同源生成，推荐）')
    ap.add_argument('--name', default='去广告固化（self-hosted）',
                    help='--emit lpx 时的 #!name')
    ap.add_argument('--desc', default=LPX_DESC, help='--emit lpx 时的 #!desc')
    ap.add_argument('--with-rules', action='store_true',
                    help='--emit lpx 时把插件 [Rule] 段的域名规则一并收进来'
                         '（注意与 AdRules 大面积重叠，默认不收）')
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
        # 别把自己的产物当成插件再吃回来：[Plugin] 里挂着 rewrite/adblock.lpx，
        # 不过滤的话下一次生成会把它算作一个插件，规则翻倍并且自我循环。
        if re.search(r'/rewrite/adblock\.(lpx|list)$', u):
            continue
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    urls = uniq

    if not urls:
        sys.exit('没有插件可处理：请给 --conf，或 --plugin / --plugin-url')

    out = [HEADER.rstrip('\n')]
    stat, skipped, failed, ok_plugins = Counter(), Counter(), [], []
    conflict = Counter()   # [(插件名, 原因)] -> 条数
    kept = []           # lpx 模式：[{name, rules, mitm, rhost, rule}]

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

        keep_rule = []
        for r in rules:
            why = conflict_reason(r)
            if why:
                conflict[(name, why)] += 1
                continue
            keep_rule.append(r)
        rules = keep_rule
        if not rules:
            continue

        if args.emit == 'lpx':
            # 原样保留新版语法：不转换、不跳过，转换器表达不了的那几类也照收
            rhost = []
            for r in rules:
                for h in rule_hosts(r):
                    if h not in rhost:
                        rhost.append(h)
            kept.append({'name': name, 'rules': rules,
                         'mitm': mitm_hostnames(text),
                         'rhost': rhost,
                         'rule': section_lines(text, 'Rule') if args.with_rules else []})
            ok_plugins.append(name)
            for r in rules:
                nm = CALLNAME_RE.match(r)
                stat[nm.group(1) if nm else '?'] += 1
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

    if args.emit == 'lpx':
        hosts = []
        for e in kept:
            for h in e['mitm'] + e['rhost']:
                if h not in hosts:
                    hosts.append(h)
        only_rule = [h for e in kept for h in e['rhost'] if h not in e['mitm']]
        print('插件 %d 个 -> 成功 %d 个，规则 %d 条（新版语法原样保留，无跳过）'
              % (len(urls), len(ok_plugins), sum(stat.values())))
        print('    MitM hostname 合并 %d 条（插件声明 + 规则反推）'
              % len(hosts))
        if only_rule:
            u = []
            for h in only_rule:
                if h not in u:
                    u.append(h)
            print('    其中 %d 个域名插件从未声明、只靠规则反推才补上：%s'
                  % (len(u), ','.join(u)))
        if args.with_rules:
            print('    [Rule] 段一并收集 %d 条' % sum(len(e['rule']) for e in kept))
    else:
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
    if conflict:
        print('  让路（已由自有脚本接管，不固化）:')
        for (n, why), c in sorted(conflict.items()):
            print('    [%s] %s x%d' % (n, why, c))

    if args.dry_run:
        print('(dry-run，未写文件)')
        return
    if not ok_plugins:
        sys.exit('没有任何规则转换成功，不写文件')
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or '.', exist_ok=True)

    if args.emit == 'lpx':
        lines = [LPX_TPL.format(name=args.name, desc=args.desc,
                                loon_version=LPX_LOON_VERSION,
                                date=time.strftime('%Y-%m-%d %H:%M:%S')).rstrip('\n')]
        lines.append('[Rewrite]')
        for e in kept:
            lines.extend(e['rules'])
        if args.with_rules:
            lines.append('[Rule]')
            seend = set()
            for e in kept:
                for r in e['rule']:
                    if r not in seend:
                        seend.add(r)
                        lines.append(r)
        lines.append('[MitM]')
        lines.append('hostname = ' + ','.join(hosts))
        body = '\n'.join(lines) + '\n'
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(body)
        print('已写入: %s（%d 条规则 / %d 个域名 / %.1f KB）'
              % (args.out, sum(stat.values()), len(hosts), len(body) / 1024.0))
        return

    with open(args.out, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(out) + '\n')
    print('已写入: %s（%d 行）' % (args.out, len(out)))


if __name__ == '__main__':
    main()
