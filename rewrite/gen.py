#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库内快捷入口 —— 等价于 skill 版脚本的默认参数。

真正干活的实现在 skills/loon-rewrite-localize/scripts/localize.py，
本文件只做参数补全，避免同一套转换逻辑在仓库里存在两份、各自漂移。

用法（仓库根目录执行）:
    python3 rewrite/gen.py              # 重新生成 rewrite/adblock.lpx（自持插件）
    python3 rewrite/gen.py --dry-run    # 只统计，不写文件
    python3 rewrite/gen.py --legacy     # 退回旧行为：生成 rewrite/adblock.list

为什么默认改成 .lpx：
    旧方案把规则放在 adblock.list、MitM 白名单放在 Loon.conf 的 [MitM]：
    hostname 段，两边靠人工对账。实测漂移过一次 —— 311 条规则里 244 条的
    解密权只来自某一个插件、22 条完全没覆盖，插件一挂那批规则就静默一起死。
    .lpx 里 [Rewrite] 和 [MitM] 同一次生成、同一个文件，不存在对账问题；
    而且规则用新版语法原样保留，body.mock / json.jq_file 这类旧语法表达不了
    的规则也不用跳过（现在有 13 条属于这类，B 站开屏就是其中之一）。

想换成别的配置文件 / 输出路径，直接用 skill 版脚本：
    python3 skills/loon-rewrite-localize/scripts/localize.py --help
"""

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, 'skills', 'loon-rewrite-localize', 'scripts', 'localize.py')

# 真机配置里启用、但公开仓库 [Plugin] 段未列出的插件。
# 对没有安装这些插件的环境毫无影响（正则不匹配即不生效）。
EXTRA = ['QuarkBrowser_remove_ads', '12306_remove_ads']

if not os.path.exists(SCRIPT):
    sys.exit('找不到 %s —— 请确认 skills/loon-rewrite-localize/ 是否完整' % SCRIPT)

legacy = '--legacy' in sys.argv
argv = [a for a in sys.argv[1:] if a != '--legacy']

cmd = [sys.executable, SCRIPT,
       '--conf', os.path.join(REPO, 'Loon.conf'),
       '--emit', 'list' if legacy else 'lpx',
       '--out', os.path.join(REPO, 'rewrite',
                             'adblock.list' if legacy else 'adblock.lpx')]
for name in EXTRA:
    cmd += ['--extra', name]
cmd += argv

sys.exit(subprocess.call(cmd))
