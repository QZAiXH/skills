#!/usr/bin/env python3
"""Validate generated Chinese GitHub Release notes before publishing."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ALLOWED_HEADINGS = [
    "版本亮点",
    "新增功能",
    "问题修复",
    "优化与重构",
    "破坏性变更",
    "升级注意事项",
    "其他变更",
    "Contributors",
]

BANNED_CONTEXT_MARKERS = [
    "# Release Notes Context",
    "## 概览",
    "## 提交分类",
    "## 按分类列出的提交",
    "## 模块线索",
    "## 风险与升级注意事项线索",
    "## 变更文件",
    "## Git Diff Stat",
]

EMPTY_FILLERS = (
    "n/a",
    "none",
    "无明确",
    "无相关",
    "暂无",
    "没有",
)


def strip_bullet(line: str) -> str:
    return re.sub(r"^\s*[-*]\s+", "", line).strip()


def parse_sections(text: str) -> tuple[list[tuple[str, int]], dict[str, list[str]]]:
    headings: list[tuple[str, int]] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            headings.append((match.group(1).strip(), index))

    sections: dict[str, list[str]] = {}
    for position, (heading, start) in enumerate(headings):
        end = headings[position + 1][1] if position + 1 < len(headings) else len(lines)
        sections[heading] = lines[start + 1 : end]
    return headings, sections


def has_real_bullet(lines: list[str]) -> bool:
    for line in lines:
        text = strip_bullet(line)
        if not text or not re.match(r"^\s*[-*]\s+", line):
            continue
        lowered = text.lower()
        if lowered in {"无", "无。", "暂无", "暂无。", "没有", "没有。"}:
            continue
        if lowered.startswith(EMPTY_FILLERS):
            continue
        if re.search(r"<[^>]+>", text):
            continue
        return True
    return False


def is_linked_contributor(text: str) -> bool:
    if re.search(r"(^|\s)@[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\b|$)", text):
        return True
    if re.search(r"\[[^\]]+\]\(https://github\.com/[^)\s]+\)", text):
        return True
    return False


def validate(text: str, allow_extra_headings: bool) -> list[str]:
    errors: list[str] = []
    stripped = text.strip()
    if not stripped:
        return ["发布说明为空。"]

    if any(marker in text for marker in BANNED_CONTEXT_MARKERS):
        errors.append("发布说明包含上下文收集脚本的中间标题，不能直接发布脚本输出。")

    if re.search(r"<[^>]+>", text):
        errors.append("发布说明包含占位符，请替换为真实内容。")

    headings, sections = parse_sections(text)
    heading_names = [heading for heading, _ in headings]

    if not headings:
        errors.append("发布说明缺少 Markdown 二级章节标题，例如 `## 版本亮点`。")
    else:
        first_heading, first_heading_line = headings[0]
        prefix_lines = [line for line in text.splitlines()[:first_heading_line] if line.strip()]
        if prefix_lines and not (len(prefix_lines) == 1 and prefix_lines[0].startswith("# ")):
            errors.append("第一个 `##` 标题前不能出现裸项目符号或正文。")
        if first_heading != "版本亮点":
            errors.append("第一个二级章节必须是 `## 版本亮点`。")

    duplicates = sorted({heading for heading in heading_names if heading_names.count(heading) > 1})
    if duplicates:
        errors.append(f"发布说明包含重复章节：{', '.join(duplicates)}。")

    unknown = [heading for heading in heading_names if heading not in ALLOWED_HEADINGS]
    if unknown and not allow_extra_headings:
        errors.append(f"发布说明包含非标准章节：{', '.join(unknown)}。")

    if "版本亮点" not in sections:
        errors.append("发布说明必须包含 `## 版本亮点`。")
    if "Contributors" not in sections:
        errors.append("发布说明必须包含 `## Contributors`。")

    standard_heading_count = sum(1 for heading in heading_names if heading in ALLOWED_HEADINGS)
    if standard_heading_count < 3:
        errors.append("发布说明至少需要 3 个标准章节：版本亮点、一个变更章节和 Contributors。")

    highlights = sections.get("版本亮点", [])
    highlight_bullets = [line for line in highlights if re.match(r"^\s*[-*]\s+", line)]
    if highlights and not 1 <= len(highlight_bullets) <= 3:
        errors.append("`## 版本亮点` 必须包含 1-3 条项目符号。")

    for heading, lines in sections.items():
        if heading.startswith("#"):
            continue
        if heading == "Contributors":
            contributors = [strip_bullet(line) for line in lines if re.match(r"^\s*[-*]\s+", line)]
            if not contributors:
                errors.append("`## Contributors` 必须包含至少一个贡献者项目符号。")
            unlinked = [contributor for contributor in contributors if not is_linked_contributor(contributor)]
            if unlinked:
                errors.append(
                    "`## Contributors` 中的贡献者必须使用 `@github-login` 或 GitHub Markdown 链接："
                    + ", ".join(unlinked)
                    + "。"
                )
            continue
        if heading in ALLOWED_HEADINGS and not has_real_bullet(lines):
            errors.append(f"`## {heading}` 缺少真实项目符号内容；没有内容时应省略该章节。")

    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Chinese GitHub Release notes Markdown.")
    parser.add_argument("notes_file", help="待校验的发布说明 Markdown 文件")
    parser.add_argument(
        "--allow-extra-headings",
        action="store_true",
        help="允许标准 Release Notes 章节以外的二级标题",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    path = Path(args.notes_file)
    if not path.exists():
        print(f"错误: 文件不存在: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    errors = validate(text, args.allow_extra_headings)
    if errors:
        print("发布说明校验失败:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("发布说明校验通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
