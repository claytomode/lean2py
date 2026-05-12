"""Lean 4 → compiled C → Python bindings (lean2py)."""

from importlib.metadata import PackageNotFoundError, version

from . import ffi
from .bindings import generate_python_bindings
from .build import (
    build_lean_project,
    build_lean_project_with_logs,
    ensure_shared_lib,
)
from .errors import (
    CmdResult,
    InvalidInputError,
    LakeBuildError,
    Lean2PyError,
    NoExportsError,
    RunResult,
)
from .parser import Export, parse_exports
from .pipeline import run, run_detailed

try:
    __version__ = version("lean2py")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = [
    "__version__",
    "parse_exports",
    "Export",
    "generate_python_bindings",
    "build_lean_project",
    "build_lean_project_with_logs",
    "ensure_shared_lib",
    "run",
    "run_detailed",
    "RunResult",
    "CmdResult",
    "Lean2PyError",
    "InvalidInputError",
    "NoExportsError",
    "LakeBuildError",
    "ffi",
]
