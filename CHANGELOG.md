# Changelog

按日期倒序。只记录会改变分流行为或文件结构的改动；每日上游同步的机器提交不单列。

## 2026-11-13

### 新增：AI 走「机场 → 住宅」代理链

- Loon 新增 `[Proxy Chain]` 段：`US-Resi-Chain = AI-Entry,US-Resi`。
  队首是机场入口，队尾是静态住宅 socks5；链行没有参数、没有 fallback，入口挂掉整条链即断。
- `[Proxy]` 新增 `US-Resi`（`socks5,<residential-host>,<port>,USERNAME,PASSWORD,udp=false`）。
  住宅出口单连接约 20 KB/s（拨号级上行），套一跳机场后实测约 250 KB/s。
- 新增 `AI-Entry` select 组作为链的入口跳，只服务 AI，不影响主 `Proxy` 组。
- Stash / Clash.Meta 没有 `[Proxy Chain]`，同一逻辑由出口节点的 `dialer-proxy: AI-Entry` 表达。
- `udp-fallback-mode = REJECT` 配合 `US-Resi` 的 `udp=false`：AI 站点的 QUIC/WebRTC
  UDP 被丢弃后回落 TCP，避免 UDP 从另一个出口出去造成 IP 不一致。

### 变更：策略组语义

- `AI`：`fallback` → `select,US-Resi-Chain,SubB-TW-All_Filter,SubA-TW_Filter,Home-Proxy`。
  默认选链，后面挂台湾家宽做手动备选。
- `Proxy`：`fallback` → `select,SubB-TW_Filter,SubB-Rest_Filter,SubA-TW_Filter,SubA-Rest_Filter,Home-Proxy`。
  select 的成员在策略页可见、可手动挑；fallback 不保存选择也不接受指定。

### 新增：GitHub / X / Epic / Steam 分流

- 新策略组：`GitHub`（`Proxy`）、`X`（`Proxy`）、`Epic`（`Proxy, DIRECT`）、`Steam`（`Proxy, DIRECT`）。
  游戏平台多给一个 DIRECT：下载/更新吃满家宽带宽，走机场只白烧流量与倍率。
- 新远程规则：`GitHub.list` → `GitHub`、`Twitter.list` → `X`、`Epic.list` → `Epic`、`Steam.list` → `Steam`。
- Stash / Clash 同步新增 4 个 `rule-providers` 与对应 `RULE-SET`。

### 变更：图标

- `AI-Entry` 用 `Bard.png`；`GitHub` / `X` / `Epic` / `Steam` 分别用
  `GitHub.png` / `TwitterX.png` / `EpicGames.png` / `Steam.png`。
- 自托管图标总数 31 个（本轮新增 5 个）。

### 变更：General

- `ip-mode = v4-only` → `prefer-v4`。
- 删除 `ipv6 = true`（端点解析不再依赖强制开 IPv6）。
- 删除 `switch-node-after-failure-times = 2`：与 `test-timeout = 3` 叠加会把弱网节点成批误判。

### 工具

- `scripts/validate_config.py` 认识 `[Proxy Chain]`：链名可作为策略被规则/组引用，
  并新增成员存在性与自引用检查。

### 文档

- README 计数更新为 31 个策略组 / 29 条本地规则 / 38 条远程规则 / 31 个图标，
  补充「AI 的代理链」一节与三份配置的链式表达差异。

### 脱敏

- 本文件里的所有地址、端口、账号、口令、订阅 token、WireGuard 密钥均为占位符：
  `192.0.2.10` / `198.51.100.7`（RFC 5737）、`<residential-host>`、`USERNAME`、`PASSWORD`、
  `YOUR_TOKEN`、`<client-private-key>`、`2001:db8::1`（RFC 3849）。
- 订阅服务商名统一为 `SubA` / `SubB`；个人常用域名、内网 NAS 规则与真实节点命名未进入仓库。

## 2026-11-12

- 每日上游同步按计划运行，无配置改动。

## 2026-11-11

- 新增 `Stash.yaml` 与 `Clash.yaml`，与 `Loon-routing.conf` 保持同一套分流策略。
- 仓库收敛为单一纯分流配置：移除插件、脚本与 MITM 相关段落，改为按 README 自行订阅。
- 去广告同时启用 `Advertising` 与 `AdRules` 两张规则表。
- 隐私清理：脱敏订阅服务商名、个人常用域名、内网 NAS 与 WireGuard 真实参数。
