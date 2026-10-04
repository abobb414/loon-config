---
name: loon-rewrite-localize
description: 把 Loon 插件（.lpx）的 [Rewrite] 去广告规则固化成自己掌控的本地规则文件，根治「插件规则用新版脚本语法、客户端 build 不够导致静默失效」与「插件自动更新、App 回写配置导致行为不可控」两类问题。含新旧语法动作映射表、可复现的转换脚本、四个坑（kelee 源站的 UA 客户端校验导致 403、正则重复锚点、jq 表达式空格未转义、源站 SSL EOF）、以及「公开仓库脱敏模板 ≠ 真机配置」的铁律。触发词：loon 插件不生效、去广告没拦住、插件规则失效、kelee 403、插件下载 403、reject_dict 不执行、response.json.jq 无效、插件升级后失效、怕插件自动更新改坏、固化插件规则、把插件规则搬到本地、loon 复写规则、Remote Rewrite、本地规则优先于插件。
version: 1.0.0
agent_created: true
read_when:
  - Loon 去广告插件不生效 / 广告照样弹
  - 插件能下载、MitM 有紫锁，但 Reject 页无记录、广告没拦住
  - 想让去广告行为不随插件更新而变动
  - 需要把插件 [Rewrite] 规则搬进本地配置或自己的仓库
  - 手改的配置被 Loon App 回写覆盖
  - 在公开仓库里维护 Loon 配置，怕把真实凭据推上去
---

# Loon 插件规则本地化（固化去广告）

## 一句话

插件规则是**别人的、会变、且依赖客户端 build**；官方文档写明「**本地配置 Rewrite 优先于插件 Rewrite**」，
所以把插件的规则转成**旧版语法**（Build 729+ 全兼容）搬进自己的规则文件，一次根治。

---

## 0. 先分清是哪一层失败

三层互不相关，**改错层完全无效**。别看到「插件不生效」就直接改规则。

```
插件不生效
 ├─ ① 下载层：带 Loon UA 的 curl 能否 200 拿到 .lpx？
 │              UA 不含「Loon/ 开头 + CFNetwork/ + Darwin/」→ 403（见坑 0，改规则无用）
 │              换成合规 UA 后仍 403 → 才轮到怀疑出口 IP 被风控
 ├─ ② 加载层：客户端 build ≥ 插件头部 #!loon_version？
 │              不够 → 升级客户端（改规则无用）
 └─ ③ 执行层：规则语法是否需要更高 build？目标是否真的被 MitM 解密？
                → 本 skill 处理的就是这一层
```

**判据必须是客户端证据，不是服务端声明。** `curl -I | grep alt-svc` 看到 `h3=":443"`
只说明服务端**支持** HTTP/3，不代表客户端真的走了 QUIC。真正的证据是 Loon 请求列表里那条请求
**有没有紫色锁**、**有没有显示完整 URL 与 Methods**：

| 请求列表里显示 | 含义 |
|---|---|
| 完整 URL + 紫锁 + `GET/POST` | MitM 已解密 → 语法层问题，看第 1 节 |
| 只有 `主机:443` + `TCP` + 无锁 | 未解密 → 域名不在 MitM 列表，或真走了 QUIC |
| 显示 `UDP` | 真走了 QUIC |

---

## 1. 判定：插件规则是不是「新版脚本语法」

```bash
# UA 必须是「Loon/ 开头 + CFNetwork/ + Darwin/」的形状，否则源站一律 403（见坑 0）
UA='Loon/998 CFNetwork/3896.100.1.1.1 Darwin/27.0.0'
curl -s -A "$UA" -o /tmp/p.lpx "https://kelee.one/Tool/Loon/Lpx/Cainiao_remove_ads.lpx"
head -3 /tmp/p.lpx                      # 看 #!loon_version=3.5.1(998)
awk '/^\[Rewrite\]/{f=1;next}/^\[/{f=0}f&&NF' /tmp/p.lpx | head
```

两种写法一眼可辨：

```ini
# 新版脚本语法（自 Loon 3.5.1(978) 引入）
request  if ${url} ~= /^https:\/\/netflow-mtop\.cainiao\.com\/gw\/.*ads/i then reject_dict(200)
response if ${url} ~= /.../i then response.json.jq("if .data.x == \"y\" then . else .data = {} end")

# 旧版语法（Build 729+ 全兼容）
^https://netflow-mtop\.cainiao\.com/gw/.*ads reject-dict
```

**静默失效的机理**：build < 978 时，新版规则被**忽略**——MitM 照常解密（所以有紫锁），
rewrite 一条都不执行。表现就是「广告拦不住，Reject 页又没有记录」。
插件头部 `#!loon_version=3.5.1(998)` 是**最低客户端版本要求**，build 号（括号里那个）不够同样不加载。

> ⚠️ 「Reject 页没记录」**本身不能单独证明失效**：只清字段（`response.json.jq`）不拦请求的规则，
> 本来就不会出现在 Reject 页。要结合「广告是否还在」一起判断。

