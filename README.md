# QZAiXH Skills

这是可通过 `skills` CLI 安装的个人技能仓库，技能文件位于标准目录 `skills/<name>/SKILL.md`。

## 安装

列出仓库里的可用技能：

```bash
npx skills@latest add QZAiXH/skills --list
```

全局安装全部技能：

```bash
npx skills@latest add QZAiXH/skills --all -g
```

安装到当前项目：

```bash
npx skills@latest add QZAiXH/skills --all
```

只安装指定技能：

```bash
npx skills@latest add QZAiXH/skills --skill release-notes tag -g -y
```

## 技能列表

- `commit`: 智能 Git 提交助手。
- `release-notes`: 根据 GitHub 仓库当前分支与上一个 tag 生成中文发布说明。
- `pr-generator`: 分析分支变更并生成中文 PR 标题和描述。
- `smart-merge`: 分析并辅助处理分支合并。
- `tag`: 基于指定 tag 生成发布说明并发布 tag 或 GitHub Release。

