---
name: tag
description: 指定用户提供的 tag，调用本仓库 .codex/skills/release-notes 生成中文发布说明，创建带发布说明的 annotated tag 并推送到 origin，由 CI/CD 自动创建 GitHub Release。用于用户要求自动打 tag、发布版本 tag、推送 tag、用 release notes 发版、触发发布流水线等场景。必须要求用户明确给出 tag，禁止自行推断、递增或生成 tag 名。
---

# Tag

用用户明确指定的 tag 生成发布说明，创建 annotated tag 并推送到远端以触发发布流水线。这个技能只编排 tag 发布流程，发布说明必须复用本仓库的 `.codex/skills/release-notes`。

## 硬性规则

- 必须由用户提供准确 tag。用户没有给 tag 时，先询问 tag，不要从历史 tag、日期、版本文件、提交信息或分支名推断。
- 只基于已提交的 `HEAD` 生成发布说明。工作区有未提交变更时，明确提醒这些变更不会包含在默认发布说明中。
- 不能使用 `gh --generate-notes` 替代 `.codex/skills/release-notes`。
- 发布说明文件必须通过 `.codex/skills/release-notes/scripts/validate_release_notes.py` 校验后，才能创建 tag 或推送 tag；校验失败时停止发布并修正文案。
- 必须创建 annotated tag，且 tag message 必须使用校验通过的发布说明：`git tag -a "$TAG" -F "$NOTES_FILE" HEAD`。禁止创建 lightweight tag。
- 禁止直接创建 GitHub Release，包括 `gh release create` 和 `gh release create --target`；仓库 CI/CD 会在 tag push 后自动创建或更新 Release。
- 遇到鉴权、权限或远端拒绝问题时，不要尝试处理凭据；保留发布说明文件路径，并把用户可以自行执行的命令列出来。
- `git push origin "$TAG"` 成功返回后，立即进入最终回复；不要等待 GitHub Actions、Docker 镜像编译、部署流水线或任何异步任务完成，也不要主动轮询构建状态。

## 工作流程

1. 确认输入：
   - `TAG`：用户明确提供的 tag。
   - 目标仓库：默认当前目录；如果用户指定路径，先切到该仓库。

2. 运行发布前检查：

```bash
git rev-parse --show-toplevel
git status --short
git tag --list "$TAG"
git ls-remote --tags origin "$TAG"
```

如果本地或远端已有同名 tag，停止并让用户决定是否换 tag 或处理已有 tag。

3. 调用 release-notes 技能：
   - 读取 `.codex/skills/release-notes/SKILL.md`。
   - 按该技能流程运行上下文收集脚本，例如：

```bash
python3 .codex/skills/release-notes/scripts/collect_release_context.py --repo . --target-ref HEAD
```

   - 生成中文 GitHub Releases 风格发布说明。
   - 将发布说明写到仓库外临时文件，避免污染工作区，例如：

```bash
NOTES_FILE="/tmp/release-notes-${TAG}.md"
```

   - 校验发布说明文件结构，确保不是裸项目符号列表，也不是上下文收集脚本输出：

```bash
python3 .codex/skills/release-notes/scripts/validate_release_notes.py "$NOTES_FILE"
```

   - 如果校验失败，先修改 `$NOTES_FILE` 并重新运行校验；不要继续执行 `git tag` 或 `git push`。

4. 创建并推送 annotated tag。

## 发布方式

创建 annotated tag，并把 tag 推送到 `origin`，由 CI/CD 自动创建或更新 GitHub Release：

```bash
git tag -a "$TAG" -F "$NOTES_FILE" HEAD
git push origin "$TAG"
```

`git push` 成功返回后，发布动作即完成；不要检查或等待后续 GitHub Actions、Docker 编译、CI、部署任务或 Release 资产上传。

如果 `git tag` 已成功但 `git push` 失败，只给用户补充推送命令：

```bash
git push origin "$TAG"
```

如果 `git tag` 也未成功，给出完整命令：

```bash
git tag -a "$TAG" -F "$NOTES_FILE" HEAD
git push origin "$TAG"
```

## 发布说明校验失败时

保持 `$NOTES_FILE` 路径不变，按 `release-notes` 的标准章节结构重写内容。最小合格结构示例：

```markdown
## 版本亮点

- <1-3 条真实发布亮点>

## 新增功能

- <真实变更>

## Contributors

- @<github-username 或作者名>
```

修正后重新运行：

```bash
python3 .codex/skills/release-notes/scripts/validate_release_notes.py "$NOTES_FILE"
```

## 最终回复

回复必须包含：

- 使用的 tag。
- 发布说明文件路径。
- 已成功执行的发布动作：annotated tag 创建与 `git push origin "$TAG"`。
- 说明 GitHub Release 由 CI/CD 在 tag push 后自动创建或更新，当前流程不直接创建 Release。
- 如果失败，明确失败点，并给出用户可自行执行的命令。
