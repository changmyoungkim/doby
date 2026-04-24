#!/usr/bin/env python3
"""
doby docgen — auto-generates spec documents from code without LLM.

Reads Python (FastAPI) and Dart (Flutter) source files, extracts structure
(endpoints, functions, classes, providers), and generates markdown spec docs.

Uses AST parsing for Python and regex for Dart. Zero LLM tokens.

Usage:
  python docgen.py [--config .dobyrc.json] [--dry-run] [--apply] [--domain @auth] [--force]
  python docgen.py --help
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

# Add doby skill dir to path for automap import
sys.path.insert(0, str(Path(__file__).parent))
from automap import (
    load_config,
    find_doc_for_file,
    scan_codebase,
)


class PythonCodeExtractor:
    """Extract endpoints, functions, classes, and imports from Python files."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.endpoints: List[Dict] = []
        self.functions: List[Dict] = []
        self.classes: List[str] = []
        self.imports: Set[str] = set()

    def extract(self) -> None:
        """Parse Python file and extract structure."""
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content)
        except (SyntaxError, UnicodeDecodeError):
            return

        for node in ast.walk(tree):
            # Extract endpoints from decorators
            if isinstance(node, ast.FunctionDef):
                self._extract_function(node)

            # Extract classes
            elif isinstance(node, ast.ClassDef):
                self.classes.append(node.name)

            # Extract imports
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    self.imports.add(node.module)

    def _extract_function(self, node: ast.FunctionDef) -> None:
        """Extract function info and check for router decorators."""
        # Check for router decorators (@router.get, @router.post, etc.)
        method = None
        path = None

        for decorator in node.decorator_list:
            # Handle @router.get(...), @router.post(...), etc.
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    attr_name = decorator.func.attr
                    if attr_name in ("get", "post", "put", "patch", "delete"):
                        method = attr_name.upper()
                        # Extract path from first argument
                        if decorator.args:
                            first_arg = decorator.args[0]
                            if isinstance(first_arg, ast.Constant):
                                path = first_arg.value

        # Extract docstring
        docstring = ast.get_docstring(node) or ""
        first_line = docstring.split("\n")[0] if docstring else ""

        # Extract parameters
        params = [arg.arg for arg in node.args.args]
        param_str = ", ".join(params)

        # Extract return type hint
        return_type = ""
        if node.returns:
            return_type = self._get_type_annotation(node.returns)

        if method and path:
            # This is an endpoint
            self.endpoints.append({
                "method": method,
                "path": path,
                "name": node.name,
                "docstring": first_line,
                "params": param_str
            })
        elif node.name not in ("__init__", "__str__", "__repr__"):
            # Regular function
            self.functions.append({
                "name": node.name,
                "params": param_str,
                "return_type": return_type,
                "docstring": first_line
            })

    def _get_type_annotation(self, node) -> str:
        """Convert AST type annotation to string."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""


class DartCodeExtractor:
    """Extract classes, widgets, providers, and routes from Dart files."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.classes: List[Dict] = []
        self.providers: List[str] = []
        self.routes: List[str] = []
        self.imports: Set[str] = set()

    def extract(self) -> None:
        """Parse Dart file and extract structure using regex."""
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            return

        # Extract imports
        self._extract_imports(content)

        # Extract class definitions
        self._extract_classes(content)

        # Extract provider references
        self._extract_providers(content)

        # Extract route references
        self._extract_routes(content)

    def _extract_imports(self, content: str) -> None:
        """Extract import statements."""
        pattern = r"import\s+['\"]([^'\"]+)['\"]"
        for match in re.finditer(pattern, content):
            import_path = match.group(1)
            self.imports.add(import_path)

    def _extract_classes(self, content: str) -> None:
        """Extract class definitions."""
        pattern = r"class\s+(\w+)\s+(?:extends|with|implements)?(?:\s+(\w+))?(?:\s+with\s+(\w+))?"
        for match in re.finditer(pattern, content):
            class_name = match.group(1)
            extends = match.group(2) or ""
            with_clause = match.group(3) or ""

            # Determine widget type
            widget_type = "Class"
            if extends:
                if "StatelessWidget" in extends:
                    widget_type = "StatelessWidget"
                elif "StatefulWidget" in extends:
                    widget_type = "StatefulWidget"
                elif "ConsumerWidget" in extends:
                    widget_type = "ConsumerWidget"
                elif "ConsumerStatefulWidget" in extends:
                    widget_type = "ConsumerStatefulWidget"
                elif with_clause:
                    widget_type = f"{extends} with {with_clause}"

            self.classes.append({
                "name": class_name,
                "type": widget_type
            })

    def _extract_providers(self, content: str) -> None:
        """Extract Riverpod provider references."""
        pattern = r"(?:final|var)\s+(\w+Provider)\s*="
        for match in re.finditer(pattern, content):
            provider_name = match.group(1)
            self.providers.append(provider_name)

        # Also look for ref.watch/ref.read patterns
        pattern = r"ref\.(watch|read)\s*\(\s*(\w+Provider)\s*\)"
        for match in re.finditer(pattern, content):
            provider_name = match.group(2)
            if provider_name not in self.providers:
                self.providers.append(provider_name)

    def _extract_routes(self, content: str) -> None:
        """Extract GoRouter route references."""
        pattern = r"path:\s*['\"](/[^'\"]*)['\"]"
        for match in re.finditer(pattern, content):
            route_path = match.group(1)
            self.routes.append(route_path)


