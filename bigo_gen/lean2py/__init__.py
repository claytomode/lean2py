"""
Lean 4 -> compiled C -> Python bindings.

takes Lean source, runs lake build, produces a shared library and
a Python module you can import to call the exported Lean functions.
"""

from bigo_gen.lean2py.parser import parse_exports, Export
from bigo_gen.lean2py.bindings import generate_python_bindings
from bigo_gen.lean2py.build import build_lean_project, ensure_shared_lib
from bigo_gen.lean2py.pipeline import run
from bigo_gen.lean2py import ffi

__all__ = [
    "parse_exports",
    "Export",
    "generate_python_bindings",
    "build_lean_project",
    "ensure_shared_lib",
    "run",
    "ffi",
]
