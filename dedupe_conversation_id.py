#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""conversation_id.txt 查重与清理工具。

用法:
    python3 dedupe_conversation_id.py            # 只体检，不改文件（dry-run）
    python3 dedupe_conversation_id.py --write    # 原地去重，备份为 .bak
    python3 dedupe_conversation_id.py --pending  # 额外导出「还没有 md 文件」的 id

规则:
    - 空行、以 # 开头的整行注释会被忽略（可选 --keep-comments 保留它们）
    - 同一行内 # 之后视为注释
    - 重复 id 只保留第一次出现的位置，其余删除
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ID_FILE = Path("conversation_id.txt")
MD_PATTERN = re.compile(r"（([0-9a-fA-F\-]{36})）\.md$")
ID_PATTERN = re.compile(r"^[0-9a-fA-F\-]{36}$")


def parse_id_file(path: Path):
    """返回 (原始行列表, 已解析的 (行号, id, 原文) 列表)。"""
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    entries = []
    for lineno, line in enumerate(raw_lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        cid = stripped.split("#", 1)[0].strip()
        if cid:
            entries.append((lineno, cid, line))
    return raw_lines, entries


def dedupe(path: Path, write: bool, keep_comments: bool = False):
    raw_lines, entries = parse_id_file(path)

    seen: dict[str, int] = {}
    duplicates: dict[str, list[int]] = {}
    keep_line_nos: set[int] = set()

    for lineno, cid, _ in entries:
        if cid in seen:
            duplicates.setdefault(cid, [seen[cid]]).append(lineno)
        else:
            seen[cid] = lineno
            keep_line_nos.add(lineno)

    print(f"📄 文件: {path}")
    print(f"  总行数     : {len(raw_lines)}")
    print(f"  有效 id 行 : {len(entries)}")
    print(f"  唯一 id    : {len(seen)}")
    print(f"  重复行     : {len(entries) - len(seen)}")
    if not duplicates:
        print("\n✅ 没有重复，无需清理。")
    else:
        print(f"\n🔁 重复的 id 共 {len(duplicates)} 个（只列前 20 个）:")
        for cid, linenos in sorted(duplicates.items(), key=lambda kv: -len(kv[1]))[:20]:
            pos = ", ".join(str(n) for n in linenos)
            print(f"  - {cid}  出现在第 {pos} 行（共 {len(linenos)} 次）")

    # 非法格式提醒（不参与去重逻辑，只是提示）
    bad = [(n, c) for n, c, _ in entries if not ID_PATTERN.match(c)]
    if bad:
        print(f"\n⚠️  有 {len(bad)} 行看起来不是标准 UUID: {bad[:5]}")

    if write:
        if not duplicates:
            return
        out_lines = []
        for lineno, line in enumerate(raw_lines, 1):
            if line.strip().startswith("#") and not keep_comments:
                # 整行注释默认丢弃，保持文件干净
                continue
            if lineno in keep_line_nos or not line.strip():
                out_lines.append(line)
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"\n💾 已备份原文件 -> {backup}")
        print(f"✍️  已重写 {path}：{len(entries)} 行 -> {len(seen)} 行，删除 {len(entries) - len(seen)} 行")
    else:
        print("\nℹ️  dry-run 模式，未修改任何文件。加 --write 才会真正去重。")


def export_pending(id_file: Path = ID_FILE, out_file: Path = Path("pending_conversation_id.txt")):
    """导出「还没有对应 md 文件」的 id，供增量下载使用。"""
    _, entries = parse_id_file(id_file)
    done = {
        m.group(1)
        for m in (MD_PATTERN.search(p.name) for p in Path(".").glob("*.md"))
        if m
    }
    pending, seen = [], set()
    for _, cid, _ in entries:
        if cid in done or cid in seen:
            continue
        seen.add(cid)
        pending.append(cid)
    out_file.write_text("\n".join(pending) + "\n", encoding="utf-8")
    print(f"\n📥 已有 md 文件 {len(done)} 个，待下载 {len(pending)} 个 -> {out_file}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="conversation_id.txt 查重 / 清理 / 断点续传")
    ap.add_argument("--file", type=Path, default=ID_FILE, help="id 文件路径，默认 conversation_id.txt")
    ap.add_argument("--write", action="store_true", help="真正写回去重后的文件（默认只体检）")
    ap.add_argument("--pending", action="store_true", help="导出还没有 md 的 id 到 pending_conversation_id.txt")
    ap.add_argument("--keep-comments", action="store_true", help="重写时保留 # 开头的注释行")
    args = ap.parse_args(argv)

    if not args.file.exists():
        print(f"❌ 找不到 {args.file}", file=sys.stderr)
        return 1
    dedupe(args.file, args.write, args.keep_comments)
    if args.pending:
        export_pending(args.file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