def group_files_by_domain(
    files: List[str],
    config: Dict,
    available_docs: List[str]
) -> Dict[str, List[str]]:
    """
    Group code files by domain using 4-tier matching.

    Args:
        files: List of code files
        config: Configuration dictionary
        available_docs: List of available doc names

    Returns:
        Dictionary mapping domain name to list of files
    """
    domain_to_files: Dict[str, List[str]] = {}

    for filepath in files:
        doc = find_doc_for_file(filepath, config, available_docs)
        if doc:
            if doc not in domain_to_files:
                domain_to_files[doc] = []
            domain_to_files[doc].append(filepath)

    return domain_to_files


def extract_code_structure(
    files: List[str]
) -> Dict[str, Dict]:
    """
    Extract code structure from all files.

    Args:
        files: List of code files to process

    Returns:
        Dictionary mapping filepath to extracted structure
    """
    results: Dict[str, Dict] = {}

    for filepath in files:
        if filepath.endswith(".py"):
            extractor = PythonCodeExtractor(filepath)
            extractor.extract()
            results[filepath] = {
                "type": "python",
                "endpoints": extractor.endpoints,
                "functions": extractor.functions,
                "classes": extractor.classes,
                "imports": list(extractor.imports)
            }
        elif filepath.endswith(".dart"):
            extractor = DartCodeExtractor(filepath)
            extractor.extract()
            results[filepath] = {
                "type": "dart",
                "classes": extractor.classes,
                "providers": extractor.providers,
                "routes": extractor.routes,
                "imports": list(extractor.imports)
            }

    return results


def extract_domain_dependencies(
    domain_files: List[str],
    code_structure: Dict[str, Dict],
    domain_name: str,
    config: Dict,
    available_docs: List[str]
) -> Set[str]:
    """
    Extract dependencies on other domains from a domain's files.

    Args:
        domain_files: List of files in the domain
        code_structure: Extracted code structure for all files
        domain_name: Name of the current domain
        config: Configuration dictionary
        available_docs: List of available docs

    Returns:
        Set of domain names this domain depends on
    """
    dependencies: Set[str] = set()

    for filepath in domain_files:
        if filepath not in code_structure:
            continue

        structure = code_structure[filepath]
        imports = structure.get("imports", [])

        for import_path in imports:
            # Try to find which domain this import belongs to
            # by checking if it matches any of the scan_dirs
            for scan_dir in config.get("scan_dirs", []):
                if import_path.startswith(scan_dir.replace("/", ".").replace("\\", ".")):
                    # Try to map this import to a domain
                    potential_domain = find_doc_for_file(
                        import_path.replace(".", "/") + ".py",
                        config,
                        available_docs
                    )
                    if potential_domain and potential_domain != domain_name:
                        dependencies.add(potential_domain)

    return dependencies


