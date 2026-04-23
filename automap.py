#!/usr/bin/env python3
"""
stmemory generic automapper — maps codebase files to documentation.

Reads config from .stmemoryrc.json in project root (or --config flag).
Uses 4-tier matching: exact_file_map → directory_rules → keyword_to_doc → fuzzy match.
Outputs markdown files linking code to docs: INDEX-codemap.md, INDEX.md.

Usage:
  python automap.py [--config .stmemoryrc.json] [--dry-run] [--apply]
  python automap.py --help
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Common path segments to ignore in fuzzy matching
STOPWORDS: set[str] = {
    "src", "app", "index", "utils", "lib", "common", "hooks", "store",
    "services", "components", "api", "db", "scripts", "tests",
    "frontend", "backend", "routers", "schemas", "pages", "public",
    "node_modules", "dist", "build", ".next", ".venv", "venv"
}


def normalize_doc_name(doc_name: str) -> str:
    """
    Normalize doc name by removing .md extension if present.

    Args:
        doc_name: Doc name (e.g., "auth-system.md" or "auth-system")

    Returns:
        Doc name without .md extension
    """
    if doc_name.endswith(".md"):
        return doc_name[:-3]
    return doc_name


def load_config(config_path: str) -> Dict:
    """
    Load stmemory configuration from JSON file.

    Args:
        config_path: Path to .stmemoryrc.json

    Returns:
        Configuration dictionary with required keys:
        - scan_dirs: list of directories to scan
        - file_extensions: list of file extensions to match
        - plans_dir: path to plans directory (usually .omc/plans)
        - wiki_dir: path to wiki/memory directory (usually .omc/wiki)
        - keyword_to_doc: dict mapping keywords to docs
        - directory_rules: dict mapping directory patterns to docs
        - exact_file_map: dict mapping exact file paths to docs

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
        ValueError: If required keys are missing
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n\n"
            "Create .stmemoryrc.json in your project root with this template:\n"
            "  https://example.com/.stmemoryrc.example.json\n\n"
            "Required keys: scan_dirs, file_extensions, keyword_to_doc, "
            "directory_rules, exact_file_map, plans_dir, wiki_dir"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    required_keys = {
        "scan_dirs", "file_extensions", "plans_dir", "wiki_dir",
        "keyword_to_doc", "directory_rules", "exact_file_map"
    }
    missing = required_keys - set(config.keys())
    if missing:
        raise ValueError(
            f"Config is missing required keys: {missing}\n"
            f"See .stmemoryrc.example.json for template"
        )

    # Normalize doc names: remove .md extension if present
    config["keyword_to_doc"] = {
        k: normalize_doc_name(v)
        for k, v in config.get("keyword_to_doc", {}).items()
    }
    config["directory_rules"] = {
        k: normalize_doc_name(v)
        for k, v in config.get("directory_rules", {}).items()
    }
    config["exact_file_map"] = {
        k: normalize_doc_name(v)
        for k, v in config.get("exact_file_map", {}).items()
    }

    return config


def extract_keywords(filepath: str) -> set[str]:
    """
    Extract keywords from a file path for fuzzy matching.

    Splits by / and _, removes file extensions, lowercases, filters stopwords.

    Args:
        filepath: e.g., "src/auth/login_service.ts"

    Returns:
        Set of keyword strings (lowercased, no stopwords)
    """
    # Remove extension
    base = os.path.splitext(filepath)[0]

    # Split by / and _
    parts = re.split(r"[/_]", base)

    # Lowercase, filter stopwords and empty strings
    keywords = {
        p.lower() for p in parts
        if p and p.lower() not in STOPWORDS
    }

    return keywords


def fuzzy_match(
    filepath: str,
    doc_names: List[str],
    threshold: float = 0.3
) -> Optional[str]:
    """
    Find best matching doc for a file using fuzzy keyword matching.

    Compares extracted keywords from filepath against doc names.
    Returns first match with score > threshold.

    Args:
        filepath: File path to match (e.g., "src/auth/login.ts")
        doc_names: List of available doc names without .md extension
        threshold: Minimum match score (0.0-1.0)

    Returns:
        Best matching doc name (without .md) or None if no match
    """
    file_keywords = extract_keywords(filepath)

    if not file_keywords:
        return None

    best_match: Optional[str] = None
    best_score: float = 0.0

    for doc_name in doc_names:
        doc_keywords = extract_keywords(doc_name)

        if not doc_keywords:
            continue

        # Calculate Jaccard similarity between keyword sets
        intersection = len(file_keywords & doc_keywords)
        union = len(file_keywords | doc_keywords)
        score = intersection / union if union > 0 else 0.0

        if score > best_score:
            best_score = score
            best_match = doc_name

    return best_match if best_score >= threshold else None


