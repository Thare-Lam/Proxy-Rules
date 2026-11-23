# 双端规则维护

统一来源为 `source/routing.json` 中的策略组、分流顺序，以及根目录的各个 `.list` 文件。`source/shadowrocket.conf` 保存 iOS 专用 DNS、Host 和 URL Rewrite 等设置。上游许可证及原文件保留。

修改后 GitHub Actions 同时生成 Shadowrocket.conf 和 OpenClash.yaml，提交到 `release` 分支。工作流也在每天北京时间 03:23 抓取外部规则集。生成器失败时任务报错，发布分支保留上一个版本。首次 fork 后需要在 Actions 页面启用工作流并运行一次。

## 输出与一致性

- `release/Shadowrocket.conf` 包含更新地址、策略组及规则引用。
- `release/OpenClash.yaml` 是供 OpenClash 本地覆写合并的 YAML，包含策略组、规则集及分流顺序。节点订阅和设备 DNS 等设置由路由器本地配置提供。
- 生成器同一次读取远端规则集，为 Shadowrocket 写入以内容哈希命名的 `.list` 快照，为 OpenClash 写入相同快照的 inline providers。发布分支保留旧快照，已下载旧配置的设备继续可用。
- `conversion-report.json` 列出两端差异。Mihomo 无对应语义的 USER-AGENT、URL-REGEX 项在小火箭保留，并记入报告。新的未知规则类型使构建失败，等待显式适配。
- `PROTOCOL` 转换为 Mihomo `NETWORK`，`FINAL` 转为 `MATCH`。小火箭组的秒级 timeout 转为毫秒。地区“其他节点”的负向前瞻转换为 Mihomo 的 exclude-filter。

本次以作者默认策略为基础。AI 默认美国组，Google 默认日本组，地区组沿用作者的自动测速类型。手机和路由器的节点选项取决于各自订阅。

## 本地生成

需要 Python 3.9 及以上版本。

```sh
python3 -m unittest discover -s tests
python3 scripts/build.py --repository Thare-Lam/Proxy-Rules
```

输出到 dist。生成器只从公开规则源读取数据。设备节点凭据保存在设备上。

## 客户端接入

Shadowrocket 导入以下地址，并在 App 中使用该配置、开启配置后台更新和 iOS 后台 App 刷新。首页继续使用自己的节点订阅。iOS 决定实际后台刷新时间。

```text
https://raw.githubusercontent.com/Thare-Lam/Proxy-Rules/release/Shadowrocket.conf
```

OpenClash 使用同仓库的 `release/OpenClash.yaml`。在路由器安装 `router/merge.rb`、`router/update.sh` 到 `/etc/openclash/custom/unified-rules/`，并保存 `repository`（账号/仓库）、`profile`（如 MetaGlide.yaml）和已验证的初始 `overlay.yaml`。

在现有 custom overwrite 脚本中，只针对这个 profile 调用 merge.rb，将缓存的 overlay.yaml 合并到启动中的 YAML。已有 blackmatrix7 生成调用由此取代。首次部署前备份入口和配置，保留入口其他功能，验证生成配置以及 Tailscale 等本地规则的优先级。

update.sh 建议每小时执行一次。它先下载候选规则、合并当前配置并用本机内核检查，通过后替换缓存并重启，检查运行状态和实际规则。失败则恢复上一个规则版本。初次安装和 cron 写入需在路由器部署时执行并验收，包内脚本本身不会安装这些设置。

## 本次验证范围

生成器与本机内核应在每次变更后完成校验。Shadowrocket 的实际导入及后台刷新需要在 iPhone 上验证。
