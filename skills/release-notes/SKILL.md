---
name: release-notes
description: 根据 GitHub 仓库当前分支最新代码与上一个 tag 的差异生成中文 GitHub Releases 发布说明。用于用户要求"生成 release notes"、"写 GitHub Releases 说明"、"根据上个 tag 总结版本变更"、"发布版本说明"、"发版说明"、"CHANGELOG 发布摘要"等场景；默认输出中文，并按业界主流 Release Notes 格式组织新增、修复、优化、破坏性变更、升级注意事项和提交者等信息。
---

# GitHub Release Notes

生成中文 GitHub Releases 发布说明，默认比较当前分支 `HEAD` 与上一个可达 tag 之间的差异。

## 工作流程

1. 先确认当前目录是目标 Git 仓库；如果用户指定分支、tag 或路径，按用户输入执行。
2. 运行脚本收集上下文：

```bash
python3 .codex/skills/release-notes/scripts/collect_release_context.py
```

常用参数：

```bash
# 指定仓库路径、目标引用或基准 tag
python3 .codex/skills/release-notes/scripts/collect_release_context.py --repo . --target-ref HEAD --base-tag v1.2.3

# 输出 JSON，便于进一步脚本化处理
python3 .codex/skills/release-notes/scripts/collect_release_context.py --json
```

3. 阅读脚本输出的提交分类、文件变化、风险提示和统计信息；必要时用 `git diff <base-tag>..<target-ref> -- <file>` 查看关键文件细节。
4. 生成最终发布说明，必须使用中文，且必须写成完整 Markdown 章节，不要输出裸项目符号列表。
5. 如果用户要求保存文件、创建 tag 或发布 GitHub Release，先运行结构校验；校验失败时修改发布说明并重新校验，不要发布未通过校验的内容：

```bash
python3 .codex/skills/release-notes/scripts/validate_release_notes.py "$NOTES_FILE"
```

除非用户要求保存文件，否则直接输出 Markdown 内容。

## 对比规则

- 默认目标引用是 `HEAD`，代表当前分支最新已提交代码。
- 默认基准 tag 是目标引用可达的上一个 tag：
  - 如果 `HEAD` 没有精确指向 tag，使用最近的可达 tag。
  - 如果 `HEAD` 正好指向一个 tag，跳过该 tag，使用它之前的可达 tag，适合已打 tag 后生成说明。
- 如果自动识别不到 tag，明确告知用户仓库没有可对比的历史 tag，并请用户提供 `--base-tag` 或手动指定对比范围。
- 仅把已提交内容作为发布说明依据；如果工作区有未提交变更，提醒用户这些变更不会包含在默认结果中。

## 输出格式

### 硬性输出契约

- 最终发布说明必须包含 Markdown 二级标题，禁止只输出连续项目符号。
- 第一个二级标题必须是 `## 版本亮点`，并包含 1-3 条真实亮点。
- 必须包含 `## Contributors`，并列出至少一个贡献者。优先使用真实 GitHub login 的 `@username`；GitHub 会把 Release description 中的 @mention 渲染为链接，并在发布页 Contributors 区域显示头像。无法确认 login 时，使用指向 GitHub profile/app 的 Markdown 链接，不要只写纯名字。
- 至少包含 3 个标准章节：`## 版本亮点`、一个变更章节、`## Contributors`。
- 只能使用下列标准章节；没有内容的章节必须省略，不要用"无"、"暂无"、"无明确修复"填充：
  - `## 版本亮点`
  - `## 新增功能`
  - `## 问题修复`
  - `## 优化与重构`
  - `## 破坏性变更`
  - `## 升级注意事项`
  - `## 其他变更`
  - `## Contributors`
- 不要把上下文收集脚本输出直接当作发布说明；最终内容不得包含 `# Release Notes Context`、`## 提交分类`、`## 变更文件`、`## Git Diff Stat` 等中间分析标题。

默认使用以下 GitHub Releases 常见结构。没有内容的章节可以省略，保持简洁。

```markdown
## 版本亮点

- <用 1-3 条说明本次发布最重要的用户价值或工程价值>

## 新增功能

- <新增能力、接口、页面、配置项等>

## 问题修复

- <修复的问题，尽量说明用户可感知影响>

## 优化与重构

- <性能、体验、架构、可维护性、内部实现优化>

## 破坏性变更

- <不兼容变更、删除能力、接口/数据结构调整>

## 升级注意事项

- <数据库迁移、配置变更、依赖升级、部署步骤、回滚注意事项>

## 其他变更

- <文档、测试、CI、构建、依赖等补充信息>

## Contributors

- @<github-username>
- [github-actions bot](https://github.com/apps/github-actions)
```

## 写作要求

- 使用面向发布读者的语言，不直接堆砌提交记录。
- 优先说明行为变化和影响，再补充关键技术细节。
- 合并重复或同类提交；不要逐条翻译所有 commit。
- 对外部用户可见的能力放在前面，内部重构、测试和 CI 放在后面。
- 破坏性变更、数据库迁移、配置项变化、依赖升级和部署注意事项必须单独突出。
- 不确定是否属于破坏性变更时，用谨慎表述，如"可能需要验证"或"建议检查"。
- Contributors 必须先通过 PR author、GitHub commit API、`gh pr view` 或 `gh api users/<login>` 尽量解析为 GitHub login；不要把 Git commit author name 直接当作 GitHub 用户名。
- 保留必要的代码标识符、接口路径、配置名和 tag 名；其余说明用中文。

## 补充检查

在最终输出前快速核对：

- 对比范围是否正确：`<base-tag>..<target-ref>`。
- 是否遗漏删除、重命名、迁移文件、协议/schema/API 变化。
- 是否把测试、文档、CI 误写成用户功能。
- 是否只输出中文发布说明；英文专有名词可以保留。
- 如果用户要发布到 GitHub Release，内容应能直接复制到 Release description。
