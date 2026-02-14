"""
End-to-end: Lean source (file or dir) → lake build → shared lib + Python bindings.
One-click: we build the .so when possible so you can import and call from Python.
"""

import shutil
from pathlib import Path

import sys

from .parser import parse_exports, Export
from .bindings import generate_python_bindings
from .build import build_lean_project, ensure_shared_lib, get_lean_bin_dir, _shared_lib_ext


BUILD_DIR_NAME = ".lean2py_build"

LAKEFILE_MINIMAL = r"""
import Lake
open Lake DSL

package lean2py_export where
  precompileModules := true
  lean_lib LeanExport where defaultFacets := #[LeanLib.sharedFacet]
"""

LAKEFILE_WITH_MATHLIB = r"""
import Lake
open Lake DSL

require mathlib from git "https://github.com/leanprover-community/mathlib4.git"

package lean2py_export where
  precompileModules := true
  lean_lib LeanExport where defaultFacets := #[LeanLib.sharedFacet]
"""


def run(
    lean_input: str | Path,
    *,
    output_dir: str | Path | None = None,
    lib_name: str = "LeanExport",
    bindings_name: str = "lean_export",
    use_mathlib: bool = False,
) -> tuple[Path | None, Path | None]:
    """
    Build Lean and generate Python bindings. Tries to build a shared library
    so you can import the generated .py and call Lean from Python in one go.

    lean_input: path to a .lean file or a directory with lakefile.lean + .lean files.
    output_dir: where to write the generated .py and (when possible) libFoo.so.
    use_mathlib: if True (single-file only), add Mathlib to the lakefile (slow first build).
    Returns (path_to_shared_lib_or_None, path_to_generated_py).
    """
    lean_input = Path(lean_input)
    if output_dir is None:
        output_dir = lean_input.parent if lean_input.is_file() else lean_input
    output_dir = Path(output_dir)
    ext = _shared_lib_ext()

    if lean_input.is_file():
        if lean_input.suffix != ".lean":
            return (None, None)
        lean_source = lean_input.read_text(encoding="utf-8")
        exports = parse_exports(lean_source)
        if not exports:
            return (None, None)
        # Persistent build dir so we can produce and keep the .so
        project = output_dir / BUILD_DIR_NAME
        project.mkdir(parents=True, exist_ok=True)
        lakefile = LAKEFILE_WITH_MATHLIB if use_mathlib else LAKEFILE_MINIMAL
        (project / "lakefile.lean").write_text(lakefile, encoding="utf-8")
        (project / "LeanExport.lean").write_text(lean_source, encoding="utf-8")
        if not build_lean_project(project):
            return (None, None)
        lib_path = ensure_shared_lib(project, lib_name=lib_name, out_dir=output_dir)
        out_py = output_dir / f"{bindings_name}.py"
        lib_str = str(lib_path) if lib_path else f"./lib{lib_name}{ext}"
        extra_dll_dirs = []
        lean_bin_dir = get_lean_bin_dir(project) if lib_path else None
        if lib_path and sys.platform == "win32" and lean_bin_dir:
            extra_dll_dirs = [lean_bin_dir]
        generate_python_bindings(
            exports,
            lib_str,
            out_py,
            extra_dll_dirs=extra_dll_dirs or None,
            lean_bin_dir=lean_bin_dir,
        )
        return (lib_path, out_py)

    # Directory: assume it's a Lean project
    project_dir = lean_input
    first_lean = next(project_dir.rglob("*.lean"), None)
    if not first_lean:
        return (None, None)
    lean_source = first_lean.read_text(encoding="utf-8")
    exports = parse_exports(lean_source)
    # Collect from all .lean in project
    for p in project_dir.rglob("*.lean"):
        if p.name.startswith("lakefile"):
            continue
        exports.extend(parse_exports(p.read_text(encoding="utf-8")))
    seen = set()
    unique = [e for e in exports if (e.c_symbol not in seen and not seen.add(e.c_symbol))]
    if not unique:
        return (None, None)
    if not build_lean_project(project_dir):
        return (None, None)
    lib_path = ensure_shared_lib(project_dir, lib_name=lib_name, out_dir=output_dir)
    out_py = output_dir / f"{bindings_name}.py"
    lib_str = str(lib_path) if lib_path else f"./lib{lib_name}{_shared_lib_ext()}"
    extra_dll_dirs = []
    lean_bin_dir = get_lean_bin_dir(project_dir) if lib_path else None
    if lib_path and sys.platform == "win32" and lean_bin_dir:
        extra_dll_dirs = [lean_bin_dir]
    generate_python_bindings(
        unique,
        lib_str,
        out_py,
        extra_dll_dirs=extra_dll_dirs or None,
        lean_bin_dir=lean_bin_dir,
    )
    return (lib_path, out_py)
