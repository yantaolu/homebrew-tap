# yantaolu Homebrew Tap

macOS 命令行工具的 Homebrew 配方与预编译 bottles。

## 安装与升级

```sh
brew install yantaolu/tap/codex-switch
brew upgrade codex-switch
```

[codex-switch](https://github.com/yantaolu/codex-switch) 管理多个 ChatGPT 官方账户和 Responses 兼容服务商，提供交互菜单及子命令。需要官方 Codex CLI 完成登录、切换核验、官方额度查询与会话接续。切换后手动打开客户端。

Apple Silicon 与 Intel 的匹配平台使用预编译 bottle；其他 macOS 平台直接安装对应架构的正式版二进制包。安装和运行都不需要 Go。

## 卸载

```sh
brew uninstall codex-switch
```

卸载保留账户库与 Keychain。账户管理说明见[使用指南](https://github.com/yantaolu/codex-switch/blob/main/docs/usage.md)。

## 配方维护

1. 主项目公开稳定 Release 后，已配置的 GitHub App 自动创建版本更新 PR。
2. CI 在 Apple Silicon 和 Intel 上安装正式版二进制包、生成并测试 bottles。
3. 双架构验收成功后，发布工作流自动核对 PR head、正式 Release 与测试附件，合并配方并上传 bottles。
4. 公开 bottles 的校验和通过后才更新主分支，关闭 PR 并清理分支。用户执行 `brew upgrade codex-switch` 即可升级。

App 仅授权本 Tap 的 Contents 与 Pull requests 写入权限，配置步骤见[发布指南](https://github.com/yantaolu/codex-switch/blob/main/docs/releasing.md)。预发布、旧版本、测试失败、过期附件和被修改的 PR 不会自动发布。重复事件不会替换已有附件；上传中断后重试只补缺失文件。

主项目 **Sync Homebrew Tap** 可输入正式 tag 手动重试同步；本仓库 **brew pr-pull** 保留手动恢复入口，填写已通过验收的 PR 编号和完整 head SHA。两种入口使用相同校验。

CI 采用 Homebrew 官方 `setup-homebrew`、`test-bot`、`pr-pull` 和 bottle 合并流程。配方与 bottle 附件均由此仓库维护，不包含任何用户账户数据。
