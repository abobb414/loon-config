<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./docs/images/logo-white.png" />
  <img src="./docs/images/logo.png" alt="Loon Config" width="124" />
</picture>

# Loon Config

**三份自用的纯分流配置（Loon / Stash / Clash.Meta）：只决定流量走哪个策略组，不做 MITM、不跑脚本、不带插件。**

31 个策略组 · 29 条本地规则 · 38 条远程规则 · 每天一次上游体检

[Loon](./Loon-routing.conf) · [Stash](./Stash.yaml) · [Clash](./Clash.yaml) · [快速开始](#快速开始) · [分流设计](#分流设计) · [插件与脚本](#插件与脚本为什么必须自己订阅) · [每日上游同步](#每日上游同步)

</div>

---

## 这是什么

仓库维护三份同源的纯分流配置：

| 客户端 | 文件 | 语法 |
|---|---|---|
| Loon | [`Loon-routing.conf`](./Loon-routing.conf) | Loon 原生（`.conf`） |
| Stash | [`Stash.yaml`](./Stash.yaml) | 完全兼容 Clash Premium |
| Clash.Meta / mihomo | [`Clash.yaml`](./Clash.yaml) | mihomo 1.18+（原版 Clash Premium 已停更） |

三份文件回答同一个问题：「哪条流量走哪个策略组」。策略组、过滤条件、规则顺序一一对应，
差异只来自客户端本身（见[三份配置的差异](#三份配置的差异)）。三份都是手工维护的镜像，
改一处要同步另外两处。

配置里没有 `[MITM]`、`[Rewrite]`、`[Script]`、`[Plugin]` —— 需要解密的去广告不在这里做，
交给你自己订阅的插件。

- 规则层去广告（`REJECT`）仍然有效：按域名/连接直接拒掉，不需要解密。
- 远程规则与 GeoIP 由客户端在运行时向上游拉取；仓库只记录它们的指纹。
- 代理地址、订阅 token、WireGuard 密钥全部是占位符，公开仓库里没有真实凭据。

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/abobb414/loon-config.git
cd loon-config

# 2. 换成自己的节点（仓库里是占位符）
#    Loon  [Proxy]        Home-Proxy 的地址 / 端口 / 用户名 / 口令
#          [Proxy]        US-Resi 住宅 socks5 的地址 / 端口 / 用户名 / 口令
#          [Proxy]        Home-NAS-WG 的私钥 / 公钥 / 端点
#          [Remote Proxy] SubA-Sub / SubB-Sub 的订阅地址
#          订阅名不要改：[Remote Filter] 按 SubA-Sub / SubB-Sub 取节点
#    YAML  proxies:            Home-Proxy / Home-NAS-WG
#          proxy-providers:   SubA-Sub / SubB-Sub
#          这两个名字被策略组的 use 引用，改名要一起改

# 3. 本地校验（可选）
python3 scripts/validate_config.py Loon-routing.conf
```

然后在客户端里导入：

```text
https://raw.githubusercontent.com/abobb414/loon-config/main/Loon-routing.conf   # Loon
https://raw.githubusercontent.com/abobb414/loon-config/main/Stash.yaml          # Stash
https://raw.githubusercontent.com/abobb414/loon-config/main/Clash.yaml          # Clash.Meta / mihomo
```

Stash 没有「订阅配置」入口时，下载 `Stash.yaml` 到 iCloud/本地再导入即可；
Clash 系客户端直接把这个地址填进「配置 / Profile」。

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
| 代理链 | `AI-Entry`（链的入口）、`[Proxy Chain]` 里的 `US-Resi-Chain` |
| 订阅总览 | `SubA`、`SubB`（select 成员是整条订阅，Loon 会展开原生节点） |
| AI | `AI`、`OpenAI`、`Claude`、`Gemini` |
| 平台 | `Google`、`GitHub`、`X`、`Epic`、`Steam`、`Apple`、`Microsoft`、`Netflix`、`Disney`、`HBO`、`Spotify`、`YouTube`、`Bilibili`、`TikTok`、`Instagram`、`Telegram`、`LinkedIn`、`Emby`、`Speedtest` |
| 金融 | `Finance` |

几个关键选择：

- `Proxy` 用 `select` 而不是 `fallback`：`select` 的成员是可见的整组节点，需要时能手动挑出口；
  `fallback` 不保存选择、也不接受手动指定，排在前面的高倍节点会一直被选。
- **AI 走「机场 → 住宅」代理链**，见下一节。
- `Claude` 单独成组，默认选 `AI`，需要时可以逐节点切换。
- `Available` 只按「台湾家宽 → 日本 → 新加坡 → Proxy」的顺序挑，香港节点全部排除。
- `GitHub` / `X` 默认走 `Proxy`；`Epic` / `Steam` 默认 `DIRECT`（下载走本地带宽更快，登录遇到问题时在组里切 `Proxy`）。
- `[Remote Filter]` 用 `NameRegex` 限定订阅名并按节点命名取节点。换机场后节点命名变了，
  这些 Filter 要跟着改。

### AI 的代理链：机场入口 → 住宅出口

住宅出口是拨号级上行，单连接只有 ~20 KB/s，直接连没法用。套一跳机场做前置后
实测能到 ~250 KB/s，而网站看到的仍然是住宅 IP。

```ini
[Proxy Chain]
US-Resi-Chain = AI-Entry,US-Resi      # 队首 = 入口，队尾 = 出口
```

- 链行只写成员名、**没有参数**，也**没有 fallback**：入口挂了整条链就断。
- `AI-Entry` 是一个普通的 `select` 组，用来手动挑入口机场；入口不写死，机场换节点不用改链。
- `AI` 组默认选 `US-Resi-Chain`，后面跟台湾住宅/机场节点做手动备选。
- Loon 用独立的 `[Proxy Chain]` 段；Stash / Clash.Meta 没有这个段，靠出口节点的
  `dialer-proxy: AI-Entry` 表达同一件事。
- 出口节点开了 `udp=false`，配合 `udp-fallback-mode = REJECT`：QUIC / WebRTC 的 UDP 被丢掉后
  浏览器回落 TCP，避免 UDP 走别的出口造成 IP 不一致。

### DNS 与 Fake-IP

- DoH 用纯 IP（`223.5.5.5`、`120.53.53.53`），不写 `h3://` —— UDP/443 常被运营商 QoS，
  表现为解析偶发挂起。
- `hijack-dns` + Fake-IP：本地不再递归真实查询，连接阶段由 Loon 按域名交给策略组。
  `198.18.0.0/15` 是 Fake-IP 池，**不能**放进 `bypass-tun`。
- 节点/订阅的解析域名要列进 `real-ip`，否则会拿到 Fake-IP 形成拨号回环。
- `192.168.0.0/16` 也**不能**放进 `bypass-tun`：远程经 WireGuard 访问 LAN 的流量要进隧道；
  在家访问 LAN 由 `[Rule]` 顶部的 `DIRECT` 兜底。
- `disable-stun` 保持关闭，否则微信视频 / FaceTime 会被迫走中继。

### 三份配置的差异

同一套策略，落到三个客户端时只有下面几处必须不同：

| 项 | Loon | Stash | Clash.Meta |
|---|---|---|---|
| 节点过滤 | `[Remote Filter]` + `NameRegex` | 策略组 `use` + `filter` | 策略组 `use` + `filter` / `exclude-filter` |
| 过滤正则 | 支持负向前瞻 | 支持负向前瞻（ICU） | **RE2，不支持负向前瞻**，排除项必须写 `exclude-filter` |
| 代理链 | `[Proxy Chain]` 独立段 | 出口节点 `dialer-proxy` | 出口节点 `dialer-proxy` |
| Speedtest 规则 | kelee.one 的 `.lsr` | blackmatrix7 同名规则集 | blackmatrix7 同名规则集 |
| `[Host]`（域名 → DNS） | 原生 | `dns.nameserver-policy` | `dns.nameserver-policy` |
| 节点域名真实解析 | `real-ip` | `proxy-server-nameserver` + `fake-ip-filter` | 同 Stash |
| 去广告插件 / 脚本 | 自行订阅 `.lpx` / `.js` | 自行订阅 Stash rewrite/script | 不在本配置范围 |

- **kelee.one 只对 Loon 的 UA 放行。** Stash / Clash 拉 `.lsr` 会 403，所以 YAML 里把两条
  Speedtest 规则换成 blackmatrix7 的 `Speedtest.yaml`，远程规则条数从 38 变成 37。
- **过滤器在 YAML 里是「策略组」。** `SubA-TW`、`SubB-JP` 这些名字等价于 Loon 的
  `SubA-TW_Filter`：`hidden: true` 不占策略组列表，只作为 `Available` / `Proxy` / `AI`
  的成员。区域池用 `url-test` 先挑最快节点，外层 `fallback` 只判断这个池子还能不能用。
- **Clash 没有负向前瞻。** Loon / Stash 里 `^(?!.*(剩余流量|...)).*` 这种写法在 mihomo 里
  会直接编译失败，所以 `Clash.yaml` 统一改成 `filter: '.*'` + `exclude-filter`。
- **`hosts` 不能写 DNS 服务器。** Clash 系的 `hosts` 只接受 IP，把域名指到某个 DNS 服务器
  要用 `dns.nameserver-policy`，三份配置的解析行为才一致。

## 每日上游同步

远程规则不在仓库里，Loon 运行时直接向上游拉取。每日任务做的是「确认它们还活着、还是规则」：

```text
.github/workflows/upstream-sync.yml   每天 09:17（Asia/Shanghai）自动运行
  ├─ 校验 Loon-routing.conf
  ├─ scripts/sync_upstreams.py 抓取 41 条上游资源
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
| `Loon-routing.conf` | Loon 配置。31 个策略组、29 条本地规则、38 条远程规则、1 条代理链 |
| `Stash.yaml` | Stash 镜像。31 个策略组 + 8 个过滤池、37 个远程规则集 |
| `Clash.yaml` | Clash.Meta / mihomo 镜像；与 Stash 版同构，过滤用 `exclude-filter` |
| `IconSet/Color/` | 自托管策略组图标（1600px PNG）与 `icons-all.json`；31 个图标都指向这里 |
| `scripts/sync_upstreams.py` | 每日上游同步：抓取、sha256、规则条数、变更检测、Step Summary |
| `scripts/validate_config.py` | Loon 静态校验：段名、策略引用、`FINAL` 收尾、图标文件是否存在 |
| `.upstream/upstreams.lock.json` | 41 条上游资源的指纹台账（Loon 版） |
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

```yaml
# Stash.yaml / Clash.yaml
private-key: "<client-private-key>"
password: "<password>"
```

真实值放本地，不要提交回来。`secret-scan.yml` 会在 push / PR 时扫描私钥、非空
`password`/`secret` 字段和 `scheme, ip, port, user, pass` 形式的代理凭据。
YAML 里的值带引号，既是为了占位符显眼，也是为了让扫描器不会把它当成真实口令。

## 限制

- 只维护纯分流配置。需要 MITM、rewrite、脚本、插件一次性带走的，请按上面的地址自己订阅。
- 三份配置是**手工维护的镜像**，没有自动一致性检查；改规则顺序、过滤条件、策略组时
  三份都要改。YAML 两份只做了语法与引用校验，没有在 Stash / mihomo 真机启动验证。
- 订阅过滤依赖节点命名；换机场后 Loon 的 `[Remote Filter]` 与 YAML 里的 `filter` /
  `exclude-filter` 都要重写。
- 配置是个人自用的公开备份，不保证适配所有 Loon 版本；`[Proxy Chain]` 需要 Loon 3.1.0+，
  旧版本会忽略该段（链名引用会变成未定义策略）。
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
