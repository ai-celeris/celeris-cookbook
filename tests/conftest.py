"""Shared test helpers: import example scripts by file path.

Both examples name their entry point main.py, so modules are loaded under
unique names instead of via sys.path.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_example(name: str, relative_path: str):
    module_name = f"cookbook_example_{name}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
