---
name: commit
description: >
  智能 Git 提交助手。仅在用户手动触发时使用（输入 /commit 或明确要求"提交代码"、"commit"）。
  自动暂存相关变更文件，校验当前分支名是否匹配提交类型，不匹配时自动创建新分支，
  生成符合 Conventional Commits 规范的中文提交信息。
  不要在用户没有明确要求 commit 的情况下主动触发此 skill。
---

# Smart Commit

智能 Git 提交助手：自动暂存、分支校验、中文 Conventional Commits。

## 何时使用

仅在用户明确要求时使用：
- 用户输入 `/commit`
- 用户说"提交代码"、"帮我 commit"、"提交一下"
- 用户完成开发后要求保存变更到 git

不要在以下场景自动触发：
- 用户只是在讨论代码
- 用户在做代码修改但没有要求提交
- 用户在做 review 或 debug

## 工作流程

### 1. 收集变更信息

并行执行以下命令，全面了解当前工作状态：

```bash
# 当前分支
git branch --show-current

# 工作区状态（不要用 -uall）
git status

# 已暂存和未暂存的变更
git diff
git diff --cached

# 最近提交记录（了解上下文）
git log --oneline -10
```

### 2. 分析变更，确定提交类型和范围

基于变更内容，判断以下信息：

**提交类型（type）**：

| type       | 含义                                     |
|------------|------------------------------------------|
| `feat`     | 新功能                                   |
| `fix`      | 修复 Bug                                 |
| `refactor` | 重构（既不是新功能也不是修复）           |
| `docs`     | 文档变更                                 |
| `style`    | 代码格式（不影响逻辑）                   |
| `perf`     | 性能优化                                 |
| `test`     | 测试相关                                 |
| `build`    | 构建系统或外部依赖变更                   |
| `ci`       | CI/CD 配置变更                           |
| `chore`    | 其他杂项（不修改 src 或 test 的变更）    |

**选择逻辑**：
- 如果变更包含多种类型，选择最主要的那个
- 新功能 + Bug 修复 → 优先 `feat`
- 纯文件格式调整 → `style`
- 不确定时，偏向 `feat` 或 `fix`

**范围（scope）**：
- 从变更文件路径自动推断模块名
  - `internal/biz/marketview/` → `marketview`
  - `internal/service/notification/` → `notification`
  - `api/user/` → `user`
  - `internal/data/ent/schema/` → `schema`
  - `configs/` → `config`
- 如果变更跨多个模块，取最主要的模块作为 scope
- 如果变更过于分散无法归纳，可以省略 scope

### 3. 校验分支名

**分支命名约定**：`<type>/<简短描述>`

例如：
- `feat/notification-system`
- `fix/user-feedback-count-query`
- `refactor/auth-middleware`
- `docs/api-guide`

**校验规则**：

1. **获取当前分支名**和步骤 2 确定的提交类型
2. **受保护分支**（`main`、`master`、`test`、`develop`）：必须创建新分支，不允许直接提交
3. **分支前缀匹配**：检查当前分支名是否以提交类型开头
   - 当前分支 `fix/user-feedback-count-query`，提交类型 `fix` → 匹配
   - 当前分支 `fix/user-feedback-count-query`，提交类型 `feat` → 不匹配
   - 当前分支 `feat/notification`，提交类型 `feat` → 匹配
4. **类型兼容性**：以下组合视为兼容（无需切分支）
   - `feat` 分支上提交 `fix`（功能开发中修 bug 很正常）
   - `feat` 分支上提交 `refactor`、`style`、`test`、`docs`（功能开发中的附带变更）
   - 任何分支上提交 `chore`、`ci`、`build`（基础设施变更不挑分支）

**不匹配时的处理**：

如果当前分支不匹配且不属于兼容组合：

1. 根据提交类型和 scope 自动生成分支名：`<type>/<scope-或-简短描述>`
2. 告知用户："当前分支 `xxx` 与提交类型 `yyy` 不匹配，建议创建新分支 `yyy/zzz`"
3. 等待用户确认后再创建分支并切换
4. 如果用户说"就在当前分支提交"，尊重用户决定，跳过分支切换

### 4. 暂存文件

**自动暂存策略**：

1. 将所有与本次变更相关的文件加入暂存区
2. 包括：已修改文件（modified）、新增文件（untracked，但与本次开发相关的）
3. **必须排除的文件**（绝对不要 add）：
   - `.env`、`.env.*` 等环境变量文件
   - `credentials.json`、`*.pem`、`*.key` 等密钥文件
   - `node_modules/`、`vendor/` 等依赖目录
   - `.DS_Store`、`Thumbs.db` 等系统文件
   - 任何看起来包含敏感信息的文件
4. **需要确认的文件**：
   - 二进制文件（图片、编译产物等）
   - 与变更主题明显无关的文件
   - `*_gen.go`、`wire_gen.go` 等生成文件（如果对应的源文件也有变更则应该包含）

使用 `git add <具体文件路径>` 逐个添加，不要用 `git add .` 或 `git add -A`。

如果发现敏感文件在变更列表中，**立即警告用户**并跳过这些文件。

### 5. 生成提交信息

**格式**（严格遵循 Conventional Commits）：

```
<type>(<scope>): <中文描述>

<可选的详细说明，中文>
```

**规则**：

- **第一行**（标题）：
  - `type` 和 `scope` 用英文，冒号后的描述用**中文**
  - 不超过 72 个字符（中文字符算 2 个宽度）
  - 使用动宾结构：`修复 XX 问题`、`新增 XX 功能`、`优化 XX 逻辑`
  - 不要以句号结尾
  - 示例：`fix(marketview): 修复字典列表 Count 查询异常`

- **正文**（可选）：
  - 当变更比较复杂时添加，简单变更可省略
  - 用中文描述变更的原因和影响
  - 与标题之间空一行

- **BREAKING CHANGE**：
  - 如果是破坏性变更，在 type 后加 `!`：`feat(api)!: 重构用户认证接口`
  - 并在正文中说明：`BREAKING CHANGE: <中文描述影响>`

**示例**：

```
feat(notification): 新增消息通知列表查询接口

支持按状态、类型筛选和关键词搜索，包含完整的三层架构实现
```

```
fix(marketview): 修复字典列表 Count 查询异常
```

### 6. 执行提交

1. 将生成的提交信息展示给用户确认
2. 用户确认后，使用 HEREDOC 格式执行 `git commit`：
   ```bash
   git commit -m "$(cat <<'EOF'
   <提交信息>
   EOF
   )"
   ```
3. 提交后运行 `git status` 确认状态

**如果 pre-commit hook 失败**：
- 读取错误信息，诊断问题
- 修复问题（如 lint 错误）
- 重新暂存修复后的文件
- 创建**新的** commit（不要用 --amend，因为之前的 commit 没有成功）

### 7. 提交后报告

简洁报告：
- 提交到哪个分支（如果切换了分支，说明从哪切到哪）
- 提交了哪些文件（数量）
- 提交信息是什么
- 如果是新分支，提醒用户后续可能需要 `git push -u origin <branch>`

## 边界情况

**没有变更**：如果 `git status` 显示工作区干净，告知用户没有需要提交的变更。

**只有暂存区有变更**：直接使用已暂存的文件，不额外添加。

**混合状态**：既有暂存又有未暂存的变更，合并处理，确保所有相关文件都被包含。

**合并冲突中**：检测到冲突状态时，提醒用户先解决冲突再提交。
