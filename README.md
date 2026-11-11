<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/images/logo-white.png" />
  <img src="./docs/images/logo.png" alt="Loon Config" width="124" />
</picture>

# Loon Config

**一份自用的 Loon 纯分流配置：只决定流量走哪个策略组，不做 MITM、不跑脚本、不带插件。**

26 个策略组 · 29 条本地规则 · 34 条远程规则 · 每天一次上游体检

[配置](./Loon-routing.conf) · [快速开始](#快速开始) · [分流设计](#分流设计) · [插件与脚本](#插件与脚本为什么必须自己订阅) · [每日上游同步](#每日上游同步)

</div>

---

## 这是什么

仓库只维护一个文件：[`Loon-routing.conf`](./Loon-routing.conf)。

它回答的问题只有「哪条流量走哪个策略组」。文件里没有 `[MITM]`、`[Rewrite]`、
`[Script]`、`[Plugin]` —— 需要解密的去广告不在这里做，交给你自己订阅的 `.lpx` 插件。

- 规则层去广告（`REJECT`）仍然有效：按域名/连接直接拒掉，不需要解密。
- 远程规则与 GeoIP 由 Loon 在运行时向上游拉取；仓库只记录它们的指纹。
- 代理地址、订阅 token、WireGuard 密钥全部是占位符，公开仓库里没有真实凭据。

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/abobb414/loon-config.git
cd loon-config

# 2. 换成自己的节点（仓库里是占位符）
#    [Proxy]        Home-Proxy 的地址 / 端口 / 用户名 / 口令
#    [Proxy]        Home-NAS-WG 的私钥 / 公钥 / 端点
#    [Remote Proxy] SubA-Sub / SubB-Sub 的订阅地址
#    订阅名不要改：[Remote Filter] 按 SubA-Sub / SubB-Sub 取节点

# 3. 本地校验（可选）
python3 scripts/validate_config.py Loon-routing.conf
```

然后在 Loon 里：**配置 → 新建配置 → 填 raw 地址 → 切换过去**。

```text
https://raw.githubusercontent.com/abobb414/loon-config/main/Loon-routing.conf
```

去广告插件和脚本不在这份配置里，按下一节的地址自行订阅。

## 插件与脚本：为什么必须自己订阅

这份配置只负责分流，但去广告有两套机制，其中一套必须解密：

1. **规则层 REJECT**（`[Rule]` / `[Remote Rule]`）
   按域名或连接直接拒掉，不需要 MITM，所以纯分流配置照样有效。

2. **Rewrite 层**（改响应体、删 JSON 字段、mock 返回值）
   必须先 MITM 解密。域名不在 `[MITM] hostname` 里，HTTPS 就是一条密文隧道，
   rewrite 静默不执行 —— Loon 不报错、日志也不提示，看起来「规则都在」而广告照播。

**为什么不在仓库里替你维护 MITM？** 因为那份 hostname 清单是静态的，不会自己长。
App 换接口域名、插件作者新增域名，清单都跟不上，于是出现「插件已加载、规则命中数为 0」
这种最难查的状态。历史上那份清单从 6 条膨胀到 188 条，仍然覆盖不全。

所以解密权只让一方维护：`[MitM]` 和 `[Rewrite]` 写在 `.lpx` 插件里，随作者一次更新。
本仓库不转发、不镜像，代价是插件得你自己订阅 —— 这样作者更新你才能跟着更新。

**脚本同理。** `[Script]` 调用的 `.js` 也要跟上游作者更新，很多还依赖 BoxJs 和 Cookie；
抄进仓库只会在作者改版后悄悄失效。脚本订阅与 BoxJs 都放在 Loon 里管。

| 类型 | 订阅地址 | 说明 |
|---|---|---|
| 去广告插件 `.lpx` | <https://kelee.one/Tool/Loon/Lpx/> | 目录页，按需逐个添加；插件自带 `[MitM]` |
| 通用拦截 | `BlockAdvertisers.lpx` / `Remove_ads_by_keli.lpx` | 规则型为主 |
| 单 App | `FleaMarket_remove_ads.lpx`（闲鱼）、`JD`、`Bilibili`、`QuarkBrowser`、`Amap`、`Cainiao`、`12306` 等 | 用哪个订哪个 |
| 脚本 `.scripts` / `.js` | <https://github.com/fmz200/wool_scripts/tree/main/Loon/script> | `tools.scripts`（工具合集）/ `tasks.scripts`（定时任务） |
| 脚本宿主 BoxJs | <https://kelee.one/Tool/Loon/Lpx/BoxJs.lpx> | 面板、通知、Cookie 类脚本依赖它 |
| 规则清单 `.list` | [Cats-Team/AdRules](https://github.com/Cats-Team/AdRules)、[blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script) | 本配置 `[Remote Rule]` 已直接引用，不用另订 |

两个必须知道的坑：

- **kelee.one 只对 Loon 客户端放行。** 站方校验 UA（必须 `Loon/` 开头），Cloudflare
  还会按出口 IP 下发机器人挑战。浏览器里点开大概率 403，要复制到 **Loon → 插件 → 添加**
  里订阅。GitHub Actions 上也拿不到，所以每日任务把它们记为 `gated` 而非失败。
- **插件越多，解密面越大。** 每加一个插件就是把它的 hostname 并进 MITM 范围，
  只订你真正在用的 App，比一次订几十个更稳定。

## 分流设计

### 规则顺序：本地规则先于远程规则

`[Rule]` 段最花心思的不是策略组，是顺序。先匹配先赢，几道闸门不能乱：

| 顺位 | 规则 | 为什么必须在这里 |
|---|---|---|
| 1 | `IP-CIDR,192.168.0.0/16,DIRECT,no-resolve` | 在家访问 NAS 不绕代理。远程访问自托管服务时，把注释里的 `AND` 规则换成自己的 IP/端口，只把具体端口放进 WG 隧道 |
| 2 | `ip.net.coffee`、STUN → `AI` / `Home-Proxy` | 检测站若走本地 DNS 解析，会看到本地出口；STUN 走能转 UDP 的节点，保证 UDP 与 TCP 出口一致 |
| 3 | `kelee.one` → `DIRECT` | 插件源在 Cloudflare 后面，经代理出海会被 `cf-mitigated: challenge` 挡住，Loon 不执行 JS，必然 403 |
| 4 | Apple OTA 域 → `REJECT` | 必须早于 Apple 白名单，否则白名单会把 OTA 域捞回去，屏蔽失效 |
| 5 | Apple 核心域 → `Apple` | 必须早于远程去广告 `REJECT`，否则 AdRules 误杀 `icloud.com` / `me.com` |
| 6 | `GEOIP,CN` → `DIRECT`；`FINAL` → `Final` | 兜底。`FINAL` 必须是最后一条 |

> 4 和 5 的相对顺序是唯一不能颠倒的一对：`swcdn.apple.com` 也匹配 `apple.com` 后缀。
> 先放白名单，屏蔽失效；先放 REJECT，白名单救不回来。这是踩过「苹果偶尔打不开」之后定下来的。

### 策略组

| 类别 | 策略组 |
|---|---|
| 入口与兜底 | `Available`、`Proxy`、`Final`、`HomeNAS` |
| 订阅总览 | `SubA`、`SubB`（select 成员是整条订阅，Loon 会展开原生节点） |
| AI | `AI`、`OpenAI`、`Claude`、`Gemini` |
| 平台 | `Google`、`Apple`、`Microsoft`、`Netflix`、`Disney`、`HBO`、`Spotify`、`YouTube`、`Bilibili`、`TikTok`、`Instagram`、`Telegram`、`LinkedIn`、`Emby`、`Speedtest` |
| 金融 | `Finance` |

几个关键选择：

- `Proxy` 用 `fallback` 而不是 `select`：`select` 会沿用 Loon 里保存的上一次手动选择，
  改配置不生效。
- `AI` 优先住宅节点、机房兜底。住宅 IP 在 AI 站点上的信任度高于机房；住宅全挂才退到机房。
  `Claude` 单独成组，默认选 `AI`，需要时可以逐节点切换。
- `Available` 只按「台湾家宽 → 日本 → 新加坡 → Proxy」的顺序挑，香港节点全部排除。
- `[Remote Filter]` 用 `NameRegex` 限定订阅名并按节点命名取节点。换机场后节点命名变了，
  这些 Filter 要跟着改。

### DNS 与 Fake-IP

- DoH 用纯 IP（`223.5.5.5`、`120.53.53.53`），不写 `h3://` —— UDP/443 常被运营商 QoS，
  表现为解析偶发挂起。
- `hijack-dns` + Fake-IP：本地不再递归真实查询，连接阶段由 Loon 按域名交给策略组。
  `198.18.0.0/15` 是 Fake-IP 池，**不能**放进 `bypass-tun`。
- 节点/订阅的解析域名要列进 `real-ip`，否则会拿到 Fake-IP 形成拨号回环。
- `192.168.0.0/16` 也**不能**放进 `bypass-tun`：远程经 WireGuard 访问 LAN 的流量要进隧道；
  在家访问 LAN 由 `[Rule]` 顶部的 `DIRECT` 兜底。
- `disable-stun` 保持关闭，否则微信视频 / FaceTime 会被迫走中继。

## 每日上游同步

远程规则不在仓库里，Loon 运行时直接向上游拉取。每日任务做的是「确认它们还活着、还是规则」：

```text
.github/workflows/upstream-sync.yml   每天 09:17（Asia/Shanghai）自动运行
  ├─ 校验 Loon-routing.conf
  ├─ scripts/sync_upstreams.py 抓取 37 条上游资源
  └─ 更新并提交 .upstream/upstreams.lock.json（每天一条台账）
```

脚本对每条资源记录：

- HTTP 状态、大小、ETag、Last-Modified、TLS 是否通过
- sha256，与上一次对比，标出 `new` / `changed` / `unchanged`
- 规则清单的条数与规则类型分布；如果返回 HTML 错误页或条数为 0，直接判失败

**它不镜像规则正文。** lock 文件里只有指纹，规则仍然从上游拉 —— 仓库不会因为
AdRules 有 20 万条规则就多出 7 MB。核心资源（规则清单、GeoIP、parser）不可达时 CI 亮红灯。
上游内容变化会在 Step Summary 里逐条列出，并把 `new` / `changed` 写进台账。

kelee.one 的 `.lsr` 资源在 GitHub Actions 上必然被 Cloudflare 拦下，脚本记为 `gated`，
不计入失败，否则每天固定产生假警报，把真正的失败淹没掉。

本地运行：

```bash
python3 scripts/sync_upstreams.py                  # 抓取并写 lock
python3 scripts/sync_upstreams.py --dry-run        # 只看结果，不写文件
python3 scripts/sync_upstreams.py --strict         # 核心资源失败时返回 1
```

## 文件说明

| 文件 | 用途 |
|---|---|
| `Loon-routing.conf` | 唯一配置。26 个策略组、29 条本地规则、34 条远程规则 |
| `IconSet/Color/` | 自托管策略组图标（1600px PNG）与 `icons-all.json`；配置里 26 个图标都指向这里 |
| `scripts/sync_upstreams.py` | 每日上游同步：抓取、sha256、规则条数、变更检测、Step Summary |
| `scripts/validate_config.py` | 静态校验：段名、策略引用、`FINAL` 收尾、图标文件是否存在 |
| `.upstream/upstreams.lock.json` | 37 条上游资源的指纹台账 |
| `.github/workflows/upstream-sync.yml` | 每日定时任务 |
| `.github/workflows/secret-scan.yml` | 推送前扫描疑似私钥、口令与代理凭据 |
| `docs/images/` | README 用的 logo |

### 图标缓存

Loon 缓存的图标按 **URL** 命中：同名覆盖字节后，客户端仍返回缓存里的旧图。
所以换图必须换文件名。历史上 `AI`、`NiceDuck`、`SubA` 改成 `*-v2` 就是为了绕开缓存；
`icons-all.json` 里显示名保持原样，只把 `url` 指向新文件。

## 不要提交真实凭据

公开仓库里只有占位符：

```ini
Home-Proxy  = socks5,192.0.2.10,7890,username,password   # RFC 5737 文档地址
Home-NAS-WG = wireguard,private-key="<client-private-key>", ...
SubA-Sub    = https://example.com/sub-a-subscribe?token=YOUR_TOKEN, ...
```

真实值放本地，不要提交回来。`secret-scan.yml` 会在 push / PR 时扫描私钥、非空
`password`/`secret` 字段和 `scheme, ip, port, user, pass` 形式的代理凭据。

## 限制

- 只维护纯分流配置。需要 MITM、rewrite、脚本、插件一次性带走的，请按上面的地址自己订阅。
- 订阅过滤依赖节点命名；换机场后 `[Remote Filter]` 的正则要重写。
- 配置是个人自用的公开备份，不保证适配所有 Loon 版本；`[Proxy Chain]` 之类的新模块
  不在本文件里，按需自行添加。
- 远程规则是第三方维护的，误杀 / 漏杀与本仓库无关。

## 致谢

规则清单来自 [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)、
[Cats-Team/AdRules](https://github.com/Cats-Team/AdRules)、
[fmz200/wool_scripts](https://github.com/fmz200/wool_scripts)；GeoIP 来自
[Loyalsoldier/geoip](https://github.com/Loyalsoldier/geoip)；订阅解析来自
[Sub-Store](https://github.com/sub-store-org/Sub-Store)；插件与脚本来自
[kelee.one](https://kelee.one/Tool/Loon/Lpx/) 与各自的作者。

## 说明

个人自用配置的公开备份，按现状提供，不附带任何担保。