def find_doc_for_file(
    filepath: str,
    config: Dict,
    available_docs: List[str]
) -> Optional[str]:
    """
    Find documentation file for a code file using 4-tier matching logic.

    Tiers (in order):
    1. exact_file_map: exact filepath match
    2. directory_rules: directory pattern match
    3. keyword_to_doc: keyword match
    4. fuzzy_match: keyword similarity

    Args:
        filepath: Code file path relative to project root
        config: Configuration dictionary
        available_docs: List of available doc names (without .md)

    Returns:
        Doc name (without .md) or None if no match found
    """
    normalized_path = filepath.replace("\\", "/")

    # Tier 1: Exact file map
    exact_map = config.get("exact_file_map", {})
    if normalized_path in exact_map:
        return exact_map[normalized_path]

    # Tier 2: Directory rules (longest match wins)
    dir_rules = config.get("directory_rules", {})
    best_dir_match: Optional[Tuple[str, str]] = None

    for dir_pattern, doc in dir_rules.items():
        normalized_pattern = dir_pattern.replace("\\", "/")
        if normalized_path.startswith(normalized_pattern):
            if not best_dir_match or len(normalized_pattern) > len(best_dir_match[0]):
                best_dir_match = (normalized_pattern, doc)

    if best_dir_match:
        return best_dir_match[1]

    # Tier 3: Keyword to doc
    keyword_map = config.get("keyword_to_doc", {})
    file_keywords = extract_keywords(filepath)

    for keyword, doc in keyword_map.items():
        if keyword.lower() in file_keywords:
            return doc

    # Tier 4: Fuzzy match
    return fuzzy_match(filepath, available_docs)


def scan_codebase(config: Dict) -> List[str]:
    """
    Scan directories for code files matching configured extensions.

    Args:
        config: Configuration dictionary with scan_dirs and file_extensions

    Returns:
        List of file paths (relative to cwd)
    """
    scan_dirs = config.get("scan_dirs", [])
    extensions = config.get("file_extensions", [])

    files: List[str] = []
    cwd = Path.cwd()

    for dir_name in scan_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            print(f"Warning: scan directory not found: {dir_name}")
            continue

        for file_path in dir_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in extensions:
                # Resolve to absolute path, then make relative to cwd
                abs_path = file_path.resolve()
                try:
                    rel_path = abs_path.relative_to(cwd.resolve())
                    files.append(str(rel_path).replace("\\", "/"))
                except ValueError:
                    # File is outside cwd, use as-is
                    files.append(str(file_path).replace("\\", "/"))

    return sorted(files)


def get_available_docs(
    plans_dir: str,
    wiki_dir: str
) -> List[str]:
    """
    Get list of available doc names from plans and wiki directories.

    Args:
        plans_dir: Plans directory (e.g., .omc/plans)
        wiki_dir: Wiki/memory directory (e.g., .omc/wiki)

    Returns:
        List of doc names without .md extension
    """
    docs: set[str] = set()

    for dir_path in [plans_dir, wiki_dir]:
        if Path(dir_path).exists():
            for file_path in Path(dir_path).glob("*.md"):
                doc_name = file_path.stem
                docs.add(doc_name)

    return sorted(list(docs))


def build_codemap(
    files: List[str],
    config: Dict,
    available_docs: List[str]
) -> Dict[str, Optional[str]]:
    """
    Build mapping of code files to documentation.

    Args:
        files: List of code files to map
        config: Configuration dictionary
        available_docs: List of available docs

    Returns:
        Dictionary mapping filepath → doc name (or None)
    """
    codemap: Dict[str, Optional[str]] = {}

    for filepath in files:
        doc = find_doc_for_file(filepath, config, available_docs)
        codemap[filepath] = doc

    return codemap