---

## 2. 动作映射表（新版 → 旧版）

| 新版 | 旧版 | 语义 |
|---|---|---|
| `reject_dict(200)` | `reject-dict` | HTTP 200 + `{}` |
| `reject(404)` | `reject-dict` | 旧语法无状态码参数 |
| `reject_img(200)` | `reject-img` | HTTP 200 + 1×1 图 |
| `reject_array(200)` | `reject-array` | HTTP 200 + `[]` |
| `response.json.jq(x)` | `response-body-json-jq 'x'` | jq 处理响应体 |
| `response.json.delete` | `response-body-json-del` | 删 JSON 字段 |
| `response.json.replace` | `response-body-json-replace` | 替换 JSON 字段 |
| `response.header.add` | `response-header-add` | 加响应头 |
| `redirect(307, url)` | `307 url` | 重定向 |

**优先选 `reject-dict` 而不是 `reject`**：前者返回合法 JSON（HTTP 200 + `{}`），
App 的 mtop 客户端视为空响应、不弹网络错误；后者直接断连，部分 App 会提示网络异常。

**无法用旧语法等价表达（仍需插件提供，转换脚本会跳过并列出）**：
`response.body.mock`、`response.json.jq_file`、`response.body.replace`。

---

## 3. 四个坑（都踩过）

### 坑 0：下载前必须冒充 Loon —— 而且「UA 里有 Loon 字样」还不够

kelee.one 挂在 Cloudflare 后面，站方给资源路径设了**客户端身份校验**，不过关一律 403：
返回 `<title>Attention Required! | Cloudflare</title>` 的拦截页，
响应头里**没有** `cf-mitigated` —— 是**拦截（block）不是人机挑战（challenge）**，别按 challenge 去解释。

| UA | 结果 |
|---|---|
| `curl/8.4.0` / Chrome / `my-script/1.0`（脚本自己的名字） | 403 |
| `Loon/998` | 403 —— 缺 `CFNetwork/` 与 `Darwin/` |
| `X Loon/998 CFNetwork/3896 Darwin/27.0.0` | 403 —— `Loon/` 不在**开头** |
| `Loon/3.5.1 CFNetwork/1494.0.7 Darwin/23.4.0` | **200 ✅** |

规则归纳：**`Loon/` 前缀锚定 + 同时含 `CFNetwork/` 与 `Darwin/`**（`loon/` 小写也放行）。

🔴 **不要用「换出口就 200」解释 403**。同一台机器、同一个出口、同一个 URL，只换 UA 就能翻转 403/200；
反过来，「换成某国节点就绿了」也可能只是顺带换了 UA。**出口、UA、URL 三个变量分别控制**，
才有资格下结论 —— 这条错结论（「出口被 Cloudflare 挑中」）曾被写进 README，后来被推翻。

🔴 **同一坑的第二个变体**：自动化体检脚本特别容易中招，因为脚本的默认 UA 是
`Python-urllib/3.x` 或项目自取的名字，而 **Loon 本体下载插件时发的就是这个形状的 UA**，
所以「手机上一切正常、只有体检台账天天红 30 条」这种症状，第一嫌疑就是脚本的 UA。

### 坑 1：插件的正则**自带 `^`**，不要无脑再补

第一版转换器无条件加前缀，生成出 `^^https:\/\/...`，整条规则失效。
正确做法是**先判断再补**：

```python
if not rx.startswith('^'):
    rx = '^' + rx
```

### 坑 2：旧语法**按空格分隔参数**，jq 表达式里的空格必须转义

jq 表达式几乎都含空格（`if .data.x == "y" then . else ... end`），
不转义会被截断成多个错误参数。官方文档要求转义为 `\x20`，单引号另需转义为 `\x27`：

```python
def esc(expr):
    return expr.replace(' ', r'\x20').replace("'", r'\x27')
```

### 坑 3：源站偶发 `SSL: UNEXPECTED_EOF`，必须退避重试

kelee.one 会在批量下载时掐连接。**不加退避重试时，30 个插件会稳定掉 5 个左右**
（规则数从 311 掉到 192，且不报错——只是少了几节，很容易漏看）。用 6 次指数退避：

```python
for i in range(retries):
    try:
        ...
    except Exception as exc:
        last = exc
        time.sleep(1.2 * (i + 1))
```

---

## 4. 落地形态：独立规则文件 + `[Remote Rewrite]`

**为什么不能直接塞主配置**：单条规则可能极长（实测 `QuarkBrowser_remove_ads` 有一条
**25745 字符**的 mock），311 条合计约 60 KB。塞进 `Loon.conf` 后完全不可维护。

标准做法是生成独立文件、主配置只加一行引用：

