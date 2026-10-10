# yantaolu Homebrew Tap

macOS 命令行工具的 Homebrew 配方与预编译 bottles。

## 安装与升级

```sh
brew install yantaolu/tap/codex-switch
brew upgrade codex-switch
```

[codex-switch](https://github.com/yantaolu/codex-switch) 管理多个 ChatGPT 官方账户和 Responses 兼容服务商，提供交互菜单及子命令。需要官方 Codex CLI 完成登录、切换核验、官方额度查询与会话接续。切换后手动打开客户端。

Apple Silicon 与 Intel 的匹配平台使用预编译 bottle；不匹配时回退源码构建并安装 Go 构建依赖。运行程序本身不需要 Go。

## 卸载

```sh
brew uninstall codex-switch
```

卸载保留账户库与 Keychain。账户管理说明见[使用指南](https://github.com/yantaolu/codex-switch/blob/main/docs/usage.md)。

## 配方维护

1. 等待主项目的稳定 Release 发布，核对源码包与校验和。
2. 通过 PR 更新 `Formula/codex-switch.rb`；CI 在 Apple Silicon 和 Intel 上构建、测试 bottles。
3. 所有检查通过后，运行 `brew pr-pull` 工作流，填写 PR 编号及已审核的 head SHA。
4. 工作流发布 bottles，提交对应校验和并关闭 PR。验证实际下载、安装和版本后完成更新。

CI 采用 Homebrew 官方 `setup-homebrew`、`test-bot` 和 `pr-pull` 流程。配方与 bottle 附件均由此仓库维护，不包含任何用户账户数据。
