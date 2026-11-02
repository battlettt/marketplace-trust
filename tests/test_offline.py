"""The analysis code must never touch the network or third-party packages."""

import ast
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "marketplace_trust"
FORBIDDEN = {"socket", "urllib", "http", "requests", "httpx", "aiohttp", "ftplib", "smtplib",
             "ssl", "webbrowser", "selenium", "bs4", "subprocess", "asyncio"}


def imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.module.split(".")[0]


def test_no_network_imports():
    for path in PACKAGE.glob("*.py"):
        bad = set(imported_modules(path)) & FORBIDDEN
        assert not bad, f"{path.name} imports {bad}"


def test_standard_library_only():
    stdlib = set(sys.stdlib_module_names)
    for path in PACKAGE.glob("*.py"):
        for name in imported_modules(path):
            assert name in stdlib, f"{path.name} imports non-stdlib module {name}"
