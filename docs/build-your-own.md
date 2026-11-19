# 从零生成一套「按自己网络」的分流配置

这份文档讲的是本文仓库 `Loon-routing.conf` 背后的思路，以及**怎么把它改成你自己的网络**。
所有示例都用占位符：`YOUR_VPS_HOST`、`YOUR_TOKEN`、`YOUR_WIFI_1`。照抄前请先替换。

---

## 0. 先选路线，别一上来堆功能

| 路线 | 适合谁 | 你要准备 |
|---|---|---|
| A. 纯机场 | 只想稳定上网 | 一个机场订阅 |
| B. 机场 + 自建 VPS | 需要固定、干净的 AI 出口 | 机场订阅 + 一台 VPS |
| C. B + 家里回环 | 家里有多台设备、想集中分流 | B + 一台能跑 mihomo 的 NAS/软路由 |

本文以 **C** 为例，A/B 是它的子集——删掉用不上的段即可。

---

## 1. 流量是怎么走的

```
App ──► Loon
        ├─ 命中 REJECT 规则 ──────────────► 直接丢弃（去广告）
        ├─ 国内域名 / GEOIP,CN ──────────► DIRECT
        ├─ AI 域名 ─────────────────────► 自建 VPS（Hysteria2）
        ├─ 视频 / GitHub / 游戏 ─────────► 机场节点
        └─ 在家（Wi-Fi 名匹配）──────────► 家里 mihomo ──► 再按它自己的规则分流
                                                          默认出口仍是 VPS
```

要点：**Loon 永远负责去广告和第一层分流**；在家时把「代理类」流量整体丢给家里那台 mihomo，
出门/蜂窝时自己直连机场。AI 分组独立存在，任何情况下都不允许落到别的出口。

---

## 2. 需要准备的参数

先把这些东西列出来，后面逐项填进配置：

1. 机场订阅地址（含 token，**不要提交到公开仓库**）
2. 自建 VPS：地址、Hy2 端口、密码、SNI
3. 家里 mihomo：内网 IP、mixed 端口、socks5 用户名/密码
4. 家里 Wi-Fi 的 SSID（区分大小写，2.4G/5G 算两个）
5. NAS 的内网 IP（如果要从外面回访问 NAS）

---

## 3. `[General]`：只写必要的键

```ini
[General]
ip-mode = prefer-v4
udp-fallback-mode = REJECT
dns-server = 223.5.5.5,119.29.29.29
hijack-dns = *:53
allow-udp-proxy = true
proxy-test-url = http://www.gstatic.com/generate_204
internet-test-url = http://cp.cloudflare.com/generate_204
test-timeout = 3
real-ip = *.your-node-domain.example,*.your-airport-cdn.example
```

逐个说为什么：

- `ip-mode = prefer-v4`：IPv6 链路不稳的网络里，prefer-v4 能省掉大量超时；如果你有纯 IPv6 的
  服务（比如 WireGuard endpoint 用 v6），**不要**改成 v4-only。
- `hijack-dns = *:53` + `real-ip`：劫持后节点域名会被解析成 Fake-IP（198.18.x），Loon 拨号就会
  连到假地址形成回环。把所有**节点/AI/CDN 域名**写进 `real-ip`，让它们返回真实 A 记录。
- `test-timeout = 3`：1s 会让弱网节点被误判失败，url-test 组会疯狂抖。
- 不要禁用 UDP 443（`disable-udp-ports = 443`）：那是 MITM 时代的做法，纯分流配置下只会白丢 HTTP/3。

---

## 4. `[Proxy]`：自建节点 + 家里回环

```ini
[Proxy]
# 自建 VPS：Hysteria2（UDP，跨境比 TCP 抗丢包）
MyVPS = Hysteria2,YOUR_VPS_HOST,2086,"YOUR_HY2_PASSWORD",sni=YOUR_SNI,skip-cert-verify=true,udp=true

# 家里 mihomo：必须是 socks5，不是 http
Home-Hub = socks5,192.168.1.10,7890,USERNAME,"PASSWORD",udp=true,block-quic=true
```

为什么家里回环用 socks5：mixed 端口同时提供 SOCKS5 **UDP ASSOCIATE**，STUN/WebRTC 才能走通；
只用 http 的话 UDP 会被 `udp-fallback-mode` 甩成直连，家宽 IP 就泄漏了。

`skip-cert-verify=true` 只在节点用自签/非标准证书时需要；能配上正确 SNI 就别开。

