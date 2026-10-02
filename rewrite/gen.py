#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库内快捷入口 —— 等价于 skill 版脚本的默认参数。

真正干活的实现在 skills/loon-rewrite-localize/scripts/localize.py，
本文件只做参数补全，避免同一套转换逻辑在仓库里存在两份、各自漂移。

用法（仓库根目录执行）:
    python3 rewrite/gen.py             # 重新生成 rewrite/adblock.list
    python3 rewrite/gen.py --dry-run   # 只统计，不写文件

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

cmd = [sys.executable, SCRIPT,
       '--conf', os.path.join(REPO, 'Loon.conf'),
       '--out', os.path.join(REPO, 'rewrite', 'adblock.list')]
for name in EXTRA:
    cmd += ['--extra', name]
cmd += sys.argv[1:]

sys.exit(subprocess.call(cmd))
