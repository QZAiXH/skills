#!/usr/bin/env python3
"""Collect Git context for Chinese GitHub release notes."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CATEGORY_LABELS = {
    "breaking": "破坏性变更",
    "feat": "新增功能",
    "fix": "问题修复",
    "perf": "性能优化",
    "refactor": "重构优化",
    "docs": "文档",
    "test": "测试",
    "ci": "CI/CD",
    "build": "构建与依赖",
    "chore": "其他变更",
}

TYPE_ALIASES = {
    "feature": "feat",
    "bugfix": "fix",
    "hotfix": "fix",
    "performance": "perf",
    "deps": "build",
    "dependency": "build",
}


class GitError(RuntimeError):
    pass


def run_git(repo: Path, args: list[str], allow_failure: bool = False) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0 and not allow_failure:
        raise GitError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def resolve_repo(path: str) -> Path:
    proc = subprocess.run(
        ["git", "-C", path, "rev-parse", "--show-toplevel"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise GitError(f"{path} 不是 Git 仓库，或无法读取仓库根目录")
    return Path(proc.stdout.strip())


def split_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def get_exact_tags(repo: Path, target_ref: str) -> list[str]:
    out = run_git(repo, ["tag", "--points-at", target_ref], allow_failure=True)
    return split_lines(out)


def get_merged_tags(repo: Path, target_ref: str) -> list[str]:
    out = run_git(
        repo,
        [
            "for-each-ref",
            "refs/tags",
            "--merged",
            target_ref,
            "--sort=-creatordate",
            "--format=%(refname:short)",
        ],
        allow_failure=True,
    )
    return split_lines(out)


def detect_base_tag(repo: Path, target_ref: str, explicit_base: str | None) -> tuple[str | None, list[str]]:
    exact_tags = get_exact_tags(repo, target_ref)
    if explicit_base:
        run_git(repo, ["rev-parse", "--verify", "--quiet", explicit_base])
        return explicit_base, exact_tags

    if exact_tags:
        for tag in get_merged_tags(repo, target_ref):
            if tag not in exact_tags:
                return tag, exact_tags
        return None, exact_tags

    described = run_git(
        repo,
        ["describe", "--tags", "--abbrev=0", target_ref],
        allow_failure=True,
    )
    if described:
        return described, exact_tags

    tags = get_merged_tags(repo, target_ref)
    return (tags[0], exact_tags) if tags else (None, exact_tags)


def parse_commits(log_text: str) -> list[dict[str, str]]:
    commits: list[dict[str, str]] = []
    for line in split_lines(log_text):
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        short_hash, date, subject, author = parts
        commits.append(
            {
                "hash": short_hash,
                "date": date,
                "subject": subject,
                "author": author,
                "category": categorize_commit(subject),
            }
        )
    return commits


def categorize_commit(subject: str) -> str:
    lowered = subject.lower()
    match = re.match(r"^([a-zA-Z]+)(?:\([^)]+\))?(!)?:\s*(.+)$", subject)
    if match:
        raw_type, bang, _ = match.groups()
        commit_type = TYPE_ALIASES.get(raw_type.lower(), raw_type.lower())
        if bang:
            return "breaking"
        if commit_type in CATEGORY_LABELS:
            return commit_type

    keyword_rules = [
        ("breaking", ["breaking", "不兼容", "破坏性", "移除", "删除"]),
        ("feat", ["feat", "feature", "add", "new", "support", "新增", "添加", "支持"]),
        ("fix", ["fix", "bug", "repair", "resolve", "修复", "修正", "异常"]),
        ("perf", ["perf", "performance", "optimize", "优化", "性能"]),
        ("refactor", ["refactor", "cleanup", "重构", "整理"]),
        ("docs", ["docs", "readme", "文档", "说明"]),
        ("test", ["test", "spec", "测试"]),
        ("ci", ["ci", "workflow", "action", "pipeline", "流水线"]),
        ("build", ["build", "deps", "dependency", "bump", "upgrade", "依赖", "升级", "构建"]),
    ]
    for category, keywords in keyword_rules:
        if any(keyword in lowered for keyword in keywords):
            return category
    return "chore"


def parse_name_status(text: str) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for line in split_lines(text):
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1]
        old_path = parts[1] if status.startswith(("R", "C")) and len(parts) >= 3 else ""
        changes.append({"status": status, "path": path, "old_path": old_path})
    return changes


def parse_numstat(text: str) -> dict[str, dict[str, int | str]]:
    stats: dict[str, dict[str, int | str]] = {}
    for line in split_lines(text):
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_raw, deleted_raw, path = parts[0], parts[1], parts[-1]
        added = int(added_raw) if added_raw.isdigit() else 0
        deleted = int(deleted_raw) if deleted_raw.isdigit() else 0
        stats[path] = {"added": added, "deleted": deleted}
    return stats


def module_name(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if not parts:
        return "."
    if parts[0] in {".github", "cmd", "internal", "pkg", "app", "apps", "packages", "services"} and len(parts) >= 2:
        return "/".join(parts[:2])
    if parts[0] in {"migrations", "migration"}:
        return parts[0]
    if len(parts) >= 2 and parts[0] in {"src", "lib", "docs", "test", "tests", "deploy", "infra"}:
        return "/".join(parts[:2])
    return parts[0]


def summarize_modules(changes: list[dict[str, str]]) -> list[dict[str, Any]]:
    counter = Counter(module_name(change["path"]) for change in changes)
    return [{"module": module, "files": count} for module, count in counter.most_common()]


def detect_risks(changes: list[dict[str, str]], commits: list[dict[str, str]]) -> dict[str, list[str]]:
    paths = [change["path"] for change in changes]
    statuses = [(change["status"], change["path"]) for change in changes]
    risks: dict[str, list[str]] = defaultdict(list)

    for commit in commits:
        if commit["category"] == "breaking":
            risks["breaking"].append(f"{commit['hash']} {commit['subject']}")

    for status, path in statuses:
        lowered = path.lower()
        if status.startswith("D"):
            risks["removed_files"].append(path)
        if status.startswith("R"):
            risks["renamed_files"].append(path)
        if re.search(r"(^|/)(migration|migrations|db|database|schema)(/|$)", lowered) or lowered.endswith((".sql", ".prisma")):
            risks["database"].append(path)
        if lowered.endswith((".proto", ".graphql", ".openapi.json", ".openapi.yaml", ".swagger.json", ".swagger.yaml")):
            risks["api_schema"].append(path)
        if re.search(r"(^|/)(api|routes|router|controllers?|handlers?)(/|$)", lowered):
            risks["api_schema"].append(path)
        if Path(lowered).name in {
            "package.json",
            "package-lock.json",
            "pnpm-lock.yaml",
            "yarn.lock",
            "go.mod",
            "go.sum",
            "requirements.txt",
            "pyproject.toml",
            "pom.xml",
            "build.gradle",
        }:
            risks["dependencies"].append(path)
        if Path(lowered).name in {".env", ".env.example", "dockerfile", "docker-compose.yml"}:
            risks["deployment"].append(path)
        if re.search(r"(^|/)(deploy|deployment|helm|k8s|terraform|cloudformation|docker)(/|$)", lowered):
            risks["deployment"].append(path)

    return {key: sorted(set(value)) for key, value in risks.items()}


def collect(args: argparse.Namespace) -> dict[str, Any]:
    repo = resolve_repo(args.repo)
    target_ref = args.target_ref
    run_git(repo, ["rev-parse", "--verify", "--quiet", target_ref])

    base_tag, exact_tags = detect_base_tag(repo, target_ref, args.base_tag)
    head_sha = run_git(repo, ["rev-parse", "--short", target_ref])
    branch = run_git(repo, ["branch", "--show-current"], allow_failure=True) or "(detached HEAD)"
    status = run_git(repo, ["status", "--short"], allow_failure=True)

    data: dict[str, Any] = {
        "repo": str(repo),
        "branch": branch,
        "target_ref": target_ref,
        "target_sha": head_sha,
        "target_exact_tags": exact_tags,
        "base_tag": base_tag,
        "worktree_dirty": bool(status),
        "worktree_status": split_lines(status),
    }

    if not base_tag:
        data["error"] = "未找到可对比的上一个 tag，请通过 --base-tag 指定基准 tag。"
        return data

    revision_range = f"{base_tag}..{target_ref}"
    log_text = run_git(
        repo,
        ["log", revision_range, "--date=short", "--pretty=format:%h%x09%ad%x09%s%x09%an"],
    )
    commits = parse_commits(log_text)
    name_status = run_git(repo, ["diff", "--name-status", "--find-renames", revision_range])
    numstat = run_git(repo, ["diff", "--numstat", revision_range])
    stat = run_git(repo, ["diff", "--stat", revision_range])
    shortstat = run_git(repo, ["diff", "--shortstat", revision_range])

    changes = parse_name_status(name_status)
    per_file_stats = parse_numstat(numstat)
    for change in changes:
        change.update(per_file_stats.get(change["path"], {"added": 0, "deleted": 0}))

    category_counts = Counter(commit["category"] for commit in commits)
    commits_by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
    for commit in commits:
        commits_by_category[commit["category"]].append(commit)

    data.update(
        {
            "revision_range": revision_range,
            "commit_count": len(commits),
            "category_counts": dict(category_counts),
            "commits_by_category": dict(commits_by_category),
            "changed_file_count": len(changes),
            "changed_files": changes,
            "modules": summarize_modules(changes),
            "risks": detect_risks(changes, commits),
            "diff_stat": stat,
            "diff_shortstat": shortstat,
        }
    )
    return data


def format_markdown(data: dict[str, Any], max_commits: int, max_files: int) -> str:
    lines: list[str] = ["# Release Notes Context", ""]
    lines.append(f"- 仓库: `{data['repo']}`")
    lines.append(f"- 当前分支: `{data['branch']}`")
    lines.append(f"- 目标引用: `{data['target_ref']}` (`{data['target_sha']}`)")
    if data.get("target_exact_tags"):
        lines.append(f"- 目标引用上的 tag: {', '.join(f'`{tag}`' for tag in data['target_exact_tags'])}")
    lines.append(f"- 基准 tag: `{data.get('base_tag') or '未识别'}`")
    if data.get("revision_range"):
        lines.append(f"- 对比范围: `{data['revision_range']}`")
    if data.get("worktree_dirty"):
        lines.append("- 工作区状态: 有未提交变更；默认发布说明只包含已提交内容。")
    else:
        lines.append("- 工作区状态: clean")
    lines.append("")

    if data.get("error"):
        lines.append(f"## 错误\n\n{data['error']}")
        return "\n".join(lines)

    lines.append("## 概览")
    lines.append("")
    lines.append(f"- 提交数: {data['commit_count']}")
    lines.append(f"- 变更文件数: {data['changed_file_count']}")
    if data.get("diff_shortstat"):
        lines.append(f"- 代码统计: {data['diff_shortstat']}")
    lines.append("")

    lines.append("## 提交分类")
    lines.append("")
    for key, label in CATEGORY_LABELS.items():
        count = data.get("category_counts", {}).get(key, 0)
        if count:
            lines.append(f"- {label}: {count}")
    lines.append("")

    lines.append("## 按分类列出的提交")
    for key, label in CATEGORY_LABELS.items():
        commits = data.get("commits_by_category", {}).get(key, [])
        if not commits:
            continue
        lines.append("")
        lines.append(f"### {label}")
        for commit in commits[:max_commits]:
            lines.append(f"- `{commit['hash']}` {commit['subject']} ({commit['author']}, {commit['date']})")
        if len(commits) > max_commits:
            lines.append(f"- ... 另有 {len(commits) - max_commits} 条")
    lines.append("")

    if data.get("modules"):
        lines.append("## 模块线索")
        lines.append("")
        for item in data["modules"][:20]:
            lines.append(f"- `{item['module']}`: {item['files']} 个文件")
        lines.append("")

    risks = data.get("risks", {})
    if risks:
        risk_labels = {
            "breaking": "疑似破坏性变更提交",
            "removed_files": "删除文件",
            "renamed_files": "重命名文件",
            "database": "数据库或 schema 相关文件",
            "api_schema": "API/协议/schema 相关文件",
            "dependencies": "依赖文件",
            "deployment": "部署或配置相关文件",
        }
        lines.append("## 风险与升级注意事项线索")
        for key, label in risk_labels.items():
            values = risks.get(key, [])
            if not values:
                continue
            lines.append("")
            lines.append(f"### {label}")
            for value in values[:max_files]:
                lines.append(f"- `{value}`")
            if len(values) > max_files:
                lines.append(f"- ... 另有 {len(values) - max_files} 项")
        lines.append("")

    lines.append("## 变更文件")
    lines.append("")
    for change in data.get("changed_files", [])[:max_files]:
        added = change.get("added", 0)
        deleted = change.get("deleted", 0)
        status = change.get("status", "")
        old_path = change.get("old_path")
        if old_path:
            lines.append(f"- `{status}` `{old_path}` -> `{change['path']}` (+{added}/-{deleted})")
        else:
            lines.append(f"- `{status}` `{change['path']}` (+{added}/-{deleted})")
    remaining = len(data.get("changed_files", [])) - max_files
    if remaining > 0:
        lines.append(f"- ... 另有 {remaining} 个文件")
    lines.append("")

    if data.get("diff_stat"):
        lines.append("## Git Diff Stat")
        lines.append("")
        lines.append("```text")
        lines.append(data["diff_stat"])
        lines.append("```")

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect Git context for Chinese GitHub release notes.")
    parser.add_argument("--repo", default=".", help="Git 仓库路径，默认当前目录")
    parser.add_argument("--target-ref", default="HEAD", help="目标引用，默认 HEAD")
    parser.add_argument("--base-tag", help="手动指定基准 tag；未指定时自动识别上一个可达 tag")
    parser.add_argument("--json", action="store_true", help="输出 JSON 而不是 Markdown")
    parser.add_argument("--max-commits", type=int, default=80, help="每个分类最多输出多少条提交")
    parser.add_argument("--max-files", type=int, default=120, help="最多输出多少个文件或风险线索")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        data = collect(args)
    except GitError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(format_markdown(data, args.max_commits, args.max_files))
    return 1 if data.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