---

## 5. `[Remote Proxy]`：机场订阅

```ini
[Remote Proxy]
Airport-A = https://example.com/subscribe?token=YOUR_TOKEN,udp=true,block-quic=true,skip-cert-verify=true,enabled=true
Airport-B = https://example.com/subscribe?token=YOUR_TOKEN,udp=true,block-quic=true,skip-cert-verify=true,enabled=true
```

- 订阅里的「剩余流量 / 套餐到期 / 官网」这类占位行会在策略组里污染 url-test，用过滤器全排掉（见下节）。
- 某些机场按 UA 发不同格式（浏览器 UA 返回 403）。Loon 自己会带 `Loon/xxx CFNetwork/...`，
  不要为了好看去加 `parser-enabled=true`。

---

## 6. `[Remote Filter]`：把订阅切成可用的集合

```ini
[Remote Filter]
# 台湾家宽（按节点名抓，排除订阅头部的占位行）
A-TW_Filter = NameRegex,Airport-A, FilterKey = "(?i)^(?!.*(剩余流量|距离下次|套餐到期|官网)).*HINET"
# 剩下的节点
A-Rest_Filter = NameRegex,Airport-A, FilterKey = "(?i)^(?!.*(剩余流量|距离下次|套餐到期|官网|HINET)).*"
# 机房节点（电台/下载这类不需要家宽的流量用）
A-IDC_Filter = NameRegex,Airport-A, FilterKey = "(?i)^(?!.*(剩余流量|HINET)).*(IDC|机房|IEPL)"
```

同一条订阅可以按节点名切出多个集合，策略组只引用集合，不引用订阅本身 —— 这样换订阅时只改一行。

---

## 7. `[Proxy Group]`：四种类型各司其职

```ini
[Proxy Group]
# 自动挑延迟最低的机场出口
Proxy = url-test,A-TW_Filter,A-Rest_Filter,url = http://www.gstatic.com/generate_204,interval = 600,tolerance = 100

# 自己的 VPS 单独成组，方便手动切
MyVPS-Group = select,MyVPS

# AI 四个入口各自独立，全部默认 VPS，都允许手动切到机场家宽兜底
AI = select,MyVPS-Group,A-TW_Filter
Claude = select,MyVPS-Group,A-TW_Filter
OpenAI = select,MyVPS-Group,A-TW_Filter
Gemini = select,MyVPS-Group,A-TW_Filter

# 在家切到家里 mihomo；出门/蜂窝回落 Proxy
WAN = ssid,default=Proxy,cellular=Proxy,"YOUR_WIFI_1"=Home-Hub,"YOUR_WIFI_2"=Home-Hub

# 代理类业务统一引用 WAN，于是「在家」这个状态只维护一处
GitHub = select,WAN
Netflix = select,WAN
YouTube = select,WAN
Emby = select,WAN,DIRECT

# 直连优先的业务
Apple = select,DIRECT,WAN
Bilibili = select,DIRECT,WAN

# 兜底
Final = select,WAN,DIRECT
```

关键点：

- **`ssid` 是唯一支持 `default/cellular/"SSID"` 参数的类型。** `select` 组写同样的参数会被静默忽略。
- `ssid` 组需要系统给 Loon **定位权限**（iOS 和 macOS 都一样），否则读不到 Wi-Fi 名，
  永远落 `default`。macOS：设置 → 隐私与安全性 → 定位服务 → Loon。
- AI 不要用一个组套所有入口：ChatGPT / Claude / Gemini 需要分别固定出口，一个被限流时只切一个。
- 想减少视觉噪音可以省掉 `cellular=`（蜂窝会落到 `default`），但不能省 SSID 项。

---

## 8. `[Rule]` 与 `[Remote Rule]`：顺序就是优先级

本地 `[Rule]` 永远先于 `[Remote Rule]` 匹配，`FINAL` 兜底。

```ini
[Rule]
# 广告阻断要能盖过白名单：本地 REJECT 写在 Apple/Google 白名单之前
DOMAIN,swcdn.apple.com,REJECT

# 订阅域名必须直连，否则拉订阅本身会走代理
DOMAIN,example-sub-backend.example,DIRECT

GEOIP,CN,DIRECT
FINAL,Final
```

