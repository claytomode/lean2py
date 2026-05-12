"""
End-to-end: Lean source (file or dir) → lake build → shared lib + Python bindings.
One-click: we build the .so when possible so you can import and call from Python.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .bindings import generate_python_bindings
from .build import (
    _shared_lib_ext,
    build_lean_project_with_logs,
    ensure_shared_lib,
    get_lean_bin_dir,
)
from .errors import RunResult
from .parser import Export, parse_exports

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


def run_detailed(
    lean_input: str | Path,
    *,
    output_dir: str | Path | None = None,
    lib_name: str = "LeanExport",
    bindings_name: str = "lean_export",
    use_mathlib: bool = False,
    lake_timeout_s: float | None = None,
    leanc_timeout_s: float | None = None,
) -> RunResult:
    """
    Build Lean and generate Python bindings. Returns a :class:`RunResult` with paths
    and, on failure, error messages and optional lake logs.

    Use :meth:`RunResult.raise_for_status` or ``strict=True`` on :func:`run` to surface
    failures as exceptions.
    """
    lean_input = Path(lean_input).resolve()
    if output_dir is None:
        output_dir = lean_input.parent if lean_input.is_file() else lean_input
    output_dir = Path(output_dir).resolve()
    ext = _shared_lib_ext()

    if lean_input.is_file():
        if lean_input.suffix != ".lean":
            return RunResult(
                False,
                None,
                None,
                errors=[f"Expected a .lean file, got: {lean_input}"],
            )
        lean_source = lean_input.read_text(encoding="utf-8")
        exports = parse_exports(lean_source)
        if not exports:
            return RunResult(
                False,
                None,
                None,
                errors=[
                    f"No @[export ...] definitions found in {lean_input.name}. "
                    "Add attributes like `@[export my_add] def myAdd ...`."
                ],
            )
        project = output_dir / BUILD_DIR_NAME
        project.mkdir(parents=True, exist_ok=True)
        lakefile = LAKEFILE_WITH_MATHLIB if use_mathlib else LAKEFILE_MINIMAL
        (project / "lakefile.lean").write_text(lakefile, encoding="utf-8")
        (project / "LeanExport.lean").write_text(lean_source, encoding="utf-8")

        lb = build_lean_project_with_logs(project, lake_timeout_s=lake_timeout_s)
        if not lb.ok:
            return RunResult(
                False,
                None,
                None,
                errors=["Lake build failed (see lake_build stdout/stderr)."],
                lake_build=lb,
            )

        lib_path = ensure_shared_lib(
            project,
            lib_name=lib_name,
            out_dir=output_dir,
            lake_timeout_s=lake_timeout_s,
            leanc_timeout_s=leanc_timeout_s,
        )
        out_py = output_dir / f"{bindings_name}.py"
        lib_str = str(lib_path) if lib_path else f"./lib{lib_name}{ext}"
        extra_dll_dirs: list[str] = []
        lean_bin_dir = get_lean_bin_dir(project) if lib_path else None
        if lib_path and sys.platform == "win32" and lean_bin_dir:
            extra_dll_dirs = [lean_bin_dir]
        generate_python_bindings(
            exports,
            lib_str,
            out_py,
            extra_dll_dirs=extra_dll_dirs or None,
            lean_bin_dir=lean_bin_dir,
            lean_lib_module=lib_name,
        )
        return RunResult(True, lib_path, out_py, errors=[], lake_build=lb)

    project_dir = lean_input
    if not project_dir.is_dir():
        return RunResult(
            False,
            None,
            None,
            errors=[f"Not a directory: {project_dir}"],
        )
    if not (
        (project_dir / "lakefile.lean").exists() or (project_dir / "lakefile.toml").exists()
    ):
        return RunResult(
            False,
            None,
            None,
            errors=[
                f"No lakefile.lean or lakefile.toml in {project_dir}. "
                "Pass a directory that is a Lean/Lake project."
            ],
        )

    lean_files = [
        p
        for p in project_dir.rglob("*.lean")
        if not p.name.startswith("lakefile")
    ]
    if not lean_files:
        return RunResult(
            False,
            None,
            None,
            errors=[f"No .lean source files under {project_dir}."],
        )

    exports: list[Export] = []
    for p in lean_files:
        exports.extend(parse_exports(p.read_text(encoding="utf-8")))
    seen: set[str] = set()
    unique = [e for e in exports if (e.c_symbol not in seen and not seen.add(e.c_symbol))]
    if not unique:
        return RunResult(
            False,
            None,
            None,
            errors=[
                "No @[export ...] definitions found in project .lean files. "
                "Add attributes like `@[export my_add] def myAdd ...`."
            ],
        )

    lb = build_lean_project_with_logs(project_dir, lake_timeout_s=lake_timeout_s)
    if not lb.ok:
        return RunResult(
            False,
            None,
            None,
            errors=["Lake build failed (see lake_build stdout/stderr)."],
            lake_build=lb,
        )

    lib_path = ensure_shared_lib(
        project_dir,
        lib_name=lib_name,
        out_dir=output_dir,
        lake_timeout_s=lake_timeout_s,
        leanc_timeout_s=leanc_timeout_s,
    )
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
        lean_lib_module=lib_name,
    )
    return RunResult(True, lib_path, out_py, errors=[], lake_build=lb)


def run(
    lean_input: str | Path,
    *,
    output_dir: str | Path | None = None,
    lib_name: str = "LeanExport",
    bindings_name: str = "lean_export",
    use_mathlib: bool = False,
    strict: bool = False,
    lake_timeout_s: float | None = None,
    leanc_timeout_s: float | None = None,
) -> tuple[Path | None, Path | None]:
    """
    Build Lean and generate Python bindings. Tries to build a shared library
    so you can import the generated .py and call Lean from Python in one go.

    lean_input: path to a .lean file or a directory with lakefile.lean + .lean files.
    output_dir: where to write the generated .py and (when possible) libFoo.so.
    use_mathlib: if True (single-file only), add Mathlib to the lakefile (slow first build).
    strict: if True, raise :class:`~lean2py.lean2py.errors.Lean2PyError` on failure instead
        of returning ``(None, None)``.
    lake_timeout_s / leanc_timeout_s: optional overrides; defaults from env
        ``LEAN2PY_LAKE_TIMEOUT`` / ``LEAN2PY_LEANC_TIMEOUT`` or built-in defaults.

    Returns (path_to_shared_lib_or_None, path_to_generated_py).
    """
    res = run_detailed(
        lean_input,
        output_dir=output_dir,
        lib_name=lib_name,
        bindings_name=bindings_name,
        use_mathlib=use_mathlib,
        lake_timeout_s=lake_timeout_s,
        leanc_timeout_s=leanc_timeout_s,
    )
    if strict:
        res.raise_for_status()
    if not res.ok:
        return (None, None)
    return (res.lib_path, res.py_path)


__all__ = ["run", "run_detailed", "BUILD_DIR_NAME"]