def render_index_codemap(codemap: Dict[str, Optional[str]]) -> str:
    """
    Render INDEX-codemap.md from code-to-doc mapping.

    Format: | filepath | → | documentation |

    Args:
        codemap: Dictionary mapping filepath → doc name

    Returns:
        Markdown content for INDEX-codemap.md
    """
    lines = [
        "# INDEX-codemap: Code → Documentation",
        "",
        "Maps source files to documentation files.",
        "",
        "| File | Documentation |",
        "|------|---|",
    ]

    for filepath, doc in sorted(codemap.items()):
        if doc:
            lines.append(f"| `{filepath}` | [{doc}](.omc/plans/{doc}.md) |")
        else:
            lines.append(f"| `{filepath}` | (no doc) |")

    return "\n".join(lines) + "\n"


def render_index(codemap: Dict[str, Optional[str]], available_docs: List[str]) -> str:
    """
    Render INDEX.md from code-to-doc mapping and doc list.

    Format:
    ## [doc-name]
    - filepath1
    - filepath2

    Args:
        codemap: Dictionary mapping filepath → doc name
        available_docs: List of available docs

    Returns:
        Markdown content for INDEX.md
    """
    lines = [
        "# INDEX: Documentation → Code",
        "",
        "Maps documentation files to source files.",
        "",
    ]

    # Group files by doc
    doc_to_files: Dict[str, List[str]] = {doc: [] for doc in available_docs}
    unmapped: List[str] = []

    for filepath, doc in codemap.items():
        if doc:
            if doc not in doc_to_files:
                doc_to_files[doc] = []
            doc_to_files[doc].append(filepath)
        else:
            unmapped.append(filepath)

    # Render each doc with its files
    for doc in sorted(available_docs):
        files = doc_to_files.get(doc, [])
        if files:
            lines.append(f"## [{doc}](.omc/plans/{doc}.md)")
            lines.append("")
            for filepath in sorted(files):
                lines.append(f"- `{filepath}`")
            lines.append("")

    # Unmapped files section
    if unmapped:
        lines.append("## (Unmapped)")
        lines.append("")
        for filepath in sorted(unmapped):
            lines.append(f"- `{filepath}`")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="stmemory automapper: map codebase files to documentation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python automap.py --dry-run
  python automap.py --config /path/to/.stmemoryrc.json --apply
  python automap.py --help

Config file (.stmemoryrc.json) required in project root with:
  - scan_dirs: list of directories to scan
  - file_extensions: list of file extensions (e.g., [".py", ".ts"])
  - keyword_to_doc: mapping of keywords to docs
  - directory_rules: mapping of directory patterns to docs
  - exact_file_map: mapping of exact files to docs
  - plans_dir: path to plans directory (usually .omc/plans)
  - wiki_dir: path to wiki directory (usually .omc/wiki)
        """
    )
    parser.add_argument(
        "--config",
        default=".stmemoryrc.json",
        help="Path to config file (default: .stmemoryrc.json)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Preview changes without writing (default: true)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to INDEX-codemap.md and INDEX.md"
    )

    args = parser.parse_args()

    # Load config
    try:
        config = load_config(args.config)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        print(f"Error: {e}")
        return

    # Scan codebase
    print("Scanning codebase...")
    files = scan_codebase(config)
    print(f"Found {len(files)} code files")

    # Get available docs
    available_docs = get_available_docs(config["plans_dir"], config["wiki_dir"])
    print(f"Found {len(available_docs)} documentation files")

    # Build mapping
    print("Building code → doc mapping...")
    codemap = build_codemap(files, config, available_docs)

    mapped = sum(1 for v in codemap.values() if v is not None)
    unmapped = len(codemap) - mapped
    print(f"Mapped: {mapped}/{len(codemap)} files ({unmapped} unmapped)")

    # Render
    codemap_content = render_index_codemap(codemap)
    index_content = render_index(codemap, available_docs)

    # Output
    if args.dry_run and not args.apply:
        print("\n--- DRY RUN: Preview of changes ---\n")
        print("INDEX-codemap.md:")
        print(codemap_content[:500] + "..." if len(codemap_content) > 500 else codemap_content)
        print("\nINDEX.md:")
        print(index_content[:500] + "..." if len(index_content) > 500 else index_content)
        print("\nRun with --apply to write changes")
    elif args.apply:
        with open("INDEX-codemap.md", "w", encoding="utf-8") as f:
            f.write(codemap_content)
        print("Wrote INDEX-codemap.md")

        with open("INDEX.md", "w", encoding="utf-8") as f:
            f.write(index_content)
        print("Wrote INDEX.md")
    else:
        print(codemap_content)


if __name__ == "__main__":
    main()
