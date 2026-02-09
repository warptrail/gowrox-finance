#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple


DEFAULT_OUTFILE = "REPO_DUMP.txt"

# Keep this conservative; repo dumps are for context transfer, not backups.
DEFAULT_MAX_FILE_BYTES = 256_000        # 256 KB per file
DEFAULT_MAX_TOTAL_BYTES = 8_000_000     # 8 MB total


@dataclass(frozen=True)
class Policy:
    repo_root: Path
    max_file_bytes: int
    max_total_bytes: int

    # Project-specific exclusions
    exclude_db_name: str = "gowrox.db"
    exclude_frontend_dir: str = "frontend"
    csv_dir_name: str = "csv"

    # NEVER include hidden files/dirs (dotfiles/dotdirs)
    exclude_hidden: bool = True

    # Hard prune dependency / build / cache dirs
    prune_dirs: tuple[str, ...] = (
        # Git / IDE / OS
        ".git", ".idea", ".vscode", ".DS_Store",

        # Python caches + environments
        "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
        "venv", ".venv", "env", ".env", ".tox",
        "__pypackages__",

        # Node / frontend deps & build
        "node_modules", ".next", "dist", "build", ".cache", "coverage",

        # Common tooling outputs
        ".turbo", ".parcel-cache",
    )

    # Also prune any directory path that contains these fragments (site-packages etc.)
    prune_path_fragments: tuple[str, ...] = (
        "site-packages",
        "dist-packages",
        ".egg-info",
        ".dist-info",
    )

    # Only inline contents for these extensions (your “code + configs”)
    include_exts: tuple[str, ...] = (
        ".py",
        ".md", ".txt",
        ".json", ".jsonl",
        ".yml", ".yaml",
        ".toml",
        ".ini", ".cfg",
        ".sql",
        ".sh", ".bash",
        ".js", ".jsx", ".ts", ".tsx",
        ".css", ".scss",
        ".html",
    )

    # Always inline these filenames even if no extension (common in repos)
    include_filenames: tuple[str, ...] = (
        "README", "LICENSE", "Makefile",
        "requirements.txt",
        "pyproject.toml",
        "Dockerfile",
    )


def relpath(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def is_hidden_path(path: Path, root: Path) -> bool:
    # Any component starting with '.' is hidden (dotfile or dotdir)
    try:
        parts = path.relative_to(root).parts
    except Exception:
        return False
    return any(p.startswith(".") for p in parts)


def has_prune_fragment(path: Path, root: Path, fragments: tuple[str, ...]) -> bool:
    rp = relpath(path, root)
    return any(frag in rp for frag in fragments)


def is_under_frontend(path: Path, policy: Policy) -> bool:
    try:
        parts = path.relative_to(policy.repo_root).parts
    except Exception:
        return False
    return len(parts) > 0 and parts[0] == policy.exclude_frontend_dir


def should_prune_dir(dir_path: Path, policy: Policy) -> bool:
    if policy.exclude_hidden and dir_path.name.startswith("."):
        return True
    if dir_path.name in policy.prune_dirs:
        return True
    if has_prune_fragment(dir_path, policy.repo_root, policy.prune_path_fragments):
        return True
    return False


def should_list_file(file_path: Path, policy: Policy) -> bool:
    # We keep topology broadly, but still skip hidden if requested
    if policy.exclude_hidden and is_hidden_path(file_path, policy.repo_root):
        return False
    return True


def should_inline_contents(path: Path, policy: Policy) -> Tuple[bool, str]:
    # Hidden files: never inline, and in this version we also don’t list them
    if policy.exclude_hidden and is_hidden_path(path, policy.repo_root):
        return (False, "EXCLUDED: hidden file")

    # Project constraints
    if path.name == policy.exclude_db_name:
        return (False, f"EXCLUDED: database file ({policy.exclude_db_name})")

    if path.suffix.lower() == ".csv":
        return (False, "EXCLUDED: CSV content")

    if is_under_frontend(path, policy):
        return (False, f"EXCLUDED: under {policy.exclude_frontend_dir}/ (boilerplate)")

    # Only inline “code/config-like” files
    if path.name in policy.include_filenames:
        return (True, "")

    if path.suffix.lower() in policy.include_exts:
        return (True, "")

    return (False, "SKIPPED: not in source/config allowlist")


def is_probably_binary(data: bytes) -> bool:
    if b"\x00" in data:
        return True
    sample = data[:4096]
    if not sample:
        return False
    textish = sum(1 for b in sample if b in (9, 10, 13) or 32 <= b <= 126)
    return (textish / len(sample)) < 0.70


def read_text_file(path: Path, policy: Policy) -> Tuple[Optional[str], str]:
    try:
        size = path.stat().st_size
    except OSError as e:
        return (None, f"SKIPPED: stat failed ({e})")

    if size > policy.max_file_bytes:
        return (None, f"SKIPPED: too large ({size} bytes > {policy.max_file_bytes})")

    try:
        data = path.read_bytes()
    except OSError as e:
        return (None, f"SKIPPED: read failed ({e})")

    if is_probably_binary(data):
        return (None, "SKIPPED: binary detected")

    try:
        return (data.decode("utf-8"), "")
    except UnicodeDecodeError:
        return (data.decode("utf-8", errors="replace"), "NOTE: utf-8 decode errors replaced")


def walk_repo(root: Path, policy: Policy) -> Iterable[Path]:
    """
    Yields directories + files in stable order, pruning hidden dirs and dependency dirs.
    Also does NOT traverse frontend/ (but we still show it in tree as present).
    """
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)

        # Prune directories in-place (os.walk uses this list to decide traversal)
        pruned = []
        for dn in dirnames:
            candidate = d / dn
            if should_prune_dir(candidate, policy):
                pruned.append(dn)
        for dn in pruned:
            dirnames.remove(dn)

        # Do not traverse into frontend/
        if d == root and policy.exclude_frontend_dir in dirnames:
            dirnames.remove(policy.exclude_frontend_dir)

        dirnames[:] = sorted(dirnames)
        filenames = sorted(filenames)

        # Yield directory (unless hidden excluded; root always included)
        if d == root or not (policy.exclude_hidden and is_hidden_path(d, root)):
            yield d

        # Yield files
        for fn in filenames:
            fp = d / fn
            if should_list_file(fp, policy):
                yield fp


