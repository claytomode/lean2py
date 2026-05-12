"""Run Lean 4 lake build and produce a loadable shared library for Python."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .errors import CmdResult


def _default_lake_timeout_s() -> float:
    raw = os.environ.get("LEAN2PY_LAKE_TIMEOUT", "300")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 300.0


def _default_leanc_timeout_s() -> float:
    raw = os.environ.get("LEAN2PY_LEANC_TIMEOUT", "120")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 120.0


def run_cmd(
    args: list[str],
    *,
    cwd: str | Path | None = None,
    timeout: float,
) -> CmdResult:
    """Run a command; never raises for normal failures—returns :class:`CmdResult`."""
    try:
        r = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return CmdResult(
            tuple(args),
            r.returncode,
            r.stdout or "",
            r.stderr or "",
        )
    except FileNotFoundError:
        return CmdResult(
            tuple(args),
            -1,
            "",
            f"Command not found (is it on PATH?): {args[0]!r}",
        )
    except subprocess.TimeoutExpired as e:
        out = e.stdout if isinstance(e.stdout, str) else (e.stdout.decode() if e.stdout else "")
        err = e.stderr if isinstance(e.stderr, str) else (e.stderr.decode() if e.stderr else "")
        return CmdResult(
            tuple(args),
            -1,
            out,
            err + "\n[lean2py] subprocess timed out",
        )


def get_lean_bin_dir(project_dir: str | Path | None = None) -> str | None:
    """Return Lean toolchain bin directory (for runtime DLLs on Windows), or None."""
    res = run_cmd(
        ["lean", "--print-prefix"],
        cwd=project_dir,
        timeout=10.0,
    )
    if not res.ok:
        return None
    prefix = res.stdout.strip()
    if not prefix:
        return None
    return str(Path(prefix) / "bin")


def _shared_lib_ext() -> str:
    if sys.platform == "win32":
        return ".dll"
    if sys.platform == "darwin":
        return ".dylib"
    return ".so"


def build_lean_project_with_logs(
    project_dir: str | Path,
    *,
    lake_timeout_s: float | None = None,
) -> CmdResult:
    """Run ``lake build`` in ``project_dir``. Returns :class:`CmdResult` (check ``.ok``)."""
    project_dir = Path(project_dir)
    has_lake = (project_dir / "lakefile.lean").exists() or (project_dir / "lakefile.toml").exists()
    if not has_lake:
        return CmdResult(
            ("lake", "build"),
            -1,
            "",
            f"No lakefile.lean or lakefile.toml in {project_dir}",
        )
    timeout = lake_timeout_s if lake_timeout_s is not None else _default_lake_timeout_s()
    return run_cmd(["lake", "build"], cwd=project_dir, timeout=timeout)


def build_lean_project(project_dir: str | Path, *, lake_timeout_s: float | None = None) -> bool:
    """Run lake build in project_dir. Returns True if success."""
    return build_lean_project_with_logs(project_dir, lake_timeout_s=lake_timeout_s).ok


def _find_ir_c_files(project_dir: Path) -> list[Path]:
    """Find .c files from lake build (under build/ir or .lake/build/ir)."""
    candidates = [
        project_dir / "build" / "ir",
        project_dir / ".lake" / "build" / "ir",
    ]
    out: list[Path] = []
    for d in candidates:
        if d.is_dir():
            out.extend(sorted(d.rglob("*.c")))
    return out


def build_shared_lib_with_logs(
    project_dir: str | Path,
    out_lib_path: str | Path,
    *,
    leanc_timeout_s: float | None = None,
) -> CmdResult:
    """
    After lake build, link C output into a shared library.
    Uses ``lake env leanc -shared -o out_lib_path *.c``.
    """
    project_dir = Path(project_dir)
    out_lib_path = Path(out_lib_path)
    c_files = _find_ir_c_files(project_dir)
    if not c_files:
        return CmdResult(
            ("lake", "env", "leanc", "-shared"),
            -1,
            "",
            "No .c IR files found under build/ir or .lake/build/ir",
        )
    timeout = leanc_timeout_s if leanc_timeout_s is not None else _default_leanc_timeout_s()
    cmd = [
        "lake",
        "env",
        "leanc",
        "-shared",
        "-o",
        str(out_lib_path),
        *[str(p) for p in c_files],
    ]
    res = run_cmd(cmd, cwd=project_dir, timeout=timeout)
    if res.ok and not out_lib_path.exists():
        return CmdResult(
            res.args,
            -1,
            res.stdout,
            res.stderr + "\n[lean2py] leanc reported success but output library is missing",
        )
    return res


def build_shared_lib(
    project_dir: str | Path,
    out_lib_path: str | Path,
    *,
    leanc_timeout_s: float | None = None,
) -> bool:
    """After lake build, link C output into a shared library. Returns True if success."""
    return build_shared_lib_with_logs(
        project_dir, out_lib_path, leanc_timeout_s=leanc_timeout_s
    ).ok


def _run_lake_shared_facet_with_logs(
    project_dir: Path,
    lib_name: str,
    *,
    lake_timeout_s: float | None = None,
) -> CmdResult:
    """Run ``lake build <lib_name>:shared`` so Lake produces .so/.dll."""
    timeout = lake_timeout_s if lake_timeout_s is not None else _default_lake_timeout_s()
    return run_cmd(
        ["lake", "build", f"{lib_name}:shared"],
        cwd=project_dir,
        timeout=timeout,
    )


def _run_lake_shared_facet(project_dir: Path, lib_name: str) -> bool:
    return _run_lake_shared_facet_with_logs(project_dir, lib_name).ok


def _find_lake_shared_lib(project_dir: Path, lib_name: str) -> Path | None:
    """Find a shared lib built by Lake (e.g. .lake/build/lib/<pkg>_<lib>.dll)."""
    ext = _shared_lib_ext()
    for build_base in (project_dir / "build", project_dir / ".lake" / "build"):
        if not build_base.is_dir():
            continue
        for p in build_base.rglob(f"*{ext}"):
            if lib_name.lower() in p.stem.lower():
                return p
    return None


def ensure_shared_lib(
    project_dir: str | Path,
    lib_name: str = "LeanExport",
    out_dir: str | Path | None = None,
    *,
    lake_timeout_s: float | None = None,
    leanc_timeout_s: float | None = None,
) -> Path | None:
    """
    After lake build, produce a shared library that Python can load.

    Tries: (1) ``lake build <lib_name>:shared`` and find result,
    (2) existing build/, (3) ``leanc -shared`` from C IR.
    Copies to out_dir as lib<lib_name><ext> so generated bindings find it.
    """
    project_dir = Path(project_dir)
    ext = _shared_lib_ext()
    out_dir = Path(out_dir or project_dir)
    out_lib_path = out_dir / f"lib{lib_name}{ext}"

    _run_lake_shared_facet_with_logs(project_dir, lib_name, lake_timeout_s=lake_timeout_s)
    found = _find_lake_shared_lib(project_dir, lib_name)
    if found and found != out_lib_path:
        shutil.copy2(found, out_lib_path)
        return out_lib_path.resolve()
    if found:
        return found.resolve()

    for build_dir in (project_dir / "build", project_dir / ".lake" / "build"):
        for name in (f"lib{lib_name}{ext}", f"{lib_name}{ext}"):
            p = build_dir / name
            if p.exists():
                if p.resolve() != out_lib_path.resolve():
                    shutil.copy2(p, out_lib_path)
                return out_lib_path.resolve()

    if build_shared_lib(project_dir, out_lib_path, leanc_timeout_s=leanc_timeout_s):
        return out_lib_path.resolve()
    return None