```ini
[Remote Rule]
https://raw.githubusercontent.com/Cats-Team/AdRules/main/adrules.list, policy=REJECT, tag=AdRules, enabled=true
https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/OpenAI/OpenAI.list, policy=OpenAI, tag=OpenAI, enabled=true
https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/Claude/Claude.list, policy=Claude, tag=Claude, enabled=true
https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/Gemini/Gemini.list, policy=Gemini, tag=Gemini, enabled=true
https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/Proxy/Proxy.list, policy=WAN, tag=Proxy, enabled=true
https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Loon/ChinaMaxNoIP/ChinaMaxNoIP.list, policy=DIRECT, tag=ChinaMaxNoIP, enabled=true
```

经验：

- 广告表（AdRules）体积大（7 MB 级），启动会慢一点；嫌慢就 `enabled=false`，别删行。
- 订阅/测速/支付类域名要抢在广告表之前直连，否则会被 TLS 重置或 challenge。
- `GEOIP,CN,DIRECT` 必须留在 `FINAL` 前面，否则国内流量会被兜底组带走。

---

## 9. 家里那台 mihomo（可选，C 路线的核心）

跑在 NAS/软路由上的 mihomo（Clash.Meta 内核）只需要三件事：

1. **默认出口 = 你的 VPS**
   ```yaml
   rules:
     - GEOIP,CN,DIRECT
     - MATCH,MyVPS
   ```
2. **AI 分组只允许 VPS**（绝不 fallback 到机场）
   ```yaml
   proxy-groups:
     - name: AI-出口
       type: select
       proxies: [MyVPS]
   ```
3. **分类流量走机场**（Loon 把视频/GitHub 丢过来后，这里再分）
   ```yaml
   rules:
     - GEOSITE,youtube,主出口
     - GEOSITE,netflix,主出口
     - GEOSITE,github,主出口
     - GEOSITE,steam,主出口
   ```
   `GeoSite.dat` 放在 mihomo 的 `-d` 工作目录即可，无需额外配置。

改完 `mixin.yaml` 后重启服务，再用 API 验证链路：

```bash
curl -H "Authorization: Bearer $SECRET" http://127.0.0.1:9091/connections
# 看 chains：应为 ["主出口"] 或 ["MyVPS"]，rule/rulePayload 显示命中的规则
```

---

## 10. 验证清单

```bash
# 1. 默认出口（应是你的 VPS 城市）
curl -s https://www.cloudflare.com/cdn-cgi/trace | grep -E '^ip=|^loc='

# 2. 在家时 YouTube/GitHub 应该落在机场（看 mihomo 的 connections chains）
# 3. 下载测速（单流 + 多流各跑一次，判断是不是 100M 端口）
curl -o /dev/null -w '%{speed_download}\n' https://speed.cloudflare.com/__down?bytes=50000000
```

如果上传很慢但下载正常，先做对照：直连同一目标（`curl --noproxy '*'`）再测一次。
两边一样慢 = 跨境上行拥塞，不是 VPS 的问题。

---

## 11. 常见坑

| 现象 | 原因 |
|---|---|
| `ssid` 组永远不走家里那条 | 没给 Loon 定位权限（iOS/macOS 都会） |
| `ssid` 参数完全不生效 | 组类型写成了 `select`，它不支持这些参数 |
| 改了配置没变化 | Loon 不热重载，必须退出重开；iOS 要手动刷新配置 |
| 删除节点后策略组还显示旧名字 | MMKV 里存着旧选中项，在 UI 里重新选一次即可 |
| 所有节点 Timeout | `hijack-dns` 把节点域名解析成 Fake-IP，补 `real-ip` |
| 家里上网 DNS 被过滤失效 | LAN 段被整体吸进隧道；只把需要的端口/主机放行 |
| 订阅一直停在旧节点 | 订阅域名走了代理；给订阅域加 DIRECT |
| 分享配置后账号被盗 | 订阅 token / 节点密码 / WG 私钥进了公开仓库 |

---

## 12. 直接引用精简版

文末的 [`Loon-minimal.conf`](../Loon-minimal.conf) 是这份思路的最小骨架（约 100 行）：
纯分流 + 可选 VPS + 可选家里回环，替换其中 `YOUR_*` / `USERNAME` / `PASSWORD` 占位符即可用。

在 Loon 里：配置 → 添加配置 → URL，填：

```
https://raw.githubusercontent.com/abobb414/loon-config/main/Loon-minimal.conf
```

想在此基础上改，Fork 仓库后改自己那份 raw 地址，别直接改本仓库。
