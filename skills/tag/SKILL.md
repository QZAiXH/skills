---
name: tag
description: 指定用户提供的 tag，调用 release-notes 技能生成中文发布说明，然后按用户选择使用 git push 或 gh release create 发布 tag 或 GitHub Release。用于用户要求自动打 tag、发布版本 tag、创建 GitHub Release、用 release notes 发版、推送 tag 等场景。必须要求用户明确给出 tag，禁止自行推断、递增或生成 tag 名。
---

# Tag

用用户明确指定的 tag 生成发布说明并发布版本。这个技能只编排 tag 发布流程，发布说明必须复用 `release-notes` 技能。

## 硬性规则

- 必须由用户提供准确 tag。用户没有给 tag 时，先询问 tag，不要从历史 tag、日期、版本文件、提交信息或分支名推断。
- 在任何会创建 tag、创建 release、推送远端的命令前，先询问用户选择 `push` 还是 `gh`。如果用户已明确指定方式，复述该方式后继续。
- 只基于已提交的 `HEAD` 生成发布说明。工作区有未提交变更时，明确提醒这些变更不会包含在默认发布说明中。
- 不能使用 `gh --generate-notes` 替代 `release-notes` 技能。
- 发布说明文件必须通过 `release-notes` 技能里的 `scripts/validate_release_notes.py` 校验后，才能创建 tag、推送 tag 或创建 GitHub Release；校验失败时停止发布并修正文案。
- 遇到鉴权、权限或远端拒绝问题时，不要尝试处理凭据；保留发布说明文件路径，并把用户可以自行执行的命令列出来。
- `git push origin "$TAG"` 或 `gh release create ...` 成功返回后，立即进入最终回复；不要等待 GitHub Actions、Docker 镜像编译、部署流水线或任何异步任务完成，也不要主动轮询构建状态。

## 工作流程

1. 确认输入：
   - `TAG`：用户明确提供的 tag。
   - `METHOD`：用户选择的 `push` 或 `gh`。
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
   - 读取已安装的 `release-notes` 技能。
   - 解析 `release-notes` 技能里的脚本时，以该技能的 `SKILL.md` 所在目录为基准，并使用绝对路径执行。
   - 按该技能流程运行上下文收集脚本，例如：

```bash
RELEASE_NOTES_SKILL_DIR="<release-notes skill dir>"
RELEASE_NOTES_SCRIPT="$RELEASE_NOTES_SKILL_DIR/scripts/collect_release_context.py"
python3 "$RELEASE_NOTES_SCRIPT" --repo . --target-ref HEAD
```

   - 生成中文 GitHub Releases 风格发布说明。
   - 将发布说明写到仓库外临时文件，避免污染工作区，例如：

```bash
NOTES_FILE="/tmp/release-notes-${TAG}.md"
```

   - 校验发布说明文件结构，确保不是裸项目符号列表，也不是上下文收集脚本输出：

```bash
VALIDATE_RELEASE_NOTES_SCRIPT="$RELEASE_NOTES_SKILL_DIR/scripts/validate_release_notes.py"
python3 "$VALIDATE_RELEASE_NOTES_SCRIPT" "$NOTES_FILE"
```

   - 如果校验失败，先修改 `$NOTES_FILE` 并重新运行校验；不要继续执行 `git tag`、`git push` 或 `gh release create`。

4. 根据用户选择发布。

## push 方式

创建 annotated tag，并把 tag 推送到 `origin`：

```bash
git tag -a "$TAG" -F "$NOTES_FILE" HEAD
git push origin "$TAG"
```

`git push` 成功返回后，发布动作即完成；不要检查或等待后续 Docker 编译、CI、部署任务。

如果 `git tag` 已成功但 `git push` 失败，只给用户补充推送命令：

```bash
git push origin "$TAG"
```

如果 `git tag` 也未成功，给出完整命令：

```bash
git tag -a "$TAG" -F "$NOTES_FILE" HEAD
git push origin "$TAG"
```

## gh 方式

先检查 `gh` 可用且已认证：

```bash
command -v gh
gh auth status
```

使用用户提供的 tag 和生成的说明创建 GitHub Release，并把 tag 指向当前 `HEAD`：

```bash
gh release create "$TAG" --target "$(git rev-parse HEAD)" --title "$TAG" --notes-file "$NOTES_FILE"
```

`gh release create` 成功返回后，发布动作即完成；不要检查或等待后续 Docker 编译、CI、部署任务。

如果要求只能基于已经存在的远端 tag 创建 Release，先让用户确认改用 `push` 方式创建并推送 tag，再执行：

```bash
gh release create "$TAG" --verify-tag --title "$TAG" --notes-file "$NOTES_FILE"
```

权限失败时，不要继续尝试登录或修改凭据；输出用户可自行执行的 `gh release create ...` 命令和 `NOTES_FILE` 路径。

## 发布说明校验失败时

保持 `$NOTES_FILE` 路径不变，按 `release-notes` 的标准章节结构重写内容。最小合格结构示例：

```markdown
## 版本亮点

- <1-3 条真实发布亮点>

## 新增功能

- <真实变更>

## Contributors

- @<github-username>
- [github-actions bot](https://github.com/apps/github-actions)
```

修正后重新运行：

```bash
python3 "$VALIDATE_RELEASE_NOTES_SCRIPT" "$NOTES_FILE"
```

## 最终回复

回复必须包含：

- 使用的 tag 和发布方式。
- 发布说明文件路径。
- 已成功执行的发布动作。
- 如果失败，明确失败点，并给出用户可自行执行的命令。