def _strip_at(name: str) -> str:
    """Strip leading @ from domain name if present."""
    return name.lstrip("@")


def render_spec_doc(
    domain: str,
    domain_files: List[str],
    code_structure: Dict[str, Dict],
    dependencies: Set[str]
) -> str:
    """
    Render markdown spec document for a domain.

    Args:
        domain: Domain name (may or may not have @ prefix)
        domain_files: List of files in the domain
        code_structure: Extracted code structure
        dependencies: Set of domain dependencies

    Returns:
        Markdown content for the spec document
    """
    clean_domain = _strip_at(domain)
    lines = [
        f"# @{clean_domain}",
        "",
        "## Overview",
        "Auto-generated spec from code analysis.",
        ""
    ]

    # Separate Python and Dart files
    py_files = [f for f in domain_files if f.endswith(".py")]
    dart_files = [f for f in domain_files if f.endswith(".dart")]

    # Backend section (Python/FastAPI)
    if py_files:
        lines.extend(["## Backend", ""])

        # Collect all endpoints
        endpoints: List[Dict] = []
        functions: List[Dict] = []
        all_classes: List[str] = []

        for filepath in py_files:
            if filepath in code_structure:
                structure = code_structure[filepath]
                endpoints.extend(structure.get("endpoints", []))
                functions.extend(structure.get("functions", []))
                all_classes.extend(structure.get("classes", []))

        # Render endpoints
        if endpoints:
            lines.append("### Endpoints")
            for ep in sorted(endpoints, key=lambda x: (x["method"], x["path"])):
                docstring = ep.get("docstring", "")
                lines.append(
                    f"- `{ep['method']} {ep['path']}` — {ep['name']}: {docstring}"
                )
            lines.append("")

        # Render service functions
        if functions:
            lines.append("### Service Functions")
            for func in sorted(functions, key=lambda x: x["name"]):
                params = func.get("params", "")
                return_type = func.get("return_type", "")
                sig = f"{func['name']}({params})"
                if return_type:
                    sig += f" → {return_type}"
                lines.append(f"- {sig}")
            lines.append("")

        # Render classes
        if all_classes:
            lines.append("### Models")
            for cls in sorted(list(set(all_classes))):
                lines.append(f"- {cls}")
            lines.append("")

    # Mobile section (Dart/Flutter)
    if dart_files:
        lines.extend(["## Mobile", ""])

        # Collect all widgets, providers, routes
        all_widgets: List[Dict] = []
        all_providers: List[str] = []
        all_routes: List[str] = []

        for filepath in dart_files:
            if filepath in code_structure:
                structure = code_structure[filepath]
                all_widgets.extend(structure.get("classes", []))
                all_providers.extend(structure.get("providers", []))
                all_routes.extend(structure.get("routes", []))

        # Render screens
        if all_widgets:
            lines.append("### Screens")
            for cls in sorted(all_widgets, key=lambda x: x["name"]):
                widget_type = cls.get("type", "Class")
                lines.append(f"- {cls['name']} ({widget_type})")
            lines.append("")

        # Render providers
        if all_providers:
            lines.append("### Providers")
            for provider in sorted(set(all_providers)):
                lines.append(f"- {provider}")
            lines.append("")

        # Render routes
        if all_routes:
            lines.append("### Routes")
            for route in sorted(set(all_routes)):
                lines.append(f"- `{route}`")
            lines.append("")

    # Dependencies section
    if dependencies:
        lines.extend(["## Dependencies", ""])
        for dep in sorted(dependencies):
            lines.append(f"- @{_strip_at(dep)}")
        lines.append("")

    # Status
    lines.extend([
        "## Status",
        "active",
        ""
    ])

    return "\n".join(lines)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="doby docgen: auto-generate spec docs from code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python docgen.py --dry-run
  python docgen.py --apply
  python docgen.py --domain @auth --apply
  python docgen.py --force --apply

