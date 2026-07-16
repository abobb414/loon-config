# Loon 配置

一份自用 Loon 配置，重点是清晰分流、自动测速、媒体与 AI 服务独立策略，以及每日上游资源刷新。

## 内容

- `Loon.conf`：主配置文件。
- `scripts/refresh_upstreams.py`：扫描配置中的上游资源并生成状态锁定清单。
- `.github/workflows/refresh-upstreams.yml`：每日自动刷新上游资源元数据。
- `.upstream/upstreams.lock.json`：上游资源状态、ETag、Last-Modified 与 sha256 记录。

公开版配置不包含节点订阅地址；请在 Loon 本地添加自己的远程代理订阅。

## 图标库

图标订阅地址：

- `https://raw.githubusercontent.com/abobb414/loon-config/refs/heads/main/IconSet/Color/icons-all.json`
- `https://raw.githubusercontent.com/fmz200/wool_scripts/main/icons/icons-all.json`

## 分流策略

配置包含以下主要策略组：

- 基础：`Proxy`、`Available`、`Final`
- 平台：`Google`、`Apple`、`Microsoft`
- 流媒体：`Netflix`、`Disney`、`HBO`、`Spotify`、`YouTube`、`Bilibili`
- 社交与通信：`WeChat`、`Instagram`、`Telegram`、`LinkedIn`
- 金融支付：`Finance`，覆盖支付宝、云闪付与常用国内银行
- 短视频：`TikTok`、`Douyin`
- AI：`AI`、`OpenAI`、`Gemini`、`Claude`；`AI` 自动测速选择非港区节点，三个应用策略默认使用 `AI`，也可手动指定地区；Gemini 规则由 blackmatrix7 基础规则和本仓库补充规则自动合并
- Emby：`Emby`、`EmbyProxy`

`Available` 负责自动测速；`Proxy` 作为总代理；`Final` 处理未命中规则的兜底流量。`AI` 及三个应用策略均不包含香港节点，避免不稳定的香港线路参与 AI 分流。

## 自动更新

GitHub Actions 每天运行一次，也可手动触发：

- 读取 `Loon.conf` 中启用的上游资源链接。
- 校验核心规则、图标、GeoIP 与资源解析器是否可访问。
- 更新 `.upstream/upstreams.lock.json`。
- 核心上游短暂不可达时保留上次成功记录，避免偶发网络抖动中断每日任务。
- 若元数据发生变化，自动提交到当前分支。

Loon 端的远程规则仍直接引用上游地址，因此应用内刷新配置时会拉取上游最新规则。

## 致谢

本配置基于以下项目与资源整理：

- [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)：Loon 远程分流规则。
- [Koolson/Qure](https://github.com/Koolson/Qure)：策略组图标。
- [fmz200/wool_scripts](https://github.com/fmz200/wool_scripts)：插件、广告规则与补充图标。
- [Moli-X/Tool](https://github.com/Moli-X/Tool)：Loon 配置结构参考、GeoIP/ASN 资源。
- [sub-store-org/Sub-Store](https://github.com/sub-store-org/Sub-Store)：订阅解析器与订阅管理生态。
- Kelee Loon 插件资源：配置中使用的插件模块来源。
- [Loon](https://apps.apple.com/app/loon/id1373567447)：客户端与配置运行环境。

感谢以上项目作者与维护者的持续更新。

## 说明

本仓库仅用于个人配置备份与学习整理。请根据自己的订阅、节点、地区需求和网络环境调整后使用。
