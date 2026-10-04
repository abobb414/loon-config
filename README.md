<p align="center"><b>简体中文</b> | <a href="./README.en.md">English</a></p>

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/images/logo-white.png" />
  <img src="./docs/images/logo.png" alt="Loon Config" width="124" />
</picture>

# Loon Config

**一份自用的 Loon 分流配置。23 个策略组、91 个上游资源、每天自动体检。**

分流不是把节点全堆进一个组就完事 —— 广告要拦在 MITM 之前、苹果要抢在去广告规则之前、
AI 要避开港区、上游挂了要能看出来是哪一条挂的。

[Loon.conf](./Loon.conf) &nbsp;·&nbsp; [分流设计](#分流设计) &nbsp;·&nbsp; [上游体检](#上游体检每天一次) &nbsp;·&nbsp; [工程笔记](#工程笔记那些踩过的坑)

[![Loon](https://img.shields.io/badge/Loon-3.x-0EA5E9?style=flat-square)](https://apps.apple.com/app/loon/id1373567447)
[![Policy Groups](https://img.shields.io/badge/策略组-23-8B5CF6?style=flat-square)](#分流设计)
[![Upstreams](https://img.shields.io/badge/上游资源-91-0EA5E9?style=flat-square)](#上游体检每天一次)
[![Checks](https://img.shields.io/badge/核心资源-31%2F31%20可达-22C55E?style=flat-square)](#上游体检每天一次)
[![Secret Scan](https://img.shields.io/badge/推送前-凭据扫描-F59E0B?style=flat-square)](#不要提交真实凭据)
[![Usage](https://img.shields.io/badge/用途-个人备份-64748B?style=flat-square)](#说明)

</div>

---

## 预览

没有界面 —— 产物就是手机上的分流行为，和每天一份的上游体检台账。以下是 **2026-10-04** 在 CI（GitHub Actions）上的实际记录：

```
$ python3 scripts/refresh_upstreams.py
扫描 Loon.conf -> 提取 91 个上游资源
  [200]  61 条可达
  [---]  30 条客户端门禁   <- Kelee plugin 30：仅 Loon 客户端可下，机房出口过不了 Cloudflare 挑战
generated_at   : 2026-10-04T00:02:31Z
resource_count : 91
合计校验       : 17.3 MB / 61 个 sha256
```

近 6 次上游体检（每天定时触发，全部成功）：

| 日期 | 10-03 | 10-02 | 10-01 | 09-30 | 09-29 | 09-28 |
|---|---|---|---|---|---|---|
| 结果 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

> 台账是**实测**，不是占位符 —— 而且它一度是**错的**。这份记录曾连续多日挂着
> 30 条来自 `kelee.one` 的红色「不可达」，先后被解释成「站点挂了」与「采集机在境外、
> 出口被 Cloudflare 挑战」。两个说法都不对：**真正卡住的是两道闸叠加**，
> 而其中一道（Cloudflare 的机器人挑战）**在 CI 上无解**。详见
> [工程笔记](#工程笔记那些踩过的坑)头两行。

---

## 它到底在解决什么

把「哪些流量走哪条线」这件事，从「凭感觉切」变成「有规则、有顺序、有兜底、有体检」。

难点从来不在堆节点，而在**顺序和边界**：

- 去广告规则是 `REJECT`，苹果服务域混在 `icloud.com` 这种通用后缀里 —— 谁先匹配谁说了算，
  规则顺序错了就是「苹果偶尔打不开」。
- AI 服务对出口地区敏感，港区线路时好时坏，混进 `url-test` 里会被测速选成最优。
- 上游资源有 91 个，跨 6 个来源。某天 `raw.githubusercontent.com` 抽风，
  你不知道是它挂了还是自己网络的问题。
- 配置里还有一堆**真实凭据**（私钥、代理口令），而仓库是公开的。

所以这份配置的工作量分布是 **七成在顺序与边界、三成在节点**。

---

## 分流设计

```mermaid
flowchart TD
    A["流量入口<br/>TUN / 局域网"] --> B["[Rule] 本地规则<br/>34 条 · 先匹配先赢"]
    B --> C{"LAN 段？"}
    C -->|"是"| D["DIRECT<br/>仅 NAS 的 HA/Emby 端口进 WG"]
    C -->|"否"| E{"专用直连域？"}
    E -->|"是"| F["DIRECT<br/>pvq.cc / kelee.one 等"]
    E -->|"否"| G{"Apple OTA 域？"}
    G -->|"是"| H["REJECT<br/>10 条固化 OTA 域名"]
    G -->|"否"| I{"Apple 核心域？"}
    I -->|"是"| J["Apple 组<br/>默认 DIRECT"]
    I -->|"否"| K["[Remote Rule]<br/>34 条远程规则表"]
    K --> L["23 个策略组"]
    L --> M{"命中？"}
    M -->|"是"| N["对应平台组<br/>Netflix / AI / Finance …"]
    M -->|"否"| O["GEOIP,CN → DIRECT"]
    O --> P["FINAL → Final 组<br/>兜底"]

    style A fill:#0ea5e9,color:#fff
    style B fill:#8b5cf6,color:#fff
    style H fill:#ef4444,color:#fff
    style J fill:#64748b,color:#fff
    style N fill:#22c55e,color:#fff
    style P fill:#64748b,color:#fff
```

### 规则顺序：四道闸门

配置里最花心思的不是策略组，是 `[Rule]` 段那 34 条的**排列**。本地规则先于远程规则匹配，
所以闸门顺序决定一切：

| 顺位 | 闸门 | 为什么必须在这个位置 |
|---|---|---|
| ① | LAN 段 `DIRECT` | 在家访问 NAS 不该绕代理。但 NAS 的 8123 / 8097 两个端口例外 —— 用 `AND` 逻辑规则单独挑出来进 WG 隧道 |
| ② | 专用直连域 | `iris.pvq.cc` / `kelee.one` 这类资源站，直连才稳（见工程笔记） |
| ③ | Apple OTA `REJECT` | 必须**早于** Apple 白名单，否则白名单会把 OTA 域捞回 Apple 组 |
| ④ | Apple 核心白名单 | 必须**早于**远程去广告 `REJECT`，否则 AdRules 误杀 `icloud.com` / `me.com` |
| ⑤ | `GEOIP,CN` → `FINAL` | 兜底 |

> ③ 和 ④ 的相对顺序是唯一不能颠倒的一对：OTA 域 `swcdn.apple.com` 也匹配 `apple.com` 后缀 ——
> 先放白名单，屏蔽就失效；先放 REJECT，白名单救不回来。
> 这是踩过「苹果偶尔打不开」之后才定下来的。

### 23 个策略组的分层

不是按国家粗暴分组，而是**按「同一类服务对出口的共同诉求」分组**：

| 层级 | 组 | 设计取向 |
|---|---|---|
| 基础 | `Available` `Proxy` `Final` | `Available` 自动测速，`Proxy` 是总代理，`Final` 兜底 |
| 平台 | `Google` `Apple` `Microsoft` | `Apple` 默认 `DIRECT`（国内苹果服务直连最稳），需要外区服务时手动切 |
| 流媒体 | `Netflix` `Disney` `HBO` `Spotify` `YouTube` `Bilibili` | `Bilibili` 默认 `DIRECT` |
| 社交 | `Instagram` `Telegram` `LinkedIn` | —— |
| 金融 | `Finance` | 覆盖支付宝、云闪付与 8 家国内银行，默认 `DIRECT` |
| 短视频 | `TikTok` | 抖音不再单列组，域名走 `ChinaMaxNoIP`、IP 走 `GEOIP,CN`，自然直连 |
| AI | `AI` `OpenAI` `Gemini` `Claude` | **全部不含香港节点** |
| 其他 | `Emby` `HomeNAS` `Speedtest` | `Emby` 默认走代理，4 个地址强制直连 |

> **2026-10-04 精简掉的那一层**：原先是 36 个组，多出来的是 12 个按国家/大洲分的 `url-test` 组
> （`HK` `TW` `SG` `JP` `KR` `US` `AU` `EU` `AS` `AM` `AF` `CF`）和 12 条配套的 `NameRegex` 过滤器。
> 出口只有「OpenClash 网关」和「`Available` 自动测速」两条腿，这几个组本就是空的 ——
> 但空组照样占着 `Proxy` 的成员列表，切一次错一次，所以连过滤器一起删了。
> 同理，`Douyin` 组被删掉后抖音回到 `GEOIP,CN` 的直连兜底，行为不变而少一个组。

### AI 组为什么排除香港

`AI` 组是 `url-test`，过滤器带负向断言：

```ini
AI_NoHK_Filter = NameRegex, FilterKey = "(?i)^(?!.*(港|香港|HK|Hong)).*(美国|...|日本|...|新加坡|...)"
```

不是嫌香港慢 —— 是**部分 AI 服务对出口地区的白名单不含香港**。健康检查
（`generate_204`）只测连通性和延迟，测不出地区风控：延迟最低的香港节点会被选成最优，
然后服务端返回「地区不支持」。`OpenAI` / `Gemini` / `Claude` 三个组默认指向 `AI`，
也可手动钉死具体地区。

> 这是本项目里最反直觉的一条：**能连通 ≠ 能用**。测速组解决不了风控问题。

---

## 上游体检（每天一次）

91 个上游资源跨 6 个来源，靠 GitHub Actions 每天跑一次 `refresh_upstreams.py`
（321 行 / 14 个函数）。

```mermaid
flowchart LR
    A["Loon.conf<br/>提取 91 个 URL"] --> B["并发抓取<br/>带重试 + TLS 校验"]
    B --> C{"HTTP 2xx/3xx？"}
    C -->|"是"| D["记录 sha256<br/>etag / last-modified"]
    C -->|"否"| E{"是核心资源？"}
    E -->|"否"| F["记 ok=false<br/>保留失败现场"]
    E -->|"是"| G["回退上次成功记录<br/>标记 stale=true"]
    D --> H["写 upstreams.lock.json"]
    F --> H
    G --> H
    H --> I["有变化则自动提交"]

    style A fill:#0ea5e9,color:#fff
    style B fill:#8b5cf6,color:#fff
    style C fill:#f59e0b,color:#fff
    style G fill:#64748b,color:#fff
    style I fill:#22c55e,color:#fff
```

### 核心资源保留上次成功记录

`CORE_MARKERS` 圈定 5 类不能断的资源（blackmatrix7 规则、Qure 图标、fmz200 脚本、
Moli-X GeoIP、Sub-Store 解析器）。它们若某次抓取失败，**不写 `ok=false`，
而是回退上次成功值并打 `stale: true`** —— 避免偶发网络抖动让每日任务产生假警报，
也避免把「上游真的挂了」淹没在噪声里。

> 改成自托管图标后，本配置已不再外链 `Koolson/Qure`，`CORE_MARKERS` 里那一条随之落空 ——
> 实际命中的只有 blackmatrix7 规则 30 条与 Sub-Store 解析器 1 条，共 **31 条**。
> 自托管图标**故意不算核心资源**：上游抽风应当被看见，而自家仓库 404 是必须修的 bug，
> 不该被 `stale` 掩盖。

最新一次体检（2026-10-04，CI 侧）实测：

| 指标 | 值 |
|---|---|
| 资源总数 | 91 |
| 可达 | 61 |
| 客户端门禁（不计失败） | 30 |
| **真·不可达** | **0** |
| **核心资源** | **31 / 31 可达** |
| 合计校验字节 | 17.3 MB |

按来源分布：

| 来源 | 条数 | 说明 |
|---|---|---|
| `abobb414/loon-config` | 24 | 自托管策略组图标 23 条 + 去广告规则 1 条 |
| `blackmatrix7/ios_rule_script` | 30 | 远程分流规则 |
| `Kelee plugin` | 30 | 插件与脚本（CI 侧全部走「客户端门禁」，见下） |
| `fmz200/wool_scripts` | 3 | 插件与定时任务 |
| `sub-store-org/Sub-Store` | 1 | 订阅解析器 |
| 其他 | 3 | GeoIP / ASN / AdRules |

> 那 30 条 `kelee.one` 不是「不可达」，是**不可由服务端验证**。站方只对 Loon 客户端放行，
> 叠加 Cloudflare 对机房 IP 的挑战 —— 于是同一份脚本：
>
> | 跑在哪 | UA | 结果 |
> |---|---|---|
> | 本机（住宅出口） | `curl/8.7.1` | 403 · `Attention Required!` |
> | 本机（住宅出口） | `Loon/998 CFNetwork/… Darwin/…` | **200 ✅** |
> | GitHub Actions（Azure 机房 IP） | 同左 | 403 · **`cf-mitigated: challenge`** |
>
> 也就是说，把 UA 装成 Loon 只是过了第一道闸；CI runner 是机房 IP，第二道闸（挑战页需要
> 执行 JS）永远过不去。脚本现在把这类资源标成 `gated`，**与「真失败」分开统计**，
> 而不是继续每天贡献 30 条假警报 —— 假警报真正的危害是让真失败没人看。
>
> 顺带修掉另一个长期的假警报：`[Rewrite]` 段那 4 条本地正则（`^https://host\.tld/path reject-dict`）
> 会被 URL 正则捞出来当成上游资源，抓一次失败一次，每天固定污染 4 条「不可达」。
> 现在按「含反斜杠转义即本地正则」跳过 —— 于是资源数从 95 收敛到 91。

---

## 不要提交真实凭据

仓库是公开的，而配置文件天然含三类敏感值：WireGuard 私钥、代理认证口令、订阅地址。

做法是把真实值全部换成占位符 —— `<client-private-key>`、`username`、`password` ——
**再加一道 CI 扫描**（`.github/workflows/secret-scan.yml`），命中即拦截：

| 检查项 | 匹配目标 |
|---|---|
| 私钥 | `private-key = "<base64 ≥ 40 字符>"` |
| 空口令 | 非空的 `secret` / `password` / `passwd` 字段（占位符除外） |
| 代理凭据 | `http, <ip>, <port>, <user>, <pass>` 形式 |

> 只靠「记得别提交」是不够的 —— 占位符容易被某次「先本地测一下」的临时代码绕过。
> 所以扫描放在 CI 上，`push` 与 `pull_request` 双触发。

---

## 去广告：规则为什么自己固化

`[Remote Rewrite]` 引用了 `rewrite/adblock.list` —— 19 个插件、311 条去广告规则，**不是「抄一份备份」**，
是为了绕开两件事：

- **插件规则用的是新版脚本语法**，形如 `request if ${url} ~= /.../i then reject_dict(200)`。
  该语法自 Loon 3.5.1(978) 引入，而插件头部普遍要求 `#!loon_version=3.5.1(998)`。
  **build 不够时规则被静默忽略** —— MitM 照常解密（请求列表里有紫锁、能看到完整 URL），
  rewrite 一条都不执行。表现就是「广告拦不住、Reject 页又空空如也」。
- **插件会随作者更新而变化**，行为不由自己掌控。

官方文档《匹配顺序》写明：**本地配置的 `[Rewrite]` 优先于插件的 `[Rewrite]`**。
所以把这些规则逐条等价转成旧版语法（Build 729+ 全兼容）搬到自己的文件里，一次解决。

| 新版 | 旧版 |
|---|---|
| `reject_dict(200)` / `reject(404)` | `reject-dict` （HTTP 200 + `{}`） |
| `reject_img(200)` | `reject-img` |
| `response.json.jq(x)` | `response-body-json-jq 'x'` |
| `response.json.delete` | `response-body-json-del` |
| `response.json.replace` | `response-body-json-replace` |
| `response.header.add` | `response-header-add` |
| `redirect(307,url)` | `307 url` |

有 10 条（`response.body.mock` / `response.json.jq_file` / `response.body.replace`）旧语法没有等价动作，
仍由插件提供，已在规则文件头部注明。

```bash
# 重新生成（插件更新后跑一次即可）
python3 rewrite/gen.py
```

转换逻辑与踩坑记录在 `skills/loon-rewrite-localize/` —— 这条链路上有三个坑：
插件正则**自带 `^`** 导致重复锚点（生成出 `^^https://…`，整条失效）、
jq 表达式里的**空格必须转义成 `\x20`**（旧语法按空格分隔参数，不转义会被截断）、
源站偶发 `SSL: UNEXPECTED_EOF` **必须退避重试**（不加时 30 个插件稳定掉 5 个，规则从 311 掉到 192 且不报错）。

---

## 文件说明

| 文件 | 行数 | 用途 |
|---|---|---|
| `Loon.conf` | 282 | 主配置。23 个策略组、34 条本地规则、34 条远程规则、28 个插件 |
| `Loon-minimal.conf` | 32 | **最小化排查配置**：只有基础分流，无插件 / 脚本 / 改写 / 远程规则 / MITM |
| `Stash.yaml` | 143 | 由 Loon 配置转换而来的 Stash 策略配置 |
| `clash-advanced.yaml` | 433 | Clash 进阶配置，含策略组锚点与订阅占位 |
| `rewrite/adblock.list` | 328 | **固化后的去广告规则**：311 条、旧版语法，由 `[Remote Rewrite]` 引用 |
| `skills/loon-rewrite-localize/` | —— | 可复用的 skill：插件规则本地化（`scripts/localize.py` + 方法论与踩坑） |
| `scripts/refresh_upstreams.py` | 385 | 上游资源体检脚本（客户端门禁资源单独计数） |
| `IconSet/Color/` | 35 (+3) | 策略组与订阅图标（icons8 Pulsar Color，1600px PNG）与 `icons-all.json`；另含 3 个 `*-v2` 的旧名兼容别名（见下） |

| `.upstream/upstreams.lock.json` | —— | 91 条资源的 ETag / Last-Modified / sha256 台账 |

### 最小化配置是干什么的

排查「某个服务访问不了」时，最怕的是**在 282 行的主配置里逐条注释试验**。
`Loon-minimal.conf` 把变量砍到只剩 5 条规则 + 2 个组，用它做 A/B：

- 最小化配置下正常 ⇒ 主配置的某个组件有问题，逐项加回定位
- 最小化配置下仍异常 ⇒ 与规则无关，问题在 Loon 本身 / TUN / 网络状态

这道二分能把排查范围一次砍掉一大半。

---

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/abobb414/loon-config.git
cd loon-config

# 2. 填上自己的凭据（仓库里是占位符，勿把真实值提交回去）
#      [Proxy]        Home-OpenClash 的地址 / 端口 / 用户名 / 口令
#      [Proxy]        Home-NAS-WG 的私钥 / 公钥 / 端点
#      [Remote Proxy] 自己的订阅地址
$EDITOR Loon.conf

# 3. 本地跑一次上游体检（可选）
python3 scripts/refresh_upstreams.py

# 4. 在 Loon 里导入
#    配置 -> 新建配置 -> 填 Loon.conf 的 raw 地址 -> 切换过去
```

---

## 工程笔记：那些踩过的坑

配置 282 行，但不少行数花在了**看起来不重要、实际会要命的地方**。

<table>
<tr><th width="34%">症状</th><th width="66%">根因与解法</th></tr>
<tr>
<td><b>kelee.one 的插件 / 脚本批量 403</b></td>
<td>它是<b>两道闸叠加</b>，少说一道就会开出错的药方。<br/>
<b>闸 1 · 站方客户端校验（看 UA）</b>：资源路径要求 UA <b>以 <code>Loon/</code> 开头</b>
（前缀锚定，前面加任何东西都不行），且同时带 <code>CFNetwork/</code> 与 <code>Darwin/</code>
两段；不满足就回 403 加一张 <code>Attention Required!</code>（Cloudflare block 页，<b>没有</b>
<code>cf-mitigated</code> 头）。<br/>
<b>闸 2 · Cloudflare 机器人挑战（看出口 IP）</b>：机房 / 数据中心 IP 会被下发
<code>cf-mitigated: challenge</code>，需要执行 JS 才过得去 —— <b>UA 装得再像也没用</b>。<br/>
实测矩阵（固定 URL，每次只动一个变量）：<br/>
<code>本机 + curl UA</code> → 403 block · <code>本机 + Loon UA</code> → <b>200 ✅</b> ·
<code>CI + 任意 UA（含 Loon）</code> → 403 challenge。<br/>
所以手机上一直是好的，而<b>体检脚本在 CI 上无论怎么装都拿不到这 30 条</b>。<br/>
解法分两半：脚本带 Loon UA（过闸 1）；闸 2 在 CI 上无解，于是把这 30 条标成 <code>gated</code>，
与真失败分开统计 —— 关键在于<b>别再让它们每天贡献 30 条假警报</b>。配置里那条
<code>DOMAIN-SUFFIX,kelee.one,DIRECT</code> 继续保留，它管的是下载走直连、不绕代理内核。</td>
</tr>
<tr>
<td><b>去广告插件「下载正常、MitM 也正常，就是拦不住」</b></td>
<td>插件规则是<b>新版脚本语法</b>（自 Loon 3.5.1(978) 引入），插件头部普遍要求 <code>#!loon_version=3.5.1(998)</code>。
build 不够时规则被<b>静默忽略</b>：MitM 照常解密（请求列表有紫锁、看得见完整 URL），rewrite 却一条不执行
—— 于是「Reject 页无记录」与「广告照样弹」同时出现。<br/>
⚠️ 「Reject 页无记录」<b>不能单独作为失效判据</b>：只清字段（<code>response.json.jq</code>）不拦请求的规则本来就不进 Reject 页。<br/>
解法：依官方「本地 Rewrite 优先于插件」，把 311 条规则转成旧版语法固化到 <code>rewrite/adblock.list</code>。</td>
</tr>
<tr>
<td><b>被 403 误导，差点得出完全错的结论</b></td>
<td>第一次排查在单一出口采样，全 403 → 写下「上游遭全站封锁」。<b>换一个出口，同一时刻全是 200。</b><br/>
教训：<b>403 判定必须多出口对照</b>。固定 URL + 固定 UA，同时记录出口 IP，
做「出口 IP × 状态码」二维统计。单点采样会得出完全错的结论。<br/>
当时实测：出口 SG-Amazon 全 403 ×6，出口 JP-GSL 全 200 ×6，6/6 稳定复现。<br/>
⚠️ 事后的补充：这张二维表还差一个维度 —— <b>UA</b>。同一出口下只换 UA 就能翻转 403/200；
反过来，「换出口变 200」也可能只是碰巧换了 UA。更要紧的是 <b>403 不止一种</b>：
响应体是 <code>Attention Required!</code> 的是 <b>block</b>（服务端规则，UA 可解），
带 <code>cf-mitigated: challenge</code> 的是<b>挑战</b>（出口 IP 风控，UA 无解）。<br/>
<b>出口、UA、URL 三个变量都钉死，并且看清 403 的成因，才有资格下结论。</b></td>
</tr>
<tr>
<td><b>苹果「偶尔访问不了」</b></td>
<td>远程 <code>AppleFirmware.list</code> 名不副实：174 条全是 <code>icloud.com</code> /
<code>itunes.com</code> / <code>me.com</code> 等正常服务域，<b>没有任何 OTA 域名</b>，
却配了 <code>REJECT</code> —— 等于把苹果服务成片误杀。<br/>
改为移除该远程表，本地固化 10 条真 OTA 域（<code>swcdn</code> / <code>swscan</code> /
<code>mesu</code> …），并置于 Apple 白名单<b>之前</b>。</td>
</tr>
<tr>
<td><b>在家时 AdGuard 拦截失效</b></td>
<td>原配置整段 <code>192.168.1.0/24</code> 走 WG 隧道，导致网关上的 AdGuard 与 smartdns
的 DNS 查询被吸入隧道、又被白名单丢弃。<br/>
改为<b>只把 NAS 的 HA / Emby 两个端口</b>用 <code>AND</code> 逻辑规则挑进隧道，LAN 其余全部直连。</td>
</tr>
<tr>
<td><b>策略组无端抖动</b></td>
<td><code>test-timeout</code> 设为 1s 太激进，弱网节点被全部误判失败，
<code>url-test</code> 组反复跳。放宽到 3s 后稳定。</td>
</tr>
<tr>
<td><b>微信视频 / FaceTime 通话质量下降</b></td>
<td>早先为省流量开了 <code>disable-stun = true</code>，阻断了 STUN 打洞，通话被迫走中继 ——
与 <code>allow-udp-proxy</code> 的初衷正好矛盾。已关闭。</td>
</tr>
<tr>
<td><b>微信收发消息黑洞</b></td>
<td><code>[Host]</code> 里 <code>*.qq.com</code> 这类通配命中后指向了不可达上游，
该域下所有服务一起黑洞。<br/>
定位方式：<code>Loon-minimal.conf</code> 二分 —— 最小配置下仍异常就与规则无关。
微信核心域现固定走 DNSPod 作保底。</td>
</tr>
</table>

---

## 限制

- **不含节点订阅**：公开版只有占位符，需自备订阅与凭据。
- **不按地区分组**：策略组里没有 `HK` / `SG` / `JP` 这类地区组，要临时走某个地区，
  直接从节点列表里选。想恢复按地区分组，把 `NameRegex` 过滤器加回来即可。
- **30 条 kelee 资源在 CI 上无法验证**：站方只对 Loon 客户端放行（闸 1，UA），
  叠加 Cloudflare 对机房 IP 的挑战（闸 2，无解）。脚本把它们记为 `gated` 而非失败 ——
  读台账时 `ok=false` 要先看有没有 `gated` 标记。想拿到这 30 条的 sha256，
  只能在本机（住宅出口）跑一次 `refresh_upstreams.py`。
- **AI 地区白名单会变**：`AI` 组排除香港是当前结论，服务端策略调整后需重新测绘。

---

## 致谢

- [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)：Loon 远程分流规则
- [Cats-Team/AdRules](https://github.com/Cats-Team/AdRules)：广告拦截规则
- [icons8](https://icons8.com) / [igoutu.cn](https://igoutu.cn)：策略组与订阅图标（**Pulsar Color** 风格，
  1600px PNG 由本仓库自托管；按免费许可要求在此署名）
- [Koolson/Qure](https://github.com/Koolson/Qure)：早期图标来源（现已改为自托管）
- [fmz200/wool_scripts](https://github.com/fmz200/wool_scripts)：插件、广告规则与补充图标
- [Moli-X/Tool](https://github.com/Moli-X/Tool)：配置结构参考、GeoIP / ASN 资源
- [sub-store-org/Sub-Store](https://github.com/sub-store-org/Sub-Store)：订阅解析器与订阅管理生态
- Kelee Loon 插件：配置中使用的插件模块来源
- [Loon](https://apps.apple.com/app/loon/id1373567447)：客户端与配置运行环境

---

## 说明

本仓库仅用于个人配置备份与学习整理。请根据自己的订阅、节点、地区需求和网络环境调整后使用。

> **不要提交真实凭据。** 本仓库公开，配置中的私钥、代理口令、订阅地址一律用占位符。
> 真实值只保留在本地配置中，CI 已配置推送前扫描，命中疑似凭据会直接拦截。

以你的实际网络环境为准，本配置不构成任何保证。