Zero LLM tokens — pure AST + regex parsing.
        """
    )
    parser.add_argument(
        "--config",
        default=".dobyrc.json",
        help="Path to config file (default: .dobyrc.json)"
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
        help="Write spec docs to plans_dir"
    )
    parser.add_argument(
        "--domain",
        help="Generate spec for one domain only (e.g., @auth)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing spec docs"
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

    # Get available docs (from existing spec docs)
    plans_dir = config.get("plans_dir", ".omc/plans")

    available_docs: List[str] = []
    if Path(plans_dir).exists():
        for file_path in Path(plans_dir).glob("*.md"):
            if not file_path.name.startswith("INDEX"):
                available_docs.append(file_path.stem)

    print(f"Found {len(available_docs)} existing spec docs")

    # Extract code structure
    print("Extracting code structure...")
    code_structure = extract_code_structure(files)
    print(f"Extracted structure from {len(code_structure)} files")

    # Group files by domain
    print("Grouping files by domain...")
    domain_to_files = group_files_by_domain(files, config, available_docs)
    print(f"Found {len(domain_to_files)} domains")

    # Filter by domain if specified
    if args.domain:
        domain_key = args.domain.lstrip("@")
        # Try with and without @ prefix
        matching_domain = None
        for d in domain_to_files.keys():
            if d == domain_key or d.lstrip("@") == domain_key:
                matching_domain = d
                break

        if matching_domain:
            domain_to_files = {matching_domain: domain_to_files[matching_domain]}
        else:
            print(f"Error: domain @{domain_key} not found")
            print(f"Available domains: {', '.join(sorted(domain_to_files.keys()))}")
            return

    # Generate spec docs
    specs_to_write: Dict[str, str] = {}

    for domain, domain_files in domain_to_files.items():
        print(f"\nProcessing @{_strip_at(domain)} ({len(domain_files)} files)...")

        # Extract dependencies
        dependencies = extract_domain_dependencies(
            domain_files,
            code_structure,
            domain,
            config,
            available_docs
        )

        # Render spec
        spec_content = render_spec_doc(
            domain,
            domain_files,
            code_structure,
            dependencies
        )

        specs_to_write[domain] = spec_content

    # Output or write
    if args.dry_run and not args.apply:
        print("\n--- DRY RUN: Preview of generated specs ---\n")
        for domain, spec_content in specs_to_write.items():
            print(f"\n{_strip_at(domain)}.md (first 500 chars):")
            print(spec_content[:500] + "..." if len(spec_content) > 500 else spec_content)
        print(f"\n\nTotal: {len(specs_to_write)} spec docs")
        print("Run with --apply to write changes")

    elif args.apply:
        Path(plans_dir).mkdir(parents=True, exist_ok=True)

        written = 0
        skipped = 0

        for domain, spec_content in specs_to_write.items():
            spec_path = Path(plans_dir) / f"{_strip_at(domain)}.md"

            # Check if file exists and handle overwrite
            if spec_path.exists() and not args.force:
                print(f"Skipped {spec_path} (exists, use --force to overwrite)")
                skipped += 1
                continue

            with open(spec_path, "w", encoding="utf-8") as f:
                f.write(spec_content)
            print(f"Wrote {spec_path}")
            written += 1

        print(f"\nSummary: {written} written, {skipped} skipped")
    else:
        # Just print
        for domain, spec_content in specs_to_write.items():
            print(spec_content)


if __name__ == "__main__":
    main()
