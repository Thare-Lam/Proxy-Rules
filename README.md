# Proxy-Rules

从同一份规则和策略组定义生成 Shadowrocket 与 OpenClash 配置。基于 LingJingMaster/Shadowrocket-Rules，保留上游 MIT 许可证与作者版权。

## 使用地址

- [Shadowrocket 配置](https://raw.githubusercontent.com/Thare-Lam/Proxy-Rules/release/Shadowrocket.conf)
- [OpenClash 路由覆写](https://raw.githubusercontent.com/Thare-Lam/Proxy-Rules/release/OpenClash.yaml)
- [两端兼容性报告](https://raw.githubusercontent.com/Thare-Lam/Proxy-Rules/release/conversion-report.json)

Shadowrocket 导入配置地址并设为使用中，首页配置自己的节点订阅。在设置中启用配置自动更新，并允许 iOS 后台 App 刷新。刷新时间由 iOS 调度。

OpenClash 的输出通过路由器本地覆写与节点订阅合并。部署细节见 [双端维护与更新](UNIFIED.md)。它包含代理组、规则集和路由规则，节点凭据及设备网络设置由路由器提供。

## 维护入口

- `source/routing.json` 维护两端共用的分流顺序、策略组和地区筛选。
- 根目录 `.list` 文件维护服务域名与 IP 条目。
- `source/shadowrocket.conf` 维护 iOS 专用 DNS、Host 等设置。

提交到 main 后，Actions 抓取外部规则快照、运行测试，并在一次提交中发布两份配置到 release 分支。每天北京时间 03:23 也会刷新外部规则。路由器每小时检查已发布配置，Shadowrocket 按 App 的设置刷新。

两端规则使用同批快照。小火箭专属的 USER-AGENT、URL-REGEX 匹配列在转换报告中。新出现的未知类型使构建失败，等待适配，发布分支保留上次版本。

## 来源

- [LingJingMaster/Shadowrocket-Rules](https://github.com/LingJingMaster/Shadowrocket-Rules)
- [blackmatrix7/ios_rule_script](https://github.com/blackmatrix7/ios_rule_script)

许可证见 [LICENSE](LICENSE)。
