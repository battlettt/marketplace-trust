"""Run every test without pytest: python3 tests/run_tests.py"""

import importlib
import sys
import traceback
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent))
sys.path.insert(0, str(TESTS_DIR))


def main():
    passed, failed = 0, []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        module = importlib.import_module(path.stem)
        for name in sorted(n for n in dir(module) if n.startswith("test_")):
            func = getattr(module, name)
            if not callable(func):
                continue
            try:
                func()
                passed += 1
            except Exception:
                failed.append(f"{path.stem}.{name}")
                traceback.print_exc()
    print(f"{passed} passed, {len(failed)} failed")
    for name in failed:
        print(f"FAILED {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