```ini
[Remote Rewrite]
# 去广告规则（由 skills/loon-rewrite-localize/scripts/localize.py 固化，旧版语法）
https://raw.githubusercontent.com/<user>/<repo>/main/rewrite/adblock.list, tag=去广告固化规则, enabled=true
```

⚠️ **退化风险**：远程规则依赖 `raw.githubusercontent.com` 可达。若该域名在你的规则下加载失败，
规则会整段不生效——此时把 `adblock.list` 内容内联进主配置的 `[Rewrite]` 段即可（功能等价，只是臃肿）。

生成脚本用法：

```bash
cd <loon-config 仓库根目录>

# 仓库版 + 真机版两份配置的插件合并去重（两版插件清单常不同）
python3 skills/loon-rewrite-localize/scripts/localize.py \
  --conf Loon.conf \
  --conf ~/Library/Mobile\ Documents/iCloud~com~ruikq~decar/Documents/Configs/Loon.conf \
  --out rewrite/adblock.list

# 只统计不写文件
python3 .../localize.py --conf Loon.conf --dry-run
```

**持久化的三层含义**：

1. **抗插件更新** —— 规则在你自己的文件里，作者改插件与你无关；
2. **抗客户端 build 门槛** —— 旧语法 Build 729+ 全支持，不再看新语法 978/998 的脸色；
3. **抗 App 回写** —— 见第 6 节。

---

## 5. 🔴 铁律：公开仓库的配置是**脱敏模板**，不能与真机配置互相覆盖

同一份 `Loon.conf` 常常有两份，**内容不同、用途不同**：

| | 公开仓库版 | 真机版（iCloud） |
|---|---|---|
| `[Proxy]` 凭据 | 占位符 `192.168.1.1 / username / password` | 真实地址 / 口令 |
| WireGuard | `<client-private-key>`、`[<your-endpoint>]` | 真实私钥与端点 |
| `[Remote Proxy]` | **空** | 真实订阅 |
| 行数 | 285 | 309 |

**所以同步只能「按结构插入」，绝不能 `cp 真机版 仓库版`** —— 那会把代理口令、WG 私钥、
订阅地址一起推上公开仓库。反过来也不要拿仓库版覆盖真机版（会抹掉凭据，代理直接不可用）。

判断该往哪边同步：**规则类改动两边都要**（用脚本生成，规则内容一致）；
**凭据类内容永远只留真机版**。

---

## 6. 🔴 主配置会被 Loon App **整段回写**

真机配置路径：
`~/Library/Mobile Documents/iCloud~com~ruikq~decar/Documents/Configs/Loon.conf`

实测：只要用户在 Loon App 内**增删任何一个插件**，App 就会用内部状态**整段回写**该文件，
把你在 `[General]` 等方法手写的修复一起冲掉（实测一次丢了 5 处修补）。

应对：

- 手改这份 iCloud conf **只算临时验证**，用户一动插件就丢；
- 要持久化 → 改**仓库版**再走 Loon 导入流程，或改 App 内设置；
- 每次动这份文件前**先 stat 看 mtime**，确认没被 App 在中间改写；
- `[Remote Rewrite]` 那一行引用也可能被一起冲掉 —— 发现规则不生效时，**先确认这行还在不在**。

---

## 7. 验证判据

改完不要只说"改好了"，给出可自查的判据：

1. **规则文件语法自检**：产物里不应出现 `^^`（坑 1 的标志）；
   `grep -c '^\\^' adblock.list` 的条数应与转换统计一致。
2. **手机重载配置**（Mac 改的是 iCloud 文件，不重载不生效）。
3. **打开目标 App，看 Reject 页应出现记录**；同时看广告是否消失。
4. 两者都对 → 生效；仍无记录 → 回到第 0 节排除 ①/② 层。
5. 顺带让用户报 **Loon 版本号**（设置 → 关于，格式 `3.5.x(build)`）——
   build 号决定插件本身还加不加载。

---

## 8. 本 skill 附带的脚本

| 文件 | 用途 |
|---|---|
| `scripts/localize.py` | 从 Loon.conf 收集插件 → 下载 → 转换 → 输出旧版语法规则文件。支持多份配置合并、`--dry-run`、`--plugin/--extra` 手工指定 |

脚本只做「下载 + 文本转换 + 写文件」，**不修改任何 Loon 配置**，可安全反复运行；
`--dry-run` 下完全不落盘。产物为纯文本规则，写之前建议先 `git diff` 确认。

---

## 9. 相关

- 上游排障方法论（下载层 / 加载层 / 双重出海 / 出口 IP 风控 / App 回写）见 skill **`loon-config-troubleshoot`**
- 官方文档：《复写（旧版语法）》<https://nsloon.app/docs/Rewrite/>、
  《规则匹配顺序》<https://nsloon.app/docs/Rule/>、《插件》<https://nsloon.app/docs/Plugin/>
- 实战仓库：[abobb414/loon-config](https://github.com/abobb414/loon-config)（`rewrite/adblock.list` + 生成脚本）