def build_tree(root: Path, policy: Policy) -> list[str]:
    lines: list[str] = [f"{root.name}/"]

    # Collect visible dirs + files
    dirs: set[Path] = set()
    files: list[Path] = []

    for p in walk_repo(root, policy):
        if p.is_dir():
            dirs.add(p)
        elif p.is_file():
            files.append(p)

    # Add frontend dir as a marker (present, but not traversed)
    frontend_dir = root / policy.exclude_frontend_dir
    if frontend_dir.exists() and frontend_dir.is_dir():
        dirs.add(frontend_dir)

    # Render dirs
    for d in sorted(dirs, key=lambda x: (len(x.relative_to(root).parts), relpath(x, root))):
        if d == root:
            continue
        indent = "  " * len(d.relative_to(root).parts)
        if d == frontend_dir:
            lines.append(f"{indent}{d.name}/  [PRESENT; CONTENTS EXCLUDED]")
        else:
            lines.append(f"{indent}{d.name}/")

    # Render files
    for f in sorted(files, key=lambda x: relpath(x, root)):
        indent = "  " * len(f.relative_to(root).parts)
        inline, reason = should_inline_contents(f, policy)
        if inline:
            lines.append(f"{indent}{f.name}")
        else:
            lines.append(f"{indent}{f.name}  [{reason}]")

    # Ensure csv/ shows if present (even if empty / pruned doesn’t apply here)
    csv_dir = root / policy.csv_dir_name
    if csv_dir.exists() and csv_dir.is_dir() and csv_dir not in dirs:
        indent = "  " * len(csv_dir.relative_to(root).parts)
        lines.append(f"{indent}{csv_dir.name}/")

    return lines


def dump_repo(root: Path, out_path: Path, policy: Policy) -> None:
    tree_lines = build_tree(root, policy)

    total_included = 0
    sections: list[str] = []

    # Frontend marker section (explicit)
    frontend_dir = root / policy.exclude_frontend_dir
    if frontend_dir.exists() and frontend_dir.is_dir():
        sections.append(
            f"\n{'='*80}\nDIR: {policy.exclude_frontend_dir}/ (contents excluded)\n{'='*80}\n"
        )

    # Gather and inline allowed file contents
    for p in sorted((x for x in walk_repo(root, policy) if x.is_file()), key=lambda x: relpath(x, root)):
        inline, reason = should_inline_contents(p, policy)
        header = f"\n{'='*80}\nFILE: {relpath(p, root)}\n{'='*80}\n"

        if not inline:
            sections.append(header + f"[{reason}]\n")
            continue

        content, note = read_text_file(p, policy)
        if content is None:
            sections.append(header + f"[{note}]\n")
            continue

        content_bytes = len(content.encode("utf-8", errors="replace"))
        if total_included + content_bytes > policy.max_total_bytes:
            sections.append(header + f"[SKIPPED: total content cap exceeded ({policy.max_total_bytes} bytes)]\n")
            continue

        total_included += content_bytes
        if note:
            sections.append(header + f"[{note}]\n" + content.rstrip() + "\n")
        else:
            sections.append(header + content.rstrip() + "\n")

    out_text = []
    out_text.append("REPO DUMP (SOURCE-ONLY)\n")
    out_text.append(f"ROOT: {root.resolve()}\n")
    out_text.append("POLICY:\n")
    out_text.append("  - Hidden files/dirs: excluded entirely\n")
    out_text.append(f"  - Frontend dir present but excluded: {policy.exclude_frontend_dir}/\n")
    out_text.append("  - CSV contents excluded: *.csv\n")
    out_text.append(f"  - DB excluded: {policy.exclude_db_name}\n")
    out_text.append(f"  - Max file bytes: {policy.max_file_bytes}\n")
    out_text.append(f"  - Max total bytes: {policy.max_total_bytes}\n")
    out_text.append("\nTREE\n")
    out_text.append("-" * 80 + "\n")
    out_text.append("\n".join(tree_lines) + "\n")
    out_text.append("\nCONTENTS\n")
    out_text.append("-" * 80 + "\n")
    out_text.append("".join(sections))

    out_path.write_text("".join(out_text), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump repo topology + source/config contents (excludes deps).")
    parser.add_argument("--root", default=".", help="Repo root directory (default: .)")
    parser.add_argument("--out", default=DEFAULT_OUTFILE, help=f"Output file (default: {DEFAULT_OUTFILE})")
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_path = Path(args.out).resolve()

    policy = Policy(
        repo_root=root,
        max_file_bytes=args.max_file_bytes,
        max_total_bytes=args.max_total_bytes,
    )

    dump_repo(root=root, out_path=out_path, policy=policy)
    print(f"Wrote: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())