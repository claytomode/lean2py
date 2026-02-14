"""Run Lean 4 lake build and produce a loadable shared library for Python."""

import subprocess
import sys
from pathlib import Path


def get_lean_bin_dir(project_dir: str | Path | None = None) -> str | None:
    """Return Lean toolchain bin directory (for runtime DLLs on Windows), or None."""
    try:
        result = subprocess.run(
            ["lean", "--print-prefix"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        prefix = result.stdout.strip()
        if not prefix:
            return None
        return str(Path(prefix) / "bin")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _shared_lib_ext() -> str:
    if sys.platform == "win32":
        return ".dll"
    if sys.platform == "darwin":
        return ".dylib"
    return ".so"


def build_lean_project(project_dir: str | Path) -> bool:
    """Run lake build in project_dir. Returns True if success."""
    project_dir = Path(project_dir)
    if not (project_dir / "lakefile.lean").exists() and not (project_dir / "lakefile.toml").exists():
        return False
    try:
        subprocess.run(
            ["lake", "build"],
            cwd=project_dir,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _find_ir_c_files(project_dir: Path) -> list[Path]:
    """Find all .c files produced by lake build (Lean emits under build/ir or .lake/build/ir, possibly in subdirs)."""
    candidates = [
        project_dir / "build" / "ir",
        project_dir / ".lake" / "build" / "ir",
    ]
    out: list[Path] = []
    for d in candidates:
        if d.is_dir():
            out.extend(sorted(d.rglob("*.c")))
    return out


def build_shared_lib(
    project_dir: str | Path,
    out_lib_path: str | Path,
) -> bool:
    """
    After lake build, link C output into a shared library.
    Uses `lake env leanc -shared -o out_lib_path *.c`. Returns True if success.
    """
    project_dir = Path(project_dir)
    out_lib_path = Path(out_lib_path)
    c_files = _find_ir_c_files(project_dir)
    if not c_files:
        return False
    try:
        cmd = [
            "lake", "env", "leanc",
            "-shared",
            "-o", str(out_lib_path),
            *[str(p) for p in c_files],
        ]
        result = subprocess.run(
            cmd,
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return False
        return out_lib_path.exists()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_lake_shared_facet(project_dir: Path, lib_name: str) -> bool:
    """Run lake build <lib_name>:shared so Lake produces .so/.dll. Returns True if success."""
    try:
        result = subprocess.run(
            ["lake", "build", f"{lib_name}:shared"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


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
) -> Path | None:
    """
    After lake build, produce a shared library that Python can load.
    Tries: (1) lake build <lib_name>:shared and find result, (2) existing build/, (3) leanc -shared from C.
    Copies to out_dir as lib<lib_name><ext> so generated bindings find it.
    """
    project_dir = Path(project_dir)
    ext = _shared_lib_ext()
    out_dir = Path(out_dir or project_dir)
    out_lib_path = out_dir / f"lib{lib_name}{ext}"

    # 1. Try building the shared facet (Lake produces .dll/.so in .lake/build/lib/)
    _run_lake_shared_facet(project_dir, lib_name)
    found = _find_lake_shared_lib(project_dir, lib_name)
    if found and found != out_lib_path:
        import shutil

        shutil.copy2(found, out_lib_path)
        return out_lib_path.resolve()
    if found:
        return found.resolve()

    # 2. Already built with expected name?
    for build_dir in (project_dir / "build", project_dir / ".lake" / "build"):
        for name in (f"lib{lib_name}{ext}", f"{lib_name}{ext}"):
            p = build_dir / name
            if p.exists():
                if p.resolve() != out_lib_path.resolve():
                    import shutil

                    shutil.copy2(p, out_lib_path)
                return out_lib_path.resolve()

    # 3. Build from C output (leanc -shared)
    if build_shared_lib(project_dir, out_lib_path):
        return out_lib_path.resolve()
    return None
